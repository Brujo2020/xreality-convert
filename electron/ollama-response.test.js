const test = require('node:test');
const assert = require('node:assert/strict');
const { extractGeneratedText } = require('./ollama-response');

test('extractGeneratedText reads generate and chat response shapes', () => {
  assert.equal(extractGeneratedText({ response: 'code-a' }), 'code-a');
  assert.equal(extractGeneratedText({ message: { content: 'code-b' } }), 'code-b');
});

test('extractGeneratedText only accepts thinking when it contains code', () => {
  assert.equal(extractGeneratedText({ thinking: 'Still planning.' }), '');
  assert.match(extractGeneratedText({ thinking: 'function main() {}\nmodule.exports = { main }' }), /module\.exports/);
});
