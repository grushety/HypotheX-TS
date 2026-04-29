import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createLabelChipDisplayModel,
  tickTimer,
  LOW_CONFIDENCE_THRESHOLD,
  DEFAULT_ACCEPT_TIMER_SECONDS,
} from './createLabelChipState.js';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeChip(overrides = {}) {
  return {
    chip_id: 'chip-001',
    segment_id: 'seg-001',
    op_id: 'op-abc',
    op_name: 'flatten',
    tier: 2,
    old_shape: 'trend',
    new_shape: 'plateau',
    confidence: 1.0,
    rule_class: 'DETERMINISTIC',
    timestamp: '2026-04-29T10:00:00.000Z',
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Fixture test 1 — PRESERVED: chip shows old_shape === new_shape
// ---------------------------------------------------------------------------

test('PRESERVED chip: newShape equals oldShape', () => {
  const chip = makeChip({ old_shape: 'cycle', new_shape: 'cycle', rule_class: 'PRESERVED', confidence: 1.0 });
  const model = createLabelChipDisplayModel(chip);
  assert.equal(model.oldShape, 'cycle');
  assert.equal(model.newShape, 'cycle');
  assert.equal(model.isPreserved, true);
  assert.equal(model.isDeterministic, false);
  assert.equal(model.isReclassify, false);
});

test('PRESERVED chip: displayText shows same shape on both sides', () => {
  const chip = makeChip({ old_shape: 'trend', new_shape: 'trend', rule_class: 'PRESERVED', confidence: 1.0 });
  const model = createLabelChipDisplayModel(chip);
  assert.ok(model.displayText.startsWith('trend → trend'));
});

// ---------------------------------------------------------------------------
// Fixture test 2 — DETERMINISTIC: shows target shape
// ---------------------------------------------------------------------------

test('DETERMINISTIC chip: newShape is the target', () => {
  const chip = makeChip({ old_shape: 'trend', new_shape: 'plateau', rule_class: 'DETERMINISTIC', confidence: 1.0 });
  const model = createLabelChipDisplayModel(chip);
  assert.equal(model.oldShape, 'trend');
  assert.equal(model.newShape, 'plateau');
  assert.equal(model.isDeterministic, true);
  assert.equal(model.isPreserved, false);
});

test('DETERMINISTIC chip: confidence 100% formats correctly', () => {
  const chip = makeChip({ confidence: 1.0, rule_class: 'DETERMINISTIC' });
  const model = createLabelChipDisplayModel(chip);
  assert.equal(model.confidencePct, 100);
  assert.ok(model.displayText.includes('(100%)'));
});

test('DETERMINISTIC chip: displayText includes rule class', () => {
  const chip = makeChip({ rule_class: 'DETERMINISTIC' });
  const model = createLabelChipDisplayModel(chip);
  assert.ok(model.displayText.includes('[DETERMINISTIC]'));
});

// ---------------------------------------------------------------------------
// Fixture test 3 — RECLASSIFY low-confidence → orange border, Override focused
// ---------------------------------------------------------------------------

test('RECLASSIFY below threshold: isLowConfidenceReclassify is true', () => {
  const chip = makeChip({
    rule_class: 'RECLASSIFY_VIA_SEGMENTER',
    confidence: 0.55,
    old_shape: 'noise',
    new_shape: 'trend',
  });
  const model = createLabelChipDisplayModel(chip);
  assert.equal(model.isReclassify, true);
  assert.equal(model.isLowConfidenceReclassify, true);
  assert.equal(model.shouldAutoFocusOverride, true);
});

test('RECLASSIFY below threshold: confidencePct rounds correctly', () => {
  const chip = makeChip({ rule_class: 'RECLASSIFY_VIA_SEGMENTER', confidence: 0.55 });
  const model = createLabelChipDisplayModel(chip);
  assert.equal(model.confidencePct, 55);
});

test('RECLASSIFY at threshold boundary (exactly 0.70): not low confidence', () => {
  const chip = makeChip({ rule_class: 'RECLASSIFY_VIA_SEGMENTER', confidence: LOW_CONFIDENCE_THRESHOLD });
  const model = createLabelChipDisplayModel(chip);
  assert.equal(model.isLowConfidenceReclassify, false);
  assert.equal(model.shouldAutoFocusOverride, false);
});

test('RECLASSIFY above threshold (0.85): not flagged', () => {
  const chip = makeChip({ rule_class: 'RECLASSIFY_VIA_SEGMENTER', confidence: 0.85 });
  const model = createLabelChipDisplayModel(chip);
  assert.equal(model.isLowConfidenceReclassify, false);
});

test('DETERMINISTIC with low confidence does not trigger low-confidence flag', () => {
  const chip = makeChip({ rule_class: 'DETERMINISTIC', confidence: 0.3 });
  const model = createLabelChipDisplayModel(chip);
  assert.equal(model.isLowConfidenceReclassify, false);
  assert.equal(model.shouldAutoFocusOverride, false);
});

// ---------------------------------------------------------------------------
// Fixture test 4 — timer auto-accept fires after acceptTimerMs
// ---------------------------------------------------------------------------

test('tickTimer: not fired before duration elapses', () => {
  const { fired, fraction } = tickTimer(5000, 2500);
  assert.equal(fired, false);
  assert.ok(fraction > 0 && fraction < 1, `fraction should be between 0 and 1, got ${fraction}`);
});

test('tickTimer: fires exactly at acceptTimerMs', () => {
  const { fired, fraction } = tickTimer(5000, 5000);
  assert.equal(fired, true);
  assert.equal(fraction, 1);
});

test('tickTimer: fires when elapsedMs exceeds acceptTimerMs', () => {
  const { fired } = tickTimer(5000, 6000);
  assert.equal(fired, true);
});

test('tickTimer: fraction is 0 at elapsed 0', () => {
  const { fired, fraction } = tickTimer(5000, 0);
  assert.equal(fired, false);
  assert.equal(fraction, 0);
});

test('tickTimer: fraction is 0.5 at half duration', () => {
  const { fraction } = tickTimer(5000, 2500);
  assert.equal(fraction, 0.5);
});

test('tickTimer: remainingMs counts down', () => {
  const { remainingMs } = tickTimer(5000, 3000);
  assert.equal(remainingMs, 2000);
});

test('tickTimer: remainingMs is 0 when fired', () => {
  const { remainingMs } = tickTimer(5000, 5000);
  assert.equal(remainingMs, 0);
});

test('DEFAULT_ACCEPT_TIMER_SECONDS is 5', () => {
  assert.equal(DEFAULT_ACCEPT_TIMER_SECONDS, 5);
});

test('tickTimer: respects custom duration (3 s)', () => {
  const { fired } = tickTimer(3000, 3001);
  assert.equal(fired, true);
});

// ---------------------------------------------------------------------------
// Fixture test 5 — Undo: opId and segmentId available on display model
// ---------------------------------------------------------------------------

test('Undo: opId is forwarded from chip for revert', () => {
  const chip = makeChip({ op_id: 'op-xyz-789' });
  const model = createLabelChipDisplayModel(chip);
  assert.equal(model.opId, 'op-xyz-789');
});

test('Undo: segmentId is forwarded from chip', () => {
  const chip = makeChip({ segment_id: 'seg-undo-target' });
  const model = createLabelChipDisplayModel(chip);
  assert.equal(model.segmentId, 'seg-undo-target');
});

// ---------------------------------------------------------------------------
// Guard — null / malformed chip
// ---------------------------------------------------------------------------

test('null chip returns null', () => {
  assert.equal(createLabelChipDisplayModel(null), null);
});

test('empty object chip does not throw', () => {
  const model = createLabelChipDisplayModel({});
  assert.ok(model);
  assert.equal(model.oldShape, null);
  assert.equal(model.newShape, null);
  assert.equal(model.isLowConfidenceReclassify, false);
});

// ---------------------------------------------------------------------------
// displayText format
// ---------------------------------------------------------------------------

test('displayText follows pattern: old → new  (pct%)  [rule]', () => {
  const chip = makeChip({ old_shape: 'step', new_shape: 'transient', rule_class: 'DETERMINISTIC', confidence: 1.0 });
  const model = createLabelChipDisplayModel(chip);
  assert.equal(model.displayText, 'step → transient  (100%)  [DETERMINISTIC]');
});

test('confidence 0.73 rounds to 73%', () => {
  const chip = makeChip({ confidence: 0.73, rule_class: 'RECLASSIFY_VIA_SEGMENTER' });
  const model = createLabelChipDisplayModel(chip);
  assert.equal(model.confidencePct, 73);
  assert.ok(model.displayText.includes('(73%)'));
});

// ---------------------------------------------------------------------------
// LOW_CONFIDENCE_THRESHOLD exported constant
// ---------------------------------------------------------------------------

test('LOW_CONFIDENCE_THRESHOLD is 0.70', () => {
  assert.equal(LOW_CONFIDENCE_THRESHOLD, 0.70);
});
