/**
 * createPlausibilityGaugesState — derive the four EVIDENCE-zone plausibility
 * gauges from real backend numbers + the local audit stream.
 *
 * Mapping (REWORK-04):
 *
 *   - **Pass rate**    ← audit events. Fraction of recent operation events
 *                        whose constraint status is PASS. This is NOT the
 *                        same as VAL-012's `validity_rate` — VAL-012 defines
 *                        validity as `predicted_class == target_class` per
 *                        edit, which requires target-class semantics that
 *                        the audit log doesn't carry yet. Until those land
 *                        end-to-end, the gauge labels itself honestly as a
 *                        constraint-pass rate so we don't fabricate VAL-012
 *                        numbers from the wrong source.
 *   - **Proximity**    ← VAL-004 native_guide.proximity_pct when calibration
 *                        is loaded; otherwise null + uncalibrated hint
 *                        showing the raw DTW distance.
 *   - **Sparsity**     ← VAL-004 native_guide.sparsity (always in [0,1]).
 *   - **Plausibility** ← VAL-003 ynn_plausibility.ynn (top-K target-class
 *                        neighbour fraction). null when the index could not
 *                        be built (rendered as "n/a").
 *
 * `null` values are honest "no data" — the UI renders them as "n/a" with a
 * descriptive hint, never as a hardcoded zero.
 */

import { SOFT_CONSTRAINT_STATUS } from "../constraints/evaluateSoftConstraints.js";

const TONE_CONFIDENT = "confident";
const TONE_MODERATE = "moderate";
const TONE_UNCERTAIN = "uncertain";

function clamp01(value) {
  // Returns null for non-finite or out-of-range inputs. The backend's
  // probability-shaped fields (sparsity, yNN fraction, proximity_pct) are
  // contracted to live in [0, 1]; anything outside is treated as bad data
  // and surfaced as "—" rather than fabricating a 0% or 100% reading.
  if (!Number.isFinite(value)) return null;
  if (value < 0 || value > 1) return null;
  return value;
}

function toneForValue(value) {
  if (!Number.isFinite(value)) return null;
  if (value >= 0.66) return TONE_CONFIDENT;
  if (value >= 0.4) return TONE_MODERATE;
  return TONE_UNCERTAIN;
}

function formatPct(value) {
  if (!Number.isFinite(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

function formatDistance(value) {
  if (!Number.isFinite(value)) return "—";
  return value.toFixed(2);
}

/**
 * Walk the audit events, count how many emitted a constraint status, and
 * return the share that passed. Events without a constraintStatus field
 * (e.g. raw segment edits, suggestion-accepts) are excluded — they don't
 * represent a constraint judgement.
 */
function computeValidityFromEvents(events) {
  if (!Array.isArray(events) || events.length === 0) {
    return { value: null, total: 0, passes: 0 };
  }
  let total = 0;
  let passes = 0;
  for (const event of events) {
    const status = event?.payload?.constraintStatus ?? event?.constraintStatus ?? null;
    if (status == null) continue;
    total += 1;
    if (status === SOFT_CONSTRAINT_STATUS.PASS) passes += 1;
  }
  if (total === 0) return { value: null, total: 0, passes: 0 };
  return { value: passes / total, total, passes };
}

export function createPlausibilityGaugesState({
  events = [],
  plausibility = null,
  hasEdit = false,
} = {}) {
  const validity = computeValidityFromEvents(events);

  const proxPct = plausibility?.proximity_pct;
  const proxRaw = plausibility?.proximity;
  const sparsity = plausibility?.sparsity;
  const ynn = plausibility?.plausibility;

  const validityClamped = clamp01(validity.value);
  const proximityClamped = clamp01(proxPct);
  const sparsityClamped = clamp01(sparsity);
  const ynnClamped = clamp01(ynn);

  const gauges = [
    {
      key: "pass_rate",
      label: "Pass rate",
      value: validityClamped,
      displayValue: validityClamped == null ? "—" : formatPct(validityClamped),
      tone: toneForValue(validityClamped),
      hint:
        validityClamped == null
          ? "Apply an operation to start tracking constraint-pass rate."
          : `${validity.passes}/${validity.total} edits passed constraint checks`,
      source: "constraint engine · session audit (not VAL-012 yet)",
    },
    {
      key: "proximity",
      label: "Proximity",
      value: proximityClamped,
      displayValue: proximityClamped == null ? "—" : formatPct(proximityClamped),
      tone: toneForValue(proximityClamped),
      hint:
        proxRaw == null
          ? "Apply an edit to compute proximity (DTW distance to baseline)."
          : proximityClamped == null
            ? `DTW distance ${formatDistance(proxRaw)} · no dataset calibration loaded`
            : `DTW distance ${formatDistance(proxRaw)} vs dataset NUN distribution`,
      source: "VAL-004 native_guide.proximity",
    },
    {
      key: "sparsity",
      label: "Sparsity",
      value: sparsityClamped,
      displayValue: sparsityClamped == null ? "—" : formatPct(sparsityClamped),
      tone: toneForValue(sparsityClamped),
      hint:
        sparsityClamped == null
          ? "Apply an edit to compute sparsity (fraction of unchanged timesteps)."
          : "Share of timesteps left unchanged by the edit",
      source: "VAL-004 native_guide.sparsity",
    },
    {
      key: "plausibility",
      label: "Plausibility",
      value: ynnClamped,
      displayValue: ynnClamped == null ? "—" : formatPct(ynnClamped),
      tone: toneForValue(ynnClamped),
      hint:
        ynnClamped == null
          ? hasEdit
            ? "No yNN index available for this dataset · gauge is n/a"
            : "Apply an edit to score the current series on the training manifold."
          : `${Math.round(ynnClamped * (plausibility?.plausibility_k ?? 0))}/${plausibility?.plausibility_k ?? "?"} neighbours match target class`,
      source: "VAL-003 yNN target-class fraction",
    },
  ];

  return {
    hasEdit,
    gauges,
  };
}

export const GAUGE_TONES = Object.freeze({
  CONFIDENT: TONE_CONFIDENT,
  MODERATE: TONE_MODERATE,
  UNCERTAIN: TONE_UNCERTAIN,
});
