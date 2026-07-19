const test = require('node:test');
const assert = require('node:assert/strict');
const { createToolRegistry, discoverLocalTools, redactProbeResult, resolveBinary } = require('./tool-registry');

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
  for (const tool of result.tools) {
    for (const field of ['path', 'command', 'stdout', 'stderr', 'env', 'environment']) {
      assert.equal(field in tool, false, `${tool.id} exposes ${field}`);
    }
  }
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
  await registry.list({ force: 'true' });
  await registry.list({ force: 1 });
  assert.equal(calls, 8);
  await registry.list({ force: true });
  assert.equal(calls, 16);
});

test('probe errors are normalized and bounded', () => {
  const result = redactProbeResult({ ok: false, reason: 'spawn_error', detail: 'x'.repeat(9000) });
  assert.equal(result.reason, 'probe_failed');
  assert.equal('detail' in result, false);
});

test('official executable aliases are ordered by tool preference', async () => {
  const definitions = new Map();
  await discoverLocalTools({
    probe: async (tool) => {
      definitions.set(tool.id, tool.executableNames);
      return { ok: false, reason: 'not_found' };
    },
  });

  assert.deepEqual(definitions.get('gltf_validator'), ['gltf_validator']);
  assert.deepEqual(definitions.get('ktx'), ['ktx', 'toktx']);

  const resolved = resolveBinary(
    { executableNames: definitions.get('ktx') },
    {
      pathEnv: ['/early', '/preferred'].join(require('node:path').delimiter),
      existsSync: (candidate) => candidate === '/early/toktx' || candidate === '/preferred/ktx',
    }
  );
  assert.equal(resolved, '/preferred/ktx');
});

test('public snapshot extracts only a bounded version token from probe output', async () => {
  const secret = 'sk_live_super_secret';
  const privatePath = '/Users/alice/.ssh/id_ed25519';
  const registry = createToolRegistry({
    now: () => 1000,
    probe: async ({ id }) => id === 'blender'
      ? { ok: true, version: `Blender 4.3.2 ${secret} ${privatePath}` }
      : id === 'gltf-transform'
        ? { ok: true, version: `${secret}:${privatePath}` }
        : { ok: false, reason: 'not_found' },
  });

  const result = await registry.list();
  const blender = result.tools.find((tool) => tool.id === 'blender');
  const gltfTransform = result.tools.find((tool) => tool.id === 'gltf-transform');
  const snapshot = JSON.stringify(result);

  assert.equal(blender.status, 'ready');
  assert.equal(blender.version, '4.3.2');
  assert.deepEqual(gltfTransform, {
    id: 'gltf-transform',
    label: 'glTF-Transform',
    category: 'interchange',
    status: 'ready',
    capabilities: ['optimize_gltf', 'convert_gltf'],
    bundled: false,
    installHint: 'Install glTF-Transform to enable optional conversions.',
  });
  assert.equal(snapshot.includes(secret), false);
  assert.equal(snapshot.includes(privatePath), false);
});
