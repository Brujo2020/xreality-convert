const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

test('renderer cannot invoke the legacy model-generated JSCAD executor', () => {
  const preload = fs.readFileSync(path.join(__dirname, 'preload.js'), 'utf8');
  assert.doesNotMatch(preload, /generateStl\s*:/);
  assert.doesNotMatch(preload, /invoke\(['"]ollama:generateStl/);
});

test('main process keeps legacy JSCAD execution hard-disabled', () => {
  const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
  assert.match(main, /const LEGACY_JSCAD_EXECUTION_ENABLED = false;/);
  const handler = main.slice(main.indexOf("ipcMain.handle('ollama:generateStl'"));
  assert.ok(
    handler.indexOf('if (!LEGACY_JSCAD_EXECUTION_ENABLED)') < handler.indexOf('activeController = new AbortController()')
  );
});
