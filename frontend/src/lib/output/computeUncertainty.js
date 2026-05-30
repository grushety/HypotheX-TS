/**
 * computeUncertainty — glance-level uncertainty cues for a classification
 * probability vector.
 *
 * Surfaces three complementary signals:
 *
 *  - **Normalized entropy** H(p) / log(K) in [0, 1] (Shannon 1948; normalised
 *    form from MacKay 2003 §2.1). 0 = one-hot, 1 = uniform.
 *  - **Top-runner margin** p_(1) − p_(2) in [0, 1] (Settles 2009, active-learning
 *    review). Small margin → near-tie.
 *  - **Top-p prediction set** — smallest set of labels whose cumulative
 *    probability ≥ `coverage`. The set IS NOT a calibrated conformal set —
 *    classification conformal calibration (Romano, Sesia, Candès 2020,
 *    "Adaptive Prediction Sets") is not yet wired into this codebase. The
 *    visual cue (set size escalates near a tie) is identical; the coverage
 *    label below the bar describes the target, not a guarantee.
 *
 * A combined `isUncertain` flag fires when either the margin is below
 * `marginThreshold` or normalized entropy is above `entropyThreshold`. The
 * defaults (0.15 / 0.60) match `designs/output.jsx`.
 */

export const DEFAULT_COVERAGE = 0.9;
export const DEFAULT_MARGIN_THRESHOLD = 0.15;
export const DEFAULT_ENTROPY_THRESHOLD = 0.60;
// "moderate" calms the chip below the full UNCERTAIN alarm. Sits roughly
// halfway between confident and the warning threshold; matches the design's
// fixed 0.35 break-point given the 0.60 default.
const MODERATE_ENTROPY_RATIO = 0.58;

const UNCERTAINTY_LEVEL = Object.freeze({
  CONFIDENT: "confident",
  MODERATE: "moderate",
  UNCERTAIN: "uncertain",
  NEAR_TIE: "near tie",
});

function sanitizeProbs(probs) {
  if (!Array.isArray(probs)) return [];
  return probs.map((p) => {
    if (!Number.isFinite(p) || p <= 0) return 0;
    if (p >= 1) return 1;
    return p;
  });
}

export function entropyNormalized(probs) {
  const clean = sanitizeProbs(probs);
  if (clean.length <= 1) return 0;
  const k = clean.length;
  let h = 0;
  for (const p of clean) {
    if (p > 1e-12) h -= p * Math.log(p);
  }
  return Math.min(1, h / Math.log(k));
}

export function topRunnerMargin(probs) {
  const clean = sanitizeProbs(probs);
  if (clean.length === 0) return 0;
  if (clean.length === 1) return 1;
  const sorted = [...clean].sort((a, b) => b - a);
  return Math.max(0, sorted[0] - sorted[1]);
}

/**
 * Smallest set of labels whose cumulative probability ≥ `coverage`. Labels are
 * picked in descending probability order. Always returns at least one label.
 */
export function topPSet(scores, coverage = DEFAULT_COVERAGE) {
  if (!Array.isArray(scores) || scores.length === 0) return [];
  const target = Math.min(Math.max(coverage, 0), 1);
  const ranked = scores
    .filter((s) => s && typeof s.label === "string")
    .map((s) => ({ label: s.label, probability: Number.isFinite(s.probability) ? s.probability : 0 }))
    .sort((a, b) => b.probability - a.probability);
  const set = [];
  let cum = 0;
  for (const entry of ranked) {
    set.push(entry.label);
    cum += entry.probability;
    if (cum >= target) break;
  }
  return set;
}

/**
 * Roll the three signals into a single descriptor for the UI. The `level`
 * string drives the chip text; `isUncertain` drives the block-level escalation
 * (border + opacity stripe on the Current card).
 */
export function assessUncertainty(scores, {
  coverage = DEFAULT_COVERAGE,
  marginThreshold = DEFAULT_MARGIN_THRESHOLD,
  entropyThreshold = DEFAULT_ENTROPY_THRESHOLD,
} = {}) {
  const probs = Array.isArray(scores)
    ? scores
        .filter((s) => s && typeof s.label === "string")
        .map((s) => (Number.isFinite(s.probability) ? s.probability : 0))
    : [];

  // Defensive no-op for empty/malformed input: no probabilities means no
  // basis to flag uncertainty. Without this guard the margin (0) trips the
  // near-tie threshold and the chip would falsely read "near tie".
  if (probs.length === 0) {
    return {
      entropy: 0,
      margin: 0,
      nearTie: false,
      isUncertain: false,
      level: UNCERTAINTY_LEVEL.CONFIDENT,
      set: [],
      coverage,
      setSize: 0,
    };
  }

  const entropy = entropyNormalized(probs);
  const margin = topRunnerMargin(probs);
  const set = topPSet(scores, coverage);
  const nearTie = margin < marginThreshold;
  const highEntropy = entropy > entropyThreshold;
  const isUncertain = nearTie || highEntropy;

  let level;
  if (nearTie) {
    level = UNCERTAINTY_LEVEL.NEAR_TIE;
  } else if (highEntropy) {
    level = UNCERTAINTY_LEVEL.UNCERTAIN;
  } else if (entropy > entropyThreshold * MODERATE_ENTROPY_RATIO) {
    level = UNCERTAINTY_LEVEL.MODERATE;
  } else {
    level = UNCERTAINTY_LEVEL.CONFIDENT;
  }

  return {
    entropy,
    margin,
    nearTie,
    isUncertain,
    level,
    set,
    coverage,
    setSize: set.length,
  };
}

export const UNCERTAINTY_LEVELS = UNCERTAINTY_LEVEL;
