const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const https = require('node:https');

const MESHY_BASE_URL = 'https://api.meshy.ai/v1';

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

  makeRequest({ method = 'GET', endpoint, apiKey, body = null }) {
    return new Promise((resolve, reject) => {
      const url = new URL(`${MESHY_BASE_URL}${endpoint}`);
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
                reject(new Error(data.message || data.error || `HTTP ${res.statusCode}`));
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

  async pollTask(taskId, endpointType, apiKey, onProgress) {
    const startTime = Date.now();
    const timeoutMs = 600000; // 10 min

    while (Date.now() - startTime < timeoutMs) {
      const data = await this.makeRequest({ endpoint: `/${endpointType}/${taskId}`, apiKey });
      const status = data.status; // 'PENDING', 'IN_PROGRESS', 'SUCCEEDED', 'FAILED'
      const progress = data.progress || 0;

      if (onProgress) {
        onProgress({
          percent: progress,
          stage: `Generando en Meshy Cloud API (${status} ${progress}%)`,
          taskId,
        });
      }

      if (status === 'SUCCEEDED') {
        return data;
      } else if (status === 'FAILED') {
        throw new Error(data.task_error?.message || 'La generación 3D en Meshy API ha fallado.');
      }

      await new Promise((r) => setTimeout(r, 2500));
    }
    throw new Error('Tiempo de espera agotado al consultar Meshy API.');
  }

  calculateCreditCost(params) {
    const isImage = !!params.imageBase64;
    const model = params.aiModel || (params.cheapValidation ? 'meshy-t2' : 'meshy-6');
    const withTexture = params.enablePbr !== false && params.mode !== 'preview_untextured';

    if (params.mode === 'remesh') return 5;
    if (params.mode === 'rig') return 5;
    if (params.mode === 'animation') return 3;
    if (params.mode === 'retexture') return 10;

    if (isImage) {
      if (model === 'meshy-t2' || model === 'other') {
        return withTexture ? 15 : 5;
      }
      // Meshy 6 / T1
      return withTexture ? 30 : 20;
    } else {
      // Text to 3D
      if (model === 'meshy-6') return 20;
      return 10;
    }
  }

  async generate3D(params, onProgress) {
    const apiKey = params.apiKey || this.getApiKey();
    if (!apiKey) {
      return { ok: false, error: 'Configura tu API Key de Meshy para continuar en modo Cloud.' };
    }

    try {
      const isImageTo3D = !!params.imageBase64;
      const endpoint = isImageTo3D ? '/image-to-3d' : '/text-to-3d';
      const pollEndpointType = isImageTo3D ? 'image-to-3d' : 'text-to-3d';
      const useCheap5Cr = params.cheapValidation || params.meshyMode === 'preview_5cr';
      const aiModel = useCheap5Cr ? 'meshy-t2' : (params.aiModel || 'meshy-6');
      const estimatedCredits = this.calculateCreditCost({ ...params, cheapValidation: useCheap5Cr });

      const payload = {
        mode: params.mode || 'preview',
        ai_model: aiModel,
        ...(isImageTo3D
          ? { image_url: `data:image/png;base64,${params.imageBase64}` }
          : { prompt: params.prompt || 'Game ready 3D asset' }),
        ...(params.preview_task_id ? { preview_task_id: params.preview_task_id } : {}),
        art_style: params.art_style || 'realistic',
        topology: params.topology || 'quad',
        target_polycount: params.target_polycount || 12000,
        origin_at: params.originAt || 'bottom',
        auto_size: params.autoSize !== false,
        remove_lighting: params.removeLighting !== false,
        target_formats: ['glb', 'usdz', 'fbx'],
        ...(useCheap5Cr ? { enable_pbr: false } : {}),
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

      const taskResult = await this.pollTask(taskId, pollEndpointType, apiKey, onProgress);

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
        creditsUsed: estimatedCredits,
        duration: (Date.now() - (params.startTime || Date.now())) / 1000,
        provider: 'meshy-api',
      };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  }

  cancel() {
    if (this.activeRequest) {
      this.activeRequest.destroy();
      this.activeRequest = null;
    }
  }
}

module.exports = { MeshyRuntime };
