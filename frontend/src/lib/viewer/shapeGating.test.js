import test from 'node:test';
import assert from 'node:assert/strict';

import {
  SHAPE_GATING_TABLE,
  computeLegalOps,
  createShapeGatingState,
  useShapeGating,
} from './shapeGating.js';

const ALL_SHAPES = ['plateau', 'trend', 'step', 'spike', 'cycle', 'transient', 'noise'];

// ─── Snapshot tests ────────────────────────────────────────────────────────

test('SHAPE_GATING_TABLE covers all 7 shapes', () => {
  assert.deepEqual(new Set(Object.keys(SHAPE_GATING_TABLE)), new Set(ALL_SHAPES));
});

test('SHAPE_GATING_TABLE values are non-empty string arrays', () => {
  for (const [shape, ops] of Object.entries(SHAPE_GATING_TABLE)) {
    assert.ok(Array.isArray(ops) && ops.length > 0, `${shape}: expected non-empty array`);
    for (const name of ops) assert.ok(typeof name === 'string', `${shape}: op_name must be string`);
  }
});

test('snapshot: plateau has exactly the 5 expected ops', () => {
  assert.deepEqual(SHAPE_GATING_TABLE.plateau, [
    'plateau_flatten',
    'plateau_add_noise',
    'plateau_scale',
    'plateau_remove_drift',
    'plateau_add_seasonal',
  ]);
});

test('snapshot: cycle has exactly the 7 expected ops', () => {
  assert.deepEqual(SHAPE_GATING_TABLE.cycle, [
    'cycle_scale_amplitude',
    'cycle_shift_phase',
    'cycle_change_frequency',
    'cycle_add_harmonics',
    'cycle_remove_harmonics',
    'cycle_damp',
    'cycle_amplify',
  ]);
});

test('snapshot: plateau has 5 ops, cycle has 7', () => {
  assert.equal(SHAPE_GATING_TABLE.plateau.length, 5);
  assert.equal(SHAPE_GATING_TABLE.cycle.length, 7);
});

// ─── computeLegalOps ───────────────────────────────────────────────────────

test('computeLegalOps([]) returns empty set', () => {
  assert.equal(computeLegalOps([]).size, 0);
});

test('computeLegalOps single shape returns that shape\'s ops', () => {
  const ops = computeLegalOps(['plateau']);
  assert.equal(ops.size, SHAPE_GATING_TABLE.plateau.length);
  for (const name of SHAPE_GATING_TABLE.plateau) assert.ok(ops.has(name));
});

test('computeLegalOps(["plateau", "step"]) returns empty set — no shared ops', () => {
  const ops = computeLegalOps(['plateau', 'step']);
  assert.equal(ops.size, 0);
});

test('computeLegalOps same shape twice returns that shape\'s full op set', () => {
  const ops = computeLegalOps(['cycle', 'cycle']);
  assert.equal(ops.size, SHAPE_GATING_TABLE.cycle.length);
});

test('computeLegalOps all 7 different shapes returns empty set', () => {
  const ops = computeLegalOps(ALL_SHAPES);
  assert.equal(ops.size, 0);
});

// ─── createShapeGatingState — single shape ─────────────────────────────────

test('single plateau: isEnabled true for all plateau ops', () => {
  const { isEnabled } = createShapeGatingState(['plateau']);
  for (const name of SHAPE_GATING_TABLE.plateau) {
    assert.equal(isEnabled(name), true, `${name} should be enabled for plateau`);
  }
});

test('single plateau: isEnabled false for non-plateau ops', () => {
  const { isEnabled } = createShapeGatingState(['plateau']);
  const nonPlateau = Object.entries(SHAPE_GATING_TABLE)
    .filter(([shape]) => shape !== 'plateau')
    .flatMap(([, ops]) => ops);
  for (const name of nonPlateau) {
    assert.equal(isEnabled(name), false, `${name} should be disabled for plateau`);
  }
});

test('single cycle: isEnabled true for all cycle ops', () => {
  const { isEnabled } = createShapeGatingState(['cycle']);
  for (const name of SHAPE_GATING_TABLE.cycle) assert.equal(isEnabled(name), true);
});

test('no shapes: isEnabled always false', () => {
  const { isEnabled } = createShapeGatingState([]);
  for (const shape of ALL_SHAPES) {
    for (const name of SHAPE_GATING_TABLE[shape]) {
      assert.equal(isEnabled(name), false, `${name} should be disabled with no shape`);
    }
  }
});

// ─── tooltipIfDisabled ─────────────────────────────────────────────────────

test('tooltipIfDisabled returns null for an enabled op', () => {
  const { tooltipIfDisabled } = createShapeGatingState(['plateau']);
  assert.equal(tooltipIfDisabled('plateau_flatten'), null);
});

test('tooltipIfDisabled mentions the active shape for a disabled op', () => {
  const { tooltipIfDisabled } = createShapeGatingState(['plateau']);
  const tip = tooltipIfDisabled('trend_change_slope');
  assert.ok(tip !== null, 'should return a tooltip');
  assert.ok(tip.includes('plateau'), `tooltip should mention active shape, got: ${tip}`);
});

test('tooltipIfDisabled mentions eligible shapes for a disabled op', () => {
  const { tooltipIfDisabled } = createShapeGatingState(['plateau']);
  const tip = tooltipIfDisabled('trend_change_slope');
  assert.ok(tip.includes('trend'), `tooltip should mention eligible shape, got: ${tip}`);
});

test('tooltipIfDisabled format: "Not available for {shape}; applies to {eligible}"', () => {
  const { tooltipIfDisabled } = createShapeGatingState(['plateau']);
  const tip = tooltipIfDisabled('cycle_damp');
  assert.ok(tip.startsWith('Not available for plateau'), `unexpected format: ${tip}`);
  assert.ok(tip.includes('applies to'), `missing "applies to": ${tip}`);
  assert.ok(tip.includes('cycle'), `missing eligible shape: ${tip}`);
});

test('tooltipIfDisabled returns null when no shape selected', () => {
  const { tooltipIfDisabled } = createShapeGatingState([]);
  assert.equal(tooltipIfDisabled('plateau_flatten'), null);
});

// ─── multi-select gating ───────────────────────────────────────────────────

test('multi-select plateau+step: no ops enabled', () => {
  const { isEnabled } = createShapeGatingState(['plateau', 'step']);
  const allOps = [...SHAPE_GATING_TABLE.plateau, ...SHAPE_GATING_TABLE.step];
  for (const name of allOps) assert.equal(isEnabled(name), false);
});

test('multi-select plateau+step: tooltips include both shapes in active list', () => {
  const { tooltipIfDisabled } = createShapeGatingState(['plateau', 'step']);
  const tip = tooltipIfDisabled('plateau_flatten');
  assert.ok(tip !== null);
  assert.ok(tip.includes('plateau'), `missing plateau: ${tip}`);
  assert.ok(tip.includes('step'), `missing step: ${tip}`);
});

test('multi-select same shape twice: all ops for that shape enabled', () => {
  const { isEnabled } = createShapeGatingState(['cycle', 'cycle']);
  for (const name of SHAPE_GATING_TABLE.cycle) assert.equal(isEnabled(name), true);
});

// ─── useShapeGating ────────────────────────────────────────────────────────

test('useShapeGating delegates to createShapeGatingState', () => {
  const gating = useShapeGating({ shapes: ['plateau'] });
  assert.equal(gating.isEnabled('plateau_flatten'), true);
  assert.equal(gating.isEnabled('trend_change_slope'), false);
});

test('useShapeGating with null/undefined activeSelection returns all-disabled', () => {
  const gating = useShapeGating(null);
  assert.equal(gating.isEnabled('plateau_flatten'), false);
  assert.equal(gating.tooltipIfDisabled('plateau_flatten'), null);
});

test('useShapeGating multi-select plateau+step: all ops disabled', () => {
  const gating = useShapeGating({ shapes: ['plateau', 'step'] });
  for (const name of SHAPE_GATING_TABLE.plateau) assert.equal(gating.isEnabled(name), false);
  for (const name of SHAPE_GATING_TABLE.step) assert.equal(gating.isEnabled(name), false);
});

// ─── Bit-identical full table snapshot ────────────────────────────────────────

test('snapshot: SHAPE_GATING_TABLE exact bit-identical content for all 7 shapes', () => {
  assert.deepEqual(SHAPE_GATING_TABLE, {
    plateau:   ['plateau_flatten', 'plateau_add_noise', 'plateau_scale', 'plateau_remove_drift', 'plateau_add_seasonal'],
    trend:     ['trend_change_slope', 'trend_reverse', 'trend_scale', 'trend_add_noise', 'trend_detrend', 'trend_fit_piecewise'],
    step:      ['step_adjust_height', 'step_smooth', 'step_scale', 'step_add_noise', 'step_remove'],
    spike:     ['spike_scale', 'spike_widen', 'spike_narrow', 'spike_remove', 'spike_add'],
    cycle:     ['cycle_scale_amplitude', 'cycle_shift_phase', 'cycle_change_frequency', 'cycle_add_harmonics', 'cycle_remove_harmonics', 'cycle_damp', 'cycle_amplify'],
    transient: ['transient_scale', 'transient_shift_onset', 'transient_change_duration', 'transient_smooth_onset', 'transient_sharpen_onset'],
    noise:     ['noise_rescale', 'noise_filter', 'noise_change_distribution', 'noise_add_periodic', 'noise_denoise'],
  });
});

// ─── Per-shape single-select: enabled ops + disabled non-ops ──────────────────

for (const shape of ALL_SHAPES) {
  test(`single ${shape}: isEnabled true for all its own ops`, () => {
    const { isEnabled } = createShapeGatingState([shape]);
    for (const name of SHAPE_GATING_TABLE[shape]) {
      assert.equal(isEnabled(name), true, `${name} should be enabled for ${shape}`);
    }
  });

  test(`single ${shape}: isEnabled false for ops belonging to other shapes`, () => {
    const { isEnabled } = createShapeGatingState([shape]);
    const otherOps = Object.entries(SHAPE_GATING_TABLE)
      .filter(([s]) => s !== shape)
      .flatMap(([, ops]) => ops);
    for (const name of otherOps) {
      assert.equal(isEnabled(name), false, `${name} should be disabled for ${shape}`);
    }
  });

  test(`single ${shape}: tooltipIfDisabled returns null for own ops`, () => {
    const { tooltipIfDisabled } = createShapeGatingState([shape]);
    for (const name of SHAPE_GATING_TABLE[shape]) {
      assert.equal(tooltipIfDisabled(name), null, `${name} should have no tooltip for ${shape}`);
    }
  });

  test(`single ${shape}: tooltipIfDisabled mentions active shape for disabled ops`, () => {
    const { tooltipIfDisabled } = createShapeGatingState([shape]);
    const otherOps = Object.entries(SHAPE_GATING_TABLE)
      .filter(([s]) => s !== shape)
      .flatMap(([, ops]) => ops);
    for (const name of otherOps) {
      const tip = tooltipIfDisabled(name);
      assert.ok(tip !== null, `${name} should have a tooltip when ${shape} is active`);
      assert.ok(tip.includes(shape), `tooltip for ${name} should mention ${shape}, got: ${tip}`);
    }
  });
}

// ─── Multi-select intersection tests for each pair with no shared ops ─────────

test('multi-select plateau+trend: no shared ops → all ops disabled', () => {
  const { isEnabled } = createShapeGatingState(['plateau', 'trend']);
  for (const name of [...SHAPE_GATING_TABLE.plateau, ...SHAPE_GATING_TABLE.trend]) {
    assert.equal(isEnabled(name), false);
  }
});

test('multi-select step+spike: no shared ops → intersection is empty', () => {
  const ops = computeLegalOps(['step', 'spike']);
  assert.equal(ops.size, 0);
});

test('multi-select transient+noise: no shared ops → intersection is empty', () => {
  const ops = computeLegalOps(['transient', 'noise']);
  assert.equal(ops.size, 0);
});

test('multi-select tooltip mentions all active shapes when empty intersection', () => {
  const { tooltipIfDisabled } = createShapeGatingState(['trend', 'noise']);
  const tip = tooltipIfDisabled('trend_change_slope');
  assert.ok(tip !== null);
  assert.ok(tip.includes('trend'), `tip should mention trend: ${tip}`);
  assert.ok(tip.includes('noise'), `tip should mention noise: ${tip}`);
});

// ─── computeLegalOps null / undefined guards ──────────────────────────────────

test('computeLegalOps(null) returns empty set', () => {
  assert.equal(computeLegalOps(null).size, 0);
});

test('computeLegalOps(undefined) returns empty set', () => {
  assert.equal(computeLegalOps(undefined).size, 0);
});

test('computeLegalOps with one unknown shape returns empty set', () => {
  assert.equal(computeLegalOps(['unknown_shape']).size, 0);
});

test('computeLegalOps mixed known+unknown shape: treats unknown as empty set', () => {
  const ops = computeLegalOps(['plateau', 'unknown_shape']);
  assert.equal(ops.size, 0);
});
