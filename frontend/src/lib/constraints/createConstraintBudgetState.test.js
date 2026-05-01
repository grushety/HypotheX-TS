import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_TOLERANCE,
  FILL_CAP,
  HARD_LAWS,
  SOFT_LAWS,
  STATUS,
  SUPPORTED_BREAKDOWN_LAWS,
  buildBreakdown,
  classifyDirection,
  classifyResidual,
  createConstraintBudgetState,
  formatResidual,
} from './createConstraintBudgetState.js';

// ─── Hard / soft law partition ──────────────────────────────────────────────

test('phase_closure and nnr_frame are hard laws', () => {
  assert.ok(HARD_LAWS.has('phase_closure'));
  assert.ok(HARD_LAWS.has('nnr_frame'));
});

test('water_balance and moment_balance are soft laws', () => {
  assert.ok(SOFT_LAWS.has('water_balance'));
  assert.ok(SOFT_LAWS.has('moment_balance'));
});

test('hard and soft law sets are disjoint', () => {
  for (const law of HARD_LAWS) {
    assert.equal(SOFT_LAWS.has(law), false, `${law} should not be in both sets`);
  }
});

// ─── classifyResidual ───────────────────────────────────────────────────────

test('classifyResidual: residual within tolerance → green', () => {
  assert.equal(classifyResidual(0.05, 0.1, 'phase_closure'), STATUS.GREEN);
  assert.equal(classifyResidual(1e-7, 1e-6, 'water_balance'), STATUS.GREEN);
});

test('classifyResidual: hard law violated → red', () => {
  assert.equal(classifyResidual(0.5, 0.1, 'phase_closure'), STATUS.RED);
  assert.equal(classifyResidual(1.0, 1e-9, 'nnr_frame'), STATUS.RED);
});

test('classifyResidual: soft law violated → amber', () => {
  assert.equal(classifyResidual(2.0, 1e-6, 'water_balance'), STATUS.AMBER);
  assert.equal(classifyResidual(0.5, 1e-9, 'moment_balance'), STATUS.AMBER);
});

test('classifyResidual: zero residual → green', () => {
  assert.equal(classifyResidual(0, 1e-6, 'water_balance'), STATUS.GREEN);
  assert.equal(classifyResidual(0, 0.1, 'phase_closure'), STATUS.GREEN);
});

test('classifyResidual: exact-tolerance residual → green (boundary inclusive)', () => {
  assert.equal(classifyResidual(0.1, 0.1, 'phase_closure'), STATUS.GREEN);
});

test('classifyResidual: just-over-tolerance hard law → red', () => {
  assert.equal(classifyResidual(0.10001, 0.1, 'phase_closure'), STATUS.RED);
});

test('classifyResidual: unknown law treated as soft (amber on violation)', () => {
  assert.equal(classifyResidual(2.0, 1e-6, 'unknown_law'), STATUS.AMBER);
});

test('classifyResidual: NaN residual → amber (defensive)', () => {
  assert.equal(classifyResidual(NaN, 1e-6, 'water_balance'), STATUS.AMBER);
});

test('classifyResidual: negative residual → magnitude considered', () => {
  assert.equal(classifyResidual(-0.05, 0.1, 'phase_closure'), STATUS.GREEN);
  assert.equal(classifyResidual(-2.0, 0.1, 'phase_closure'), STATUS.RED);
});

// ─── formatResidual ─────────────────────────────────────────────────────────

test('formatResidual: large value uses fixed notation', () => {
  assert.equal(formatResidual(123.456), '123.456');
});

test('formatResidual: small value uses scientific notation', () => {
  const formatted = formatResidual(1.234e-7);
  assert.match(formatted, /^1\.23e-7$/);
});

test('formatResidual: mid-range value uses 4-decimal fixed', () => {
  assert.equal(formatResidual(0.05), '0.0500');
});

test('formatResidual: zero is formatted as "0"', () => {
  assert.equal(formatResidual(0), '0');
});

test('formatResidual: null and NaN render as em-dash', () => {
  assert.equal(formatResidual(null), '—');
  assert.equal(formatResidual(NaN), '—');
});

test('formatResidual: negative values keep their sign', () => {
  assert.equal(formatResidual(-0.5), '-0.5000');
});

test('formatResidual: appends units when provided', () => {
  assert.equal(formatResidual(1.5, 'mm/day'), '1.500 mm/day');
});

// ─── classifyDirection ──────────────────────────────────────────────────────

test('classifyDirection: smaller-magnitude final → improving', () => {
  assert.equal(classifyDirection(1.0, 0.1), 'improving');
  assert.equal(classifyDirection(-1.0, 0.1), 'improving');
});

test('classifyDirection: larger-magnitude final → worsening', () => {
  assert.equal(classifyDirection(0.1, 0.5), 'worsening');
});

test('classifyDirection: equal magnitude → unchanged', () => {
  assert.equal(classifyDirection(0.5, 0.5), 'unchanged');
  assert.equal(classifyDirection(0.5, -0.5), 'unchanged');
});

// ─── createConstraintBudgetState — basic shape ──────────────────────────────

test('createConstraintBudgetState: returns the documented field set', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    compensationMode: 'local',
    initialResidual: 1.0,
    finalResidual: 0.0,
    tolerance: 1e-6,
  });
  for (const key of [
    'law', 'compensationMode', 'status', 'initialStatus', 'initial', 'final',
    'tolerance', 'fillFraction', 'initialFillFraction', 'showPrePost',
    'direction', 'formattedResidual', 'formattedInitial', 'formattedTolerance',
    'ariaText', 'hoverText', 'isHardLaw', 'isSoftLaw',
  ]) {
    assert.ok(key in state, `missing key ${key}`);
  }
});

test('createConstraintBudgetState: green status when within tolerance', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    compensationMode: 'local',
    initialResidual: 1e-7,
    finalResidual: 1e-8,
    tolerance: 1e-6,
  });
  assert.equal(state.status, STATUS.GREEN);
});

test('createConstraintBudgetState: red status for hard law over tolerance', () => {
  const state = createConstraintBudgetState({
    law: 'phase_closure',
    compensationMode: 'naive',
    initialResidual: 0.5,
    finalResidual: 0.5,
  });
  assert.equal(state.status, STATUS.RED);
});

test('createConstraintBudgetState: amber status for soft law over tolerance', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    compensationMode: 'naive',
    initialResidual: 1.0,
    finalResidual: 1.0,
  });
  assert.equal(state.status, STATUS.AMBER);
});

// ─── createConstraintBudgetState — compensation modes ───────────────────────

test('createConstraintBudgetState: showPrePost is false in naive mode', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    compensationMode: 'naive',
    initialResidual: 1.0,
    finalResidual: 1.0,
    tolerance: 1e-6,
  });
  assert.equal(state.showPrePost, false);
});

test('createConstraintBudgetState: showPrePost is true in local mode with both residuals', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    compensationMode: 'local',
    initialResidual: 1.0,
    finalResidual: 0.0,
    tolerance: 1e-6,
  });
  assert.equal(state.showPrePost, true);
});

test('createConstraintBudgetState: showPrePost is true in coupled mode with both residuals', () => {
  const state = createConstraintBudgetState({
    law: 'moment_balance',
    compensationMode: 'coupled',
    initialResidual: 6.0,
    finalResidual: 0.0,
    tolerance: 1e-9,
  });
  assert.equal(state.showPrePost, true);
});

test('createConstraintBudgetState: showPrePost is false when initial is missing', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    compensationMode: 'coupled',
    finalResidual: 0.5,
    tolerance: 1e-6,
  });
  assert.equal(state.showPrePost, false);
});

// ─── createConstraintBudgetState — direction ────────────────────────────────

test('createConstraintBudgetState: direction "improving" when final < initial', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    compensationMode: 'local',
    initialResidual: 5.0,
    finalResidual: 0.5,
  });
  assert.equal(state.direction, 'improving');
});

test('createConstraintBudgetState: direction "worsening" when final > initial', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    compensationMode: 'local',
    initialResidual: 0.5,
    finalResidual: 5.0,
  });
  assert.equal(state.direction, 'worsening');
});

// ─── createConstraintBudgetState — fill fractions ───────────────────────────

test('createConstraintBudgetState: fillFraction caps at FILL_CAP', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    finalResidual: 1e6,
    tolerance: 1e-6,
  });
  assert.equal(state.fillFraction, FILL_CAP);
});

test('createConstraintBudgetState: residual at tolerance → fillFraction = 1', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    finalResidual: 1e-6,
    tolerance: 1e-6,
  });
  assert.equal(state.fillFraction, 1.0);
});

test('createConstraintBudgetState: zero residual → fillFraction = 0', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    finalResidual: 0,
    tolerance: 1e-6,
  });
  assert.equal(state.fillFraction, 0);
});

// ─── createConstraintBudgetState — text & aria ──────────────────────────────

test('createConstraintBudgetState: hoverText matches the AC format string', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    compensationMode: 'naive',
    initialResidual: 0.023,
    finalResidual: 0.023,
    tolerance: 0.10,
    units: 'mm/day',
  });
  // Per AC: "Δ = 0.023 mm/day (of 0.10 tolerance)"
  assert.match(state.hoverText, /Δ = 0\.0230 mm\/day/);
  assert.match(state.hoverText, /\(of 0\.1000 mm\/day tolerance\)/);
});

test('createConstraintBudgetState: ariaText mentions both initial and final when showPrePost', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    compensationMode: 'local',
    initialResidual: 1.0,
    finalResidual: 0.0,
    tolerance: 1e-6,
  });
  assert.match(state.ariaText, /from 1\.000/);
  assert.match(state.ariaText, /to 0/);
});

test('createConstraintBudgetState: ariaText omits "from→to" in naive mode', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    compensationMode: 'naive',
    initialResidual: 1.0,
    finalResidual: 1.0,
  });
  assert.equal(/from /.test(state.ariaText), false);
});

// ─── createConstraintBudgetState — defaults & guards ────────────────────────

test('createConstraintBudgetState: tolerance defaults to DEFAULT_TOLERANCE[law]', () => {
  const state = createConstraintBudgetState({
    law: 'phase_closure',
    finalResidual: 0.05,
  });
  assert.equal(state.tolerance, DEFAULT_TOLERANCE.phase_closure);
});

test('createConstraintBudgetState: unknown law gets 1e-6 fallback tolerance', () => {
  const state = createConstraintBudgetState({
    law: 'unknown_law',
    finalResidual: 0,
  });
  assert.equal(state.tolerance, 1e-6);
});

test('createConstraintBudgetState: missing residuals → final defaults to initial', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
    initialResidual: 0.5,
  });
  assert.equal(state.final, 0.5);
});

test('createConstraintBudgetState: missing both residuals → status green by default', () => {
  const state = createConstraintBudgetState({
    law: 'water_balance',
  });
  assert.equal(state.status, STATUS.GREEN);
});

test('createConstraintBudgetState: isHardLaw and isSoftLaw flags set correctly', () => {
  const hard = createConstraintBudgetState({ law: 'phase_closure', finalResidual: 0 });
  const soft = createConstraintBudgetState({ law: 'water_balance', finalResidual: 0 });
  assert.equal(hard.isHardLaw, true);
  assert.equal(hard.isSoftLaw, false);
  assert.equal(soft.isHardLaw, false);
  assert.equal(soft.isSoftLaw, true);
});

// ─── buildBreakdown ─────────────────────────────────────────────────────────

test('buildBreakdown: water_balance returns 4 items in canonical order', () => {
  const result = buildBreakdown('water_balance', { P: 10, ET: 3, Q: 2, dS: 4 });
  assert.equal(result.supported, true);
  assert.equal(result.items.length, 4);
  assert.deepEqual(
    result.items.map((i) => i.key),
    ['P', 'ET', 'Q', 'dS'],
  );
});

test('buildBreakdown: water_balance signed values match the law equation', () => {
  const result = buildBreakdown('water_balance', { P: 10, ET: 3, Q: 2, dS: 4 });
  // P − ET − Q − ΔS = +10 −3 −2 −4 = 1
  assert.equal(result.total, 1);
  const map = Object.fromEntries(result.items.map((i) => [i.key, i.signedValue]));
  assert.equal(map.P, +10);
  assert.equal(map.ET, -3);
  assert.equal(map.Q, -2);
  assert.equal(map.dS, -4);
});

test('buildBreakdown: moment_balance returns trace components', () => {
  const result = buildBreakdown('moment_balance', { Mxx: 1, Myy: 2, Mzz: 3 });
  assert.equal(result.supported, true);
  assert.equal(result.total, 6);
  assert.deepEqual(
    result.items.map((i) => i.key),
    ['Mxx', 'Myy', 'Mzz'],
  );
});

test('buildBreakdown: phase_closure has phi_13 with sign -1', () => {
  const result = buildBreakdown('phase_closure', {
    phi_12: 0.5, phi_23: 0.4, phi_13: 0.6,
  });
  // closure = phi_12 + phi_23 - phi_13 = 0.3
  assert.equal(result.total.toFixed(6), '0.300000');
  const phi13 = result.items.find((i) => i.key === 'phi_13');
  assert.equal(phi13.sign, -1);
});

test('buildBreakdown: nnr_frame has all positive signs', () => {
  const result = buildBreakdown('nnr_frame', {
    omega_x: 0.1, omega_y: 0.2, omega_z: 0.3,
  });
  for (const item of result.items) assert.equal(item.sign, +1);
});

test('buildBreakdown: unknown law returns supported=false with empty items', () => {
  const result = buildBreakdown('not_a_law', { foo: 1 });
  assert.equal(result.supported, false);
  assert.deepEqual(result.items, []);
  assert.equal(result.total, 0);
});

test('buildBreakdown: skips components that are not finite numbers', () => {
  const result = buildBreakdown('water_balance', { P: 10, ET: NaN, Q: null, dS: 4 });
  const keys = result.items.map((i) => i.key);
  assert.ok(keys.includes('P'));
  assert.ok(keys.includes('dS'));
  assert.ok(!keys.includes('ET'));
  assert.ok(!keys.includes('Q'));
});

test('buildBreakdown: empty components → empty items, total = 0', () => {
  const result = buildBreakdown('water_balance', {});
  assert.deepEqual(result.items, []);
  assert.equal(result.total, 0);
});

test('buildBreakdown: emits formatted strings ready for the UI', () => {
  const result = buildBreakdown('water_balance', { P: 10, ET: 3, Q: 2, dS: 4 });
  for (const item of result.items) {
    assert.equal(typeof item.formatted, 'string');
    assert.equal(typeof item.formattedSigned, 'string');
  }
  assert.equal(typeof result.formattedTotal, 'string');
});

test('SUPPORTED_BREAKDOWN_LAWS lists every law with a breakdown config', () => {
  for (const law of ['water_balance', 'moment_balance', 'phase_closure', 'nnr_frame']) {
    assert.ok(SUPPORTED_BREAKDOWN_LAWS.includes(law));
  }
});
