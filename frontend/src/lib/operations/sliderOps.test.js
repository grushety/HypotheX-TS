import test from 'node:test';
import assert from 'node:assert/strict';

import { SLIDER_OPS, sliderConfigFor, groupTier2Controls } from './sliderOps.js';

// ─── registry ─────────────────────────────────────────────────────────────

test('cycle_amplify and cycle_damp share a groupId', () => {
  assert.equal(SLIDER_OPS.cycle_amplify.groupId, SLIDER_OPS.cycle_damp.groupId);
});

test('cycle_amplify commits to amplify_amplitude (sign-disambiguated α)', () => {
  assert.equal(SLIDER_OPS.cycle_amplify.commitOpName, 'amplify_amplitude');
  assert.equal(SLIDER_OPS.cycle_damp.commitOpName, 'amplify_amplitude');
});

test('spike_scale is amplify-only (single direction)', () => {
  assert.equal(SLIDER_OPS.spike_scale.mode, 'amplify-only');
});

test('cycle / transient / noise sliders are bidirectional', () => {
  assert.equal(SLIDER_OPS.cycle_amplify.mode, 'bidirectional');
  assert.equal(SLIDER_OPS.transient_scale.mode, 'bidirectional');
  assert.equal(SLIDER_OPS.noise_rescale.mode, 'bidirectional');
});

test('sliderConfigFor returns null for non-slider ops', () => {
  assert.equal(sliderConfigFor('cycle_shift_phase'), null);
  assert.equal(sliderConfigFor('plateau_flatten'), null);
});

test('sliderConfigFor returns config for known slider ops', () => {
  assert.ok(sliderConfigFor('cycle_amplify'));
  assert.ok(sliderConfigFor('cycle_damp'));
  assert.ok(sliderConfigFor('transient_scale'));
  assert.ok(sliderConfigFor('spike_scale'));
  assert.ok(sliderConfigFor('noise_rescale'));
});

// ─── groupTier2Controls ───────────────────────────────────────────────────

test('groupTier2Controls collapses cycle_amplify + cycle_damp into one slider', () => {
  const buttons = [
    { op_name: 'cycle_scale_amplitude', enabled: true, loading: false, tier: 2 },
    { op_name: 'cycle_damp', enabled: true, loading: false, tier: 2 },
    { op_name: 'cycle_amplify', enabled: true, loading: false, tier: 2 },
  ];
  const controls = groupTier2Controls(buttons);
  assert.equal(controls.length, 2, 'should produce 1 button control + 1 slider control');
  const slider = controls.find((c) => c.kind === 'slider');
  assert.ok(slider, 'should include a slider control');
  assert.equal(slider.members.length, 2, 'slider should have both cycle_amplify and cycle_damp as members');
  assert.equal(slider.slider.groupId, 'cycle_amplitude');
  assert.equal(slider.slider.commitOpName, 'amplify_amplitude');
});

test('groupTier2Controls preserves first-occurrence ordering', () => {
  const buttons = [
    { op_name: 'cycle_damp', enabled: true, loading: false, tier: 2 },
    { op_name: 'cycle_scale_amplitude', enabled: true, loading: false, tier: 2 },
    { op_name: 'cycle_amplify', enabled: true, loading: false, tier: 2 },
  ];
  const controls = groupTier2Controls(buttons);
  assert.equal(controls[0].kind, 'slider', 'slider should appear at first cycle_damp position');
  assert.equal(controls[1].kind, 'button');
  assert.equal(controls[1].button.op_name, 'cycle_scale_amplitude');
});

test('groupTier2Controls treats unknown ops as plain buttons', () => {
  const buttons = [
    { op_name: 'plateau_flatten', enabled: true, loading: false, tier: 2 },
    { op_name: 'plateau_add_noise', enabled: true, loading: false, tier: 2 },
  ];
  const controls = groupTier2Controls(buttons);
  assert.equal(controls.length, 2);
  for (const c of controls) assert.equal(c.kind, 'button');
});

test('groupTier2Controls: spike_scale becomes a single-member amplify-only slider', () => {
  const buttons = [
    { op_name: 'spike_scale', enabled: true, loading: false, tier: 2 },
    { op_name: 'spike_widen', enabled: true, loading: false, tier: 2 },
  ];
  const controls = groupTier2Controls(buttons);
  const slider = controls.find((c) => c.kind === 'slider');
  assert.ok(slider);
  assert.equal(slider.slider.mode, 'amplify-only');
  assert.equal(slider.members.length, 1);
});

test('groupTier2Controls: slider enabled if any member enabled; loading if any loading', () => {
  const buttons = [
    { op_name: 'cycle_damp', enabled: false, loading: false, tier: 2 },
    { op_name: 'cycle_amplify', enabled: true, loading: true, tier: 2 },
  ];
  const controls = groupTier2Controls(buttons);
  const slider = controls.find((c) => c.kind === 'slider');
  assert.equal(slider.slider.enabled, true);
  assert.equal(slider.slider.loading, true);
});

test('groupTier2Controls: slider disabled when all members disabled', () => {
  const buttons = [
    { op_name: 'cycle_damp', enabled: false, loading: false, tier: 2, disabledTooltip: 'Not for plateau' },
    { op_name: 'cycle_amplify', enabled: false, loading: false, tier: 2 },
  ];
  const controls = groupTier2Controls(buttons);
  const slider = controls.find((c) => c.kind === 'slider');
  assert.equal(slider.slider.enabled, false);
  assert.equal(slider.slider.disabledTooltip, 'Not for plateau');
});

test('groupTier2Controls: empty input → empty output', () => {
  assert.deepEqual(groupTier2Controls([]), []);
});
