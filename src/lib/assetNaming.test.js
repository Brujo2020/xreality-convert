import test from 'node:test';
import assert from 'node:assert/strict';
import { assetFilename, buildAssetName, sanitizeAssetName } from './assetNaming.js';

test('sanitizeAssetName creates filesystem-safe ascii names', () => {
  assert.equal(sanitizeAssetName('Máquina Núm. 42 / Planta A.glb'), 'maquina-num-42-planta-a-glb');
});

test('buildAssetName includes source, category, profile and date', () => {
  assert.equal(
    buildAssetName({
      sourceName: 'Bomba hidráulica.png',
      category: 'industrial',
      profile: 'xreal',
      createdAt: new Date('2026-07-20T12:00:00Z').getTime(),
    }),
    'bomba-hidraulica-industrial-xreal-20260720'
  );
});

test('assetFilename applies the final extension', () => {
  assert.equal(assetFilename('Mi Activo XR', '.glb'), 'mi-activo-xr.glb');
});
