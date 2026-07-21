const test = require('node:test');
const assert = require('node:assert/strict');
const { loadedGenerativeModelIds, parseModelKey, rankOmlxModels, toOmlxModelKey } = require('./model-routing');

test('model keys preserve provider and model id', () => {
  assert.deepEqual(parseModelKey(toOmlxModelKey('coder:4bit')), { provider: 'omlx', id: 'coder:4bit' });
  assert.deepEqual(parseModelKey('gemma4:12b'), { provider: 'ollama', id: 'gemma4:12b' });
});

test('oMLX ranking excludes non-generative and short-output models', () => {
  const ranked = rankOmlxModels([
    { id: 'embed', model_type: 'embedding', max_tokens: 8192, loaded: true },
    { id: 'qwen3-4b', model_type: 'llm', max_tokens: 256, loaded: true },
    { id: 'general-8b', model_type: 'llm', max_tokens: 4096, loaded: true },
    { id: 'gemma-coder-12b', model_type: 'vlm', max_tokens: 4096, loaded: false },
  ]);
  assert.deepEqual(ranked, [toOmlxModelKey('gemma-coder-12b'), toOmlxModelKey('general-8b')]);
});

test('loadedGenerativeModelIds excludes pinned helper models', () => {
  assert.deepEqual(loadedGenerativeModelIds([
    { id: 'coder', model_type: 'llm', loaded: true },
    { id: 'embed', model_type: 'embedding', loaded: true, pinned: true },
    { id: 'idle-vlm', model_type: 'vlm', loaded: false },
  ]), ['coder']);
});
