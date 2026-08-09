const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');

const {
  inspectHunyuanRuntime,
  engineProcessEnv,
  appleSiliconExecutionPlan,
} = require('./hunyuan-runtime.cjs');

function createRuntime(version = '10', revision = 'xreality-art-director-v2') {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'xreality-runtime-'));
  const files = [
    ['.installed', version],
    ['.source-version', revision],
    ['venv/bin/python', ''],
    ['server.py', ''],
    ['Hunyuan3D-2.1-mlx/hy3dshape/hy3dshape/pipeline_mlx.py', ''],
    ['Hunyuan3D-2.1-mlx/hy3dpaint/textureGenPipeline_mlx.py', ''],
    ['AgenticVibes-Hunyuan3D-Paint/hy3dpaint/mlx/hybrid_unet.py', ''],
    ['agentic_paint_service.py', ''],
    ['asset_director.py', ''],
    ['buffalo_strategy.py', ''],
    ['openusd_export.py', ''],
    ['agentic_paint_runner.py', ''],
  ];
  for (const [relativePath, contents] of files) {
    const filePath = path.join(root, relativePath);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, contents);
  }
  return root;
}

test('accepts only a complete runtime with the expected source revision', (t) => {
  const root = createRuntime();
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(inspectHunyuanRuntime(root, '10', 'xreality-art-director-v2'), {
    ready: true,
    missing: [],
  });
});

test('rejects a stale installed marker even when the bundled server is current', (t) => {
  const root = createRuntime('4');
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));

  const status = inspectHunyuanRuntime(root, '10', 'xreality-art-director-v2');
  assert.equal(status.ready, false);
  assert.deepEqual(status.missing, ['runtime_version']);
});

test('rejects old eager-loading Shape source', (t) => {
  const root = createRuntime('10', 'old-shape-source');
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));

  const status = inspectHunyuanRuntime(root, '10', 'xreality-art-director-v2');
  assert.equal(status.ready, false);
  assert.deepEqual(status.missing, ['source_revision']);
});

test('adds Homebrew Python locations for Finder-launched apps', () => {
  const env = engineProcessEnv(
    { PATH: '/usr/bin:/bin', CUSTOM_ENGINE_VALUE: 'preserved' },
    '/Users/tester'
  );

  assert.deepEqual(env.PATH.split(path.delimiter), [
    '/opt/homebrew/bin',
    '/usr/local/bin',
    '/Users/tester/.local/bin',
    '/usr/bin',
    '/bin',
  ]);
  assert.equal(env.CUSTOM_ENGINE_VALUE, 'preserved');
});

test('rejects a runtime missing the deterministic art director', (t) => {
  const root = createRuntime();
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.unlinkSync(path.join(root, 'asset_director.py'));

  const status = inspectHunyuanRuntime(root, '10', 'xreality-art-director-v2');

  assert.equal(status.ready, false);
  assert.deepEqual(status.missing, ['asset_director']);
});

test('rejects a runtime missing the Buffalo MLX strategy contract', (t) => {
  const root = createRuntime();
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.unlinkSync(path.join(root, 'buffalo_strategy.py'));

  const status = inspectHunyuanRuntime(root, '10', 'xreality-art-director-v2');

  assert.equal(status.ready, false);
  assert.deepEqual(status.missing, ['buffalo_strategy']);
});

test('rejects a runtime missing the OpenUSD delivery gate', (t) => {
  const root = createRuntime();
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.unlinkSync(path.join(root, 'openusd_export.py'));

  const status = inspectHunyuanRuntime(root, '10', 'xreality-art-director-v2');

  assert.equal(status.ready, false);
  assert.deepEqual(status.missing, ['openusd_export']);
});

test('scales bounded CPU work without overlapping Metal stages', () => {
  assert.deepEqual(
    appleSiliconExecutionPlan({ logicalCores: 8, totalMemoryBytes: 16 * 1024 ** 3 }),
    { mathThreads: 4, validationWorkers: 2, cacheMiB: 256, scheduling: 'metal-sequential-cpu-bounded' }
  );
  assert.deepEqual(
    appleSiliconExecutionPlan({ logicalCores: 16, totalMemoryBytes: 64 * 1024 ** 3 }),
    { mathThreads: 8, validationWorkers: 4, cacheMiB: 1024, scheduling: 'metal-sequential-cpu-bounded' }
  );
});

test('keeps Electron, setup and server engine versions aligned', () => {
  const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
  const setup = fs.readFileSync(path.join(__dirname, '..', 'engine', 'setup.sh'), 'utf8');
  const server = fs.readFileSync(path.join(__dirname, '..', 'engine', 'server.py'), 'utf8');
  const electronVersion = main.match(/HUNYUAN_INSTALL_VERSION = '([^']+)'/)[1];
  const setupVersion = setup.match(/INSTALL_VERSION="([^"]+)"/)[1];
  const serverVersion = server.match(/ENGINE_VERSION = "([^"]+)"/)[1];
  const electronRevision = main.match(/HUNYUAN_SOURCE_REVISION = '([^']+)'/)[1];
  const setupRevision = setup.match(/SOURCE_REVISION="([^"]+)"/)[1];

  assert.equal(electronVersion, setupVersion);
  assert.equal(electronVersion, serverVersion);
  assert.equal(electronRevision, setupRevision);
});

test('singleflights engine startup and self-recovers before generation', () => {
  const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');

  assert.match(main, /let hunyuanServerStartPromise = null/);
  assert.match(main, /function startHunyuanServer\(\)/);
  assert.match(main, /async function ensureHunyuanServerReady\(\)/);
  assert.match(main, /if \(!\(await ensureHunyuanServerReady\(\)\)\)/);
  assert.match(main, /hunyuanServerProc\.exitCode === null/);
  assert.match(main, /return \{ started: false, starting: true \}/);
  assert.match(main, /ipcMain\.handle\('hunyuan:convertOpenUsd'/);
  assert.match(main, /pathName: '\/to-openusd'/);
});

test('renderer submits requested steps before reading the engine response', () => {
  const appSource = fs.readFileSync(path.join(__dirname, '..', 'src', 'App.jsx'), 'utf8');
  const request = appSource.match(/window\.hunyuan\.generate3D\(\{([\s\S]*?)\}\);/);

  assert.ok(request, 'generate3D request block should exist');
  assert.match(request[1], /steps: steps3d/);
  assert.doesNotMatch(request[1], /res\.executionPlan/);
  assert.match(appSource, /steps: res\.executionPlan\?\.steps \?\? steps3d/);
});
