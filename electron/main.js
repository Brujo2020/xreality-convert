const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const os = require('node:os');
const http = require('node:http');
const vm = require('node:vm');
const jscadModeling = require('@jscad/modeling');
const stlSerializer = require('@jscad/stl-serializer');

const OLLAMA_HOST = 'localhost';
const OLLAMA_PORT = 11434;

const isDev = process.env.NODE_ENV === 'development';

// --- Persistence paths -----------------------------------------------------
const APP_SUPPORT_DIR = path.join(
  app.getPath('appData'),
  'OllamaImageStudio'
);
const HISTORY_FILE = path.join(APP_SUPPORT_DIR, 'history.json');
const STL_CACHE_DIR = path.join(APP_SUPPORT_DIR, 'stl-cache');
const PICTURES_DIR = path.join(app.getPath('pictures'), 'OllamaImageStudio');
const STL_SAVE_DIR = path.join(app.getPath('documents'), 'OllamaImageStudio');

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

// --- STL generation --------------------------------------------------------
// A local LLM can't reliably emit raw STL (thousands of triangles), so we ask
// it for parametric JSCAD code instead and build the mesh ourselves. This is
// far more robust and keeps the geometry watertight/printable.
const STL_SYSTEM_PROMPT = `You are an expert 3D modeling assistant. Turn the user's request into a DETAILED 3D model expressed as JSCAD code (JavaScript), compiled to STL with @jscad/modeling v2.

OUTPUT RULES:
- Output a single JavaScript code block. You may add a few short // comment lines at the top to plan the parts, but no prose outside the code.
- Use CommonJS: const { ... } = require('@jscad/modeling').
- Define function main() that RETURNS a single solid geometry (or an array of geometries).
- Export it with: module.exports = { main }.
- Units are millimeters. Center the model near the origin. Keep overall size to a few centimeters.
- Produce a watertight, printable solid. Avoid zero-thickness shapes.

AIM FOR RICHNESS, NOT A BOUNDING PRIMITIVE. A good model is recognizable and detailed:
- Decompose the object into several distinct parts and combine them (union/subtract/intersect).
- For anything turned/round (vases, bottles, chess pieces, knobs, lamps, cups): build a 2D side profile with polygon({points:[...]}) and revolve it with extrudeRotate({segments:64}, profile) — this gives smooth, characteristic silhouettes instead of a plain cylinder.
- For tapered/lofted/organic transitions: stack cross-sections and blend them with hullChain(...).
- For extruded shapes with character: extrudeLinear({height, twistAngle, twistSteps}, profile2D) (profiles can be star, polygon, circle, rectangle).
- Round edges for realism with roundedCuboid / roundedCylinder, or expand({delta, corners:'round', segments:16}, solid).
- Use generous segment counts (32–64) on curved surfaces so they look smooth.
- Add the small features that make the object readable (handles, spouts, feet, bases, holes, ridges).
- Prefer richer geometry over the absolute simplest interpretation.

THE ONLY VALID API (exact names and signatures — nothing else exists):
3D primitives (.primitives): cuboid({size:[x,y,z]}), cube({size}), sphere({radius,segments}),
  cylinder({radius,height,segments}) (hexagon prism = segments:6),
  cylinderElliptic({height,startRadius:[x,y],endRadius:[x,y],segments}),
  roundedCuboid({size:[x,y,z],roundRadius,segments}), roundedCylinder({radius,height,roundRadius,segments}),
  torus({innerRadius,outerRadius,innerSegments,outerSegments})
2D primitives (.primitives, for extrusion): rectangle({size:[x,y]}), circle({radius,segments}),
  ellipse({radius:[x,y]}), star({vertices,outerRadius,innerRadius}), polygon({points:[[x,y],...]})
Booleans (.booleans): union(a,b,...), subtract(a,b,...), intersect(a,b,...)
Transforms (.transforms): translate([x,y,z],obj), rotate([rx,ry,rz],obj), scale([x,y,z],obj), mirror({normal:[x,y,z]},obj)
Extrusions (.extrusions): extrudeLinear({height,twistAngle,twistSteps},geom2), extrudeRotate({segments,angle},geom2)
Hulls (.hulls): hull(...objs), hullChain(...objs)
Expansions (.expansions): expand({delta,corners,segments},obj), offset({delta},geom2)

COMMON MISTAKES TO AVOID (these fail):
- There is NO "prism". Hexagonal/triangular prism = cylinder({radius,height,segments:6}).
- Booleans are union/subtract/intersect — NOT difference/intersection/booleanOps.
- Transforms take (params, object): translate([0,0,5], obj) — never obj.translate(...).
- For extrudeRotate, the 2D profile must stay on x>=0 (it revolves around the Y axis).
- Import everything from require('@jscad/modeling') only.

EXAMPLE — a turned/lathed shape (note the profile + revolve, far richer than a cylinder):
const { extrusions, primitives, transforms, booleans } = require('@jscad/modeling')
const { extrudeRotate } = extrusions
const { polygon, sphere } = primitives
const { translate } = transforms
const { union } = booleans

const main = () => {
  // chess-pawn style: revolve a side profile, then top a sphere on it
  const profile = polygon({ points: [[0,0],[14,0],[11,6],[5,18],[9,26],[6,40],[0,42]] })
  const body = extrudeRotate({ segments: 64 }, profile)
  const head = translate([0, 0, 46], sphere({ radius: 7, segments: 48 }))
  return union(body, head)
}

module.exports = { main }`;

// Pull the JS out of a possibly-chatty model response (strip ``` fences / prose).
function extractCode(text) {
  if (!text) return '';
  const fence = text.match(/```(?:javascript|js|jscad)?\s*([\s\S]*?)```/i);
  let code = fence ? fence[1] : text;
  // If the model still prefixed prose, start at the first meaningful token.
  const start = code.search(/const|let|var|function|module\.exports|\(\s*\)\s*=>/);
  if (start > 0) code = code.slice(start);
  return code.trim();
}

// Models frequently invent a handful of plausible-but-wrong API names. Rather
// than fail outright, expose a forgiving variant of @jscad/modeling with the
// most common aliases mapped to the real functions. This catches first-try
// mistakes; anything subtler is handled by the auto-repair retry.
let jscadCompatCache = null;
function jscadCompat() {
  if (jscadCompatCache) return jscadCompatCache;
  const m = jscadModeling;

  // Flatten every building function onto the top level so BOTH destructuring
  // styles work — `const { extrudeRotate } = require('@jscad/modeling')` and
  // `const { extrusions } = require(...); const { extrudeRotate } = extrusions`.
  // Models constantly mix these up; flattening removes a whole class of failures.
  const flat = {};
  for (const ns of [
    'primitives',
    'booleans',
    'transforms',
    'extrusions',
    'expansions',
    'hulls',
    'modifiers',
    'text',
  ]) {
    if (m[ns]) Object.assign(flat, m[ns]);
  }

  // "prism" isn't real — emulate with a low-segment cylinder.
  const prism = (opts = {}) =>
    m.primitives.cylinder({
      radius: opts.radius ?? 10,
      height: opts.height ?? 10,
      segments: opts.segments ?? 6,
      ...(opts.center ? { center: opts.center } : {}),
    });

  flat.prism = prism;
  flat.difference = m.booleans.subtract;
  flat.intersection = m.booleans.intersect;

  // Weak models also pull functions from the WRONG namespace
  // (e.g. `const { extrudeRotate } = transforms`). So make every function
  // reachable from every namespace too: each namespace = its own funcs on top
  // of the full flat set. Maximally forgiving for LLM-generated code.
  const namespaces = {};
  for (const ns of [
    'primitives',
    'booleans',
    'transforms',
    'extrusions',
    'expansions',
    'hulls',
    'modifiers',
    'text',
  ]) {
    namespaces[ns] = { ...flat, ...(m[ns] || {}) };
  }

  jscadCompatCache = {
    ...m, // keep original namespaces / maths / measurements / …
    ...flat, // every building function at top level
    ...namespaces, // namespaces augmented with the full flat set
    booleanOps: namespaces.booleans,
  };
  return jscadCompatCache;
}

// Evaluate JSCAD code in a locked-down vm context: the generated code can only
// reach @jscad/modeling — no fs, no network, no arbitrary require. Synchronous
// execution is time-boxed so a runaway loop can't hang the app.
function buildStlFromCode(code) {
  let finalCode = code;
  // Tolerate code that defines main() but forgets to export it.
  if (!/module\.exports/.test(finalCode)) {
    finalCode += '\n;try { module.exports = { main }; } catch (e) {}';
  }

  const sandboxModule = { exports: {} };
  const sandbox = {
    module: sandboxModule,
    exports: sandboxModule.exports,
    require: (name) => {
      if (name === '@jscad/modeling') return jscadCompat();
      throw new Error(`Module non autorisé dans le code généré : ${name}`);
    },
    console: { log() {}, warn() {}, error() {} },
    Math,
  };
  const context = vm.createContext(sandbox);

  new vm.Script(finalCode, { filename: 'generated.jscad.js' }).runInContext(
    context,
    { timeout: 5000 }
  );

  const mainFn = sandboxModule.exports.main || sandboxModule.exports;
  if (typeof mainFn !== 'function') {
    throw new Error('Le code généré ne définit pas de fonction main() exportée.');
  }

  // Run main() inside the vm too, so its execution is also time-boxed.
  sandbox.__mainFn = mainFn;
  new vm.Script('__geom = __mainFn();').runInContext(context, { timeout: 10000 });
  const geometry = sandbox.__geom;
  if (!geometry) {
    throw new Error('main() n\'a retourné aucune géométrie.');
  }

  const objects = Array.isArray(geometry) ? geometry : [geometry];
  const raw = stlSerializer.serialize({ binary: false }, objects);
  const stl = Array.isArray(raw) ? raw.join('') : raw;
  if (!stl || !/facet/i.test(stl)) {
    throw new Error('La géométrie générée est vide (aucune facette).');
  }
  return stl;
}

// One call to the model asking for JSCAD code. When `repair` is provided, the
// previous (broken) code and its error are fed back so the model can fix it.
async function requestJscadCode(model, userPrompt, seed, signal, repair) {
  const prompt = repair
    ? `Your previous JSCAD code failed to build with this error:\n${repair.error}\n\nPrevious code:\n${repair.code}\n\nReturn corrected JSCAD code (only valid @jscad/modeling APIs). Object to model: ${userPrompt}`
    : `Object to model: ${userPrompt}`;
  return ollamaRequest({
    method: 'POST',
    pathName: '/api/generate',
    timeout: 600000,
    signal,
    body: {
      model,
      system: STL_SYSTEM_PROMPT,
      prompt,
      stream: false,
      options: { seed, temperature: repair ? 0.3 : 0.6 },
    },
  });
}

const STL_MAX_ATTEMPTS = 3;

ipcMain.handle('ollama:generateStl', async (_event, params) => {
  const { model, prompt, seed } = params;
  activeController = new AbortController();
  const startedAt = Date.now();

  try {
    let stl = null;
    let code = '';
    let lastError = null;
    let attempts = 0;

    // Generate → build → (if it fails) feed the error back and retry. Weaker
    // local models often nail it on the second try once they see the error.
    for (let i = 0; i < STL_MAX_ATTEMPTS && !stl; i++) {
      attempts = i + 1;
      const repair = i > 0 ? { error: lastError, code } : null;
      const res = await requestJscadCode(
        model,
        prompt,
        seed,
        activeController.signal,
        repair
      );

      if (res.statusCode !== 200) {
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
        // Server-side errors (e.g. model won't load) won't improve on retry.
        return { ok: false, error: message };
      }

      const data = JSON.parse(res.body);
      code = extractCode(data.response || '');
      if (!code) {
        lastError = 'Le modèle n\'a renvoyé aucun code.';
        continue;
      }
      try {
        stl = buildStlFromCode(code);
      } catch (err) {
        lastError = err.message;
        stl = null;
      }
    }

    if (!stl) {
      return {
        ok: false,
        error: `Code 3D invalide après ${attempts} essai(s) : ${lastError}`,
        code,
      };
    }

    const duration = (Date.now() - startedAt) / 1000;
    const triangles = (stl.match(/facet normal/g) || []).length;

    // Cache the STL on disk so the gallery can re-display it without bloating
    // history.json with megabytes of mesh text.
    ensureDir(STL_CACHE_DIR);
    const cacheName = `${Date.now()}-${seed}.stl`;
    const stlPath = path.join(STL_CACHE_DIR, cacheName);
    await fsp.writeFile(stlPath, stl, 'utf8');

    return { ok: true, stl, code, duration, triangles, stlPath };
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

// Read a cached/saved STL file back for re-display from the gallery.
ipcMain.handle('ollama:readStl', async (_event, filePath) => {
  try {
    return await fsp.readFile(filePath, 'utf8');
  } catch {
    return null;
  }
});

// Save an STL to ~/Documents/OllamaImageStudio/.
ipcMain.handle('ollama:saveStl', async (_event, { data, filename }) => {
  ensureDir(STL_SAVE_DIR);
  const filePath = path.join(STL_SAVE_DIR, filename);
  await fsp.writeFile(filePath, data, 'utf8');
  return filePath;
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

// --- Hunyuan3D (image -> 3D mesh) via local FastAPI server -----------------
const HUNYUAN_PORT = 8765;

function hunyuanRequest({ method, pathName, body, timeout }) {
  return new Promise((resolve, reject) => {
    const payload = body ? JSON.stringify(body) : null;
    const req = http.request(
      {
        host: '127.0.0.1',
        port: HUNYUAN_PORT,
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
        res.on('end', () =>
          resolve({
            statusCode: res.statusCode,
            body: Buffer.concat(chunks).toString('utf8'),
          })
        );
      }
    );
    if (timeout) req.setTimeout(timeout, () => req.destroy(new Error('TIMEOUT')));
    req.on('error', reject);
    if (payload) req.write(payload);
    req.end();
  });
}

ipcMain.handle('hunyuan:health', async () => {
  try {
    const r = await hunyuanRequest({
      method: 'GET',
      pathName: '/health',
      timeout: 2000,
    });
    if (r.statusCode !== 200) return { up: false };
    return { up: true, ...JSON.parse(r.body) };
  } catch {
    return { up: false };
  }
});

let hunyuanCancelled = false;
ipcMain.handle('hunyuan:cancel3D', async () => {
  hunyuanCancelled = true;
  return { ok: true };
});

// Pick an input image via a native dialog; returns it as a data URL + base64.
ipcMain.handle('hunyuan:pickImage', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    properties: ['openFile'],
    filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'webp'] }],
  });
  if (canceled || !filePaths[0]) return null;
  const buf = await fsp.readFile(filePaths[0]);
  const ext = path.extname(filePaths[0]).slice(1).toLowerCase();
  const mime = ext === 'jpg' ? 'jpeg' : ext;
  const base64 = buf.toString('base64');
  return {
    name: path.basename(filePaths[0]),
    dataUrl: `data:image/${mime};base64,${base64}`,
    base64,
  };
});

// Start a job and poll until done. The mesh build is long (~9 min), so we poll
// the server's job status rather than holding one giant request.
ipcMain.handle('hunyuan:generate3D', async (_event, params) => {
  const { imageBase64, steps, octree, texture, mock } = params;
  hunyuanCancelled = false;
  try {
    const startRes = await hunyuanRequest({
      method: 'POST',
      pathName: '/generate',
      timeout: 30000,
      body: {
        image_base64: imageBase64,
        steps: steps || 30,
        octree_resolution: octree || 256,
        texture: !!texture,
        mock: !!mock,
      },
    });
    if (startRes.statusCode !== 200) {
      return { ok: false, error: `Serveur 3D: HTTP ${startRes.statusCode}` };
    }
    const { job_id } = JSON.parse(startRes.body);

    // Poll loop.
    for (;;) {
      if (hunyuanCancelled) return { ok: false, cancelled: true };
      await new Promise((r) => setTimeout(r, 2000));
      const s = await hunyuanRequest({
        method: 'GET',
        pathName: `/status/${job_id}`,
        timeout: 10000,
      });
      const js = JSON.parse(s.body);
      if (js.status === 'done') {
        const buf = await fsp.readFile(js.glb_path);
        return {
          ok: true,
          glbBase64: buf.toString('base64'),
          glbPath: js.glb_path,
          faces: js.faces,
          duration: js.elapsed,
        };
      }
      if (js.status === 'error') {
        return { ok: false, error: js.error || 'Génération 3D échouée.' };
      }
      if (js.status === 'unknown') {
        return { ok: false, error: 'Job 3D introuvable.' };
      }
      // queued / running -> keep polling
    }
  } catch (err) {
    if (err.code === 'ECONNREFUSED') {
      return {
        ok: false,
        error:
          'Serveur 3D non démarré. Lance-le : cd hunyuan3d-mlx && ./venv/bin/python server.py',
      };
    }
    return { ok: false, error: err.message };
  }
});

// Convert a generated GLB into a printable STL (scaled to target_mm).
ipcMain.handle('hunyuan:convertStl', async (_event, { glbPath, targetMm }) => {
  try {
    const r = await hunyuanRequest({
      method: 'POST',
      pathName: '/to-stl',
      timeout: 60000,
      body: { glb_path: glbPath, target_mm: targetMm || 60 },
    });
    if (r.statusCode !== 200) return { ok: false, error: `HTTP ${r.statusCode}` };
    return JSON.parse(r.body);
  } catch (err) {
    if (err.code === 'ECONNREFUSED') {
      return { ok: false, error: 'Serveur 3D non démarré.' };
    }
    return { ok: false, error: err.message };
  }
});

ipcMain.handle('hunyuan:readGlb', async (_event, filePath) => {
  try {
    const buf = await fsp.readFile(filePath);
    return buf.toString('base64');
  } catch {
    return null;
  }
});

ipcMain.handle('hunyuan:saveGlb', async (_event, { srcPath, base64, filename }) => {
  ensureDir(STL_SAVE_DIR); // ~/Documents/OllamaImageStudio
  const dest = path.join(STL_SAVE_DIR, filename);
  if (srcPath && fs.existsSync(srcPath)) {
    await fsp.copyFile(srcPath, dest);
  } else {
    await fsp.writeFile(dest, Buffer.from(base64, 'base64'));
  }
  return dest;
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
