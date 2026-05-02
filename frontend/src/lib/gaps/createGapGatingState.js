/**
 * Gap-gating state for dense-data ops (UI-017).
 *
 * Some operations silently produce garbage on segments with significant
 * missing data — FFT-based cycle ops, ETM harmonic fits, STL
 * decomposition.  This module classifies a segment's missingness, gates
 * those ops behind a configurable threshold, and produces the payload
 * for the Tier-1 ``suppress`` op that fills the gap.
 *
 * Cross-references
 * ----------------
 * - SEG-023 emits ``semantic_label = 'cloud_gap'`` for segments that are
 *   purely a gap; the chip badge picks up that signal.
 * - OP-013 ships ``suppress`` with strategies linear / spline /
 *   climatology / stl_trend / baseflow.  UI-005's gap-fill picker
 *   exposes the first three.
 * - The gating applies *to the named ops only*; non-FFT ops on
 *   gap-heavy segments stay enabled (the user may genuinely want to
 *   ``mute_zero`` or ``offset`` a gap-heavy region without filling).
 */

export const DEFAULT_DENSE_OPS_THRESHOLD_PCT = 30;
export const MIN_DENSE_OPS_THRESHOLD_PCT = 0;
export const MAX_DENSE_OPS_THRESHOLD_PCT = 100;

export const SUPPRESS_STRATEGIES = Object.freeze(['linear', 'spline', 'climatology']);
export const DEFAULT_SUPPRESS_STRATEGY = 'linear';

export const SUPPRESS_STRATEGY_LABELS = Object.freeze({
  linear: 'Linear interpolation',
  spline: 'Cubic spline',
  climatology: 'Day-of-year climatology',
});

/**
 * Op names that must NOT run on a gap-heavy segment.
 *
 * Mirrors the AC list — OP-024 ``change_period`` (= ``cycle_change_frequency``
 * in the frontend op catalogue), OP-024 ``phase_shift`` (=
 * ``cycle_shift_phase``), the FFT-based add/remove harmonics, and the
 * Tier-3 ``decompose`` op (which fans out to ETM-harmonic and STL fits
 * downstream).
 */
export const DENSE_DATA_OPS = Object.freeze(
  new Set([
    'cycle_change_frequency',
    'cycle_shift_phase',
    'cycle_add_harmonics',
    'cycle_remove_harmonics',
    'decompose',
  ]),
);

const CLOUD_GAP_LABEL = 'cloud_gap';

/** True when ``v`` should be counted as a missing observation. */
export function isMissingValue(v) {
  return v == null || (typeof v === 'number' && Number.isNaN(v));
}

/** Fraction of values in ``[0, 1]`` that are missing. */
export function computeMissingnessRatio(values) {
  if (!Array.isArray(values) || values.length === 0) return 0;
  let missing = 0;
  for (const v of values) if (isMissingValue(v)) missing += 1;
  return missing / values.length;
}

/** Clamp a percentage value into the legal threshold range. */
export function clampThresholdPct(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return DEFAULT_DENSE_OPS_THRESHOLD_PCT;
  if (n < MIN_DENSE_OPS_THRESHOLD_PCT) return MIN_DENSE_OPS_THRESHOLD_PCT;
  if (n > MAX_DENSE_OPS_THRESHOLD_PCT) return MAX_DENSE_OPS_THRESHOLD_PCT;
  return n;
}

/**
 * Build the gap classification view model for a segment.
 *
 * Resolution priority for missingness:
 *   1. ``segment.missingness_ratio`` / ``segment.missingnessRatio`` if the
 *      caller has it pre-computed (e.g. from the backend).
 *   2. ``segmentValues`` — count NaN/null directly.
 *   3. Fall back to 0.
 *
 * The ``isFilled`` flag short-circuits the gating: once a segment has
 * been suppress-filled, dense ops re-enable even if the underlying
 * series still carries the original NaNs (the filled values live in the
 * decomposition blob, not the raw series).
 */
export function classifyGap({
  segment = null,
  segmentValues = null,
  thresholdPct = DEFAULT_DENSE_OPS_THRESHOLD_PCT,
} = {}) {
  const explicit =
    segment?.missingness_ratio ?? segment?.missingnessRatio ?? null;
  let ratio = 0;
  if (typeof explicit === 'number' && Number.isFinite(explicit)) {
    ratio = explicit;
  } else if (Array.isArray(segmentValues)) {
    ratio = computeMissingnessRatio(segmentValues);
  }
  const clampedRatio = Math.max(0, Math.min(1, ratio));
  const missingnessPct = Math.round(clampedRatio * 100);
  const threshold = clampThresholdPct(thresholdPct);
  // Compare against the raw ratio (not the rounded percent) so a segment at
  // 30.4% missing is still gated — the AC threshold is "ratio > 30 %", not
  // "rounded percent > 30".
  const exceedsThreshold = clampedRatio * 100 > threshold;

  const isFilled = Boolean(segment?.metadata?.filled ?? segment?.filled ?? false);
  const fillStrategy =
    segment?.metadata?.fill_strategy ??
    segment?.metadata?.fillStrategy ??
    segment?.fillStrategy ??
    null;

  const semanticLabel = segment?.semanticLabel ?? segment?.semantic_label ?? null;
  const isCloudGap = semanticLabel === CLOUD_GAP_LABEL;

  return Object.freeze({
    missingnessRatio: clampedRatio,
    missingnessPct,
    thresholdPct: threshold,
    exceedsThreshold,
    isFilled,
    isCloudGap,
    fillStrategy,
  });
}

/** True when the named op is a dense-data op AND the gap exceeds the threshold. */
export function isOpBlockedByGap(opName, gapInfo) {
  if (!gapInfo) return false;
  if (gapInfo.isFilled) return false;
  if (!DENSE_DATA_OPS.has(opName)) return false;
  return gapInfo.exceedsThreshold;
}

/**
 * Tooltip string for a gap-blocked op (the AC-spec format).
 * Returns ``null`` for non-blocked ops.
 */
export function gapDisabledTooltip(opName, gapInfo) {
  if (!isOpBlockedByGap(opName, gapInfo)) return null;
  return (
    `Not available: segment has ${gapInfo.missingnessPct}% missing data. ` +
    'Fill via Tier-1 suppress first.'
  );
}

/**
 * Augment a palette button entry with gap gating.
 *
 * Returns the input button unchanged when the op is not blocked; otherwise
 * a copy with ``enabled=false`` and ``disabledTooltip`` set.  Designed to
 * sit at the end of the existing gating chain in
 * ``createTieredPaletteState`` so shape gating + multi-select gating still
 * apply.
 */
export function applyGapGatingToButton(button, gapInfo) {
  if (!isOpBlockedByGap(button?.op_name, gapInfo)) return button;
  return {
    ...button,
    enabled: false,
    disabledTooltip: gapDisabledTooltip(button.op_name, gapInfo),
  };
}

/**
 * Build the OP-013 ``suppress`` op-invoked payload for the gap-fill UI.
 */
export function buildSuppressPayload({
  segmentId,
  strategy = DEFAULT_SUPPRESS_STRATEGY,
}) {
  if (!segmentId) {
    throw new Error('buildSuppressPayload requires segmentId.');
  }
  if (!SUPPRESS_STRATEGIES.includes(strategy)) {
    throw new Error(`buildSuppressPayload: unknown strategy '${strategy}'.`);
  }
  return {
    tier: 1,
    op_name: 'suppress',
    params: {
      segment_id: segmentId,
      strategy,
    },
  };
}
