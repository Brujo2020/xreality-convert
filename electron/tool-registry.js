const { spawn: nodeSpawn } = require('node:child_process');
const { existsSync: nodeExistsSync } = require('node:fs');
const path = require('node:path');

const CACHE_MS = 30_000;
const PROBE_TIMEOUT_MS = 2_000;
const MAX_PROBE_BYTES = 8_192;

const TOOL_DEFINITIONS = Object.freeze([
  Object.freeze({
    id: 'trimesh', label: 'Trimesh', category: 'geometry', bundled: true,
    packageName: 'trimesh', capabilities: Object.freeze(['inspect_mesh', 'repair_basic', 'convert_stl']),
  }),
  Object.freeze({
    id: 'pymeshlab', label: 'PyMeshLab', category: 'geometry', bundled: true,
    packageName: 'pymeshlab', capabilities: Object.freeze(['inspect_mesh', 'repair_advanced', 'simplify_mesh']),
  }),
  Object.freeze({
    id: 'xatlas', label: 'xatlas', category: 'uv', bundled: true,
    packageName: 'xatlas', capabilities: Object.freeze(['unwrap_uv']),
  }),
  Object.freeze({
    id: 'pygltflib', label: 'pygltflib', category: 'interchange', bundled: true,
    packageName: 'pygltflib', capabilities: Object.freeze(['inspect_gltf', 'edit_gltf']),
  }),
  Object.freeze({
    id: 'gltf_validator', label: 'glTF Validator', category: 'validation', bundled: false,
    executableNames: Object.freeze(['gltf-validator']), capabilities: Object.freeze(['validate_gltf']),
    installHint: 'Install Khronos glTF Validator to enable validation.',
  }),
  Object.freeze({
    id: 'gltf-transform', label: 'glTF-Transform', category: 'interchange', bundled: false,
    executableNames: Object.freeze(['gltf-transform']), capabilities: Object.freeze(['optimize_gltf', 'convert_gltf']),
    installHint: 'Install glTF-Transform to enable optional conversions.',
  }),
  Object.freeze({
    id: 'ktx', label: 'KTX-Software', category: 'texture', bundled: false,
    executableNames: Object.freeze(['toktx']), capabilities: Object.freeze(['encode_ktx2']),
    installHint: 'Install KTX-Software to enable KTX2 encoding.',
  }),
  Object.freeze({
    id: 'blender', label: 'Blender', category: 'authoring', bundled: false,
    executableNames: Object.freeze(['blender']),
    macOSCandidates: Object.freeze(['/Applications/Blender.app/Contents/MacOS/Blender']),
    capabilities: Object.freeze(['inspect_scene', 'convert_scene']),
    installHint: 'Install Blender to enable optional scene conversion.',
  }),
]);

function redactProbeResult(result) {
  if (!result || result.ok !== true) {
    return { ok: false, reason: result?.reason === 'not_found' ? 'not_found' : 'probe_failed' };
  }
  const version = typeof result.version === 'string' ? result.version.trim().slice(0, 256) : '';
  return version ? { ok: true, version } : { ok: true };
}

function resolveBinary(tool, { pathEnv, existsSync }) {
  const candidates = [];
  for (const directory of (pathEnv || '').split(path.delimiter)) {
    if (!directory) continue;
    for (const executableName of tool.executableNames) candidates.push(path.join(directory, executableName));
  }
  if (process.platform === 'darwin') candidates.push(...(tool.macOSCandidates || []));
  return candidates.find((candidate) => existsSync(candidate)) || null;
}

function collectProcessOutput(executable, args, { spawn, timeoutMs = PROBE_TIMEOUT_MS }) {
  return new Promise((resolve) => {
    let child;
    try {
      child = spawn(executable, args, { shell: false, stdio: ['ignore', 'pipe', 'pipe'] });
    } catch {
      resolve({ ok: false, reason: 'spawn_error' });
      return;
    }

    let output = Buffer.alloc(0);
    let settled = false;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(result);
    };
    const append = (chunk) => {
      if (output.length >= MAX_PROBE_BYTES) return;
      output = Buffer.concat([output, Buffer.from(chunk)]).subarray(0, MAX_PROBE_BYTES);
    };
    const timer = setTimeout(() => {
      child.kill();
      finish({ ok: false, reason: 'timeout' });
    }, timeoutMs);

    child.stdout?.on('data', append);
    child.stderr?.on('data', append);
    child.on('error', () => finish({ ok: false, reason: 'spawn_error' }));
    child.on('close', (code) => {
      if (code !== 0) return finish({ ok: false, reason: 'probe_error' });
      const version = output.toString('utf8').trim().split(/\r?\n/)[0];
      finish({ ok: true, version });
    });
  });
}

async function probeTool(tool, options) {
  const { enginePython, pathEnv, spawn = nodeSpawn, existsSync = nodeExistsSync } = options;
  if (tool.bundled) {
    if (typeof enginePython !== 'string' || !enginePython) return { ok: false, reason: 'not_found' };
    const script = `import importlib.metadata; print(importlib.metadata.version(${JSON.stringify(tool.packageName)}))`;
    return collectProcessOutput(enginePython, ['-c', script], { spawn });
  }
  const executable = resolveBinary(tool, { pathEnv: pathEnv ?? process.env.PATH, existsSync });
  if (!executable) return { ok: false, reason: 'not_found' };
  return collectProcessOutput(executable, ['--version'], { spawn });
}

function toPublicTool(tool, rawResult) {
  const result = redactProbeResult(rawResult);
  const status = result.ok ? 'ready' : result.reason === 'not_found' ? 'missing' : 'blocked';
  return {
    id: tool.id,
    label: tool.label,
    category: tool.category,
    status,
    ...(result.version ? { version: result.version } : {}),
    capabilities: [...tool.capabilities],
    bundled: tool.bundled,
    installHint: tool.bundled ? null : tool.installHint,
  };
}

async function discoverLocalTools(options = {}) {
  const { now = Date.now, probe = (tool) => probeTool(tool, options) } = options;
  const rawResults = await Promise.all(TOOL_DEFINITIONS.map((tool) => probe(tool)));
  return {
    checkedAt: now(),
    tools: TOOL_DEFINITIONS.map((tool, index) => toPublicTool(tool, rawResults[index])),
  };
}

function createToolRegistry(options = {}) {
  let cached = null;
  let checkedAt = 0;
  const now = options.now || Date.now;
  return {
    async list({ force = false } = {}) {
      if (!force && cached && now() - checkedAt < CACHE_MS) return cached;
      cached = await discoverLocalTools({ ...options, now });
      checkedAt = now();
      return cached;
    },
  };
}

module.exports = { createToolRegistry, discoverLocalTools, redactProbeResult };
