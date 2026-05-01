import test from 'node:test';
import assert from 'node:assert/strict';

import {
  COMPENSATION_MODES,
  MODE_LABELS,
  MODE_TOOLTIPS,
  createCompensationModeSelectorState,
  defaultModeForDomain,
  isCompensationRequired,
  isValidMode,
  nextMode,
} from './createCompensationModeSelectorState.js';

// ─── Constants ──────────────────────────────────────────────────────────────

test('COMPENSATION_MODES contains exactly naive / local / coupled in order', () => {
  assert.deepEqual([...COMPENSATION_MODES], ['naive', 'local', 'coupled']);
});

test('MODE_TOOLTIPS has the AC strings', () => {
  assert.equal(MODE_TOOLTIPS.naive, 'Report residual; do not adjust');
  assert.equal(MODE_TOOLTIPS.local, 'Adjust within this segment only');
  assert.equal(
    MODE_TOOLTIPS.coupled,
    'Adjust across all segments via conservation coupling',
  );
});

test('MODE_LABELS has a label for every mode', () => {
  for (const m of COMPENSATION_MODES) {
    assert.ok(MODE_LABELS[m], `missing label for ${m}`);
  }
});

// ─── isValidMode ────────────────────────────────────────────────────────────

test('isValidMode accepts all COMPENSATION_MODES', () => {
  for (const m of COMPENSATION_MODES) assert.equal(isValidMode(m), true);
});

test('isValidMode rejects unknown / null / undefined', () => {
  assert.equal(isValidMode('invalid'), false);
  assert.equal(isValidMode(null), false);
  assert.equal(isValidMode(undefined), false);
  assert.equal(isValidMode(''), false);
});

// ─── defaultModeForDomain ──────────────────────────────────────────────────

test('hydrology defaults to local', () => {
  assert.equal(defaultModeForDomain('hydrology'), 'local');
});

test('seismo-geodesy defaults to coupled (both hyphen and underscore)', () => {
  assert.equal(defaultModeForDomain('seismo-geodesy'), 'coupled');
  assert.equal(defaultModeForDomain('seismo_geodesy'), 'coupled');
  assert.equal(defaultModeForDomain('geodesy'), 'coupled');
});

test('remote-sensing defaults to local', () => {
  assert.equal(defaultModeForDomain('remote-sensing'), 'local');
  assert.equal(defaultModeForDomain('remote_sensing'), 'local');
});

test('unknown domain defaults to naive', () => {
  assert.equal(defaultModeForDomain('quantum_mechanics'), 'naive');
});

test('null and undefined domains default to naive', () => {
  assert.equal(defaultModeForDomain(null), 'naive');
  assert.equal(defaultModeForDomain(undefined), 'naive');
});

test('domain lookup is case-insensitive', () => {
  assert.equal(defaultModeForDomain('HYDROLOGY'), 'local');
  assert.equal(defaultModeForDomain('Seismo-Geodesy'), 'coupled');
});

// ─── isCompensationRequired ─────────────────────────────────────────────────

test('hydrology + plateau/trend/step/transient is required', () => {
  for (const op of ['plateau', 'trend', 'step', 'transient']) {
    assert.equal(isCompensationRequired('hydrology', op), true, op);
  }
});

test('seismo-geodesy + plateau/trend/step/transient is required', () => {
  for (const op of ['plateau', 'trend', 'step', 'transient']) {
    assert.equal(isCompensationRequired('seismo-geodesy', op), true, op);
  }
});

test('remote-sensing is NOT required even for the same op categories', () => {
  for (const op of ['plateau', 'trend', 'step', 'transient']) {
    assert.equal(isCompensationRequired('remote-sensing', op), false, op);
  }
});

test('hydrology + cycle/spike/noise are NOT required', () => {
  for (const op of ['cycle', 'spike', 'noise']) {
    assert.equal(isCompensationRequired('hydrology', op), false, op);
  }
});

test('null domain or null op_category is not required', () => {
  assert.equal(isCompensationRequired(null, 'plateau'), false);
  assert.equal(isCompensationRequired('hydrology', null), false);
  assert.equal(isCompensationRequired(null, null), false);
});

test('isCompensationRequired is case-insensitive on both args', () => {
  assert.equal(isCompensationRequired('HYDROLOGY', 'PLATEAU'), true);
});

// ─── nextMode ───────────────────────────────────────────────────────────────

test('nextMode +1 cycles forward through the modes', () => {
  assert.equal(nextMode('naive', 1), 'local');
  assert.equal(nextMode('local', 1), 'coupled');
  assert.equal(nextMode('coupled', 1), 'naive');
});

test('nextMode -1 cycles backward through the modes', () => {
  assert.equal(nextMode('naive', -1), 'coupled');
  assert.equal(nextMode('local', -1), 'naive');
  assert.equal(nextMode('coupled', -1), 'local');
});

test('nextMode from invalid current starts at index 0', () => {
  assert.equal(nextMode('invalid', 1), 'local');
  assert.equal(nextMode(null, 1), 'local');
});

// ─── createCompensationModeSelectorState — defaults ─────────────────────────

test('returns the documented field set', () => {
  const state = createCompensationModeSelectorState({
    domainHint: 'hydrology', opCategory: 'plateau',
  });
  for (const key of [
    'mode', 'defaultMode', 'isRequired', 'hasExplicitChoice',
    'canSubmit', 'choices',
  ]) {
    assert.ok(key in state, `missing key ${key}`);
  }
});

test('selector has 3 choices in the correct order', () => {
  const state = createCompensationModeSelectorState();
  const order = state.choices.map((c) => c.mode);
  assert.deepEqual(order, ['naive', 'local', 'coupled']);
});

test('hydrology domain pre-selects local with no explicit choice', () => {
  const state = createCompensationModeSelectorState({
    domainHint: 'hydrology', opCategory: 'plateau',
  });
  assert.equal(state.mode, 'local');
  assert.equal(state.defaultMode, 'local');
  assert.equal(state.hasExplicitChoice, false);
});

test('seismo-geodesy domain pre-selects coupled', () => {
  const state = createCompensationModeSelectorState({
    domainHint: 'seismo-geodesy', opCategory: 'step',
  });
  assert.equal(state.mode, 'coupled');
});

test('null domain pre-selects naive', () => {
  const state = createCompensationModeSelectorState({});
  assert.equal(state.mode, 'naive');
  assert.equal(state.defaultMode, 'naive');
});

test('explicit selectedMode overrides the domain default', () => {
  const state = createCompensationModeSelectorState({
    domainHint: 'hydrology',
    opCategory: 'plateau',
    selectedMode: 'naive',
  });
  assert.equal(state.mode, 'naive');
  assert.equal(state.defaultMode, 'local');
  assert.equal(state.hasExplicitChoice, true);
});

test('invalid selectedMode falls back to the domain default', () => {
  const state = createCompensationModeSelectorState({
    domainHint: 'hydrology',
    opCategory: 'plateau',
    selectedMode: 'quantum',
  });
  assert.equal(state.mode, 'local');
  assert.equal(state.hasExplicitChoice, false);
});

// ─── createCompensationModeSelectorState — required + canSubmit ─────────────

test('hydrology + plateau is required and not submittable until explicit choice', () => {
  const state = createCompensationModeSelectorState({
    domainHint: 'hydrology', opCategory: 'plateau',
  });
  assert.equal(state.isRequired, true);
  assert.equal(state.canSubmit, false);
});

test('hydrology + plateau becomes submittable once selectedMode is set', () => {
  const state = createCompensationModeSelectorState({
    domainHint: 'hydrology', opCategory: 'plateau',
    selectedMode: 'local',
  });
  assert.equal(state.isRequired, true);
  assert.equal(state.hasExplicitChoice, true);
  assert.equal(state.canSubmit, true);
});

test('hydrology + plateau is submittable when hasExplicitChoice forced true', () => {
  const state = createCompensationModeSelectorState({
    domainHint: 'hydrology', opCategory: 'plateau',
    hasExplicitChoice: true,
  });
  assert.equal(state.canSubmit, true);
});

test('non-required domains are always submittable', () => {
  const state = createCompensationModeSelectorState({
    domainHint: 'remote-sensing', opCategory: 'plateau',
  });
  assert.equal(state.isRequired, false);
  assert.equal(state.canSubmit, true);
});

test('non-required + no domain is submittable with naive default', () => {
  const state = createCompensationModeSelectorState({});
  assert.equal(state.isRequired, false);
  assert.equal(state.canSubmit, true);
  assert.equal(state.mode, 'naive');
});

test('canSubmit is true when explicit choice equals default', () => {
  const state = createCompensationModeSelectorState({
    domainHint: 'hydrology', opCategory: 'plateau',
    selectedMode: 'local',  // matches default but is explicit
  });
  assert.equal(state.canSubmit, true);
});

// ─── createCompensationModeSelectorState — choices array ────────────────────

test('exactly one choice has isSelected=true', () => {
  const state = createCompensationModeSelectorState({
    domainHint: 'hydrology', opCategory: 'plateau',
    selectedMode: 'coupled',
  });
  const selected = state.choices.filter((c) => c.isSelected);
  assert.equal(selected.length, 1);
  assert.equal(selected[0].mode, 'coupled');
});

test('exactly one choice has isRecommended=true (the domain default)', () => {
  const state = createCompensationModeSelectorState({
    domainHint: 'hydrology', opCategory: 'plateau',
  });
  const recommended = state.choices.filter((c) => c.isRecommended);
  assert.equal(recommended.length, 1);
  assert.equal(recommended[0].mode, 'local');
});

test('isSelected and isRecommended can disagree when user overrides default', () => {
  const state = createCompensationModeSelectorState({
    domainHint: 'hydrology', opCategory: 'plateau',
    selectedMode: 'naive',
  });
  const selected = state.choices.find((c) => c.isSelected);
  const recommended = state.choices.find((c) => c.isRecommended);
  assert.equal(selected.mode, 'naive');
  assert.equal(recommended.mode, 'local');
  assert.notEqual(selected.mode, recommended.mode);
});

test('every choice has tooltip, label, mode fields populated', () => {
  const state = createCompensationModeSelectorState({});
  for (const c of state.choices) {
    assert.equal(typeof c.mode, 'string');
    assert.equal(typeof c.label, 'string');
    assert.equal(typeof c.tooltip, 'string');
    assert.equal(c.tooltip.length > 0, true);
  }
});

// ─── Integration sanity ─────────────────────────────────────────────────────

test('selection change between modes flips the isSelected flag accordingly', () => {
  const before = createCompensationModeSelectorState({
    domainHint: 'hydrology', opCategory: 'plateau',
    selectedMode: 'local',
  });
  const after = createCompensationModeSelectorState({
    domainHint: 'hydrology', opCategory: 'plateau',
    selectedMode: 'coupled',
  });
  assert.equal(before.mode, 'local');
  assert.equal(after.mode, 'coupled');
  assert.equal(before.choices.find((c) => c.mode === 'local').isSelected, true);
  assert.equal(after.choices.find((c) => c.mode === 'coupled').isSelected, true);
});
