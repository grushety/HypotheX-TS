/**
 * Build a JSON body for ``POST /api/operations/invoke`` from the UI state.
 *
 * Pure module — no Vue, no fetch — so it can be unit-tested standalone.
 *
 * Resolves three concerns the dispatcher in ``BenchmarkViewerPage`` would
 * otherwise have to handle inline:
 *
 *   1. Picker-bound ops route to ``{ kind: 'picker-pending' }`` instead of
 *      a request body. HTS-104 / HTS-105 / HTS-106 wire those pickers.
 *   2. Per-op default params are filled in for button-only ops the user
 *      clicks without slider input (e.g. ``mute_zero``, ``reverse_time``).
 *   3. Unknown op names are rejected up-front so the route layer never
 *      sees them — the user gets a ``"unknown op"`` message synchronously.
 *
 * The op_name set must stay in sync with the backend ``_TIER1_REGISTRY``
 * / ``_TIER2_REGISTRY`` and the Tier-3 op list in ``invoke_service.py``.
 */
function segmentIsGapHeavy(gapInfo) {
  return Boolean(gapInfo && gapInfo.exceedsThreshold && !gapInfo.isFilled);
}

const TIER1_OPS = new Set([
  'scale',
  'offset',
  'mute_zero',
  'time_shift',
  'reverse_time',
  'resample',
  'suppress',
  'add_uncertainty',
  'replace_from_library',
]);

const TIER2_OPS = new Set([
  // plateau
  'plateau_scale',
  'plateau_remove_drift',
  'plateau_flatten',
  'plateau_add_seasonal',
  // trend
  'trend_change_slope',
  'trend_reverse',
  'trend_detrend',
  'trend_fit_piecewise',
  // step
  'step_remove',
  'step_adjust_height',
  'step_smooth',
  // spike
  'spike_remove',
  'spike_scale',
  'spike_widen',
  // cycle
  'cycle_shift_phase',
  'cycle_amplify',
  'cycle_damp',
  'cycle_change_frequency',
  'cycle_remove_harmonics',
  'cycle_add_harmonics',
  // transient
  'transient_change_duration',
  'transient_scale',
  'transient_shift_onset',
  // noise
  'noise_denoise',
  'noise_rescale',
  'noise_filter',
  // slider commit aliases (UI-016)
  'amplify_amplitude',
]);

const TIER3_OPS = new Set([
  'decompose',
  'align_warp',
  'enforce_conservation',
  'aggregate',
]);

/** Ops that need a picker before the dispatcher can build a request body. */
const PICKER_BOUND_OPS = new Set(['replace_from_library', 'decompose', 'align_warp']);

export class UnknownOpError extends Error {
  constructor(opName) {
    super(`Unknown op: ${opName}`);
    this.name = 'UnknownOpError';
    this.opName = opName;
  }
}

/** Default params for button-only ops the user can click without slider input. */
function defaultParamsFor(opName, params = {}) {
  if (opName === 'mute_zero') return { fill: 'zero', ...params };
  if (opName === 'reverse_time') return { ...params };
  if (opName === 'time_shift') return { delta_t: 1, ...params };
  if (opName === 'resample') return { new_dt: 1.0, old_dt: 1.0, method: 'antialiased', ...params };
  if (opName === 'add_uncertainty') return { sigma: 0.1, color: 'white', ...params };
  if (opName === 'offset') return { delta: 1.0, ...params };
  if (opName === 'scale') return { alpha: 1.0, ...params };
  if (opName === 'aggregate') return { metric: 'peak', ...params };
  return params;
}

/**
 * Build the request body or a picker-pending sentinel.
 *
 * @returns {{kind: 'request', body: object}} for a real backend dispatch
 * @returns {{kind: 'picker-pending', message: string}} when the op needs a picker first
 * @throws {UnknownOpError} if op_name is not in the dispatch table
 */
export function buildInvokeRequest({
  tier,
  op_name,
  params = {},
  sample,
  selectedSegment,
  allSegments = null,
  gapInfo = null,
  domain_hint = null,
  compensation_mode = null,
  target_class = null,
  bypassPickerCheck = false,
}) {
  const knownTiers = { 1: TIER1_OPS, 2: TIER2_OPS, 3: TIER3_OPS };
  const tierOps = knownTiers[tier];
  if (!tierOps) {
    throw new UnknownOpError(`tier=${tier} op=${op_name}`);
  }
  if (!tierOps.has(op_name)) {
    throw new UnknownOpError(op_name);
  }

  if (PICKER_BOUND_OPS.has(op_name) && !bypassPickerCheck) {
    return { kind: 'picker-pending', message: `${op_name}: picker pending` };
  }
  if (op_name === 'suppress' && segmentIsGapHeavy(gapInfo) && !bypassPickerCheck) {
    return { kind: 'picker-pending', message: 'suppress: GapFillPicker pending' };
  }

  if (!sample || !selectedSegment) {
    throw new Error('buildInvokeRequest: sample and selectedSegment are required.');
  }

  const segments = (allSegments ?? sample.segments ?? []).map((seg) => ({
    id: seg.id,
    start: seg.start,
    end: seg.end,
    label: seg.shape ?? seg.label ?? 'noise',
  }));

  const body = {
    series_id: sample.sampleId ?? sample.id ?? 'unknown',
    segment_id: selectedSegment.id,
    tier,
    op_name,
    params: defaultParamsFor(op_name, params),
    domain_hint,
    sample_values: Array.isArray(sample.values) ? sample.values : [],
    segments,
    compensation_mode,
    target_class,
  };
  return { kind: 'request', body };
}
