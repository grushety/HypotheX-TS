/**
 * Pure state for the donor-picker side panel (UI-008).
 *
 * The picker shows candidate donor signals from one of six backends for the
 * Tier-1 ``replace_from_library`` op (OP-012).  Three backends ship today
 * (NativeGuide / SETSDonor / DiscordDonor); ``TimeGAN`` and ``ShapeDBA``
 * are dropdown-reachable but raise ``NotImplemented`` from the backend
 * until their generators land.  ``UserDrawn`` is special: the donor curve
 * is sketched in the browser, so no network round-trip is needed.
 *
 * The state module is deliberately UI-framework-agnostic: it returns a
 * view model that the Vue component renders; all reactive bookkeeping
 * lives in the component.
 */

export const BACKEND_OPTIONS = Object.freeze([
  { key: 'NativeGuide', label: 'NativeGuide', metric: 'DTW distance', supported: true },
  { key: 'SETSDonor', label: 'SETS', metric: 'Shapelet distance', supported: true },
  { key: 'DiscordDonor', label: 'Discord', metric: 'Matrix-profile value', supported: true },
  { key: 'TimeGAN', label: 'TimeGAN', metric: 'Latent distance', supported: false },
  { key: 'ShapeDBA', label: 'ShapeDBA', metric: 'Soft-DTW distance', supported: false },
  { key: 'UserDrawn', label: 'User-drawn', metric: 'Sketch', supported: true },
]);

export const USER_DRAWN_BACKEND = 'UserDrawn';
export const DEFAULT_BACKEND = 'NativeGuide';
export const DEFAULT_CROSSFADE_WIDTH = 0.1;
export const MIN_CROSSFADE_WIDTH = 0.0;
export const MAX_CROSSFADE_WIDTH = 0.5;

/**
 * Validate a crossfade width (fraction of the segment length) against the
 * UI-allowed range.  Returns the clamped value plus a flag indicating
 * whether clamping was needed (used by the slider for visual feedback).
 */
export function clampCrossfadeWidth(value) {
  const v = Number(value);
  if (!Number.isFinite(v)) {
    return { value: DEFAULT_CROSSFADE_WIDTH, clamped: true };
  }
  if (v < MIN_CROSSFADE_WIDTH) return { value: MIN_CROSSFADE_WIDTH, clamped: true };
  if (v > MAX_CROSSFADE_WIDTH) return { value: MAX_CROSSFADE_WIDTH, clamped: true };
  return { value: v, clamped: false };
}

/**
 * Build the OP-012 ``op-invoked`` payload from a picked candidate.
 *
 * Returns the exact shape the operation palette emits up to
 * ``BenchmarkViewerPage.handleOpInvoked``:
 *   ``{ tier: 1, op_name: 'replace_from_library', params: {...} }``.
 *
 * For ``UserDrawn`` the donor values are inlined (the backend never sees
 * them); for the other backends the ``donor_id`` opaque token is enough
 * for the backend to re-fetch.
 */
export function buildAcceptPayload({ backend, candidate, crossfadeWidth }) {
  if (!backend || !candidate) {
    throw new Error('buildAcceptPayload requires backend and candidate.');
  }
  const { value: width } = clampCrossfadeWidth(crossfadeWidth);
  const params = {
    backend,
    donor_id: candidate.donor_id,
    crossfade_width: width,
  };
  if (backend === USER_DRAWN_BACKEND && Array.isArray(candidate.values)) {
    params.donor_values = candidate.values;
  }
  return {
    tier: 1,
    op_name: 'replace_from_library',
    params,
  };
}

/**
 * Compose the picker view model from raw inputs.
 *
 * Inputs:
 *   selectedBackend     — current dropdown selection
 *   candidates          — array of {donor_id, values, distance, ...}
 *   selectedCandidateId — id of the candidate currently in the comparison plot
 *   crossfadeWidth      — slider value, fraction of segment length
 *   sketchpadValues     — current UserDrawn signal (or null)
 *   loading             — fetch in progress
 *   error               — last error message, or null
 *
 * Returns a frozen-shape view model with derived fields the component
 * reads directly.
 */
export function createDonorPickerState({
  selectedBackend = DEFAULT_BACKEND,
  candidates = [],
  selectedCandidateId = null,
  crossfadeWidth = DEFAULT_CROSSFADE_WIDTH,
  sketchpadValues = null,
  loading = false,
  error = null,
} = {}) {
  const option =
    BACKEND_OPTIONS.find((o) => o.key === selectedBackend) ??
    BACKEND_OPTIONS.find((o) => o.key === DEFAULT_BACKEND);
  const isUserDrawn = option.key === USER_DRAWN_BACKEND;
  const { value: clampedWidth } = clampCrossfadeWidth(crossfadeWidth);

  let displayedCandidates = candidates;
  if (isUserDrawn) {
    if (sketchpadValues && sketchpadValues.length > 1) {
      displayedCandidates = [
        {
          donor_id: 'user-drawn',
          backend: USER_DRAWN_BACKEND,
          values: sketchpadValues,
          distance: null,
          metric: 'sketch',
        },
      ];
    } else {
      displayedCandidates = [];
    }
  }

  const selectedCandidate =
    displayedCandidates.find((c) => c.donor_id === selectedCandidateId) ??
    displayedCandidates[0] ??
    null;

  return {
    backendKey: option.key,
    backendLabel: option.label,
    metricLabel: option.metric,
    backendSupported: option.supported,
    isUserDrawn,
    options: BACKEND_OPTIONS,
    candidates: displayedCandidates,
    selectedCandidateId: selectedCandidate?.donor_id ?? null,
    selectedCandidate,
    crossfadeWidth: clampedWidth,
    loading,
    error,
    canAccept: !loading && !error && selectedCandidate != null,
    canReject: !loading && !isUserDrawn && displayedCandidates.length > 0,
  };
}

/**
 * Format a candidate's distance metric for display.
 *
 * Numbers larger than 100 use 0 decimals, < 1 use 4, in between use 2.
 * ``null``/non-finite values render as em-dash.
 */
export function formatDistance(distance) {
  if (distance == null || !Number.isFinite(Number(distance))) return '—';
  const v = Number(distance);
  const abs = Math.abs(v);
  if (abs >= 100) return v.toFixed(0);
  if (abs >= 1) return v.toFixed(2);
  if (abs >= 0.001) return v.toFixed(4);
  return v.toExponential(2);
}
