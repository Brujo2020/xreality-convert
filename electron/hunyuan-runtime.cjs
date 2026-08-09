const fs = require('node:fs');
const path = require('node:path');

function readMarker(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8').trim();
  } catch {
    return '';
  }
}

function inspectHunyuanRuntime(engineDir, installVersion, sourceRevision) {
  const checks = [
    [readMarker(path.join(engineDir, '.installed')) === installVersion, 'runtime_version'],
    [readMarker(path.join(engineDir, '.source-version')) === sourceRevision, 'source_revision'],
    [fs.existsSync(path.join(engineDir, 'venv', 'bin', 'python')), 'python_runtime'],
    [fs.existsSync(path.join(engineDir, 'server.py')), 'server'],
    [
      fs.existsSync(
        path.join(engineDir, 'Hunyuan3D-2.1-mlx', 'hy3dshape', 'hy3dshape', 'pipeline_mlx.py')
      ),
      'shape_source',
    ],
    [
      fs.existsSync(
        path.join(engineDir, 'Hunyuan3D-2.1-mlx', 'hy3dpaint', 'textureGenPipeline_mlx.py')
      ),
      'paint_source',
    ],
    [
      fs.existsSync(
        path.join(engineDir, 'AgenticVibes-Hunyuan3D-Paint', 'hy3dpaint', 'mlx', 'hybrid_unet.py')
      ),
      'agentic_paint_source',
    ],
    [fs.existsSync(path.join(engineDir, 'agentic_paint_service.py')), 'agentic_paint_service'],
    [fs.existsSync(path.join(engineDir, 'asset_director.py')), 'asset_director'],
    [fs.existsSync(path.join(engineDir, 'buffalo_strategy.py')), 'buffalo_strategy'],
    [fs.existsSync(path.join(engineDir, 'openusd_export.py')), 'openusd_export'],
    [fs.existsSync(path.join(engineDir, 'agentic_paint_runner.py')), 'agentic_paint_runner'],
  ];
  const missing = checks.filter(([passed]) => !passed).map(([, name]) => name);
  return { ready: missing.length === 0, missing };
}

function engineProcessEnv(baseEnv = process.env, homeDir = '') {
  const additions = [
    '/opt/homebrew/bin',
    '/usr/local/bin',
    homeDir ? path.join(homeDir, '.local', 'bin') : '',
  ].filter(Boolean);
  const pathEntries = String(baseEnv.PATH || '')
    .split(path.delimiter)
    .filter(Boolean);
  const mergedPath = [...new Set([...additions, ...pathEntries])].join(path.delimiter);
  return { ...baseEnv, PATH: mergedPath };
}

function appleSiliconExecutionPlan({ logicalCores, totalMemoryBytes }) {
  const cores = Math.max(1, Number(logicalCores) || 1);
  const memoryGiB = Math.max(1, Number(totalMemoryBytes) || 0) / (1024 ** 3);
  // Keep Metal inference exclusive. These workers are only for bounded CPU
  // preparation, BLAS geometry work, hashing and evidence-file output.
  const mathThreads = Math.max(2, Math.min(memoryGiB <= 16 ? 4 : 8, Math.ceil(cores / 2)));
  const validationWorkers = Math.max(1, Math.min(memoryGiB <= 16 ? 2 : 4, Math.floor(cores / 3)));
  const cacheMiB = memoryGiB <= 16 ? 256 : memoryGiB <= 32 ? 512 : 1024;
  return {
    mathThreads,
    validationWorkers,
    cacheMiB,
    scheduling: 'metal-sequential-cpu-bounded',
  };
}

module.exports = { inspectHunyuanRuntime, engineProcessEnv, appleSiliconExecutionPlan };
