const { contextBridge } = require('electron');
const fs = require('node:fs');
const smokeState = process.env.XREALITY_SMOKE_STATE || 'ready';

const glbPath = process.env.XREALITY_SMOKE_GLB || '';
const glbBase64 = glbPath && fs.existsSync(glbPath)
  ? fs.readFileSync(glbPath).toString('base64')
  : null;
const referencePath = process.env.XREALITY_SMOKE_REFERENCE || '';
const referenceBase64 = referencePath && fs.existsSync(referencePath)
  ? fs.readFileSync(referencePath).toString('base64')
  : '';
const referenceDataUrl = referenceBase64 ? `data:image/png;base64,${referenceBase64}` : null;
const resultImagePath = process.env.XREALITY_SMOKE_RESULT_IMAGE || '';
const resultImageBase64 = resultImagePath && fs.existsSync(resultImagePath)
  ? fs.readFileSync(resultImagePath).toString('base64')
  : null;
const history = glbBase64 ? [{
  id: 'visual-smoke-glb',
  type: 'glb',
  glbPath,
  faces: 5120,
  duration: 58.4,
  steps: 35,
  textured: true,
  textureSize: '2K',
  prompt: 'Referencia de control visual',
  inputDataUrl: referenceDataUrl,
  model: 'hunyuan3d-2.1-mlx',
  category: 'product',
  profile: 'xreal',
  qualityLevel: 'listo',
  qualityText: 'Geometría y material aprobados por los gates de entrega.',
  textureReport: {
    visual_fidelity: {
      gate: {
        passed: true,
        front: { metrics: { spatialColorCorrelation: 0.83 } },
      },
    },
  },
}] : resultImageBase64 ? [{
  id: 'visual-smoke-image',
  type: 'image',
  image: resultImageBase64,
  width: 1024,
  height: 1024,
  duration: 14.2,
  steps: 12,
  prompt: 'Referencia de control visual',
  model: 'flux-local',
  profile: 'mobile',
  qualityLevel: 'listo',
  qualityText: 'Referencia visual aprobada para reconstrucción.',
}] : [];

contextBridge.exposeInMainWorld('ollama', {
  checkStatus: async () => ({ connected: true, models: ['qwen3-coder:latest'], allModels: ['qwen3-coder:latest'] }),
  pullModel: async () => ({ ok: true }),
  generate: async () => ({ ok: false, error: 'No disponible en smoke test.' }),
  generateStl: async () => ({ ok: false, error: 'No disponible en smoke test.' }),
  readStl: async () => null,
  saveStl: async () => null,
  cancel: async () => true,
  saveImage: async () => null,
  revealInFinder: async () => false,
  loadHistory: async () => history,
  saveHistory: async () => true,
});

contextBridge.exposeInMainWorld('hunyuan', {
  health: async () => ({ up: smokeState === 'ready', ready: smokeState === 'ready' }),
  analyze: async () => ({ ok: false, error: 'Sin referencia.' }),
  install: async () => {
    if (smokeState === 'loading') return new Promise(() => {});
    if (smokeState === 'error') return {
      ok: false,
      error: 'Python 3.10 o superior no está disponible en este equipo. Instala Python 3.11 o 3.12 y vuelve a intentar la instalación del motor 3D.',
    };
    return { ok: true, cached: true };
  },
  generate3D: async () => ({ ok: false, error: 'No disponible en smoke test.' }),
  onProgress: () => () => {},
  cancel3D: async () => true,
  pickImage: async () => null,
  convertStl: async () => ({ ok: false }),
  convertOpenUsd: async () => ({ ok: false }),
  readGlb: async () => glbBase64,
  saveGlb: async () => null,
});
