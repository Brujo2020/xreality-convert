const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const {
  ALLOWED_EXECUTORS,
  LocalMissionOrchestrator,
  loadSkillCatalog,
  skillForPipelineState,
} = require('./local-orchestrator');

const catalog = loadSkillCatalog(path.join(__dirname, '..', 'skills', 'xreality-core.json'));

function orchestrator() {
  let clock = 1_000;
  return new LocalMissionOrchestrator({
    catalog,
    now: () => ++clock,
    idFactory: () => 'mission-test',
  });
}

test('skill catalog is offline and every executor is allowlisted', () => {
  assert.equal(catalog.pack.offline, true);
  assert.equal(catalog.skills.length, 9);
  for (const skill of catalog.skills) {
    assert.ok(ALLOWED_EXECUTORS.has(skill.executor));
    assert.doesNotMatch(`${skill.id} ${skill.description}`, /https?:|shell|spawn|child_process/i);
  }
});

test('packaged Electron app includes the file-backed skill catalog', () => {
  const packageJson = JSON.parse(
    require('node:fs').readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8')
  );
  assert.ok(packageJson.build.files.includes('skills/**/*'));
  assert.match(packageJson.scripts['test:tools'], /electron\/local-orchestrator\.test\.js/);
});

test('text to 3D mission builds a dependency-ordered specialist DAG', () => {
  const mission = orchestrator().preview({
    mode: 'stl',
    category: 'industrial',
    profile: 'xreal',
    texture: true,
    textureSize: '2K',
    inputReady: true,
  });
  assert.equal(mission.offline, true);
  assert.deepEqual(
    mission.tasks.map((item) => item.skillId),
    [
      'reference.generate',
      'reference.guard',
      'geometry.reconstruct',
      'geometry.audit',
      'delivery.canonicalize',
      'material.paint',
      'quality.pbr_gate',
      'delivery.manifest',
    ]
  );
  assert.deepEqual(mission.tasks[1].dependencies, ['reference.generate']);
  assert.deepEqual(mission.tasks.at(-1).dependencies, ['quality.pbr_gate']);
});

test('pipeline events advance the actual agent and never regress completed work', () => {
  const local = orchestrator();
  local.start({ mode: 'image3d', texture: true });
  let mission = local.transition('mission-test', {
    type: 'stage',
    skillId: skillForPipelineState('reconstructing'),
  });
  assert.equal(mission.tasks[0].status, 'done');
  assert.equal(mission.tasks[1].skillId, 'geometry.reconstruct');
  assert.equal(mission.tasks[1].status, 'running');

  mission = local.transition('mission-test', {
    type: 'stage',
    skillId: skillForPipelineState('texture_validated'),
  });
  assert.equal(mission.tasks.find((item) => item.skillId === 'geometry.reconstruct').status, 'done');
  assert.equal(mission.tasks.find((item) => item.skillId === 'quality.pbr_gate').status, 'running');
});

test('repeated backend polls for the same skill are idempotent', () => {
  const local = orchestrator();
  local.start({ mode: 'image3d', texture: false });
  const first = local.transition('mission-test', {
    type: 'stage',
    skillId: 'geometry.reconstruct',
  });
  const repeated = local.transition('mission-test', {
    type: 'stage',
    skillId: 'geometry.reconstruct',
  });
  assert.equal(repeated.updatedAt, first.updatedAt);
  assert.deepEqual(repeated.tasks, first.tasks);
});

test('failure is terminal and records the bounded local error', () => {
  const local = orchestrator();
  local.start({ mode: 'image' });
  const failed = local.transition('mission-test', {
    type: 'failed',
    error: 'local model failed',
  });
  assert.equal(failed.status, 'failed');
  assert.equal(failed.tasks[0].status, 'failed');
  assert.equal(local.activeMissionId, null);

  const unchanged = local.transition('mission-test', { type: 'done' });
  assert.equal(unchanged.status, 'failed');
});

test('unknown mission modes are rejected', () => {
  assert.throws(() => orchestrator().preview({ mode: 'remote-agent' }), /no permitido/);
});
