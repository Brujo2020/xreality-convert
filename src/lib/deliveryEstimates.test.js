import test from 'node:test';
import assert from 'node:assert/strict';
import { estimateImage3dDelivery } from './deliveryEstimates.js';

test('estimateImage3dDelivery includes profile and texture cost', () => {
  const estimate = estimateImage3dDelivery({
    asset: { profile: 'pcvr' },
    analysis: { status: 'Óptima' },
    textureEnabled: true,
  });
  assert.equal(estimate.quality, 'Alta');
  assert.equal(estimate.minutes, 16);
  assert.equal(estimate.memoryGb, 19);
  assert.equal(estimate.textureReady, true);
});

test('estimateImage3dDelivery flags risky input quality', () => {
  const estimate = estimateImage3dDelivery({
    asset: { profile: 'mobile' },
    analysis: { status: 'No recomendada' },
    textureEnabled: false,
  });
  assert.equal(estimate.quality, 'Riesgo alto');
  assert.equal(estimate.minutes, 6);
});

test('estimateImage3dDelivery reports low poly delivery skill', () => {
  const estimate = estimateImage3dDelivery({
    asset: { profile: 'lowpoly' },
    analysis: { status: 'Óptima' },
    textureEnabled: false,
  });
  assert.equal(estimate.minutes, 5);
  assert.equal(estimate.lowPolyReady, true);
});
