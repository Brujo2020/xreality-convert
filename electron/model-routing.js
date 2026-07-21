const OMLX_PREFIX = 'oMLX · ';

function toOmlxModelKey(id) {
  return `${OMLX_PREFIX}${id}`;
}

function parseModelKey(value) {
  if (typeof value === 'string' && value.startsWith(OMLX_PREFIX)) {
    return { provider: 'omlx', id: value.slice(OMLX_PREFIX.length) };
  }
  return { provider: 'ollama', id: value };
}

function omlxModelScore(model) {
  const id = String(model.id || '').toLowerCase();
  let score = 0;
  if (/coder/.test(id)) score += 100;
  if (/qwen3.*coder/.test(id)) score += 30;
  if (/devstral/.test(id)) score += 25;
  if (/gemma.*coder/.test(id)) score += 22;
  if (/qwen3\.5/.test(id)) score += 18;
  if (/gpt-oss/.test(id)) score += 16;
  if (/qwen3-8b/.test(id)) score += 12;
  if (model.loaded) score += 5;
  score += Math.min(Number(model.max_tokens) || 0, 8192) / 8192;
  return score;
}

function rankOmlxModels(models) {
  return (Array.isArray(models) ? models : [])
    .filter((model) => ['llm', 'vlm'].includes(model.model_type))
    .filter((model) => (Number(model.max_tokens) || 0) >= 1024)
    .filter((model) => typeof model.id === 'string' && model.id.length > 0)
    .sort((a, b) => omlxModelScore(b) - omlxModelScore(a))
    .map((model) => toOmlxModelKey(model.id));
}

function loadedGenerativeModelIds(models) {
  return (Array.isArray(models) ? models : [])
    .filter((model) => model.loaded && ['llm', 'vlm'].includes(model.model_type))
    .map((model) => model.id)
    .filter(Boolean);
}

module.exports = { OMLX_PREFIX, loadedGenerativeModelIds, parseModelKey, rankOmlxModels, toOmlxModelKey };
