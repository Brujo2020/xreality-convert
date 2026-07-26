const fs = require('node:fs');

const ALLOWED_EXECUTORS = new Set([
  'ollama.generate',
  'hunyuan.prepare',
  'hunyuan.shape',
  'hunyuan.paint',
  'engine.geometry_gate',
  'engine.delivery',
  'engine.pbr_gate',
  'engine.image_gate',
  'engine.report',
]);
const ALLOWED_MODES = new Set(['image', 'image3d', 'stl', 'texture']);
const TERMINAL_STATUSES = new Set(['done', 'failed', 'cancelled']);

function cleanText(value, fallback, max = 80) {
  const text = String(value ?? '').trim();
  return (text || fallback).slice(0, max);
}

function loadSkillCatalog(filePath) {
  const payload = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  if (payload?.schemaVersion !== 1 || !payload?.pack?.offline || !Array.isArray(payload.skills)) {
    throw new Error('El catálogo de skills locales no cumple el schema v1 offline.');
  }
  const seen = new Set();
  const skills = payload.skills.map((skill) => {
    const id = cleanText(skill?.id, '');
    const executor = cleanText(skill?.executor, '');
    if (!/^[a-z][a-z0-9_.-]{2,63}$/.test(id) || seen.has(id)) {
      throw new Error(`Skill local inválida o duplicada: ${id || '<vacía>'}.`);
    }
    if (!ALLOWED_EXECUTORS.has(executor)) {
      throw new Error(`Executor no permitido para ${id}: ${executor || '<vacío>'}.`);
    }
    seen.add(id);
    return Object.freeze({
      id,
      label: cleanText(skill.label, id),
      agent: cleanText(skill.agent, 'Agente local'),
      executor,
      resource: skill.resource === 'gpu' ? 'gpu' : 'cpu',
      description: cleanText(skill.description, '', 180),
    });
  });
  return Object.freeze({
    pack: Object.freeze({
      id: cleanText(payload.pack.id, 'local-skills'),
      label: cleanText(payload.pack.label, 'Local skills'),
      version: cleanText(payload.pack.version, '1.0.0', 24),
      offline: true,
    }),
    skills: Object.freeze(skills),
  });
}

function normalizeInput(input = {}) {
  const mode = cleanText(input.mode, '');
  if (!ALLOWED_MODES.has(mode)) throw new Error(`Modo de misión no permitido: ${mode || '<vacío>'}.`);
  return {
    mode,
    category: cleanText(input.category, 'custom', 32),
    profile: cleanText(input.profile, 'xreal', 32),
    texture: input.texture === true || mode === 'texture',
    textureSize: input.textureSize === '1K' ? '1K' : '2K',
    inputReady: input.inputReady === true,
  };
}

function task(skillId, dependencies = []) {
  return { skillId, dependencies };
}

function recipeFor(input) {
  if (input.mode === 'image') {
    return [
      task('reference.generate'),
      task('quality.image_gate', ['reference.generate']),
      task('delivery.manifest', ['quality.image_gate']),
    ];
  }
  if (input.mode === 'texture') {
    return [
      task('material.paint'),
      task('quality.pbr_gate', ['material.paint']),
      task('delivery.manifest', ['quality.pbr_gate']),
    ];
  }
  const recipe = [];
  if (input.mode === 'stl') recipe.push(task('reference.generate'));
  recipe.push(task('reference.guard', input.mode === 'stl' ? ['reference.generate'] : []));
  recipe.push(task('geometry.reconstruct', ['reference.guard']));
  recipe.push(task('geometry.audit', ['geometry.reconstruct']));
  recipe.push(task('delivery.canonicalize', ['geometry.audit']));
  if (input.texture) {
    recipe.push(task('material.paint', ['delivery.canonicalize']));
    recipe.push(task('quality.pbr_gate', ['material.paint']));
    recipe.push(task('delivery.manifest', ['quality.pbr_gate']));
  } else {
    recipe.push(task('delivery.manifest', ['delivery.canonicalize']));
  }
  return recipe;
}

function publicSnapshot(mission) {
  return JSON.parse(JSON.stringify(mission));
}

class LocalMissionOrchestrator {
  constructor({ catalog, now = () => Date.now(), idFactory } = {}) {
    if (!catalog?.pack?.offline || !Array.isArray(catalog.skills)) {
      throw new Error('Se requiere un catálogo de skills local validado.');
    }
    this.catalog = catalog;
    this.skills = new Map(catalog.skills.map((skill) => [skill.id, skill]));
    this.now = now;
    this.idFactory = idFactory || (() => `mission-${this.now()}-${Math.random().toString(16).slice(2, 10)}`);
    this.missions = new Map();
    this.activeMissionId = null;
  }

  listSkills() {
    return publicSnapshot(this.catalog);
  }

  build(input, { preview = false } = {}) {
    const normalized = normalizeInput(input);
    const recipe = recipeFor(normalized);
    const createdAt = this.now();
    const tasks = recipe.map((definition, index) => {
      const skill = this.skills.get(definition.skillId);
      if (!skill) throw new Error(`La receta requiere una skill no instalada: ${definition.skillId}.`);
      return {
        id: `${String(index + 1).padStart(2, '0')}-${skill.id}`,
        skillId: skill.id,
        label: skill.label,
        agent: skill.agent,
        executor: skill.executor,
        resource: skill.resource,
        dependencies: [...definition.dependencies],
        status: index === 0 ? 'ready' : 'blocked',
        startedAt: null,
        finishedAt: null,
      };
    });
    return {
      id: preview ? 'preview' : this.idFactory(),
      status: preview ? 'preview' : 'running',
      offline: true,
      pack: this.catalog.pack,
      input: normalized,
      createdAt,
      updatedAt: createdAt,
      activeTaskId: preview ? null : tasks[0]?.id || null,
      tasks,
    };
  }

  preview(input) {
    return publicSnapshot(this.build(input, { preview: true }));
  }

  start(input) {
    if (this.activeMissionId) {
      const active = this.missions.get(this.activeMissionId);
      if (active && !TERMINAL_STATUSES.has(active.status)) {
        throw new Error('Ya existe una misión local activa.');
      }
    }
    const mission = this.build(input);
    if (mission.tasks[0]) {
      mission.tasks[0].status = 'running';
      mission.tasks[0].startedAt = mission.createdAt;
    }
    this.missions.set(mission.id, mission);
    this.activeMissionId = mission.id;
    return publicSnapshot(mission);
  }

  get(missionId = this.activeMissionId) {
    const mission = missionId ? this.missions.get(missionId) : null;
    return mission ? publicSnapshot(mission) : null;
  }

  transition(missionId, event = {}) {
    const mission = this.missions.get(missionId);
    if (!mission || TERMINAL_STATUSES.has(mission.status)) return this.get(missionId);
    const at = this.now();
    if (event.type === 'failed' || event.type === 'cancelled') {
      const current = mission.tasks.find((item) => item.status === 'running');
      if (current) {
        current.status = event.type;
        current.finishedAt = at;
        current.error = event.type === 'failed' ? cleanText(event.error, 'Fallo local', 240) : null;
      }
      mission.status = event.type;
      mission.activeTaskId = null;
      mission.updatedAt = at;
      if (this.activeMissionId === mission.id) this.activeMissionId = null;
      return publicSnapshot(mission);
    }
    if (event.type === 'done') {
      mission.tasks.forEach((item) => {
        if (!TERMINAL_STATUSES.has(item.status)) {
          item.status = 'done';
          item.startedAt ||= at;
          item.finishedAt = at;
        }
      });
      mission.status = 'done';
      mission.activeTaskId = null;
      mission.updatedAt = at;
      if (this.activeMissionId === mission.id) this.activeMissionId = null;
      return publicSnapshot(mission);
    }
    if (event.type !== 'stage') return publicSnapshot(mission);
    const index = mission.tasks.findIndex((item) => item.skillId === event.skillId);
    if (index < 0) return publicSnapshot(mission);
    if (mission.activeTaskId === mission.tasks[index].id && mission.tasks[index].status === 'running') {
      return publicSnapshot(mission);
    }
    mission.tasks.forEach((item, itemIndex) => {
      if (itemIndex < index && !TERMINAL_STATUSES.has(item.status)) {
        item.status = 'done';
        item.startedAt ||= at;
        item.finishedAt = at;
      } else if (itemIndex === index && !TERMINAL_STATUSES.has(item.status)) {
        item.status = 'running';
        item.startedAt ||= at;
        item.finishedAt = null;
      } else if (itemIndex > index && item.status !== 'done') {
        item.status = 'blocked';
      }
    });
    mission.activeTaskId = mission.tasks[index].id;
    mission.updatedAt = at;
    return publicSnapshot(mission);
  }
}

function skillForPipelineState(state) {
  if (['preparing', 'input_saved', 'isolating', 'reference_ready'].includes(state)) return 'reference.guard';
  if (['loading', 'model_ready', 'reconstructing', 'mesh_ready'].includes(state)) return 'geometry.reconstruct';
  if (['optimizing', 'mesh_cleaned', 'quality_checked'].includes(state)) return 'geometry.audit';
  if (['mesh_simplified', 'delivery_ready', 'packaging', 'glb_exported'].includes(state)) return 'delivery.canonicalize';
  if (['paint_loading', 'texturing'].includes(state)) return 'material.paint';
  if (state === 'texture_validated') return 'quality.pbr_gate';
  if (['lods_exported', 'report_saved'].includes(state)) return 'delivery.manifest';
  return null;
}

module.exports = {
  ALLOWED_EXECUTORS,
  LocalMissionOrchestrator,
  loadSkillCatalog,
  normalizeInput,
  recipeFor,
  skillForPipelineState,
};
