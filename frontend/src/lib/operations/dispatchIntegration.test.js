/**
 * Integration smoke tests for the HTS-102 visual surface.
 *
 * The frontend test runner is plain ``node --test`` (no Vue mount
 * harness), so this file pins the integration *contracts* that
 * ``BenchmarkViewerPage.vue`` relies on to wire the three components:
 *
 *   1. ``labelChipBus`` round-trips a chip from publisher to subscriber.
 *   2. ``isCompensationRequired('hydrology', 'plateau')`` is ``true``
 *      so the selector mounts on a hydrology-plateau context.
 *   3. ``createConstraintBudgetState`` produces a renderable state for
 *      an ``enforce_conservation`` response carrying ``law``,
 *      ``initial_residual``, ``final_residual``, ``tolerance``.
 *   4. ``buildInvokeRequest`` forwards ``domain_hint`` and
 *      ``compensation_mode`` into the request body.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { labelChipBus } from '../audit/labelChipBus.js';
import { isCompensationRequired } from '../constraints/createCompensationModeSelectorState.js';
import { createConstraintBudgetState } from '../constraints/createConstraintBudgetState.js';
import { buildInvokeRequest } from './buildInvokeRequest.js';

const SAMPLE = {
  sampleId: 'sample-1',
  values: [0, 1, 2, 3, 4],
  segments: [{ id: 's0', start: 0, end: 4, label: 'plateau' }],
};

test('labelChipBus: publish reaches subscribers (PredictedLabelChip subscription contract)', () => {
  const received = [];
  const unsubscribe = labelChipBus.subscribe((chip) => received.push(chip));
  try {
    labelChipBus.publish({
      chip_id: 'c1',
      segment_id: 's0',
      op_id: 'o1',
      op_name: 'flatten',
      tier: 2,
      old_shape: 'plateau',
      new_shape: 'plateau',
      confidence: 0.92,
      rule_class: 'PRESERVED',
    });
  } finally {
    unsubscribe();
  }
  assert.equal(received.length, 1);
  assert.equal(received[0].op_name, 'flatten');
});

test('CompensationModeSelector visibility gate: hydrology + plateau → required', () => {
  assert.equal(isCompensationRequired('hydrology', 'plateau'), true);
  assert.equal(isCompensationRequired('hydrology', 'noise'), false);
  assert.equal(isCompensationRequired('remote-sensing', 'plateau'), false);
  assert.equal(isCompensationRequired(null, 'plateau'), false);
});

test('ConstraintBudgetBar state: produced for an enforce_conservation response', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    compensationMode: 'local',
    initialResidual: 0.1,
    finalResidual: 1e-7,
    tolerance: 1e-6,
    units: 'mm',
  });
  assert.equal(state.status, 'green');
  assert.equal(state.direction, 'improving');
  assert.ok(state.fillFraction >= 0 && state.fillFraction <= 1.5);
});

test('buildInvokeRequest forwards domain_hint and compensation_mode', () => {
  const plan = buildInvokeRequest({
    tier: 2,
    op_name: 'plateau_scale',
    params: { delta: 1.0 },
    sample: SAMPLE,
    selectedSegment: SAMPLE.segments[0],
    domain_hint: 'hydrology',
    compensation_mode: 'local',
  });
  assert.equal(plan.kind, 'request');
  assert.equal(plan.body.domain_hint, 'hydrology');
  assert.equal(plan.body.compensation_mode, 'local');
});
