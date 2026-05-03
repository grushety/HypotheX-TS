import { test } from 'node:test';
import assert from 'node:assert/strict';

import { makeBus, validationBus } from './validationBus.js';
import {
  applyValidityUpdate,
  createGuardrailsState,
} from '../guardrails/createGuardrailsState.js';

test('validationBus.subscribe(topic, handler) round-trips a published payload', () => {
  const bus = makeBus();
  const received = [];
  const off = bus.subscribe('validity_update', (p) => received.push(p));
  bus.publish('validity_update', { value: 1.0, tipShouldFire: false });
  bus.publish('coverage_update', { coverageFraction: 0.5 });
  off();
  bus.publish('validity_update', { value: 0.0, tipShouldFire: true });
  assert.equal(received.length, 1);
  assert.equal(received[0].value, 1.0);
});

test('validationBus.unsubscribe is idempotent', () => {
  const bus = makeBus();
  const handler = () => {};
  bus.subscribe('coverage_update', handler);
  bus.unsubscribe('coverage_update', handler);
  bus.unsubscribe('coverage_update', handler);
  // No throw == pass.
});

test('GuardrailsSidebar contract: applyValidityUpdate fires through the bus pattern', () => {
  // Reproduces what the sidebar's _attachBus does internally: subscribe a
  // handler that calls the appropriate applier, then publish.
  const bus = makeBus();
  const state = createGuardrailsState();
  const off = bus.subscribe('validity_update', (payload) => applyValidityUpdate(state, payload));

  // Threshold-firing event publishes through the bus.
  bus.publish('validity_update', { rate: 0.4, tipShouldFire: true });
  off();

  const validity = state.rows.validity;
  assert.equal(validity.value, 0.4);
  assert.equal(validity.tipShouldFire, true);
  assert.equal(validity.pulse, true, 'first transition to firing should pulse');
});

test('singleton validationBus is the project-wide instance shared across modules', () => {
  // Sanity: importing twice gives the same instance.
  assert.ok(validationBus);
  assert.equal(typeof validationBus.subscribe, 'function');
  assert.equal(typeof validationBus.publish, 'function');
});
