const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const https = require('node:https');

const MESHY_BASE_URL = 'https://api.meshy.ai';

class MeshyRuntime {
  constructor(appSupportDir) {
    this.appSupportDir = appSupportDir;
    this.cacheDir = path.join(appSupportDir, 'meshy-cache');
    this.configPath = path.join(appSupportDir, 'meshy-config.json');
    this.activeRequest = null;
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
        return data.apiKey || process.env.MESHY_API_KEY || '';
      }
    } catch {}
    return process.env.MESHY_API_KEY || '';
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
                reject(new Error(data.message || data.error || `HTTP ${res.statusCode}: ${raw}`));
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

  downloadFile(url, destPath) {
    return new Promise((resolve, reject) => {
      const file = fs.createWriteStream(destPath);
      https.get(url, (res) => {
        if (res.statusCode !== 200) {
          reject(new Error(`Falló la descarga del activo 3D: HTTP ${res.statusCode}`));
          return;
        }
        res.pipe(file);
        file.on('finish', () => {
          file.close();
          resolve(destPath);
        });
      }).on('error', (err) => {
        fs.unlink(destPath, () => {});
        reject(err);
      });
    });
  }

  async pollTask(taskId, pollPath, apiKey, onProgress) {
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
          stage: `Aceleración Meshy Cloud API v6 (${status === 'SUCCEEDED' ? 'Completado' : 'Procesando ' + displayPercent + '%'})`,
          taskId,
        });
      }

      if (status === 'SUCCEEDED') {
        return data;
      } else if (status === 'FAILED') {
        throw new Error(data.task_error?.message || 'La generación 3D en Meshy API ha fallado.');
      }

      const pollDelay = maxProgressSeen >= 80 ? 750 : 1100;
      await new Promise((r) => setTimeout(r, pollDelay));
    }
    throw new Error('Tiempo de espera agotado al consultar Meshy API.');
  }

  calculateCreditCost(params) {
    if (params.mode === 'retexture' || params.mode === 'refine') return 20;
    return 5;
  }

  async generate3D(params, onProgress) {
    this.cancelled = false;
    const apiKey = params.apiKey || this.getApiKey();
    if (!apiKey) {
      return { ok: false, error: 'Configura tu API Key de Meshy para continuar en modo Cloud.' };
    }

    try {
      const isRefineOrRetexture = params.mode === 'retexture' || params.mode === 'refine';
      const previewTaskId = params.preview_task_id || params.taskId;

      if (isRefineOrRetexture && !previewTaskId) {
        return {
          ok: false,
          error: 'Para texturizar o refinar en Meshy Cloud, primero debes generar la vista previa 3D.',
        };
      }

      const isImageTo3D = !!params.imageBase64 && !isRefineOrRetexture;
      
      let endpoint = '/v2/text-to-3d';
      let pollPath = '/v2/text-to-3d';

      if (isImageTo3D) {
        endpoint = '/v1/image-to-3d';
        pollPath = '/v1/image-to-3d';
      }

      const payload = isRefineOrRetexture
        ? {
            mode: 'refine',
            preview_task_id: previewTaskId,
            texture_richness: 'high',
            ...(params.prompt ? { prompt: params.prompt } : {}),
          }
        : isImageTo3D
        ? {
            image_url: `data:image/png;base64,${params.imageBase64}`,
            enable_pbr: false,
          }
        : {
            mode: params.mode || 'preview',
            prompt: params.prompt || 'Game ready 3D asset',
            art_style: params.art_style || 'realistic',
            topology: params.topology || 'quad',
            target_polycount: params.target_polycount || 12000,
            enable_pbr: false,
          };

      if (onProgress) onProgress({ percent: 5, stage: 'Enviando tarea a Meshy Cloud API…' });

      const createRes = await this.makeRequest({
        method: 'POST',
        endpoint,
        apiKey,
        body: payload,
      });

      const taskId = createRes.result || createRes.id;
      if (!taskId) throw new Error('Meshy API no devolvió un ID de tarea válido.');

      const taskResult = await this.pollTask(taskId, pollPath, apiKey, onProgress);

      const modelUrls = taskResult.model_urls || {};
      const glbUrl = modelUrls.glb || taskResult.model_url;

      if (!glbUrl) throw new Error('No se encontró URL de modelo GLB en la respuesta de Meshy.');

      const filename = `meshy-${Date.now()}-${taskId.slice(0, 8)}.glb`;
      const localGlbPath = path.join(this.cacheDir, filename);

      if (onProgress) onProgress({ percent: 95, stage: 'Descargando activo GLB optimizado…' });
      await this.downloadFile(glbUrl, localGlbPath);

      const glbBuffer = await fsp.readFile(localGlbPath);
      const glbBase64 = glbBuffer.toString('base64');

      return {
        ok: true,
        taskId,
        glbPath: localGlbPath,
        glbBase64,
        modelUrls,
        thumbnailUrl: taskResult.thumbnail_url,
        faces: taskResult.polycount || params.target_polycount,
        mode: params.mode,
        creditsUsed: this.calculateCreditCost(params),
        duration: (Date.now() - (params.startTime || Date.now())) / 1000,
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
