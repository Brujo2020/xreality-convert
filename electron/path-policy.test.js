const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { resolveWithinRoots, safeOutputFilename } = require('./path-policy');

test('path policy accepts descendants and rejects traversal or sibling prefixes', () => {
  const root = path.join(path.sep, 'safe', 'jobs');
  assert.equal(resolveWithinRoots(path.join(root, 'asset.glb'), [root]), path.join(root, 'asset.glb'));
  assert.equal(resolveWithinRoots(path.join(root, '..', 'secret.txt'), [root]), null);
  assert.equal(resolveWithinRoots(`${root}-evil/asset.glb`, [root]), null);
});

test('output filenames reject paths, unsafe text, and wrong extensions', () => {
  assert.equal(safeOutputFilename('asset-final.glb', ['.glb']), 'asset-final.glb');
  assert.equal(safeOutputFilename('../asset.glb', ['.glb']), null);
  assert.equal(safeOutputFilename('asset.png', ['.glb']), null);
  assert.equal(safeOutputFilename('asset name.glb', ['.glb']), null);
});
