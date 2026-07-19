const test = require('node:test');
const assert = require('node:assert/strict');
const { createToolRegistry, redactProbeResult } = require('./tool-registry');

test('registry returns closed public descriptors without executable paths', async () => {
  const registry = createToolRegistry({
    enginePython: '/private/runtime/python',
    now: () => 1000,
    probe: async ({ id }) => id === 'trimesh'
      ? { ok: true, version: '4.7.1', executablePath: '/private/runtime/python' }
      : { ok: false, reason: 'not_found' },
  });
  const result = await registry.list();
  assert.equal(result.tools.find((tool) => tool.id === 'trimesh').status, 'ready');
  assert.equal(JSON.stringify(result).includes('/private/runtime'), false);
});

test('registry caches probes until forced', async () => {
  let calls = 0;
  const registry = createToolRegistry({
    enginePython: '/runtime/python',
    now: () => 1000,
    probe: async () => { calls += 1; return { ok: false, reason: 'not_found' }; },
  });
  await registry.list();
  await registry.list();
  assert.equal(calls, 8);
  await registry.list({ force: true });
  assert.equal(calls, 16);
});

test('probe errors are normalized and bounded', () => {
  const result = redactProbeResult({ ok: false, reason: 'spawn_error', detail: 'x'.repeat(9000) });
  assert.equal(result.reason, 'probe_failed');
  assert.equal('detail' in result, false);
});
