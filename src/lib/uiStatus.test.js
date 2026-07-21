import test from 'node:test';
import assert from 'node:assert/strict';
import { getAuditSemaphore, getControlStatus } from './uiStatus.js';

test('getControlStatus distinguishes recommended, modified and out of range', () => {
  assert.equal(getControlStatus(40, 40, { min: 10, max: 60 }), 'recommended');
  assert.equal(getControlStatus(45, 40, { min: 10, max: 60 }), 'modified');
  assert.equal(getControlStatus(80, 40, { min: 10, max: 60 }), 'out');
});

test('getAuditSemaphore maps audit levels to visual lights', () => {
  assert.equal(getAuditSemaphore('listo'), 'green');
  assert.equal(getAuditSemaphore('atencion'), 'amber');
  assert.equal(getAuditSemaphore('critico'), 'red');
});
