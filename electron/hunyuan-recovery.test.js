const test = require('node:test');
const assert = require('node:assert/strict');

const { recovered3DFromReport } = require('./hunyuan-recovery');

test('completed report becomes a recoverable gallery asset', () => {
  const report = {
    job_id: 'a'.repeat(32),
    created_at: 123.5,
    elapsed: 45,
    input: { category: 'animal', profile: 'xreal', steps: 50 },
    metrics: { faces: 100000, score: 70, level: 'atencion', reasons: ['Revisar malla.'] },
    texture: { requested: true, applied: true, profile: '2K', gate: { passed: true } },
  };
  const recovered = recovered3DFromReport(report, '/engine', (file) => file.endsWith('.glb'));

  assert.equal(recovered.glbPath, `/engine/jobs/${'a'.repeat(32)}.glb`);
  assert.equal(recovered.textureApplied, true);
  assert.equal(recovered.qualityText, 'Revisar malla.');
  assert.equal(recovered.createdAt, 123500);
});

test('invalid or missing artifacts are not recovered', () => {
  assert.equal(recovered3DFromReport({ job_id: '../escape' }, '/engine', () => true), null);
  assert.equal(recovered3DFromReport({ job_id: 'b'.repeat(32) }, '/engine', () => false), null);
});
