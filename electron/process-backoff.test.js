const test = require('node:test');
const assert = require('node:assert/strict');
const { nextRestartDelayMs } = require('./process-backoff');

test('restart backoff doubles until the configured cap', () => {
  const options = { baseMs: 100, maxMs: 500 };
  assert.equal(nextRestartDelayMs(1, options), 100);
  assert.equal(nextRestartDelayMs(2, options), 200);
  assert.equal(nextRestartDelayMs(3, options), 400);
  assert.equal(nextRestartDelayMs(4, options), 500);
  assert.equal(nextRestartDelayMs(99, options), 500);
});

test('restart backoff normalizes invalid attempts', () => {
  assert.equal(nextRestartDelayMs(0, { baseMs: 100, maxMs: 500 }), 100);
  assert.equal(nextRestartDelayMs(Number.NaN, { baseMs: 100, maxMs: 500 }), 100);
});
