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

// Hunyuan3D image->3D mesh, served by the local Python (MLX) FastAPI server.
contextBridge.exposeInMainWorld('hunyuan', {
  // -> { up: boolean, model_loaded?: boolean }
  health: () => ipcRenderer.invoke('hunyuan:health'),

  // params: { imageBase64, steps, octree, mock }
  // -> { ok, glbBase64, glbPath, faces, duration } | { ok:false, error, cancelled? }
  generate3D: (params) => ipcRenderer.invoke('hunyuan:generate3D', params),

  cancel3D: () => ipcRenderer.invoke('hunyuan:cancel3D'),

  // Native image picker -> { name, dataUrl, base64 } | null
  pickImage: () => ipcRenderer.invoke('hunyuan:pickImage'),

  // Convert a generated GLB to a printable STL -> { ok, stl_path, dims_mm, watertight }
  convertStl: (args) => ipcRenderer.invoke('hunyuan:convertStl', args),

  // Read a cached/saved GLB back as base64 (for gallery re-display).
  readGlb: (filePath) => ipcRenderer.invoke('hunyuan:readGlb', filePath),

  // Save a GLB to ~/Documents/OllamaImageStudio/
  saveGlb: (args) => ipcRenderer.invoke('hunyuan:saveGlb', args),
});
