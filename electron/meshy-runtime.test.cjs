const assert = require('node:assert');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const { EventEmitter } = require('node:events');
const http = require('node:http');
const https = require('node:https');
const { MeshyRuntime } = require('./meshy-runtime.cjs');

test('MeshyRuntime - initialization and API key handling', (t) => {
  const tmpDir = path.join(__dirname, '..', 'tmp', 'test-meshy-' + Date.now());
  const runtime = new MeshyRuntime(tmpDir);

  assert.strictEqual(runtime.getApiKey(), '');
  runtime.saveApiKey('msy_test_key_12345');
  assert.strictEqual(runtime.getApiKey(), 'msy_test_key_12345');

  // Clean up
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

test('MeshyRuntime - calculateCreditCost', (t) => {
  const runtime = new MeshyRuntime(__dirname);

  assert.strictEqual(runtime.calculateCreditCost({ mode: 'preview' }), 5);
  assert.strictEqual(runtime.calculateCreditCost({ mode: 'preview', ultra_mode: true }), 10);
  assert.strictEqual(runtime.calculateCreditCost({ mode: 'refine' }), 20);
  assert.strictEqual(runtime.calculateCreditCost({ mode: 'retexture', texture_resolution: '2k' }), 10);
  assert.strictEqual(runtime.calculateCreditCost({ mode: 'retexture', texture_resolution: '8k' }), 15);
});

test('MeshyRuntime - downloadFile redirect logic (mocked http/https)', async (t) => {
  const tmpDir = path.join(__dirname, '..', 'tmp', 'test-meshy-download-mock-' + Date.now());
  fs.mkdirSync(tmpDir, { recursive: true });
  const runtime = new MeshyRuntime(tmpDir);

  const origHttpGet = http.get;
  const origHttpsGet = https.get;

  const dummyGlb = Buffer.from('glTF-mock-mesh-binary-data');

  try {
    let callCount = 0;
    http.get = (url, cb) => {
      callCount++;
      const req = new EventEmitter();
      req.setTimeout = () => req;
      req.destroy = () => {};

      process.nextTick(() => {
        const urlStr = url.toString();
        if (urlStr.includes('/first')) {
          const res = new EventEmitter();
          res.statusCode = 302;
          res.headers = { location: 'http://cdn.meshy.ai/second' };
          res.resume = () => {};
          cb(res);
        } else if (urlStr.includes('/second')) {
          const res = new EventEmitter();
          res.statusCode = 200;
          res.headers = {};
          res.pipe = (destination) => {
            destination.write(dummyGlb);
            destination.end();
            process.nextTick(() => res.emit('end'));
            return destination;
          };
          cb(res);
          res.emit('data', dummyGlb);
        }
      });

      return req;
    };

    const destPath = path.join(tmpDir, 'downloaded.glb');
    const result = await runtime.downloadFile('http://api.meshy.ai/first', destPath);

    assert.strictEqual(callCount, 2);
    assert.strictEqual(result.destPath, destPath);
    assert.deepStrictEqual(result.buffer, dummyGlb);
    assert.ok(fs.existsSync(destPath));
    assert.deepStrictEqual(fs.readFileSync(destPath), dummyGlb);
  } finally {
    http.get = origHttpGet;
    https.get = origHttpsGet;
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('MeshyRuntime - generate3D validation without API key', async (t) => {
  const tmpDir = path.join(__dirname, '..', 'tmp', 'test-meshy-nokey-' + Date.now());
  const runtime = new MeshyRuntime(tmpDir);

  const res = await runtime.generate3D({ mode: 'preview' });
  assert.strictEqual(res.ok, false);
  assert.ok(res.error.includes('API Key'));

  fs.rmSync(tmpDir, { recursive: true, force: true });
});
