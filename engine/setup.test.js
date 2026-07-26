import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const engineDir = path.dirname(fileURLToPath(import.meta.url));
const appDir = path.dirname(engineDir);

test('preflight finds a supported user-local Python with Finder PATH', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'ois-python-home-'));
  try {
    const python = path.join(home, '.local', 'bin', 'python3.11');
    fs.mkdirSync(path.dirname(python), { recursive: true });
    fs.writeFileSync(python, '#!/bin/sh\nexit 0\n', { mode: 0o755 });

    const result = spawnSync('/bin/zsh', [path.join(engineDir, 'setup.sh'), '--preflight'], {
      encoding: 'utf8',
      env: { HOME: home, PATH: '/usr/bin:/bin:/usr/sbin:/sbin' },
    });

    assert.equal(result.status, 0, result.stderr || result.stdout);
    assert.equal(result.stdout.trim(), python);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test('packaged app includes Hunyuan Paint runtime files', () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(appDir, 'package.json'), 'utf8'));
  const paintRuntime = 'engine/Hunyuan3D-2.1-mlx/hy3dpaint/**/*';
  const generationPolicy = 'engine/generation_policy.py';
  const materialPolicy = 'engine/material_policy.py';
  const textureQuality = 'engine/texture_quality.py';

  assert.ok(pkg.build.files.includes(paintRuntime));
  assert.ok(pkg.build.asarUnpack.includes(paintRuntime));
  assert.ok(pkg.build.files.includes(generationPolicy));
  assert.ok(pkg.build.asarUnpack.includes(generationPolicy));
  assert.ok(pkg.build.files.includes(materialPolicy));
  assert.ok(pkg.build.asarUnpack.includes(materialPolicy));
  assert.ok(pkg.build.files.includes(textureQuality));
  assert.ok(pkg.build.asarUnpack.includes(textureQuality));
});

test('engine updater copies every local server module', () => {
  const main = fs.readFileSync(path.join(appDir, 'electron', 'main.js'), 'utf8');
  assert.match(main, /'generation_policy\.py'/);
  assert.match(main, /'material_policy\.py'/);
  assert.match(main, /'texture_quality\.py'/);
});

test('renderer CSP permits blob URLs used by GLTFLoader embedded textures', () => {
  const html = fs.readFileSync(path.join(appDir, 'index.html'), 'utf8');
  assert.match(html, /img-src[^;]*blob:/);
});
