import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import './index.css';

// Global error handlers to prevent unhandled promise rejections or script errors from freezing the UI
window.addEventListener('unhandledrejection', (event) => {
  console.warn('Caught unhandled promise rejection:', event.reason);
});

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
    admitMultiView: async () => ({ ok: true, admission: { passed: true } }),
    multiViewStatus: async () => ({ available: true }),
    convertStl: async () => ({ ok: false }),
    convertOpenUsd: async () => ({ ok: false }),
    readGlb: async () => null,
    saveGlb: async () => null,
  };
  window.meshy = {
    getApiKey: async () => '',
    saveApiKey: async () => true,
    generate3D: async () => ({ ok: false, error: 'La generación Meshy requiere abrir la app Electron con una API Key válida.' }),
    cancel: async () => ({ ok: true }),
  };
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);

