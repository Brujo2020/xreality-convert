import test from 'node:test';
import assert from 'node:assert/strict';
import { applyLowPolySkill, restoreCategoryDelivery } from './lowPolySkill.js';

test('applyLowPolySkill keeps lightweight geometry with close-up texture quality', () => {
  const asset = applyLowPolySkill({ profile: 'xreal', texture: true, textureSize: '2K', targetFaces: 100000 });
  assert.equal(asset.profile, 'lowpoly');
  assert.equal(asset.octree, 192);
  assert.equal(asset.targetFaces, 12000);
  assert.equal(asset.textureSize, '2K');
});

test('restoreCategoryDelivery returns category delivery while preserving texture intent', () => {
  const asset = restoreCategoryDelivery('industrial', { profile: 'lowpoly', texture: true, textureSize: '1K' });
  assert.equal(asset.profile, 'xreal');
  assert.equal(asset.targetFaces, 100000);
  assert.equal(asset.texture, true);
  assert.equal(asset.textureSize, '2K');
});
