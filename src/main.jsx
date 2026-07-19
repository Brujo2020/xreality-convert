import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';

const BROWSER_LOCAL_TOOLS = [
  { id: 'trimesh', label: 'Trimesh', category: 'geometry', status: 'ready', capabilities: ['inspect_mesh', 'repair_basic', 'convert_stl'], bundled: true, installHint: null },
  { id: 'pymeshlab', label: 'PyMeshLab', category: 'geometry', status: 'ready', capabilities: ['inspect_mesh', 'repair_advanced', 'simplify_mesh'], bundled: true, installHint: null },
  { id: 'xatlas', label: 'xatlas', category: 'uv', status: 'ready', capabilities: ['unwrap_uv'], bundled: true, installHint: null },
  { id: 'pygltflib', label: 'pygltflib', category: 'interchange', status: 'ready', capabilities: ['inspect_gltf', 'edit_gltf'], bundled: true, installHint: null },
  { id: 'gltf_validator', label: 'glTF Validator', category: 'validation', status: 'missing', capabilities: ['validate_gltf'], bundled: false, installHint: 'Install Khronos glTF Validator to enable validation.' },
  { id: 'gltf-transform', label: 'glTF-Transform', category: 'interchange', status: 'missing', capabilities: ['optimize_gltf', 'convert_gltf'], bundled: false, installHint: 'Install glTF-Transform to enable optional conversions.' },
  { id: 'ktx', label: 'KTX-Software', category: 'texture', status: 'missing', capabilities: ['encode_ktx2'], bundled: false, installHint: 'Install KTX-Software to enable KTX2 encoding.' },
  { id: 'blender', label: 'Blender', category: 'authoring', status: 'missing', capabilities: ['inspect_scene', 'convert_scene'], bundled: false, installHint: 'Install Blender to enable optional scene conversion.' },
];

// Browser-only preview bridge. Electron replaces these APIs through preload;
// this fallback keeps the interface testable in Vite without touching services.
if (import.meta.env.DEV && !window.ollama) {
  window.ollama = {
    checkStatus: async () => ({ connected: true, models: ['x/flux2-klein:latest'], allModels: ['x/flux2-klein:latest', 'qwen3-coder:30b'] }),
    pullModel: async () => ({ ok: true }),
    loadHistory: async () => [],
    saveHistory: async () => true,
    generate: async () => ({ ok: false, error: 'La generación requiere abrir la app Electron.' }),
    generateStl: async () => ({ ok: false, error: 'La generación requiere abrir la app Electron.' }),
    cancel: async () => ({ ok: true }),
    saveImage: async () => null,
    saveStl: async () => null,
    readStl: async () => null,
    revealInFinder: async () => false,
  };
  window.hunyuan = {
    health: async () => ({ up: true, model_loaded: false }),
    install: async () => ({ ok: true }),
    generate3D: async () => ({ ok: false, error: 'La conversión requiere abrir la app Electron.' }),
    cancel3D: async () => ({ ok: true }),
    pickImage: async () => null,
    convertStl: async () => ({ ok: false }),
    readGlb: async () => null,
    saveGlb: async () => null,
  };
}

if (import.meta.env.DEV && !window.localTools) {
  window.localTools = {
    list: async () => ({ checkedAt: 0, tools: BROWSER_LOCAL_TOOLS }),
  };
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
