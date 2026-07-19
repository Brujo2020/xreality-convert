import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const engineDir = path.dirname(fileURLToPath(import.meta.url));

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
