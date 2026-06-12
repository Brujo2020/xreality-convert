const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const os = require('node:os');
const http = require('node:http');

const OLLAMA_HOST = 'localhost';
const OLLAMA_PORT = 11434;

const isDev = process.env.NODE_ENV === 'development';

// --- Persistence paths -----------------------------------------------------
const APP_SUPPORT_DIR = path.join(
  app.getPath('appData'),
  'OllamaImageStudio'
);
const HISTORY_FILE = path.join(APP_SUPPORT_DIR, 'history.json');
const PICTURES_DIR = path.join(app.getPath('pictures'), 'OllamaImageStudio');

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

// --- Lightweight HTTP helper (Node core, no deps) --------------------------
// Performs a request against the local Ollama server. `signal` allows the
// renderer-driven cancellation to abort an in-flight generation.
function ollamaRequest({ method, pathName, body, timeout, signal }) {
  return new Promise((resolve, reject) => {
    const payload = body ? JSON.stringify(body) : null;
    const req = http.request(
      {
        host: OLLAMA_HOST,
        port: OLLAMA_PORT,
        path: pathName,
        method,
        headers: {
          'Content-Type': 'application/json',
          ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {}),
        },
      },
      (res) => {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => {
          const raw = Buffer.concat(chunks).toString('utf8');
          resolve({ statusCode: res.statusCode, body: raw });
        });
      }
    );

    if (timeout) {
      req.setTimeout(timeout, () => {
        req.destroy(new Error('TIMEOUT'));
      });
    }

    if (signal) {
      if (signal.aborted) {
        req.destroy(new Error('ABORTED'));
      }
      signal.addEventListener('abort', () => req.destroy(new Error('ABORTED')), {
        once: true,
      });
    }

    req.on('error', (err) => reject(err));
    if (payload) req.write(payload);
    req.end();
  });
}

// Track the active generation so Cancel can abort it.
let activeController = null;

// --- IPC: check Ollama status + list image models --------------------------
ipcMain.handle('ollama:checkStatus', async () => {
  try {
    const res = await ollamaRequest({
      method: 'GET',
      pathName: '/api/tags',
      timeout: 4000,
    });
    if (res.statusCode !== 200) {
      return { connected: false, models: [], error: `HTTP ${res.statusCode}` };
    }
    const data = JSON.parse(res.body);
    const allModels = Array.isArray(data.models)
      ? data.models.map((m) => m.name)
      : [];
    // Keep only image-capable model names.
    const imageModels = allModels.filter(
      (name) => /z-image|flux/i.test(name)
    );
    return { connected: true, models: imageModels, allModels };
  } catch (err) {
    return { connected: false, models: [], error: err.message };
  }
});

// --- IPC: generate image ---------------------------------------------------
ipcMain.handle('ollama:generate', async (_event, params) => {
  const { model, prompt, width, height, steps, seed } = params;
  activeController = new AbortController();
  const startedAt = Date.now();

  try {
    const res = await ollamaRequest({
      method: 'POST',
      pathName: '/api/generate',
      timeout: 600000,
      signal: activeController.signal,
      body: {
        model,
        prompt,
        stream: false,
        options: { width, height, steps, seed },
      },
    });

    const duration = (Date.now() - startedAt) / 1000;

    if (res.statusCode !== 200) {
      // Try to surface Ollama's error message.
      let message = `HTTP ${res.statusCode}`;
      try {
        const parsed = JSON.parse(res.body);
        if (parsed.error) message = parsed.error;
      } catch {
        if (res.body) message = res.body;
      }
      if (/not found|no such model|pull/i.test(message)) {
        return {
          ok: false,
          error: `Model not found. Run: ollama pull ${model.split(':')[0]}`,
        };
      }
      return { ok: false, error: message };
    }

    const data = JSON.parse(res.body);
    const image = data.response || data.image || '';
    if (!image) {
      return { ok: false, error: 'Ollama returned an empty image response.' };
    }
    return { ok: true, image, duration };
  } catch (err) {
    if (err.message === 'ABORTED') {
      return { ok: false, cancelled: true, error: 'Generation cancelled.' };
    }
    if (err.message === 'TIMEOUT') {
      return { ok: false, error: 'Generation timed out.' };
    }
    if (err.code === 'ECONNREFUSED') {
      return {
        ok: false,
        error: 'Ollama is not running. Start it with: ollama serve',
      };
    }
    return { ok: false, error: err.message };
  } finally {
    activeController = null;
  }
});

// --- IPC: cancel in-flight generation --------------------------------------
ipcMain.handle('ollama:cancel', async () => {
  if (activeController) {
    activeController.abort();
    return { ok: true };
  }
  return { ok: false };
});

// --- IPC: save image to ~/Pictures/OllamaImageStudio/ ----------------------
ipcMain.handle('ollama:saveImage', async (_event, { base64, filename }) => {
  ensureDir(PICTURES_DIR);
  const clean = base64.replace(/^data:image\/\w+;base64,/, '');
  const filePath = path.join(PICTURES_DIR, filename);
  await fsp.writeFile(filePath, Buffer.from(clean, 'base64'));
  return filePath;
});

// --- IPC: reveal a saved file in Finder ------------------------------------
ipcMain.handle('ollama:revealInFinder', async (_event, filePath) => {
  if (filePath && fs.existsSync(filePath)) {
    shell.showItemInFolder(filePath);
    return true;
  }
  return false;
});

// --- IPC: history persistence ----------------------------------------------
async function readHistory() {
  try {
    const raw = await fsp.readFile(HISTORY_FILE, 'utf8');
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

ipcMain.handle('ollama:loadHistory', async () => {
  return readHistory();
});

ipcMain.handle('ollama:saveHistory', async (_event, history) => {
  ensureDir(APP_SUPPORT_DIR);
  const trimmed = Array.isArray(history) ? history.slice(0, 50) : [];
  await fsp.writeFile(HISTORY_FILE, JSON.stringify(trimmed, null, 2));
  return true;
});

// --- Window ----------------------------------------------------------------
function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#0f0f0f',
    titleBarStyle: 'default', // native macOS traffic lights
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  if (isDev) {
    win.loadURL('http://localhost:5173');
  } else {
    win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }
}

app.whenReady().then(() => {
  ensureDir(APP_SUPPORT_DIR);
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
