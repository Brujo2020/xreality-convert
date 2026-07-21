import test from 'node:test';
import assert from 'node:assert/strict';
import { nextActionForError } from './errorActions.js';

test('nextActionForError maps service and input errors to concrete actions', () => {
  assert.match(nextActionForError('Ollama is not running'), /Comprueba servicios/);
  assert.match(nextActionForError('Selecciona una imagen de referencia.', 'image3d'), /Selecciona o arrastra/);
  assert.match(nextActionForError('espacio insuficiente'), /Libera espacio/);
});
