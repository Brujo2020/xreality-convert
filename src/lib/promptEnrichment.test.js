import test from 'node:test';
import assert from 'node:assert/strict';
import { enrichImagePrompt } from './promptEnrichment.js';

test('enrichImagePrompt preserves user prompt and adds category guidance', () => {
  const prompt = enrichImagePrompt('robot toy', 'product');
  assert.match(prompt, /^robot toy\./);
  assert.match(prompt, /single product/);
  assert.match(prompt, /sharp edges/);
});

test('enrichImagePrompt falls back to custom guidance', () => {
  const prompt = enrichImagePrompt('strange object', 'unknown');
  assert.match(prompt, /single complete subject/);
});
