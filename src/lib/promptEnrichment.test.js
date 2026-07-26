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

test('enrichImagePrompt keeps animal references photorealistic instead of silhouette-like', () => {
  const prompt = enrichImagePrompt('perro salchicha', 'animal');
  assert.match(prompt, /photorealistic full body animal/);
  assert.match(prompt, /natural fur colors and texture/);
  assert.doesNotMatch(prompt, /silhouette/i);
});

test('enrichImagePrompt enforces photographic output for every category', () => {
  for (const category of ['animal', 'person', 'product', 'industrial', 'architecture', 'custom']) {
    const prompt = enrichImagePrompt('subject', category);
    assert.match(prompt, /photorealistic/i);
    assert.match(prompt, /real-world photography only/i);
    assert.match(prompt, /exclude illustration, drawing, sketch/i);
  }
});

test('enrichImagePrompt applies custom photographic controls', () => {
  const prompt = enrichImagePrompt('motor', 'industrial', {
    lighting: 'natural',
    view: 'orthographic',
    background: 'contextual',
    customInstructions: 'brushed steel with visible wear',
  });
  assert.match(prompt, /natural daylight/);
  assert.match(prompt, /orthographic product photography/);
  assert.match(prompt, /realistic but uncluttered real-world context/);
  assert.match(prompt, /brushed steel with visible wear/);
});
