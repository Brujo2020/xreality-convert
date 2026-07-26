import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';
import coreSkillCatalog from '../skills/xreality-core.json';

const BROWSER_LOCAL_TOOLS = [
  { id: 'trimesh', label: 'Trimesh', category: 'geometry', status: 'ready', capabilities: ['inspect_mesh', 'repair_basic', 'convert_stl'], bundled: true, installHint: null },
  { id: 'pymeshlab', label: 'PyMeshLab', category: 'geometry', status: 'ready', capabilities: ['inspect_mesh', 'repair_advanced', 'simplify_mesh'], bundled: true, installHint: null },
  { id: 'xatlas', label: 'xatlas', category: 'uv', status: 'ready', capabilities: ['unwrap_uv'], bundled: true, installHint: null },
  { id: 'pygltflib', label: 'pygltflib', category: 'interchange', status: 'ready', capabilities: ['inspect_gltf', 'edit_gltf'], bundled: true, installHint: null },
  { id: 'gltf_validator', label: 'glTF Validator', category: 'validation', status: 'missing', capabilities: ['validate_gltf'], bundled: false, installHint: 'Instala Khronos glTF Validator para habilitar la validación.' },
  { id: 'gltf-transform', label: 'glTF-Transform', category: 'interchange', status: 'missing', capabilities: ['optimize_gltf', 'convert_gltf'], bundled: false, installHint: 'Instala glTF-Transform para habilitar conversiones opcionales.' },
  { id: 'ktx', label: 'KTX-Software', category: 'texture', status: 'missing', capabilities: ['encode_ktx2'], bundled: false, installHint: 'Instala KTX-Software para habilitar la codificación KTX2.' },
  { id: 'blender', label: 'Blender', category: 'authoring', status: 'missing', capabilities: ['inspect_scene', 'convert_scene'], bundled: false, installHint: 'Instala Blender para habilitar la conversión opcional de escenas.' },
];

function browserMission(input, running = false) {
  const skillIds = input.mode === 'image'
    ? ['reference.generate', 'quality.image_gate', 'delivery.manifest']
    : input.mode === 'texture'
      ? ['material.paint', 'quality.pbr_gate', 'delivery.manifest']
      : [
          ...(input.mode === 'stl' ? ['reference.generate'] : []),
          'reference.guard',
          'geometry.reconstruct',
          'geometry.audit',
          'delivery.canonicalize',
          ...(input.texture ? ['material.paint', 'quality.pbr_gate'] : []),
          'delivery.manifest',
        ];
  const byId = new Map(coreSkillCatalog.skills.map((skill) => [skill.id, skill]));
  return {
    id: running ? `browser-${Date.now()}` : 'preview',
    status: running ? 'running' : 'preview',
    offline: true,
    pack: coreSkillCatalog.pack,
    input,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    activeTaskId: running ? `01-${skillIds[0]}` : null,
    tasks: skillIds.map((skillId, index) => {
      const skill = byId.get(skillId);
      return {
        id: `${String(index + 1).padStart(2, '0')}-${skillId}`,
        skillId,
        label: skill.label,
        agent: skill.agent,
        executor: skill.executor,
        resource: skill.resource,
        dependencies: index ? [skillIds[index - 1]] : [],
        status: running && index === 0 ? 'running' : index === 0 ? 'ready' : 'blocked',
      };
    }),
  };
}

// Browser-only preview bridge. Electron replaces these APIs through preload;
// this fallback keeps the interface testable in Vite without touching services.
if (import.meta.env.DEV && !window.ollama) {
  window.ollama = {
    checkStatus: async () => ({ connected: true, models: ['x/flux2-klein:latest'], allModels: ['x/flux2-klein:latest', 'qwen3-coder:30b'] }),
    pullModel: async () => ({ ok: true }),
    loadHistory: async () => [],
    saveHistory: async () => true,
    generate: async () => ({ ok: false, error: 'La generación requiere abrir la app Electron.' }),
    cancel: async () => ({ ok: true }),
    saveImage: async () => null,
    saveStl: async () => null,
    readStl: async () => null,
    revealInFinder: async () => false,
  };
  window.hunyuan = {
    health: async () => ({ up: true, model_loaded: false }),
    analyze: async () => ({ ok: true, status: 'Preview local', actions: [] }),
    install: async () => ({ ok: true }),
    generate3D: async () => ({ ok: false, error: 'La conversión requiere abrir la app Electron.' }),
    recoverCompleted3D: async () => [],
    onProgress: () => () => {},
    cancel3D: async () => ({ ok: true }),
    pickImage: async () => null,
    convertStl: async () => ({ ok: false }),
    textureGlb: async () => ({ ok: false, error: 'Paint requiere abrir la app Electron.' }),
    cacheReference: async () => null,
    readReference: async () => null,
    readGlb: async () => null,
    saveGlb: async () => null,
  };
}

if (import.meta.env.DEV && !window.localTools) {
  window.localTools = {
    list: async () => ({ checkedAt: 0, tools: BROWSER_LOCAL_TOOLS }),
  };
}

if (import.meta.env.DEV && !window.superagents) {
  window.superagents = {
    listSkills: async () => coreSkillCatalog,
    preview: async (input) => browserMission(input),
    start: async (input) => browserMission(input, true),
    active: async () => null,
    onMission: () => () => {},
  };
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
