const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const https = require('node:https');
const http = require('node:http');

const MESHY_BASE_URL = 'https://api.meshy.ai';

class MeshyRuntime {
  constructor(appSupportDir) {
    this.appSupportDir = appSupportDir;
    this.cacheDir = path.join(appSupportDir, 'meshy-cache');
    this.configPath = path.join(appSupportDir, 'meshy-config.json');
    this.activeRequest = null;
    this.cancelled = false;
    this.ensureDirs();
  }

  ensureDirs() {
    if (!fs.existsSync(this.appSupportDir)) fs.mkdirSync(this.appSupportDir, { recursive: true });
    if (!fs.existsSync(this.cacheDir)) fs.mkdirSync(this.cacheDir, { recursive: true });
  }

  getApiKey() {
    try {
      if (fs.existsSync(this.configPath)) {
        const data = JSON.parse(fs.readFileSync(this.configPath, 'utf8'));
        return (data.apiKey || process.env.MESHY_API_KEY || '').trim();
      }
    } catch {}
    return (process.env.MESHY_API_KEY || '').trim();
  }

  saveApiKey(apiKey) {
    this.ensureDirs();
    const current = fs.existsSync(this.configPath)
      ? JSON.parse(fs.readFileSync(this.configPath, 'utf8'))
      : {};
    current.apiKey = (apiKey || '').trim();
    fs.writeFileSync(this.configPath, JSON.stringify(current, null, 2), 'utf8');
    return { ok: true, apiKey: current.apiKey };
  }

  async getCredits(apiKey) {
    const key = (apiKey || this.getApiKey()).trim();
    if (!key) return { ok: false, credits: null, error: 'Sin API Key' };

    const endpoints = [
      '/openapi/v1/balance',
      '/v1/balance',
      '/openapi/v1/user/credits',
      '/v1/user/credits',
      '/v1/credits'
    ];

    let lastError = null;
    for (const endpoint of endpoints) {
      try {
        const res = await this.makeRequest({ endpoint, apiKey: key });
        if (res) {
          const balance = res.balance ?? res.credits ?? res.credit ?? res.total_credits ?? (res.data && res.data.balance);
          if (balance !== undefined && balance !== null) {
            return { ok: true, credits: Number(balance) };
          }
        }
      } catch (err) {
        lastError = err;
      }
    }
    return { ok: false, credits: null, error: lastError?.message || 'No se pudo consultar el saldo de créditos' };
  }

  makeRequest({ method = 'GET', endpoint, apiKey, body = null }) {
    return new Promise((resolve, reject) => {
      const fullEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
      const url = new URL(`${MESHY_BASE_URL}${fullEndpoint}`);
      const payload = body ? JSON.stringify(body) : null;

      const req = https.request(
        url,
        {
          method,
          headers: {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json',
            ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {}),
          },
        },
        (res) => {
          let chunks = [];
          res.on('data', (c) => chunks.push(c));
          res.on('end', () => {
            const raw = Buffer.concat(chunks).toString('utf8');
            try {
              const data = JSON.parse(raw);
              if (res.statusCode >= 200 && res.statusCode < 300) {
                resolve(data);
              } else {
                const message = data.message || data.error || data.task_error?.message || `HTTP ${res.statusCode}: ${raw}`;
                reject(new Error(message));
              }
            } catch {
              reject(new Error(`Respuesta inválida de Meshy API (HTTP ${res.statusCode}): ${raw}`));
            }
          });
        }
      );

      req.on('error', (err) => reject(err));
      this.activeRequest = req;
      if (payload) req.write(payload);
      req.end();
    });
  }

  downloadFile(initialUrl, destPath, maxRedirects = 5) {
    return new Promise((resolve, reject) => {
      const executeDownload = (targetUrl, redirectsLeft) => {
        if (redirectsLeft <= 0) {
          reject(new Error('Demasiadas redirecciones al descargar el archivo 3D de Meshy.'));
          return;
        }

        let parsedUrl;
        try {
          parsedUrl = new URL(targetUrl);
        } catch (e) {
          reject(new Error(`URL de descarga inválida: ${targetUrl}`));
          return;
        }

        const httpModule = parsedUrl.protocol === 'http:' ? http : https;
        const request = httpModule.get(parsedUrl, (res) => {
          // Handle HTTP redirects (301, 302, 303, 307, 308)
          if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
            const redirectUrl = new URL(res.headers.location, parsedUrl).toString();
            res.resume();
            executeDownload(redirectUrl, redirectsLeft - 1);
            return;
          }

          if (res.statusCode !== 200) {
            reject(new Error(`Falló la descarga del activo 3D (HTTP ${res.statusCode}) desde: ${targetUrl}`));
            return;
          }

          const chunks = [];
          const file = fs.createWriteStream(destPath);

          res.on('data', (chunk) => {
            chunks.push(chunk);
          });

          res.pipe(file);

          file.on('finish', () => {
            file.close(() => {
              const buffer = Buffer.concat(chunks);
              if (buffer.length === 0) {
                fs.unlink(destPath, () => {});
                reject(new Error('El archivo 3D descargado está vacío (0 bytes).'));
                return;
              }
              resolve({ destPath, buffer });
            });
          });

          file.on('error', (err) => {
            fs.unlink(destPath, () => {});
            reject(err);
          });
        });

        request.on('error', (err) => {
          fs.unlink(destPath, () => {});
          reject(err);
        });

        request.setTimeout(120000, () => {
          request.destroy();
          fs.unlink(destPath, () => {});
          reject(new Error('Tiempo de espera agotado al descargar el activo 3D.'));
        });
      };

      executeDownload(initialUrl, maxRedirects);
    });
  }

  async pollTask(taskId, pollPath, apiKey, onProgress, stagePrefix = 'Aceleración Meshy Cloud API v7') {
    const startTime = Date.now();
    const timeoutMs = 600000; // 10 min
    let maxProgressSeen = 10;

    while (Date.now() - startTime < timeoutMs) {
      if (this.cancelled) {
        throw new Error('Generación cancelada por el usuario.');
      }
      const pollEndpoint = pollPath.startsWith('/') ? `${pollPath}/${taskId}` : `/${pollPath}/${taskId}`;
      const data = await this.makeRequest({ endpoint: pollEndpoint, apiKey });
      const status = data.status; // 'PENDING', 'IN_PROGRESS', 'SUCCEEDED', 'FAILED'
      
      const rawProgress = Number(data.progress || 0);
      if (rawProgress > maxProgressSeen && rawProgress < 100) {
        maxProgressSeen = rawProgress;
      }

      const displayPercent = status === 'SUCCEEDED' ? 100 : maxProgressSeen;

      if (onProgress) {
        onProgress({
          percent: displayPercent,
          stage: `${stagePrefix} (${status === 'SUCCEEDED' ? 'Completado' : 'Procesando ' + displayPercent + '%'})`,
          taskId,
        });
      }

      if (status === 'SUCCEEDED') {
        return data;
      } else if (status === 'FAILED') {
        const detail = data.task_error?.message || data.message || 'La generación 3D en Meshy API ha fallado.';
        throw new Error(`Meshy Error: ${detail}`);
      }

      // Responsive polling: 500ms when near completion, 700ms when pending/in-progress
      const pollDelay = maxProgressSeen >= 75 ? 500 : 700;
      await new Promise((r) => setTimeout(r, pollDelay));
    }
    throw new Error('Tiempo de espera agotado al consultar Meshy API.');
  }

  calculateCreditCost(params) {
    if (params.mode === 'retexture') {
      const res = params.texture_resolution || '2k';
      return res.toLowerCase() === '8k' ? 15 : 10;
    }
    if (params.mode === 'refine') {
      return 20;
    }
    let cost = 5;
    if (params.ultra_mode) cost += 5;
    return cost;
  }

  async generate3D(params, onProgress) {
    this.cancelled = false;
    const apiKey = (params.apiKey || this.getApiKey()).trim();
    if (!apiKey) {
      return { ok: false, error: 'Configura tu API Key de Meshy para continuar en modo Cloud.' };
    }

    const startTime = Date.now();

    try {
      const previewTaskId = params.preview_task_id || params.previewTaskId || params.taskId;
      const rawRes = (params.texture_resolution || '2k').toString().toLowerCase().trim();
      const textureResolution = ['2k', '4k', '8k'].includes(rawRes) ? rawRes : '2k';
      const aiModel = params.ai_model || 'latest';
      const shouldTexture = params.should_texture !== false;

      // --- 1. RETEXTURE WORKFLOW (/openapi/v1/retexture) ---
      if (params.mode === 'retexture') {
        const payload = {
          ai_model: aiModel,
          texture_resolution: textureResolution,
          enable_pbr: true,
        };

        if (previewTaskId) {
          payload.input_task_id = previewTaskId;
        } else if (params.glbBase64) {
          payload.model_url = `data:model/gltf-binary;base64,${params.glbBase64}`;
        } else {
          return {
            ok: false,
            error: 'Para re-texturizar en Meshy Cloud, necesitas tener un ID de tarea previo o un modelo cargado.',
          };
        }

        if (params.multiview_image_urls && params.multiview_image_urls.length > 0) {
          payload.multiview_image_urls = params.multiview_image_urls;
        } else if (params.prompt && params.prompt.trim()) {
          payload.text_style_prompt = params.prompt.trim().slice(0, 600);
        } else {
          payload.text_style_prompt = 'realistic PBR material with high quality textures';
        }

        if (onProgress) onProgress({ percent: 5, stage: 'Enviando retexturizado a Meshy Cloud…' });

        const createRes = await this.makeRequest({
          method: 'POST',
          endpoint: '/openapi/v1/retexture',
          apiKey,
          body: payload,
        });

        const taskId = createRes.result || createRes.id;
        if (!taskId) throw new Error('Meshy API no devolvió un ID de tarea válido para retexturizado.');

        const taskResult = await this.pollTask(
          taskId,
          '/openapi/v1/retexture',
          apiKey,
          onProgress,
          'Aplicando texturas PBR HD en Meshy Cloud'
        );

        const modelUrls = taskResult.model_urls || {};
        const glbUrl = modelUrls.glb || taskResult.model_url;
        if (!glbUrl) throw new Error('No se encontró URL de modelo GLB en la respuesta de retexturizado de Meshy.');

        const filename = `meshy-retexture-${Date.now()}-${taskId.slice(0, 8)}.glb`;
        const localGlbPath = path.join(this.cacheDir, filename);

        if (onProgress) onProgress({ percent: 95, stage: 'Descargando modelo texturizado GLB HD…' });
        const { buffer } = await this.downloadFile(glbUrl, localGlbPath);
        const glbBase64 = buffer.toString('base64');

        return {
          ok: true,
          taskId,
          previewTaskId: previewTaskId || taskId,
          glbPath: localGlbPath,
          glbBase64,
          modelUrls,
          textureUrls: taskResult.texture_urls || {},
          thumbnailUrl: taskResult.thumbnail_url,
          faces: taskResult.polycount || params.target_polycount || 12000,
          mode: 'retexture',
          textured: true,
          textureResolution,
          creditsUsed: this.calculateCreditCost(params),
          duration: (Date.now() - startTime) / 1000,
          provider: 'meshy-api',
        };
      }

      // --- 2. MULTI-IMAGE TO 3D WORKFLOW ---
      if (params.image_urls && params.image_urls.length > 0) {
        const payload = {
          image_urls: params.image_urls,
          ai_model: aiModel,
          should_texture: shouldTexture,
          enable_pbr: true,
          texture_resolution: textureResolution,
          should_remesh: Boolean(params.topology || params.target_polycount),
          topology: params.topology || 'quad',
          target_polycount: params.target_polycount || 12000,
        };

        if (onProgress) onProgress({ percent: 5, stage: 'Iniciando reconstrucción multi-imagen en Meshy Cloud…' });

        const createRes = await this.makeRequest({
          method: 'POST',
          endpoint: '/openapi/v1/multi-image-to-3d',
          apiKey,
          body: payload,
        });

        const taskId = createRes.result || createRes.id;
        if (!taskId) throw new Error('Meshy API no devolvió un ID de tarea válido para multi-imagen.');

        const taskResult = await this.pollTask(
          taskId,
          '/openapi/v1/multi-image-to-3d',
          apiKey,
          onProgress,
          'Reconstrucción multi-imagen con PBR'
        );

        const modelUrls = taskResult.model_urls || {};
        const glbUrl = modelUrls.glb || taskResult.model_url;
        if (!glbUrl) throw new Error('No se encontró URL de modelo GLB en la respuesta de Meshy.');

        const filename = `meshy-multi-${Date.now()}-${taskId.slice(0, 8)}.glb`;
        const localGlbPath = path.join(this.cacheDir, filename);

        if (onProgress) onProgress({ percent: 95, stage: 'Descargando activo GLB completado…' });
        const { buffer } = await this.downloadFile(glbUrl, localGlbPath);
        const glbBase64 = buffer.toString('base64');

        return {
          ok: true,
          taskId,
          previewTaskId: taskId,
          glbPath: localGlbPath,
          glbBase64,
          modelUrls,
          textureUrls: taskResult.texture_urls || {},
          thumbnailUrl: taskResult.thumbnail_url,
          faces: taskResult.polycount || params.target_polycount || 12000,
          mode: 'multi-image-to-3d',
          textured: shouldTexture,
          textureResolution,
          creditsUsed: this.calculateCreditCost(params),
          duration: (Date.now() - startTime) / 1000,
          provider: 'meshy-api',
        };
      }

      // --- 3. SINGLE IMAGE TO 3D WORKFLOW ---
      if (params.imageBase64) {
        const payload = {
          image_url: `data:image/png;base64,${params.imageBase64}`,
          ai_model: aiModel,
          ultra_mode: Boolean(params.ultra_mode),
          should_texture: shouldTexture,
          enable_pbr: true,
          texture_resolution: textureResolution,
          should_remesh: Boolean(params.topology || params.target_polycount),
          topology: params.topology || 'quad',
          target_polycount: params.target_polycount || 12000,
        };

        if (params.prompt && params.prompt.trim()) {
          payload.texture_prompt = params.prompt.trim().slice(0, 600);
        }

        if (onProgress) onProgress({ percent: 5, stage: 'Iniciando conversión de imagen a 3D en Meshy Cloud…' });

        const createRes = await this.makeRequest({
          method: 'POST',
          endpoint: '/openapi/v1/image-to-3d',
          apiKey,
          body: payload,
        });

        const taskId = createRes.result || createRes.id;
        if (!taskId) throw new Error('Meshy API no devolvió un ID de tarea válido para imagen.');

        const taskResult = await this.pollTask(
          taskId,
          '/openapi/v1/image-to-3d',
          apiKey,
          onProgress,
          'Generando geometría y texturas PBR'
        );

        const modelUrls = taskResult.model_urls || {};
        const glbUrl = modelUrls.glb || taskResult.model_url;
        if (!glbUrl) throw new Error('No se encontró URL de modelo GLB en la respuesta de Meshy.');

        const filename = `meshy-image-${Date.now()}-${taskId.slice(0, 8)}.glb`;
        const localGlbPath = path.join(this.cacheDir, filename);

        if (onProgress) onProgress({ percent: 95, stage: 'Descargando modelo 3D optimizado…' });
        const { buffer } = await this.downloadFile(glbUrl, localGlbPath);
        const glbBase64 = buffer.toString('base64');

        return {
          ok: true,
          taskId,
          previewTaskId: taskId,
          glbPath: localGlbPath,
          glbBase64,
          modelUrls,
          textureUrls: taskResult.texture_urls || {},
          thumbnailUrl: taskResult.thumbnail_url,
          faces: taskResult.polycount || params.target_polycount || 12000,
          mode: 'image-to-3d',
          textured: shouldTexture,
          textureResolution,
          creditsUsed: this.calculateCreditCost(params),
          duration: (Date.now() - startTime) / 1000,
          provider: 'meshy-api',
        };
      }

      // --- 4. TEXT TO 3D WORKFLOW ---
      // 4A: Refine with existing preview_task_id
      if (params.mode === 'refine' && previewTaskId) {
        if (onProgress) onProgress({ percent: 5, stage: 'Enviando tarea de refinamiento HD a Meshy Cloud…' });

        const refineRes = await this.makeRequest({
          method: 'POST',
          endpoint: '/openapi/v2/text-to-3d',
          apiKey,
          body: {
            mode: 'refine',
            preview_task_id: previewTaskId,
            texture_richness: 'high',
            ai_model: aiModel,
            texture_resolution: textureResolution,
            enable_pbr: true,
            ...(params.prompt ? { prompt: params.prompt.trim() } : {}),
          },
        });

        const refineId = refineRes.result || refineRes.id;
        if (!refineId) throw new Error('Meshy API no devolvió un ID de tarea para refinamiento.');

        const refineTaskResult = await this.pollTask(
          refineId,
          '/openapi/v2/text-to-3d',
          apiKey,
          onProgress,
          'Aplicando texturas PBR HD'
        );

        const modelUrls = refineTaskResult.model_urls || {};
        const glbUrl = modelUrls.glb || refineTaskResult.model_url;
        if (!glbUrl) throw new Error('No se encontró URL de modelo GLB en la respuesta de refinamiento.');

        const filename = `meshy-refine-${Date.now()}-${refineId.slice(0, 8)}.glb`;
        const localGlbPath = path.join(this.cacheDir, filename);

        if (onProgress) onProgress({ percent: 98, stage: 'Descargando activo GLB HD…' });
        const { buffer } = await this.downloadFile(glbUrl, localGlbPath);
        const glbBase64 = buffer.toString('base64');

        return {
          ok: true,
          taskId: refineId,
          previewTaskId: previewTaskId,
          glbPath: localGlbPath,
          glbBase64,
          modelUrls,
          textureUrls: refineTaskResult.texture_urls || {},
          thumbnailUrl: refineTaskResult.thumbnail_url,
          faces: refineTaskResult.polycount || params.target_polycount || 12000,
          mode: 'refine',
          textured: true,
          textureResolution,
          creditsUsed: 20,
          duration: (Date.now() - startTime) / 1000,
          provider: 'meshy-api',
        };
      }

      // 4B: Refine from scratch (Two-step pipeline: Preview -> Refine)
      if (params.mode === 'refine' && !previewTaskId) {
        if (onProgress) onProgress({ percent: 5, stage: 'Paso 1/2: Generando geometría base en Meshy Cloud…' });

        const previewRes = await this.makeRequest({
          method: 'POST',
          endpoint: '/openapi/v2/text-to-3d',
          apiKey,
          body: {
            mode: 'preview',
            prompt: params.prompt || 'Game ready 3D asset',
            art_style: params.art_style || 'realistic',
            topology: params.topology || 'quad',
            target_polycount: params.target_polycount || 12000,
            ai_model: aiModel,
          },
        });

        const previewId = previewRes.result || previewRes.id;
        if (!previewId) throw new Error('Meshy API no devolvió un ID de tarea para la vista previa.');

        await this.pollTask(previewId, '/openapi/v2/text-to-3d', apiKey, (p) => {
          if (onProgress) onProgress({ percent: Math.round(p.percent * 0.4), stage: `Paso 1/2: Geometría (${p.percent}%)` });
        });

        // Step 2: Refine
        if (onProgress) onProgress({ percent: 45, stage: 'Paso 2/2: Aplicando texturas PBR HD en Meshy Cloud…' });
        const refineRes = await this.makeRequest({
          method: 'POST',
          endpoint: '/openapi/v2/text-to-3d',
          apiKey,
          body: {
            mode: 'refine',
            preview_task_id: previewId,
            texture_richness: 'high',
            ai_model: aiModel,
            texture_resolution: textureResolution,
            enable_pbr: true,
            ...(params.prompt ? { prompt: params.prompt.trim() } : {}),
          },
        });

        const refineId = refineRes.result || refineRes.id;
        if (!refineId) throw new Error('Meshy API no devolvió un ID de tarea para el refinamiento.');

        const refineTaskResult = await this.pollTask(refineId, '/openapi/v2/text-to-3d', apiKey, (p) => {
          if (onProgress) onProgress({ percent: 45 + Math.round(p.percent * 0.5), stage: `Paso 2/2: Texturizando (${p.percent}%)` });
        });

        const modelUrls = refineTaskResult.model_urls || {};
        const glbUrl = modelUrls.glb || refineTaskResult.model_url;
        if (!glbUrl) throw new Error('No se encontró URL de modelo GLB en la respuesta de Meshy.');

        const filename = `meshy-refine-${Date.now()}-${refineId.slice(0, 8)}.glb`;
        const localGlbPath = path.join(this.cacheDir, filename);

        if (onProgress) onProgress({ percent: 98, stage: 'Descargando activo GLB HD…' });
        const { buffer } = await this.downloadFile(glbUrl, localGlbPath);
        const glbBase64 = buffer.toString('base64');

        return {
          ok: true,
          taskId: refineId,
          previewTaskId: previewId,
          glbPath: localGlbPath,
          glbBase64,
          modelUrls,
          textureUrls: refineTaskResult.texture_urls || {},
          thumbnailUrl: refineTaskResult.thumbnail_url,
          faces: refineTaskResult.polycount || params.target_polycount || 12000,
          mode: 'refine',
          textured: true,
          textureResolution,
          creditsUsed: 25,
          duration: (Date.now() - startTime) / 1000,
          provider: 'meshy-api',
        };
      }

      // 4C: Preview Only
      if (onProgress) onProgress({ percent: 5, stage: 'Enviando vista previa 3D a Meshy Cloud…' });

      const previewRes = await this.makeRequest({
        method: 'POST',
        endpoint: '/openapi/v2/text-to-3d',
        apiKey,
        body: {
          mode: 'preview',
          prompt: params.prompt || 'Game ready 3D asset',
          art_style: params.art_style || 'realistic',
          topology: params.topology || 'quad',
          target_polycount: params.target_polycount || 12000,
          ai_model: aiModel,
        },
      });

      const taskId = previewRes.result || previewRes.id;
      if (!taskId) throw new Error('Meshy API no devolvió un ID de tarea válido.');

      const taskResult = await this.pollTask(
        taskId,
        '/openapi/v2/text-to-3d',
        apiKey,
        onProgress,
        'Generando malla 3D base'
      );

      const modelUrls = taskResult.model_urls || {};
      const glbUrl = modelUrls.glb || taskResult.model_url;
      if (!glbUrl) throw new Error('No se encontró URL de modelo GLB en la respuesta de Meshy.');

      const filename = `meshy-preview-${Date.now()}-${taskId.slice(0, 8)}.glb`;
      const localGlbPath = path.join(this.cacheDir, filename);

      if (onProgress) onProgress({ percent: 95, stage: 'Descargando modelo 3D…' });
      const { buffer } = await this.downloadFile(glbUrl, localGlbPath);
      const glbBase64 = buffer.toString('base64');

      return {
        ok: true,
        taskId,
        previewTaskId: taskId,
        glbPath: localGlbPath,
        glbBase64,
        modelUrls,
        textureUrls: taskResult.texture_urls || {},
        thumbnailUrl: taskResult.thumbnail_url,
        faces: taskResult.polycount || params.target_polycount || 12000,
        mode: 'preview',
        textured: false,
        textureResolution,
        creditsUsed: 5,
        duration: (Date.now() - startTime) / 1000,
        provider: 'meshy-api',
      };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  }

  cancel() {
    this.cancelled = true;
    if (this.activeRequest) {
      this.activeRequest.destroy();
      this.activeRequest = null;
    }
  }
}

module.exports = { MeshyRuntime };
