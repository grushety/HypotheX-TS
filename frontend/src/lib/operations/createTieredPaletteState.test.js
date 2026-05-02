import test from 'node:test';
import assert from 'node:assert/strict';

import { createTieredPaletteState } from './createTieredPaletteState.js';

test('no selection — tier0 and tier1 buttons are all disabled', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: [] });
  for (const btn of state.tier0.buttons) assert.equal(btn.enabled, false, `tier0 ${btn.op_name} should be disabled`);
  for (const btn of state.tier1.buttons) assert.equal(btn.enabled, false, `tier1 ${btn.op_name} should be disabled`);
});

test('single selection — tier0 and tier1 buttons are enabled', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['plateau'] });
  for (const btn of state.tier0.buttons) assert.equal(btn.enabled, true, `tier0 ${btn.op_name} should be enabled`);
  for (const btn of state.tier1.buttons) assert.equal(btn.enabled, true, `tier1 ${btn.op_name} should be enabled`);
});

test('plateau shape → tier2 has exactly 5 buttons', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['plateau'] });
  assert.equal(state.tier2.buttons.length, 5);
});

test('cycle shape → tier2 has exactly 7 buttons', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['cycle'] });
  assert.equal(state.tier2.buttons.length, 7);
});

test('tier2 buttons are enabled on single select', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['plateau'] });
  for (const btn of state.tier2.buttons) assert.equal(btn.enabled, true, `${btn.op_name} should be enabled`);
});

test('multi-select different shapes → tier2 disabled flag set, intersectionTooltip present', () => {
  const state = createTieredPaletteState({
    selectedSegmentIds: ['seg-1', 'seg-2'],
    selectedShapes: ['plateau', 'step'],
  });
  assert.equal(state.tier2.disabled, true);
  assert.ok(typeof state.tier2.intersectionTooltip === 'string' && state.tier2.intersectionTooltip.length > 0);
});

test('multi-select different shapes → tier2 buttons all disabled', () => {
  const state = createTieredPaletteState({
    selectedSegmentIds: ['seg-1', 'seg-2'],
    selectedShapes: ['cycle', 'noise'],
  });
  assert.ok(state.tier2.buttons.length > 0, 'union should produce buttons');
  for (const btn of state.tier2.buttons) {
    assert.equal(btn.enabled, false, `${btn.op_name} should be disabled in multi-select`);
  }
});

test('single select, no shape → tier2 has no buttons', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: [] });
  assert.equal(state.tier2.buttons.length, 0);
});

test('unknown shape → tier2 has no buttons', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['unknown_shape'] });
  assert.equal(state.tier2.buttons.length, 0);
});

test('pendingOp = split → split button has loading: true, others false', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], pendingOp: 'split' });
  const splitBtn = state.tier0.buttons.find((b) => b.op_name === 'split');
  const otherBtns = state.tier0.buttons.filter((b) => b.op_name !== 'split');
  assert.equal(splitBtn.loading, true);
  for (const btn of otherBtns) assert.equal(btn.loading, false);
});

test('pendingOp = scale → scale tier1 button loading, others not', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], pendingOp: 'scale' });
  const scaleBtn = state.tier1.buttons.find((b) => b.op_name === 'scale');
  assert.equal(scaleBtn.loading, true);
  for (const btn of state.tier1.buttons.filter((b) => b.op_name !== 'scale')) {
    assert.equal(btn.loading, false);
  }
});

test('align_warp disabled on single selection', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'] });
  const btn = state.tier3.buttons.find((b) => b.op_name === 'align_warp');
  assert.equal(btn.enabled, false);
});

test('align_warp enabled with ≥2 selections', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1', 'seg-2'] });
  const btn = state.tier3.buttons.find((b) => b.op_name === 'align_warp');
  assert.equal(btn.enabled, true);
});

test('other tier3 ops enabled on single selection', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'] });
  const others = state.tier3.buttons.filter((b) => b.op_name !== 'align_warp');
  for (const btn of others) assert.equal(btn.enabled, true, `${btn.op_name} should be enabled`);
});

test('tier labels match expected strings', () => {
  const state = createTieredPaletteState();
  assert.equal(state.tier0.label, 'Tier 0: structural');
  assert.equal(state.tier1.label, 'Tier 1: basic atoms');
  assert.equal(state.tier2.label, 'Tier 2: shape-specific');
  assert.equal(state.tier3.label, 'Tier 3: composite');
});

test('single select with no shape — tier2 not disabled (no multi-select)', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: [] });
  assert.equal(state.tier2.disabled, false);
  assert.equal(state.tier2.intersectionTooltip, null);
});

test('no selection — tier3 non-multiselect ops are disabled', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: [] });
  const decompose = state.tier3.buttons.find((b) => b.op_name === 'decompose');
  assert.equal(decompose.enabled, false);
});

test('state has id fields on all tiers', () => {
  const state = createTieredPaletteState();
  assert.equal(state.tier0.id, 'tier-0');
  assert.equal(state.tier1.id, 'tier-1');
  assert.equal(state.tier2.id, 'tier-2');
  assert.equal(state.tier3.id, 'tier-3');
});

test('no pendingOp — all buttons have loading: false', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['plateau'] });
  const all = [
    ...state.tier0.buttons,
    ...state.tier1.buttons,
    ...state.tier2.buttons,
    ...state.tier3.buttons,
  ];
  for (const btn of all) assert.equal(btn.loading, false, `${btn.op_name} should not be loading`);
});

test('pendingOp = plateau_flatten → that tier2 button has loading: true', () => {
  const state = createTieredPaletteState({
    selectedSegmentIds: ['seg-1'],
    selectedShapes: ['plateau'],
    pendingOp: 'plateau_flatten',
  });
  const flattenBtn = state.tier2.buttons.find((b) => b.op_name === 'plateau_flatten');
  assert.ok(flattenBtn, 'plateau_flatten not found in tier2 buttons');
  assert.equal(flattenBtn.loading, true);
  for (const btn of state.tier2.buttons.filter((b) => b.op_name !== 'plateau_flatten')) {
    assert.equal(btn.loading, false, `${btn.op_name} should not be loading`);
  }
});

test('pendingOp = decompose → decompose tier3 button loading, others not', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], pendingOp: 'decompose' });
  const decomposeBtn = state.tier3.buttons.find((b) => b.op_name === 'decompose');
  assert.equal(decomposeBtn.loading, true);
  for (const btn of state.tier3.buttons.filter((b) => b.op_name !== 'decompose')) {
    assert.equal(btn.loading, false, `${btn.op_name} should not be loading`);
  }
});

test('align_warp disabled with 0 selections', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: [] });
  const btn = state.tier3.buttons.find((b) => b.op_name === 'align_warp');
  assert.equal(btn.enabled, false);
});

test('multi-select — non-requiresMultiSelect tier3 ops are disabled', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1', 'seg-2'] });
  const others = state.tier3.buttons.filter((b) => b.op_name !== 'align_warp');
  for (const btn of others) {
    assert.equal(btn.enabled, false, `${btn.op_name} should be disabled on multi-select`);
  }
});

test('multi-select with no shape — tier2 still disabled with tooltip', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1', 'seg-2'], selectedShapes: [] });
  assert.equal(state.tier2.disabled, true);
  assert.ok(typeof state.tier2.intersectionTooltip === 'string' && state.tier2.intersectionTooltip.length > 0);
});

test('no selection — tier2 not disabled and intersectionTooltip is null', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: [] });
  assert.equal(state.tier2.disabled, false);
  assert.equal(state.tier2.intersectionTooltip, null);
});

// ─── disabledTooltip field on tier2 buttons ───────────────────────────────────

test('single select plateau: tier2 buttons have disabledTooltip null (all enabled)', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['plateau'] });
  for (const btn of state.tier2.buttons) {
    assert.equal(btn.disabledTooltip, null, `${btn.op_name} should have null disabledTooltip when enabled`);
  }
});

test('multi-select plateau+step: tier2 buttons have non-null disabledTooltip', () => {
  const state = createTieredPaletteState({
    selectedSegmentIds: ['seg-1', 'seg-2'],
    selectedShapes: ['plateau', 'step'],
  });
  for (const btn of state.tier2.buttons) {
    assert.ok(btn.disabledTooltip !== null, `${btn.op_name} should have a disabledTooltip when disabled`);
    assert.ok(typeof btn.disabledTooltip === 'string' && btn.disabledTooltip.length > 0,
      `${btn.op_name} disabledTooltip should be a non-empty string`);
  }
});

test('tier2 buttons always carry disabledTooltip field (never undefined)', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['cycle'] });
  for (const btn of state.tier2.buttons) {
    assert.ok('disabledTooltip' in btn, `${btn.op_name} is missing disabledTooltip field`);
  }
});

// ─── Per-shape tier2 button op_name snapshots ─────────────────────────────────

test('single select trend: tier2 has exactly 6 buttons with correct op_names', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['trend'] });
  assert.equal(state.tier2.buttons.length, 6);
  const names = state.tier2.buttons.map((b) => b.op_name);
  assert.deepEqual(names, ['trend_change_slope', 'trend_reverse', 'trend_scale', 'trend_add_noise', 'trend_detrend', 'trend_fit_piecewise']);
});

test('single select step: tier2 has exactly 5 buttons with correct op_names', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['step'] });
  assert.equal(state.tier2.buttons.length, 5);
  const names = state.tier2.buttons.map((b) => b.op_name);
  assert.deepEqual(names, ['step_adjust_height', 'step_smooth', 'step_scale', 'step_add_noise', 'step_remove']);
});

test('single select spike: tier2 has exactly 5 buttons with correct op_names', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['spike'] });
  assert.equal(state.tier2.buttons.length, 5);
  const names = state.tier2.buttons.map((b) => b.op_name);
  assert.deepEqual(names, ['spike_scale', 'spike_widen', 'spike_narrow', 'spike_remove', 'spike_add']);
});

test('single select transient: tier2 has exactly 5 buttons with correct op_names', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['transient'] });
  assert.equal(state.tier2.buttons.length, 5);
  const names = state.tier2.buttons.map((b) => b.op_name);
  assert.deepEqual(names, ['transient_scale', 'transient_shift_onset', 'transient_change_duration', 'transient_smooth_onset', 'transient_sharpen_onset']);
});

test('single select noise: tier2 has exactly 5 buttons with correct op_names', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['noise'] });
  assert.equal(state.tier2.buttons.length, 5);
  const names = state.tier2.buttons.map((b) => b.op_name);
  assert.deepEqual(names, ['noise_rescale', 'noise_filter', 'noise_change_distribution', 'noise_add_periodic', 'noise_denoise']);
});

test('single select plateau: all tier2 buttons have enabled true', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['plateau'] });
  for (const btn of state.tier2.buttons) {
    assert.equal(btn.enabled, true, `${btn.op_name} should be enabled`);
  }
});

test('single select trend: all tier2 buttons have enabled true', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], selectedShapes: ['trend'] });
  for (const btn of state.tier2.buttons) {
    assert.equal(btn.enabled, true, `${btn.op_name} should be enabled`);
  }
});

// ─── Multi-select union of tier2 buttons ──────────────────────────────────────

test('multi-select plateau+step: tier2 buttons contain union of both shapes ops', () => {
  const state = createTieredPaletteState({
    selectedSegmentIds: ['seg-1', 'seg-2'],
    selectedShapes: ['plateau', 'step'],
  });
  const names = new Set(state.tier2.buttons.map((b) => b.op_name));
  for (const op of ['plateau_flatten', 'plateau_add_noise', 'plateau_scale', 'plateau_remove_drift', 'plateau_add_seasonal']) {
    assert.ok(names.has(op), `${op} should be in tier2 union buttons`);
  }
  for (const op of ['step_adjust_height', 'step_smooth', 'step_scale', 'step_add_noise', 'step_remove']) {
    assert.ok(names.has(op), `${op} should be in tier2 union buttons`);
  }
  assert.equal(state.tier2.buttons.length, 10, 'union of plateau(5) + step(5) = 10 buttons');
});

test('multi-select same shape twice: tier2 shows that shape ops without duplicates', () => {
  const state = createTieredPaletteState({
    selectedSegmentIds: ['seg-1', 'seg-2'],
    selectedShapes: ['cycle', 'cycle'],
  });
  assert.equal(state.tier2.buttons.length, 7, 'deduplication: cycle appears once = 7 buttons');
});

test('UI-017 gap gating: tier2 cycle FFT ops disabled when gapInfo exceeds threshold', () => {
  const state = createTieredPaletteState({
    selectedSegmentIds: ['seg-1'],
    selectedShapes: ['cycle'],
    gapInfo: { exceedsThreshold: true, isFilled: false, missingnessPct: 60 },
  });
  const fftOps = state.tier2.buttons.filter(
    (b) => b.op_name === 'cycle_change_frequency' || b.op_name === 'cycle_shift_phase',
  );
  assert.equal(fftOps.length, 2);
  for (const op of fftOps) {
    assert.equal(op.enabled, false, `${op.op_name} should be gated`);
    assert.match(op.disabledTooltip, /60% missing/);
  }
});

test('UI-017 gap gating: non-FFT cycle ops stay enabled even on heavy gaps', () => {
  const state = createTieredPaletteState({
    selectedSegmentIds: ['seg-1'],
    selectedShapes: ['cycle'],
    gapInfo: { exceedsThreshold: true, isFilled: false, missingnessPct: 60 },
  });
  const damp = state.tier2.buttons.find((b) => b.op_name === 'cycle_damp');
  assert.ok(damp);
  assert.equal(damp.enabled, true);
});

test('UI-017 gap gating: tier3 decompose disabled when gap exceeds threshold', () => {
  const state = createTieredPaletteState({
    selectedSegmentIds: ['seg-1'],
    selectedShapes: ['cycle'],
    gapInfo: { exceedsThreshold: true, isFilled: false, missingnessPct: 45 },
  });
  const decompose = state.tier3.buttons.find((b) => b.op_name === 'decompose');
  assert.ok(decompose);
  assert.equal(decompose.enabled, false);
  assert.match(decompose.disabledTooltip, /45% missing/);
});

test('UI-017 gap gating: filled segment re-enables dense ops', () => {
  const state = createTieredPaletteState({
    selectedSegmentIds: ['seg-1'],
    selectedShapes: ['cycle'],
    gapInfo: { exceedsThreshold: true, isFilled: true, missingnessPct: 60 },
  });
  const phase = state.tier2.buttons.find((b) => b.op_name === 'cycle_shift_phase');
  assert.equal(phase.enabled, true);
});

test('UI-017 gap gating: omitted gapInfo leaves all ops untouched', () => {
  const state = createTieredPaletteState({
    selectedSegmentIds: ['seg-1'],
    selectedShapes: ['cycle'],
  });
  for (const btn of state.tier2.buttons) {
    assert.equal(btn.enabled, true, `${btn.op_name} should be enabled without gapInfo`);
  }
});
