/**
 * Pure state logic for the decomposition editor (UI-007 / Screen D).
 *
 * Converts a DecompositionBlob into an array of typed component editor rows,
 * each carrying its edit handles.  Handle changes produce op-invoked payloads
 * that map to Tier-2 backend ops (OP-021..025).
 *
 * Component type detection:
 *   linear   — 'linear_rate' (ETM), 'trend' (STL/MSTL/Constant), 'linear'
 *   seasonal — 'seasonal' (STL), 'seasonal_{T}' (MSTL)
 *   step     — 'step_at_{t_s}' (ETM)
 *   transient— 'log_{t}_{tau}', 'exp_{t}_{tau}' (ETM),  'transient_*' (GrAtSiD)
 *   residual — 'residual', unknown keys
 */

const HANDLE_DEFS = {
  linear: [
    {
      name: 'slope',
      label: 'Slope',
      opName: 'change_slope',
      paramKey: 'alpha',
      coeffKey: 'linear_rate',
      altCoeffKeys: ['slope_1', 'slope', 'linear_rate'],
      fallback: 0,
      min: -10,
      max: 10,
      step: 0.01,
    },
  ],
  seasonal: [
    {
      name: 'amplitude',
      label: 'Amplitude factor',
      opName: 'amplify_amplitude',
      paramKey: 'factor',
      coeffKey: 'amplitude',
      altCoeffKeys: [],
      fallback: 1,
      min: 0,
      max: 5,
      step: 0.05,
    },
    {
      name: 'phase',
      label: 'Phase shift (rad)',
      opName: 'phase_shift',
      paramKey: 'delta_phase',
      coeffKey: 'phase',
      altCoeffKeys: [],
      fallback: 0,
      min: -3.14159,
      max: 3.14159,
      step: 0.01,
    },
    {
      name: 'period',
      label: 'Period (samples)',
      opName: 'change_period',
      paramKey: 'new_period',
      coeffKey: 'period',
      altCoeffKeys: [],
      fallback: 12,
      min: 2,
      max: 365,
      step: 1,
    },
  ],
  step: [
    {
      name: 'magnitude',
      label: 'Magnitude factor',
      opName: 'scale_magnitude',
      paramKey: 'factor',
      coeffKey: null,
      altCoeffKeys: [],
      fallback: 1,
      min: -5,
      max: 5,
      step: 0.05,
    },
    {
      name: 'shift',
      label: 'Time shift (samples)',
      opName: 'shift_in_time',
      paramKey: 'delta_t',
      coeffKey: null,
      altCoeffKeys: [],
      fallback: 0,
      min: -50,
      max: 50,
      step: 1,
    },
  ],
  transient: [
    {
      name: 'amplitude',
      label: 'Amplitude factor',
      opName: 'amplify',
      paramKey: 'factor',
      coeffKey: null,
      altCoeffKeys: [],
      fallback: 1,
      min: 0,
      max: 5,
      step: 0.05,
    },
    {
      name: 'tau',
      label: 'Decay constant (τ)',
      opName: 'change_decay_constant',
      paramKey: 'tau',
      coeffKey: null,
      altCoeffKeys: [],
      fallback: 10,
      min: 0.5,
      max: 200,
      step: 0.5,
    },
  ],
  residual: [],
};

const COMPONENT_LABELS = {
  linear: 'Linear trend',
  seasonal: 'Seasonal',
  step: 'Step',
  transient: 'Transient',
  residual: 'Residual',
};

function detectComponentType(key) {
  if (key === 'residual') return 'residual';
  if (key === 'linear_rate' || key === 'trend' || key === 'linear') return 'linear';
  if (key === 'seasonal' || key.startsWith('seasonal_')) return 'seasonal';
  if (key.startsWith('step_at_') || key === 'step') return 'step';
  if (key.startsWith('log_') || key.startsWith('exp_') || key.startsWith('transient_')) return 'transient';
  return 'residual';
}

function parseTauFromKey(key) {
  const m = key.match(/(?:_tau|_)(\d+(?:\.\d+)?)$/);
  return m ? parseFloat(m[1]) : null;
}

function resolveHandleValue(handleDef, componentKey, coefficients) {
  if (handleDef.name === 'tau') {
    const fromKey = parseTauFromKey(componentKey);
    if (fromKey != null) return fromKey;
    return coefficients['tau'] ?? handleDef.fallback;
  }

  if (handleDef.coeffKey !== null) {
    for (const k of [handleDef.coeffKey, ...handleDef.altCoeffKeys]) {
      if (k in coefficients) return coefficients[k];
    }
  }

  if (componentKey in coefficients) return coefficients[componentKey];

  return handleDef.fallback;
}

function buildHandles(componentType, componentKey, coefficients) {
  return (HANDLE_DEFS[componentType] ?? []).map((def) => ({
    name: def.name,
    label: def.label,
    opName: def.opName,
    paramKey: def.paramKey,
    min: def.min,
    max: def.max,
    step: def.step,
    currentValue: resolveHandleValue(def, componentKey, coefficients),
    originalValue: resolveHandleValue(def, componentKey, coefficients),
  }));
}

function buildRow(componentKey, componentValues, coefficients) {
  const componentType = detectComponentType(componentKey);
  const handles = buildHandles(componentType, componentKey, coefficients);
  const originalCoefficientValues = Object.fromEntries(
    handles.map((h) => [h.name, h.originalValue]),
  );

  return {
    componentKey,
    componentType,
    label: `${COMPONENT_LABELS[componentType] ?? componentType} (${componentKey})`,
    handles,
    componentValues: Array.isArray(componentValues) ? componentValues : [],
    originalCoefficientValues,
    readOnly: componentType === 'residual',
  };
}

export function createDecompositionEditorState(blob) {
  if (!blob || typeof blob !== 'object') {
    return { rows: [], getOpInvoked: () => null, getResetOp: () => null };
  }

  const components = blob.components ?? {};
  const coefficients = blob.coefficients ?? {};

  const rows = Object.entries(components).map(([key, values]) =>
    buildRow(key, values, coefficients),
  );

  const rowByKey = new Map(rows.map((r) => [r.componentKey, r]));

  function getOpInvoked(componentKey, handleName, newValue, segmentId) {
    const row = rowByKey.get(componentKey);
    if (!row) return null;
    const handle = row.handles.find((h) => h.name === handleName);
    if (!handle) return null;

    const params = { [handle.paramKey]: newValue };
    if (row.componentType === 'step' || row.componentType === 'transient') {
      params.feature_id = componentKey;
    }

    return { op_name: handle.opName, params, segmentId };
  }

  function getResetOp(componentKey, segmentId) {
    const row = rowByKey.get(componentKey);
    if (!row) return null;
    return {
      op_name: 'reset_component',
      params: {
        componentKey,
        originalCoefficients: { ...row.originalCoefficientValues },
      },
      segmentId,
    };
  }

  return { rows, getOpInvoked, getResetOp };
}

export const PREVIEW_DEBOUNCE_MS = 80;
