import test from 'node:test';
import assert from 'node:assert/strict';

import { createTieredPaletteState } from './createTieredPaletteState.js';

test('no selection — tier0 and tier1 buttons are all disabled', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: [] });
  for (const btn of state.tier0.buttons) assert.equal(btn.enabled, false, `tier0 ${btn.op_name} should be disabled`);
  for (const btn of state.tier1.buttons) assert.equal(btn.enabled, false, `tier1 ${btn.op_name} should be disabled`);
});

test('single selection — tier0 and tier1 buttons are enabled', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], activeShape: 'plateau' });
  for (const btn of state.tier0.buttons) assert.equal(btn.enabled, true, `tier0 ${btn.op_name} should be enabled`);
  for (const btn of state.tier1.buttons) assert.equal(btn.enabled, true, `tier1 ${btn.op_name} should be enabled`);
});

test('plateau shape → tier2 has exactly 5 buttons', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], activeShape: 'plateau' });
  assert.equal(state.tier2.buttons.length, 5);
});

test('cycle shape → tier2 has exactly 7 buttons', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], activeShape: 'cycle' });
  assert.equal(state.tier2.buttons.length, 7);
});

test('tier2 buttons are enabled on single select', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], activeShape: 'plateau' });
  for (const btn of state.tier2.buttons) assert.equal(btn.enabled, true, `${btn.op_name} should be enabled`);
});

test('multi-select → tier2 disabled flag set, intersectionTooltip present', () => {
  const state = createTieredPaletteState({
    selectedSegmentIds: ['seg-1', 'seg-2'],
    activeShape: 'plateau',
  });
  assert.equal(state.tier2.disabled, true);
  assert.ok(typeof state.tier2.intersectionTooltip === 'string' && state.tier2.intersectionTooltip.length > 0);
});

test('multi-select → tier2 buttons all disabled', () => {
  const state = createTieredPaletteState({
    selectedSegmentIds: ['seg-1', 'seg-2'],
    activeShape: 'cycle',
  });
  for (const btn of state.tier2.buttons) {
    assert.equal(btn.enabled, false, `${btn.op_name} should be disabled in multi-select`);
  }
});

test('single select, no shape → tier2 has no buttons', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], activeShape: null });
  assert.equal(state.tier2.buttons.length, 0);
});

test('unknown shape → tier2 has no buttons', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], activeShape: 'unknown_shape' });
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
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], activeShape: null });
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
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1'], activeShape: 'plateau' });
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
    activeShape: 'plateau',
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
  const state = createTieredPaletteState({ selectedSegmentIds: ['seg-1', 'seg-2'], activeShape: null });
  assert.equal(state.tier2.disabled, true);
  assert.ok(typeof state.tier2.intersectionTooltip === 'string' && state.tier2.intersectionTooltip.length > 0);
});

test('no selection — tier2 not disabled and intersectionTooltip is null', () => {
  const state = createTieredPaletteState({ selectedSegmentIds: [] });
  assert.equal(state.tier2.disabled, false);
  assert.equal(state.tier2.intersectionTooltip, null);
});
