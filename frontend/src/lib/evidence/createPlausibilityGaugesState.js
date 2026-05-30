/**
 * createPlausibilityGaugesState — derive the four EVIDENCE-zone plausibility
 * gauges from real backend numbers + the local prediction-rerun stream.
 *
 * Mapping (REWORK-06):
 *
 *   - **Validity**     ← VAL-012 `validity_rate.py` semantic, specialised
 *                        for our prototype classifier. An edit "is_valid"
 *                        iff the rerun prediction differs from the locked
 *                        baseline (`current.predicted_label !==
 *                        baseline.predicted_label`). The gauge is the
 *                        session-cumulative rate across reruns. Source: the
 *                        prediction service (REWORK-02) produced the
 *                        prediction labels; this lib aggregates them.
 *                        Refs: Verma et al. *ACM CSUR* 56:312 (2024) Eq. 3;
 *                        Mothilal et al. "DiCE," FAccT 2020 §3.1.
 *   - **Proximity**    ← VAL-004 native_guide.proximity_pct when calibration
 *                        is loaded; otherwise null + uncalibrated hint
 *                        showing the raw DTW distance. Ref: Delaney et al.
 *                        "Instance-based Counterfactual Explanations for
 *                        Time Series Classification," ICCBR 2021.
 *   - **Sparsity**     ← VAL-004 native_guide.sparsity (always in [0,1]).
 *                        Ref: same paper, §3.2.
 *   - **Plausibility** ← VAL-003 ynn_plausibility.ynn (fraction of top-K
 *                        target-class neighbours). null when the index
 *                        could not be built (rendered as "n/a"). Ref:
 *                        Verma et al. *CSUR* 2024 §4.4 (yNN plausibility
 *                        proxy), Pawelczyk et al. *NeurIPS* 2020.
 *
 * `null` values are honest "no data" — the UI renders them as "n/a" with a
 * descriptive hint, never as a hardcoded zero.
 *
 * Tone thresholds are presentation-only and live alongside the gauge tone
 * computation in this module — they describe WHEN to escalate visually, not
 * what the metric means.
 */

const TONE_CONFIDENT = "confident";
const TONE_MODERATE = "moderate";
const TONE_UNCERTAIN = "uncertain";

/** Below this, the plausibility gauge fires the cluster-level
 * "OFF-DISTRIBUTION" badge. Matches `toneForValue`'s uncertain cutoff so
 * "uncertain plausibility" and "off-distribution" mean the same thing. */
const OFF_DISTRIBUTION_THRESHOLD = 0.4;

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
 * Aggregate per-rerun validity outcomes. Each entry is `{flipped: boolean}`
 * representing one successful prediction rerun (REWORK-02). Returns the
 * session-cumulative rate plus counters for the tooltip caption.
 */
function computeValidity(validityRuns) {
  if (!Array.isArray(validityRuns) || validityRuns.length === 0) {
    return { value: null, total: 0, flipped: 0 };
  }
  let total = 0;
  let flipped = 0;
  for (const run of validityRuns) {
    if (!run || typeof run.flipped !== "boolean") continue;
    total += 1;
    if (run.flipped) flipped += 1;
  }
  if (total === 0) return { value: null, total: 0, flipped: 0 };
  return { value: flipped / total, total, flipped };
}

export function createPlausibilityGaugesState({
  validityRuns = [],
  plausibility = null,
  hasEdit = false,
} = {}) {
  const validity = computeValidity(validityRuns);

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
      key: "validity",
      label: "Validity",
      value: validityClamped,
      displayValue: validityClamped == null ? "—" : formatPct(validityClamped),
      tone: toneForValue(validityClamped),
      hint:
        validityClamped == null
          ? "Rerun the prediction after an edit to start tracking validity."
          : `${validity.flipped}/${validity.total} reruns flipped the model from baseline`,
      source: "VAL-012 validity_rate",
      reference:
        "Verma et al. ACM CSUR 56:312 (2024) §3; Mothilal et al. DiCE, FAccT 2020 §3.1",
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
      reference: "Delaney et al. ICCBR 2021 (Native-Guide, §3.1)",
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
      reference: "Delaney et al. ICCBR 2021 (Native-Guide, §3.2)",
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
      reference: "Verma et al. ACM CSUR 56:312 (2024) §4.4; Pawelczyk et al. NeurIPS 2020",
    },
  ];

  // Cluster-level "off-distribution" warning. Fires only on real plausibility
  // data (null → no claim; the calibration just isn't loaded). Sparsity
  // collapse is a strong corroborating signal — when the edit also touches
  // almost every timestep, the manifold drift is more likely real.
  const offDistribution =
    Number.isFinite(ynnClamped) && ynnClamped < OFF_DISTRIBUTION_THRESHOLD;
  const lowSparsity = Number.isFinite(sparsityClamped) && sparsityClamped < 0.5;

  return {
    hasEdit,
    gauges,
    offDistribution,
    offDistributionReason: offDistribution
      ? lowSparsity
        ? `Few training neighbours share the target class (yNN ${formatPct(ynnClamped)}) AND the edit touches more than half of the series.`
        : `Few training neighbours share the target class (yNN ${formatPct(ynnClamped)}).`
      : null,
  };
}

export const GAUGE_TONES = Object.freeze({
  CONFIDENT: TONE_CONFIDENT,
  MODERATE: TONE_MODERATE,
  UNCERTAIN: TONE_UNCERTAIN,
});

export { OFF_DISTRIBUTION_THRESHOLD };
