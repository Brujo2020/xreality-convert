import test from 'node:test';
import assert from 'node:assert/strict';
import { summarizeTools } from './toolSummary.js';

test('summarizes ready bundled and optional tools', () => {
  const summary = summarizeTools([
    { id: 'trimesh', status: 'ready', bundled: true },
    { id: 'blender', status: 'missing', bundled: false },
  ]);
  assert.deepEqual(summary, { ready: 1, bundledReady: 1, missing: 1, blocked: 0, total: 2 });
});

test('unknown status fails closed as blocked', () => {
  assert.equal(summarizeTools([{ status: 'surprise' }]).blocked, 1);
});
