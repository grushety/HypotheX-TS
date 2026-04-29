import test from 'node:test';
import assert from 'node:assert/strict';

import { createDecompositionEditorState } from './createDecompositionEditorState.js';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const ETM_3_COMPONENT_BLOB = {
  method: 'ETM',
  components: {
    linear_rate: [0, 0.5, 1.0, 1.5, 2.0],
    step_at_100: [0, 0, 0, 1, 1],
    residual: [0.05, -0.03, 0.02, -0.01, 0.04],
  },
  coefficients: {
    x0: 10.0,
    linear_rate: 0.5,
    step_at_100: 2.5,
  },
  fit_metadata: { rmse: 0.035 },
};

const STL_BLOB = {
  method: 'STL',
  components: {
    trend: [5, 5.1, 5.2, 5.3, 5.4],
    seasonal: [0.3, -0.3, 0.3, -0.3, 0.3],
    residual: [0.01, -0.01, 0.005, -0.005, 0.002],
  },
  coefficients: {
    period: 12,
    amplitude: 1.0,
    phase: 0.0,
  },
  fit_metadata: { rmse: 0.01 },
};

const TRANSIENT_BLOB = {
  method: 'ETM',
  components: {
    linear_rate: [0, 0.1, 0.2],
    log_60_tau20: [0.8, 0.5, 0.3],
    residual: [0.01, -0.01, 0.005],
  },
  coefficients: {
    x0: 0,
    linear_rate: 0.1,
    log_60_tau20: 1.2,
  },
  fit_metadata: {},
};

// ---------------------------------------------------------------------------
// Fixture test 1 — load ETM blob with 3 components → 3 editor rows
// ---------------------------------------------------------------------------

test('ETM blob with 3 components produces 3 editor rows', () => {
  const state = createDecompositionEditorState(ETM_3_COMPONENT_BLOB);
  assert.equal(state.rows.length, 3);
});

test('ETM blob rows have correct component types', () => {
  const state = createDecompositionEditorState(ETM_3_COMPONENT_BLOB);
  const byKey = Object.fromEntries(state.rows.map((r) => [r.componentKey, r]));
  assert.equal(byKey['linear_rate'].componentType, 'linear');
  assert.equal(byKey['step_at_100'].componentType, 'step');
  assert.equal(byKey['residual'].componentType, 'residual');
});

// ---------------------------------------------------------------------------
// Fixture test 2 — edit slope slider → backend receives `change_slope` call
// ---------------------------------------------------------------------------

test('slope handle emits change_slope op with alpha param', () => {
  const state = createDecompositionEditorState(ETM_3_COMPONENT_BLOB);
  const payload = state.getOpInvoked('linear_rate', 'slope', 0.8, 'seg-001');
  assert.ok(payload, 'payload should not be null');
  assert.equal(payload.op_name, 'change_slope');
  assert.equal(payload.params.alpha, 0.8);
  assert.equal(payload.segmentId, 'seg-001');
});

// ---------------------------------------------------------------------------
// Fixture test 3 — reset → original coefficients restored
// ---------------------------------------------------------------------------

test('getResetOp returns reset_component with original coefficients', () => {
  const state = createDecompositionEditorState(ETM_3_COMPONENT_BLOB);
  const reset = state.getResetOp('linear_rate', 'seg-001');
  assert.ok(reset, 'reset payload should not be null');
  assert.equal(reset.op_name, 'reset_component');
  assert.equal(reset.params.componentKey, 'linear_rate');
  assert.equal(reset.segmentId, 'seg-001');
  assert.ok('originalCoefficients' in reset.params, 'should include originalCoefficients');
  assert.equal(reset.params.originalCoefficients.slope, 0.5);
});

// ---------------------------------------------------------------------------
// Component type detection
// ---------------------------------------------------------------------------

test('STL blob produces linear row for trend key', () => {
  const state = createDecompositionEditorState(STL_BLOB);
  const trend = state.rows.find((r) => r.componentKey === 'trend');
  assert.ok(trend, 'trend row should exist');
  assert.equal(trend.componentType, 'linear');
});

test('STL blob produces seasonal row for seasonal key', () => {
  const state = createDecompositionEditorState(STL_BLOB);
  const seasonal = state.rows.find((r) => r.componentKey === 'seasonal');
  assert.ok(seasonal, 'seasonal row should exist');
  assert.equal(seasonal.componentType, 'seasonal');
});

test('seasonal row has amplitude, phase, period handles', () => {
  const state = createDecompositionEditorState(STL_BLOB);
  const seasonal = state.rows.find((r) => r.componentKey === 'seasonal');
  const handleNames = seasonal.handles.map((h) => h.name);
  assert.ok(handleNames.includes('amplitude'));
  assert.ok(handleNames.includes('phase'));
  assert.ok(handleNames.includes('period'));
});

test('amplitude handle emits amplify_amplitude op', () => {
  const state = createDecompositionEditorState(STL_BLOB);
  const payload = state.getOpInvoked('seasonal', 'amplitude', 1.5, 'seg-002');
  assert.equal(payload.op_name, 'amplify_amplitude');
  assert.equal(payload.params.factor, 1.5);
});

test('phase handle emits phase_shift op', () => {
  const state = createDecompositionEditorState(STL_BLOB);
  const payload = state.getOpInvoked('seasonal', 'phase', 0.3, 'seg-002');
  assert.equal(payload.op_name, 'phase_shift');
  assert.equal(payload.params.delta_phase, 0.3);
});

test('period handle emits change_period op', () => {
  const state = createDecompositionEditorState(STL_BLOB);
  const payload = state.getOpInvoked('seasonal', 'period', 24, 'seg-002');
  assert.equal(payload.op_name, 'change_period');
  assert.equal(payload.params.new_period, 24);
});

// ---------------------------------------------------------------------------
// Step component
// ---------------------------------------------------------------------------

test('step component has magnitude and shift handles', () => {
  const state = createDecompositionEditorState(ETM_3_COMPONENT_BLOB);
  const step = state.rows.find((r) => r.componentKey === 'step_at_100');
  const handleNames = step.handles.map((h) => h.name);
  assert.ok(handleNames.includes('magnitude'));
  assert.ok(handleNames.includes('shift'));
});

test('step magnitude handle emits scale_magnitude with feature_id', () => {
  const state = createDecompositionEditorState(ETM_3_COMPONENT_BLOB);
  const payload = state.getOpInvoked('step_at_100', 'magnitude', 1.5, 'seg-001');
  assert.equal(payload.op_name, 'scale_magnitude');
  assert.equal(payload.params.factor, 1.5);
  assert.equal(payload.params.feature_id, 'step_at_100');
});

test('step shift handle emits shift_in_time with feature_id', () => {
  const state = createDecompositionEditorState(ETM_3_COMPONENT_BLOB);
  const payload = state.getOpInvoked('step_at_100', 'shift', 5, 'seg-001');
  assert.equal(payload.op_name, 'shift_in_time');
  assert.equal(payload.params.delta_t, 5);
  assert.equal(payload.params.feature_id, 'step_at_100');
});

// ---------------------------------------------------------------------------
// Transient component
// ---------------------------------------------------------------------------

test('transient key produces transient row', () => {
  const state = createDecompositionEditorState(TRANSIENT_BLOB);
  const transient = state.rows.find((r) => r.componentKey === 'log_60_tau20');
  assert.ok(transient, 'transient row should exist');
  assert.equal(transient.componentType, 'transient');
});

test('transient amplitude handle emits amplify with feature_id', () => {
  const state = createDecompositionEditorState(TRANSIENT_BLOB);
  const payload = state.getOpInvoked('log_60_tau20', 'amplitude', 1.5, 'seg-003');
  assert.equal(payload.op_name, 'amplify');
  assert.equal(payload.params.factor, 1.5);
  assert.equal(payload.params.feature_id, 'log_60_tau20');
});

test('transient tau parsed from key name', () => {
  const state = createDecompositionEditorState(TRANSIENT_BLOB);
  const transient = state.rows.find((r) => r.componentKey === 'log_60_tau20');
  const tauHandle = transient.handles.find((h) => h.name === 'tau');
  assert.ok(tauHandle, 'tau handle should exist');
  assert.equal(tauHandle.currentValue, 20);
});

test('transient tau handle emits change_decay_constant', () => {
  const state = createDecompositionEditorState(TRANSIENT_BLOB);
  const payload = state.getOpInvoked('log_60_tau20', 'tau', 30, 'seg-003');
  assert.equal(payload.op_name, 'change_decay_constant');
  assert.equal(payload.params.tau, 30);
  assert.equal(payload.params.feature_id, 'log_60_tau20');
});

// ---------------------------------------------------------------------------
// Residual display
// ---------------------------------------------------------------------------

test('residual row is read-only with no handles', () => {
  const state = createDecompositionEditorState(ETM_3_COMPONENT_BLOB);
  const residual = state.rows.find((r) => r.componentKey === 'residual');
  assert.equal(residual.readOnly, true);
  assert.equal(residual.handles.length, 0);
});

test('residual row exposes component values array', () => {
  const state = createDecompositionEditorState(ETM_3_COMPONENT_BLOB);
  const residual = state.rows.find((r) => r.componentKey === 'residual');
  assert.ok(Array.isArray(residual.componentValues));
  assert.equal(residual.componentValues.length, 5);
});

// ---------------------------------------------------------------------------
// Guard — missing / null blob
// ---------------------------------------------------------------------------

test('null blob returns empty rows without throwing', () => {
  const state = createDecompositionEditorState(null);
  assert.equal(state.rows.length, 0);
});

test('empty blob returns empty rows without throwing', () => {
  const state = createDecompositionEditorState({});
  assert.equal(state.rows.length, 0);
});

// ---------------------------------------------------------------------------
// getOpInvoked / getResetOp guard — unknown key
// ---------------------------------------------------------------------------

test('getOpInvoked returns null for unknown component key', () => {
  const state = createDecompositionEditorState(ETM_3_COMPONENT_BLOB);
  assert.equal(state.getOpInvoked('nonexistent', 'slope', 1.0, 'seg-1'), null);
});

test('getOpInvoked returns null for unknown handle name', () => {
  const state = createDecompositionEditorState(ETM_3_COMPONENT_BLOB);
  assert.equal(state.getOpInvoked('linear_rate', 'nonexistent', 1.0, 'seg-1'), null);
});

test('getResetOp returns null for unknown component key', () => {
  const state = createDecompositionEditorState(ETM_3_COMPONENT_BLOB);
  assert.equal(state.getResetOp('nonexistent', 'seg-1'), null);
});

// ---------------------------------------------------------------------------
// Slope coefficient extraction from blob
// ---------------------------------------------------------------------------

test('slope handle reads linear_rate coefficient from ETM blob', () => {
  const state = createDecompositionEditorState(ETM_3_COMPONENT_BLOB);
  const linear = state.rows.find((r) => r.componentKey === 'linear_rate');
  const slopeHandle = linear.handles.find((h) => h.name === 'slope');
  assert.equal(slopeHandle.currentValue, 0.5);
});

// ---------------------------------------------------------------------------
// Component values forwarded
// ---------------------------------------------------------------------------

test('component values are forwarded from blob.components', () => {
  const state = createDecompositionEditorState(ETM_3_COMPONENT_BLOB);
  const linear = state.rows.find((r) => r.componentKey === 'linear_rate');
  assert.deepEqual(linear.componentValues, [0, 0.5, 1.0, 1.5, 2.0]);
});
