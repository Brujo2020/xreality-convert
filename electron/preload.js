const { contextBridge, ipcRenderer } = require('electron');

// Expose a minimal, typed surface to the renderer. No Node access leaks
// through; everything goes over IPC to the main process.
contextBridge.exposeInMainWorld('ollama', {
  // -> { connected: boolean, models: string[], allModels?: string[], error?: string }
  checkStatus: () => ipcRenderer.invoke('ollama:checkStatus'),

  // params: { model, prompt, width, height, steps, seed }
  // -> { ok: true, image: base64, duration: number } | { ok: false, error, cancelled? }
  generate: (params) => ipcRenderer.invoke('ollama:generate', params),

  // params: { model, prompt, seed }
  // -> { ok: true, stl, code, duration, triangles, stlPath } | { ok: false, error, code?, cancelled? }
  generateStl: (params) => ipcRenderer.invoke('ollama:generateStl', params),

  // Read a cached/saved STL file back (for gallery re-display).
  readStl: (filePath) => ipcRenderer.invoke('ollama:readStl', filePath),

  // -> absolute file path of the saved STL
  saveStl: (data, filename) =>
    ipcRenderer.invoke('ollama:saveStl', { data, filename }),

  // Abort the in-flight generation.
  cancel: () => ipcRenderer.invoke('ollama:cancel'),

  // -> absolute file path of the saved PNG
  saveImage: (base64, filename) =>
    ipcRenderer.invoke('ollama:saveImage', { base64, filename }),

  // Reveal a saved file in Finder.
  revealInFinder: (filePath) =>
    ipcRenderer.invoke('ollama:revealInFinder', filePath),

  // -> Array<historyEntry>
  loadHistory: () => ipcRenderer.invoke('ollama:loadHistory'),

  // Persist the full history array.
  saveHistory: (history) => ipcRenderer.invoke('ollama:saveHistory', history),
});
