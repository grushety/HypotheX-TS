/**
 * Integration test pinning the HTS-103 contract: a Tier-2 op response
 * (chip + constraint_residual) flowing through the HTS-101/102
 * audit-event creator produces an AuditLogPanel row with non-null
 * ``tier``, ``ruleClass``, and ``constraintResidual`` columns.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  appendAuditEvent,
  createOperationAuditEvent,
} from './auditEvents.js';
import { createAuditLogPanelState } from './createAuditLogPanelState.js';

test('Tier-2 op audit event renders a row with non-null tier + ruleClass + residual', () => {
  const chip = {
    chip_id: 'c1',
    segment_id: 's0',
    op_id: 'o1',
    op_name: 'change_slope',
    tier: 2,
    old_shape: 'trend',
    new_shape: 'trend',
    confidence: 0.92,
    rule_class: 'PRESERVED',
  };
  const constraintResidual = {
    law: 'water_balance',
    initial_residual: 0.1,
    final_residual: 1e-7,
    converged: true,
    tolerance: 1e-6,
    compensation_mode: 'local',
  };

  const event = createOperationAuditEvent(
    { type: 'trend_change_slope', tier: 2, op_name: 'trend_change_slope', params: { alpha: 0.5 } },
    {
      ok: true,
      constraintStatus: 'WARN',
      warnings: [],
      operationResult: { affectedSegmentIds: ['s0'] },
      message: 'trend_change_slope: applied.',
      selectedSegmentId: 's0',
      chip,
      constraintResidual,
    },
    { sampleId: 'sample-1', selectedSegmentId: 's0' },
  );
  const events = appendAuditEvent([], event);

  const state = createAuditLogPanelState(events, [], {}, 0);
  assert.equal(state.rows.length, 1);
  const row = state.rows[0];
  assert.equal(row.tier, 2);
  assert.equal(row.ruleClass, 'PRESERVED');
  assert.equal(row.preShape, 'trend');
  assert.equal(row.postShape, 'trend');
  assert.equal(row.compensationMode, null); // request didn't carry compensation_mode
  assert.equal(row.plausibilityBadge, 'green');
  assert.deepEqual(row.constraintResidual, constraintResidual);
  assert.equal(row.fullChip.chip_id, 'c1');
});

test('Tier-0 boundary edit row still has tier=0 and null chip/residual fields', () => {
  const event = createOperationAuditEvent(
    { type: 'merge', leftSegmentId: 's0', rightSegmentId: 's1' },
    {
      ok: true,
      constraintStatus: 'PASS',
      warnings: [],
      operationResult: { affectedSegmentIds: ['s0'] },
      message: 'merge applied.',
      selectedSegmentId: 's0',
    },
    { sampleId: 'sample-1', selectedSegmentId: 's0' },
  );
  const events = appendAuditEvent([], event);
  const state = createAuditLogPanelState(events, [], {}, 0);
  const row = state.rows[0];
  assert.equal(row.tier, 0);
  assert.equal(row.ruleClass, null);
  assert.equal(row.constraintResidual, null);
  assert.equal(row.fullChip, null);
});
