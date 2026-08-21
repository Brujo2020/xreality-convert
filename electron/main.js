const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const os = require('node:os');
const http = require('node:http');
const { createHash, randomBytes } = require('node:crypto');
const vm = require('node:vm');
const { execFileSync, spawn } = require('node:child_process');
const jscadModeling = require('@jscad/modeling');
const stlSerializer = require('@jscad/stl-serializer');
const {
  inspectHunyuanRuntime,
  engineProcessEnv,
  appleSiliconExecutionPlan,
  engineRestartDelay,
} = require('./hunyuan-runtime.cjs');
const { MeshyRuntime } = require('./meshy-runtime.cjs');

const APP_NAME = 'Xreality Convert';

const APP_ID = 'com.xreality.convert';

const OLLAMA_HOST = 'localhost';
const OLLAMA_PORT = 11434;

const isDev = process.env.NODE_ENV === 'development';

app.setName(APP_NAME);
app.setAppUserModelId(APP_ID);
const hasSingleInstanceLock = app.requestSingleInstanceLock();
if (!hasSingleInstanceLock) app.exit(0);

// --- Persistence paths -----------------------------------------------------
const APP_SUPPORT_DIR = path.join(
  app.getPath('appData'),
  'XrealityConvert'
);
const HISTORY_FILE = path.join(APP_SUPPORT_DIR, 'history.json');
const STL_CACHE_DIR = path.join(APP_SUPPORT_DIR, 'stl-cache');
const PICTURES_DIR = path.join(app.getPath('pictures'), 'XrealityConvert');
const STL_SAVE_DIR = path.join(app.getPath('documents'), 'XrealityConvert');
const ENGINE_TOKEN_FILE = path.join(APP_SUPPORT_DIR, '.engine-token');
const localHttpAgent = new http.Agent({ keepAlive: true, maxSockets: 4 });
let engineToken = null;

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function getEngineToken() {
  if (engineToken) return engineToken;
  ensureDir(APP_SUPPORT_DIR);
  try {
    engineToken = fs.readFileSync(ENGINE_TOKEN_FILE, 'utf8').trim();
  } catch {}
  if (!engineToken) {
    engineToken = randomBytes(32).toString('hex');
    fs.writeFileSync(ENGINE_TOKEN_FILE, engineToken, { mode: 0o600 });
  }
  return engineToken;
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
        agent: localHttpAgent,
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
let ollamaProcess = null;
let ollamaStartPromise = null;

async function ollamaIsUp() {
  try {
    const res = await ollamaRequest({ method: 'GET', pathName: '/api/tags', timeout: 1500 });
    return res.statusCode === 200;
  } catch {
    return false;
  }
}

async function waitForOllama(timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await ollamaIsUp()) return true;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

async function ensureOllamaRunning() {
  if (await ollamaIsUp()) return true;
  if (ollamaStartPromise) return ollamaStartPromise;
  ollamaStartPromise = (async () => {
    const candidates = [
      process.env.OLLAMA_PATH,
      '/opt/homebrew/bin/ollama',
      '/usr/local/bin/ollama',
      'ollama',
    ].filter(Boolean);
    for (const executable of candidates) {
      try {
        ollamaProcess = spawn(executable, ['serve'], {
          detached: false,
          stdio: 'ignore',
          env: process.env,
        });
        ollamaProcess.on('error', () => {});
        if (await waitForOllama(8000)) return true;
      } catch {}
    }
    // The macOS app may be installed even when its CLI isn't in PATH.
    try {
      spawn('/usr/bin/open', ['-a', 'Ollama'], { detached: true, stdio: 'ignore' }).unref();
      return await waitForOllama(12000);
    } catch {
      return false;
    }
  })();
  try {
    return await ollamaStartPromise;
  } finally {
    ollamaStartPromise = null;
  }
}

// --- IPC: check Ollama status + list image models --------------------------
ipcMain.handle('ollama:checkStatus', async () => {
  try {
    await ensureOllamaRunning();
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

ipcMain.handle('ollama:pullModel', async (_event, model) => {
  await ensureOllamaRunning();
  try {
    const res = await ollamaRequest({
      method: 'POST',
      pathName: '/api/pull',
      timeout: 3600000,
      body: { model, stream: false },
    });
    if (res.statusCode !== 200) {
      let error = `HTTP ${res.statusCode}`;
      try { error = JSON.parse(res.body).error || error; } catch {}
      return { ok: false, error };
    }
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err.message };
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
  const { model, prompt, seed, profile, targetFaces } = params;
  const productionConstraint = profile === 'lowpoly'
    ? `\nXR DELIVERY PROFILE: LOW POLY. Use a clean readable silhouette, merge parts, avoid invisible details, use 8-16 segments on curves, and stay below ${targetFaces || 12000} triangles.`
    : profile === 'maxquality'
    ? `\nXR DELIVERY PROFILE: MAXIMUM QUALITY. Use 48-64 segments on curves, refined transitions, and detailed but watertight construction.`
    : `\nXR DELIVERY PROFILE: ${profile || 'xreal'}. Keep the result efficient and below approximately ${targetFaces || 50000} triangles.`;
  const optimizedPrompt = `${prompt}${productionConstraint}`;
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
        optimizedPrompt,
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
const HUNYUAN_INSTALL_VERSION = '21';
const HUNYUAN_SOURCE_REVISION = 'xreality-buffalo-mlx-openusd-watertight-v2';

function hunyuanRequest({ method, pathName, body, timeout }) {
  return new Promise((resolve, reject) => {
    const payload = body ? JSON.stringify(body) : null;
    const req = http.request(
      {
        host: '127.0.0.1',
        port: HUNYUAN_PORT,
        path: pathName,
        method,
        agent: localHttpAgent,
        headers: {
          'Content-Type': 'application/json',
          'X-Xreality-Engine-Token': getEngineToken(),
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

async function hunyuanCancelCurrentJob() {
  if (!hunyuanActiveJobId) return false;
  try {
    await hunyuanRequest({
      method: 'POST',
      pathName: `/cancel/${hunyuanActiveJobId}`,
      timeout: 5000,
    });
    return true;
  } catch {
    return false;
  }
}

// Auto-start the local 3D server when the app launches, so the Img→3D mode
// works without the user manually running it. We only manage (and later kill)
// the process if WE started it — a server the user launched by hand is left
// untouched. The server is light at idle (weights load lazily per job).
const BUNDLED_ENGINE_DIR = isDev
  ? path.join(__dirname, '..', 'engine')
  : path.join(process.resourcesPath, 'app.asar.unpacked', 'engine');
const HUNYUAN_SERVER_DIR = process.env.OIS_3D_SERVER_DIR || (isDev
  ? BUNDLED_ENGINE_DIR
  : path.join(APP_SUPPORT_DIR, 'engine'));
let hunyuanServerProc = null;
let hunyuanServerStartPromise = null;
let hunyuanInstallProc = null;
let hunyuanActiveJobId = null;
let hunyuanLastExit = null;
let hunyuanRestartTimer = null;
let hunyuanRestartAttempts = 0;
let hunyuanShutdownRequested = false;
const HUNYUAN_RESTART_LIMIT = 4;
const HUNYUAN_LOG_FILE = path.join(APP_SUPPORT_DIR, 'engine-runtime.log');
// Keep Electron/Finder launches on the same Hugging Face object store used by
// terminal runs. An explicit HF_HUB_CACHE still wins (for example, an external
// SSD), but the app never invents a second cache under Application Support.
const HUGGINGFACE_HUB_CACHE = process.env.HF_HUB_CACHE || path.join(
  process.env.HF_HOME || path.join(os.homedir(), '.cache', 'huggingface'),
  'hub'
);

function clearHunyuanRestartTimer() {
  if (hunyuanRestartTimer) clearTimeout(hunyuanRestartTimer);
  hunyuanRestartTimer = null;
}

function scheduleHunyuanRestart() {
  if (hunyuanShutdownRequested || hunyuanRestartTimer) return;
  if (hunyuanRestartAttempts >= HUNYUAN_RESTART_LIMIT) {
    appendHunyuanLog(`reinicio automático agotado tras ${HUNYUAN_RESTART_LIMIT} intentos`);
    return;
  }
  hunyuanRestartAttempts += 1;
  const delayMs = engineRestartDelay(hunyuanRestartAttempts);
  appendHunyuanLog(`reinicio automático ${hunyuanRestartAttempts}/${HUNYUAN_RESTART_LIMIT} en ${delayMs}ms`);
  hunyuanRestartTimer = setTimeout(() => {
    hunyuanRestartTimer = null;
    startHunyuanServer().catch((error) => {
      appendHunyuanLog(`reinicio automático falló: ${error.message}`);
      scheduleHunyuanRestart();
    });
  }, delayMs);
  hunyuanRestartTimer.unref?.();
}

function hunyuanRuntimeStatus() {
  return inspectHunyuanRuntime(
    HUNYUAN_SERVER_DIR,
    HUNYUAN_INSTALL_VERSION,
    HUNYUAN_SOURCE_REVISION
  );
}

function appendHunyuanLog(message) {
  ensureDir(APP_SUPPORT_DIR);
  fs.appendFileSync(HUNYUAN_LOG_FILE, `${new Date().toISOString()} ${message}\n`, {
    encoding: 'utf8',
    mode: 0o600,
  });
}

async function prepareHunyuanEngineFiles() {
  if (HUNYUAN_SERVER_DIR === BUNDLED_ENGINE_DIR) return { cached: true };
  const bundleMarker = path.join(HUNYUAN_SERVER_DIR, '.bundle-version');
  const sourceMarker = path.join(HUNYUAN_SERVER_DIR, '.source-version');
  const requiredRuntimeFiles = [
    'server.py',
    'setup.sh',
    'paint_service.py',
    'agentic_paint_service.py',
    'pbr_glb.py',
    'material_policy.py',
    'asset_director.py',
    'buffalo_strategy.py',
    'openusd_export.py',
    'reference_projection.py',
    'm5_optimizer.py',
    'requirements-macos.lock',
  ];
  // Keep the installed runtime congruent with the bundled control plane. The
  // server imports several small, fail-closed gates; copying only the original
  // inference files would let a packaged build pass installation then fail at
  // import time. Tests and bytecode are deliberately excluded.
  let bundledRuntimeFiles = [];
  try {
    bundledRuntimeFiles = (await fsp.readdir(BUNDLED_ENGINE_DIR)).filter(
      (filename) => filename.endsWith('.py') && !filename.startsWith('test_')
    );
  } catch {}
  const filenames = [...new Set([...requiredRuntimeFiles, ...bundledRuntimeFiles])];
  let copiedVersion = '';
  let copiedSourceRevision = '';
  try { copiedVersion = (await fsp.readFile(bundleMarker, 'utf8')).trim(); } catch {}
  try { copiedSourceRevision = (await fsp.readFile(sourceMarker, 'utf8')).trim(); } catch {}
  const bundleComplete = filenames.every((filename) =>
    fs.existsSync(path.join(HUNYUAN_SERVER_DIR, filename))
  ) && fs.existsSync(
    path.join(HUNYUAN_SERVER_DIR, 'Hunyuan3D-2.1-mlx', 'hy3dshape', 'hy3dshape', 'pipeline_mlx.py')
  ) && fs.existsSync(
    path.join(HUNYUAN_SERVER_DIR, 'AgenticVibes-Hunyuan3D-Paint', 'hy3dpaint', 'mlx', 'hybrid_unet.py')
  ) && fs.existsSync(
    path.join(HUNYUAN_SERVER_DIR, 'agentic_paint_runner.py')
  ) && fs.existsSync(
    path.join(HUNYUAN_SERVER_DIR, 'Hunyuan3D-2-official', 'hy3dgen', 'shapegen', 'pipelines.py')
  );
  if (
    copiedVersion === HUNYUAN_INSTALL_VERSION &&
    copiedSourceRevision === HUNYUAN_SOURCE_REVISION &&
    bundleComplete
  ) {
    return { cached: true };
  }

  ensureDir(HUNYUAN_SERVER_DIR);
  await Promise.all(filenames.map(async (filename) => {
    const source = path.join(BUNDLED_ENGINE_DIR, filename);
    if (fs.existsSync(source)) {
      await fsp.copyFile(source, path.join(HUNYUAN_SERVER_DIR, filename));
    }
  }));
  const bundledAgenticRunner = path.join(
    path.dirname(BUNDLED_ENGINE_DIR),
    'benchmarks',
    'model-arena',
    'run_agenticvibes_paint.py'
  );
  if (fs.existsSync(bundledAgenticRunner)) {
    await fsp.copyFile(
      bundledAgenticRunner,
      path.join(HUNYUAN_SERVER_DIR, 'agentic_paint_runner.py')
    );
  }
  const bundledPaint = path.join(BUNDLED_ENGINE_DIR, 'Hunyuan3D-2.1-mlx', 'hy3dpaint');
  const installedPaint = path.join(HUNYUAN_SERVER_DIR, 'Hunyuan3D-2.1-mlx', 'hy3dpaint');
  if (fs.existsSync(bundledPaint)) {
    ensureDir(path.dirname(installedPaint));
    await fsp.cp(bundledPaint, installedPaint, { recursive: true, force: true });
  }
  const bundledShape = path.join(
    BUNDLED_ENGINE_DIR,
    'Hunyuan3D-2.1-mlx',
    'hy3dshape',
    'hy3dshape'
  );
  const installedShape = path.join(
    HUNYUAN_SERVER_DIR,
    'Hunyuan3D-2.1-mlx',
    'hy3dshape',
    'hy3dshape'
  );
  if (fs.existsSync(bundledShape)) {
    ensureDir(path.dirname(installedShape));
    await fsp.cp(bundledShape, installedShape, { recursive: true, force: true });
  }
  const bundledMultiView = path.join(BUNDLED_ENGINE_DIR, 'Hunyuan3D-2-official', 'hy3dgen');
  const installedMultiView = path.join(HUNYUAN_SERVER_DIR, 'Hunyuan3D-2-official', 'hy3dgen');
  if (fs.existsSync(bundledMultiView)) {
    ensureDir(path.dirname(installedMultiView));
    await fsp.cp(bundledMultiView, installedMultiView, { recursive: true, force: true });
  }
  const bundledAgentic = path.join(BUNDLED_ENGINE_DIR, 'AgenticVibes-Hunyuan3D-Paint');
  const installedAgentic = path.join(HUNYUAN_SERVER_DIR, 'AgenticVibes-Hunyuan3D-Paint');
  if (fs.existsSync(bundledAgentic)) {
    await fsp.cp(bundledAgentic, installedAgentic, { recursive: true, force: true });
  }
  await fsp.writeFile(bundleMarker, HUNYUAN_INSTALL_VERSION, 'utf8');
  await fsp.writeFile(sourceMarker, HUNYUAN_SOURCE_REVISION, 'utf8');
  return { cached: false };
}

function hunyuanIsUp() {
  return new Promise((resolve) => {
    const req = http.request(
      { host: '127.0.0.1', port: HUNYUAN_PORT, path: '/health', method: 'GET' },
      (res) => {
        const chunks = [];
        res.on('data', (chunk) => chunks.push(chunk));
        res.on('end', () => {
          if (res.statusCode !== 200) return resolve(false);
          try {
            const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
            resolve(data.engine_version === HUNYUAN_INSTALL_VERSION);
          } catch {
            resolve(false);
          }
        });
      }
    );
    req.setTimeout(1500, () => req.destroy());
    req.on('error', () => resolve(false));
    req.end();
  });
}

function localEngineListenerPids() {
  try {
    return execFileSync('/usr/sbin/lsof', [
      '-nP',
      `-iTCP:${HUNYUAN_PORT}`,
      '-sTCP:LISTEN',
      '-t',
    ], { encoding: 'utf8' })
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .map(Number)
      .filter(Number.isInteger);
  } catch {
    return [];
  }
}

async function stopStaleOwnedHunyuanServer() {
  const expectedScript = path.join(HUNYUAN_SERVER_DIR, 'server.py');
  let stopped = false;
  for (const pid of localEngineListenerPids()) {
    let command = '';
    try {
      command = execFileSync('/bin/ps', ['-p', String(pid), '-o', 'command='], { encoding: 'utf8' }).trim();
    } catch {}
    if (!command.includes(expectedScript)) continue;
    try {
      process.kill(pid, 'SIGTERM');
      stopped = true;
    } catch {}
  }
  if (!stopped) return false;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    if (!localEngineListenerPids().length) return true;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return false;
}

async function startHunyuanServerOnce() {
  await prepareHunyuanEngineFiles();
  const runtime = hunyuanRuntimeStatus();
  if (!runtime.ready) {
    await stopStaleOwnedHunyuanServer();
    appendHunyuanLog(`runtime bloqueado; faltan ${runtime.missing.join(',')}`);
    return { started: false, needsInstall: true, missing: runtime.missing };
  }
  if (await hunyuanIsUp()) return; // already running (e.g. started manually)
  // The first spawn can still be importing MLX while the renderer performs its
  // initial health/bootstrap pass. Do not create a second Uvicorn process in
  // that short interval before port 8765 starts accepting connections.
  if (
    hunyuanServerProc &&
    hunyuanServerProc.exitCode === null &&
    !hunyuanServerProc.killed
  ) {
    return { started: false, starting: true };
  }
  if (localEngineListenerPids().length) {
    const stopped = await stopStaleOwnedHunyuanServer();
    if (!stopped && localEngineListenerPids().length) {
      console.warn('[hunyuan] el puerto 8765 está ocupado por otro proceso; no se reemplazará.');
      return;
    }
  }
  const py = path.join(HUNYUAN_SERVER_DIR, 'venv', 'bin', 'python');
  const script = path.join(HUNYUAN_SERVER_DIR, 'server.py');
  if (!fs.existsSync(py) || !fs.existsSync(script)) {
    console.warn(
      `[hunyuan] serveur introuvable dans ${HUNYUAN_SERVER_DIR} — Img→3D restera indisponible jusqu'au lancement manuel.`
    );
    return;
  }
  try {
    const executionPlan = appleSiliconExecutionPlan({
      logicalCores: os.cpus().length,
      totalMemoryBytes: os.totalmem(),
    });
    appendHunyuanLog(`iniciando motor local; plan=${JSON.stringify(executionPlan)}`);
    const logFd = fs.openSync(HUNYUAN_LOG_FILE, 'a', 0o600);
    hunyuanServerProc = spawn(py, [script], {
      cwd: HUNYUAN_SERVER_DIR,
      env: {
        ...engineProcessEnv(process.env, os.homedir()),
        XREALITY_ENGINE_TOKEN: getEngineToken(),
        PYTHONUNBUFFERED: '1',
        HF_HUB_OFFLINE: '0',
        TRANSFORMERS_OFFLINE: '0',
        XREALITY_MAX_SHAPE_SWAP_GROWTH_MB: '16384',
        XREALITY_MAX_AGENTIC_SWAP_GROWTH_MB: '16384',
        XREALITY_VALIDATION_WORKERS: String(executionPlan.validationWorkers),
        XREALITY_MLX_CACHE_MIB: String(executionPlan.cacheMiB),
        HF_HUB_CACHE: HUGGINGFACE_HUB_CACHE,
        OMP_NUM_THREADS: String(executionPlan.mathThreads),
        OPENBLAS_NUM_THREADS: String(executionPlan.mathThreads),
        VECLIB_MAXIMUM_THREADS: String(executionPlan.mathThreads),
        ...(process.env.HUNYUAN3D_MLX_WEIGHTS_DIR
          ? { HUNYUAN3D_MLX_WEIGHTS_DIR: process.env.HUNYUAN3D_MLX_WEIGHTS_DIR }
          : {}),
      },
      stdio: ['ignore', logFd, logFd],
    });
    fs.closeSync(logFd);
    const startedProc = hunyuanServerProc;
    const startedAt = Date.now();
    startedProc.on('exit', (code, signal) => {
      hunyuanLastExit = { code, signal, at: new Date().toISOString() };
      appendHunyuanLog(`motor finalizado code=${code ?? 'null'} signal=${signal ?? 'null'}`);
      if (hunyuanServerProc === startedProc) hunyuanServerProc = null;
      if (Date.now() - startedAt >= 30000) hunyuanRestartAttempts = 0;
      if (!hunyuanShutdownRequested) scheduleHunyuanRestart();
    });
  } catch (err) {
    console.warn('[hunyuan] échec du démarrage du serveur 3D :', err.message);
    appendHunyuanLog(`spawn del motor falló: ${err.message}`);
    scheduleHunyuanRestart();
  }
}

function startHunyuanServer() {
  if (hunyuanServerStartPromise) return hunyuanServerStartPromise;
  hunyuanServerStartPromise = startHunyuanServerOnce().finally(() => {
    hunyuanServerStartPromise = null;
  });
  return hunyuanServerStartPromise;
}

async function ensureHunyuanServerReady() {
  if (await hunyuanIsUp()) {
    hunyuanRestartAttempts = 0;
    clearHunyuanRestartTimer();
    return true;
  }
  await startHunyuanServer();
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if (await hunyuanIsUp()) {
      hunyuanRestartAttempts = 0;
      clearHunyuanRestartTimer();
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return false;
}

function stopHunyuanServer() {
  hunyuanShutdownRequested = true;
  clearHunyuanRestartTimer();
  if (hunyuanServerProc) {
    try {
      hunyuanServerProc.kill('SIGTERM');
    } catch {}
    hunyuanServerProc = null;
  }
}

ipcMain.handle('hunyuan:health', async () => {
  const runtime = hunyuanRuntimeStatus();
  if (!runtime.ready) {
    return {
      up: false,
      needsInstall: true,
      error: `El motor local requiere actualización (${runtime.missing.join(', ')}).`,
    };
  }
  try {
    const r = await hunyuanRequest({
      method: 'GET',
      pathName: '/health',
      timeout: 2000,
    });
    if (r.statusCode !== 200) return { up: false };
    const data = JSON.parse(r.body);
    if (data.engine_version !== HUNYUAN_INSTALL_VERSION) {
      return { up: false, error: 'El motor local activo es de una versión anterior.' };
    }
    return { up: true, ...data };
  } catch {
    return { up: false };
  }
});

ipcMain.handle('hunyuan:analyze', async (_event, params) => {
  try {
    const r = await hunyuanRequest({
      method: 'POST',
      pathName: '/analyze',
      timeout: 60000,
      body: {
        image_base64: params.imageBase64,
        category: params.category || 'custom',
        background_mode: params.backgroundMode || 'auto',
      },
    });
    if (r.statusCode !== 200) {
      let error = `HTTP ${r.statusCode}`;
      try {
        const parsed = JSON.parse(r.body);
        error = parsed.detail || parsed.error || error;
      } catch {}
      return { ok: false, error };
    }
    return { ok: true, ...JSON.parse(r.body) };
  } catch (err) {
    if (err.code === 'ECONNREFUSED') {
      return { ok: false, error: 'Serveur 3D non démarré.' };
    }
    return { ok: false, error: err.message };
  }
});

// Bootstrap the bundled Apple-Silicon engine. We install code and Python
// dependencies once; model weights are fetched lazily at first conversion.
ipcMain.handle('hunyuan:install', async () => {
  if (hunyuanInstallProc) {
    return { ok: false, error: 'La instalación del motor ya está en curso.' };
  }
  await prepareHunyuanEngineFiles();
  if (hunyuanRuntimeStatus().ready) {
    await startHunyuanServer();
    return { ok: true, cached: true };
  }
  stopHunyuanServer();
  await stopStaleOwnedHunyuanServer();
  const setup = path.join(HUNYUAN_SERVER_DIR, 'setup.sh');
  if (!fs.existsSync(setup)) {
    return { ok: false, error: 'No se encontró el instalador del motor 3D.' };
  }
  return new Promise((resolve) => {
    const output = [];
    hunyuanInstallProc = spawn('/bin/zsh', [setup], {
      cwd: HUNYUAN_SERVER_DIR,
      env: engineProcessEnv(process.env, os.homedir()),
    });
    hunyuanInstallProc.stdout.on('data', (data) => output.push(data.toString()));
    hunyuanInstallProc.stderr.on('data', (data) => output.push(data.toString()));
    hunyuanInstallProc.on('error', (err) => {
      hunyuanInstallProc = null;
      resolve({ ok: false, error: err.message });
    });
    hunyuanInstallProc.on('close', (code) => {
      hunyuanInstallProc = null;
      if (code !== 0) {
        resolve({ ok: false, error: output.join('').slice(-1400) || `El instalador terminó con código ${code}.` });
        return;
      }
      startHunyuanServer();
      resolve({ ok: true });
    });
  });
});

let hunyuanCancelled = false;
ipcMain.handle('hunyuan:cancel3D', async () => {
  hunyuanCancelled = true;
  await hunyuanCancelCurrentJob();
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

ipcMain.handle('hunyuan:admitMultiView', async (_event, params) => {
  try {
    if (!(await ensureHunyuanServerReady())) return { ok: false, error: 'Motor multi-vista no disponible.' };
    const views = (params?.views || []).map((view) => ({
      view_id: view.viewId,
      evidence_class: 'measured',
      sha256: createHash('sha256').update(Buffer.from(view.base64, 'base64')).digest('hex'),
    }));
    const response = await hunyuanRequest({ method: 'POST', pathName: '/multiview/admit', timeout: 10000, body: { views, profile: params?.profile || 'xreal' } });
    return response.statusCode === 200 ? JSON.parse(response.body) : { ok: false, error: `HTTP ${response.statusCode}` };
  } catch (error) { return { ok: false, error: error.message }; }
});

ipcMain.handle('hunyuan:multiViewStatus', async () => {
  try {
    if (!(await ensureHunyuanServerReady())) return { available: false, state: 'unavailable', reason_code: 'engine_unavailable' };
    const response = await hunyuanRequest({ method: 'GET', pathName: '/multiview/status', timeout: 10000 });
    return response.statusCode === 200 ? JSON.parse(response.body) : { available: false, state: 'unavailable', reason_code: `http_${response.statusCode}` };
  } catch (error) { return { available: false, state: 'unavailable', reason_code: 'status_failed', detail: error.message }; }
});

// Start a job and poll until done. The mesh build is long (~9 min), so we poll
// the server's job status rather than holding one giant request.
ipcMain.handle('hunyuan:generate3D', async (event, params) => {
  const { imageBase64, multiViewImages, useMultiviewShape, steps, octree, texture, textureSize, paintBackend, materialHint, targetFaces, scale, profile, category, guidance, backgroundMode, subjectPadding } = params;
  hunyuanCancelled = false;
  try {
    event.sender.send('hunyuan:progress', {
      stage: 'Verificando motor local',
      progress: 1,
      percent: 1,
      remaining: null,
      status: 'starting',
    });
    if (!(await ensureHunyuanServerReady())) {
      return {
        ok: false,
        error: `El motor 3D no respondió después del reinicio automático. Revisa ${HUNYUAN_LOG_FILE}.`,
      };
    }
    event.sender.send('hunyuan:progress', {
      stage: 'Preparando referencia',
      progress: 4,
      percent: 4,
      remaining: null,
      status: 'starting',
    });
    const startRes = await hunyuanRequest({
      method: 'POST',
      pathName: '/generate',
      timeout: 30000,
      body: {
        image_base64: imageBase64,
        multi_view_images: multiViewImages || {},
        use_multiview_shape: useMultiviewShape === true,
        steps: steps || 30,
        octree_resolution: octree || 256,
        texture: !!texture,
        texture_resolution: textureSize === '1K' ? 1024 : 2048,
        paint_backend: paintBackend || 'fast',
        material_hint: materialHint || 'auto',
        target_faces: targetFaces || 50000,
        scale_meters: scale || 1,
        profile: profile || 'xreal',
        category: category || 'custom',
        guidance: guidance || 6.0,
        background_mode: backgroundMode || 'auto',
        subject_padding: subjectPadding || 0.16,
      },
    });
    if (startRes.statusCode !== 200) {
      return { ok: false, error: `Serveur 3D: HTTP ${startRes.statusCode}` };
    }
    const { job_id } = JSON.parse(startRes.body);
    hunyuanActiveJobId = job_id;

    // Poll quickly during queue/startup, then at a steady cadence.
    let pollDelay = 300;
    let consecutivePollErrors = 0;
    for (;;) {
      if (hunyuanCancelled) {
        await hunyuanCancelCurrentJob();
        hunyuanActiveJobId = null;
        return { ok: false, cancelled: true };
      }
      await new Promise((r) => setTimeout(r, pollDelay));

      let s;
      try {
        s = await hunyuanRequest({
          method: 'GET',
          pathName: `/status/${job_id}`,
          timeout: 60000,
        });
        consecutivePollErrors = 0;
      } catch (pollErr) {
        consecutivePollErrors += 1;
        console.warn(`[hunyuan] status poll exception (${consecutivePollErrors}): ${pollErr.message}`);
        // If Python backend is busy calculating dense MLX / decimation / textures, DO NOT ABORT!
        if (consecutivePollErrors < 60) {
          pollDelay = 1500;
          continue;
        }
        throw pollErr;
      }

      if (s.statusCode !== 200) {
        console.warn(`[hunyuan] status poll returned HTTP ${s.statusCode}, retrying...`);
        pollDelay = 1500;
        continue;
      }

      let js;
      try {
        js = JSON.parse(s.body);
      } catch (parseErr) {
        console.warn(`[hunyuan] status poll JSON parse error, retrying...`);
        pollDelay = 1000;
        continue;
      }

      pollDelay = js.status === 'queued' ? 300 : 750;
      event.sender.send('hunyuan:progress', {
        jobId: job_id,
        stage: js.stage || 'Procesando',
        progress: Number.isFinite(js.progress) ? js.progress : 0,
        percent: Number.isFinite(js.progress) ? js.progress : 0,
        remaining: null,
        status: js.status,
      });

      if (js.status === 'done') {
        hunyuanActiveJobId = null;
        let glbBase64 = null;
        if (js.glb_path && fs.existsSync(js.glb_path)) {
          try {
            glbBase64 = fs.readFileSync(js.glb_path).toString('base64');
          } catch (readErr) {
            console.warn('[hunyuan] Failed to read glb to base64:', readErr.message);
          }
        }
        return {
          ok: true,
          glbPath: js.glb_path,
          glbBase64,
          usdzPath: js.usdz_path || null,
          faces: js.faces,
          duration: js.elapsed,
          reportPath: js.report_path,
          qualityLevel: js.quality_level,
          qualityScore: js.quality_score,
          qualityText: js.quality_text,
          textureApplied: js.texture_applied === true,
          textureReport: js.texture_report || null,
          shapeGlbPath: js.shape_glb_path || null,
          masterGlbPath: js.master_glb_path || null,
          executionPlan: js.execution_plan || null,
          material: js.material || null,
          artDirector: js.art_director || null,
          buffaloStrategy: js.buffalo_strategy || null,
        };
      }
      if (js.status === 'error') {
        hunyuanActiveJobId = null;
        return { ok: false, error: js.error || 'Génération 3D échouée.' };
      }
      if (js.status === 'unknown') {
        consecutivePollErrors += 1;
        if (consecutivePollErrors < 10) {
          pollDelay = 1000;
          continue;
        }
        hunyuanActiveJobId = null;
        return { ok: false, error: 'Job 3D introuvable.' };
      }
      // queued / running -> keep polling
    }
  } catch (err) {
    hunyuanActiveJobId = null;
    if (err.code === 'ECONNREFUSED') {
      return {
        ok: false,
        error: `El motor 3D se detuvo durante la conversión. Log: ${HUNYUAN_LOG_FILE}${
          hunyuanLastExit ? ` (${JSON.stringify(hunyuanLastExit)})` : ''
        }`,
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

// Convert a generated GLB into a strict, RealityKit-compatible OpenUSD package.
ipcMain.handle('hunyuan:convertOpenUsd', async (_event, { glbPath }) => {
  try {
    const r = await hunyuanRequest({
      method: 'POST',
      pathName: '/to-openusd',
      timeout: 120000,
      body: { glb_path: glbPath, format: 'usdz' },
    });
    if (r.statusCode !== 200) return { ok: false, error: `HTTP ${r.statusCode}` };
    return JSON.parse(r.body);
  } catch (err) {
    if (err.code === 'ECONNREFUSED') {
      return { ok: false, error: 'El motor 3D local no está iniciado.' };
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

// --- Meshy AI Cloud API Handlers -------------------------------------------
const meshyRuntime = new MeshyRuntime(APP_SUPPORT_DIR);

ipcMain.handle('meshy:getApiKey', async () => {
  return meshyRuntime.getApiKey();
});

ipcMain.handle('meshy:saveApiKey', async (_event, apiKey) => {
  return meshyRuntime.saveApiKey(apiKey);
});

ipcMain.handle('meshy:getCredits', async (_event, apiKey) => {
  return meshyRuntime.getCredits(apiKey);
});

ipcMain.handle('meshy:generate3D', async (_event, params) => {
  return meshyRuntime.generate3D(params, (progressPayload) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('hunyuan:progress', progressPayload);
    }
  });
});

ipcMain.handle('meshy:cancel', async () => {
  meshyRuntime.cancel();
  return { ok: true };
});

let mainWindow = null;

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#020b1c',
    title: APP_NAME,
    titleBarStyle: 'default', // native macOS traffic lights
    icon: path.join(__dirname, '..', 'build', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  mainWindow = win;
  win.on('closed', () => {
    mainWindow = null;
  });

  if (isDev) {
    win.loadURL('http://localhost:5173');
  } else {
    win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }
}

app.whenReady().then(() => {
  ensureDir(APP_SUPPORT_DIR);
  getEngineToken();
  if (process.platform === 'darwin' && app.dock?.setIcon) {
    const dockIcon = path.join(__dirname, '..', 'build', 'icon.png');
    if (fs.existsSync(dockIcon)) {
      app.dock.setIcon(dockIcon);
    }
  }
  createWindow();
  // Show the UI before copying/checking the engine. The versioned async copy
  // is skipped entirely on normal launches.
  startHunyuanServer().catch((error) => {
    console.warn('[hunyuan] no se pudo preparar el motor local:', error.message);
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('second-instance', () => {
  const [win] = BrowserWindow.getAllWindows();
  if (!win) return;
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
});

// Shut the 3D server down with the app (only if we started it).
app.on('before-quit', stopHunyuanServer);
app.on('will-quit', stopHunyuanServer);

app.on('window-all-closed', () => {
  stopHunyuanServer();
  if (process.platform !== 'darwin') app.quit();
});
