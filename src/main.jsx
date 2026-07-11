import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';

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

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
