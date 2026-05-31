/**
 * createCohortResultModel — turn the /api/cohort/apply payload into
 * ready-to-render rows + sign-aware aggregates for the cohort view.
 *
 * Sorting / formatting decisions live here (not in the component) so
 * the panel stays declarative.
 */

const DEFAULT_CHERRY_PICKING_CI_WIDTH = 0.4;

function clamp01(value) {
  if (!Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

function formatPct(value) {
  if (!Number.isFinite(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

function signedPp(value) {
  if (!Number.isFinite(value)) return "0";
  const sign = value >= 0 ? "+" : "−";
  return `${sign}${Math.abs(value * 100).toFixed(1)}`;
}

export function createCohortResultModel(payload, options = {}) {
  if (!payload || !Array.isArray(payload.per_series) || !payload.aggregates) {
    return {
      hasData: false,
      rows: [],
      summary: null,
      histogram: null,
      method: "",
      reference: "",
      cherryPickingWarning: null,
    };
  }

  const aggregates = payload.aggregates;
  const cherryWidthThreshold =
    typeof options.cherryPickingCiWidth === "number"
      ? options.cherryPickingCiWidth
      : DEFAULT_CHERRY_PICKING_CI_WIDTH;

  // Sort rows by signed delta DESC (largest positive movers first, then
  // negative movers). Matches the design's dumbbell ordering and makes
  // the FLIP tags cluster at the top when the op pushed predictions away
  // from the baseline class.
  const rows = payload.per_series
    .filter((s) => s && typeof s.sample_index === "number")
    .map((s) => ({
      sampleIndex: s.sample_index,
      baselineClass: typeof s.baseline_class === "string" ? s.baseline_class : "—",
      currentClass: typeof s.current_class === "string" ? s.current_class : "—",
      baselineProb: clamp01(s.baseline_prob),
      currentProb: clamp01(s.current_prob),
      delta: Number.isFinite(s.delta) ? s.delta : 0,
      deltaLabel: signedPp(s.delta),
      flipped: Boolean(s.flipped),
      isBiggestMover: s.sample_index === aggregates.biggest_mover_index,
    }))
    .sort((a, b) => b.delta - a.delta);

  const flipRateCi = aggregates.flip_rate_ci ?? {};
  const meanDeltaCi = aggregates.mean_delta_ci ?? {};

  const summary = {
    total: Number.isFinite(aggregates.total) ? aggregates.total : 0,
    flippedCount: Number.isFinite(aggregates.flipped_count) ? aggregates.flipped_count : 0,
    flipRate: clamp01(aggregates.flip_rate),
    flipRateLabel: formatPct(aggregates.flip_rate),
    flipRateCi: {
      lower: clamp01(flipRateCi.lower),
      upper: clamp01(flipRateCi.upper),
      lowerLabel: formatPct(flipRateCi.lower),
      upperLabel: formatPct(flipRateCi.upper),
      confidence: Number.isFinite(flipRateCi.confidence_level) ? flipRateCi.confidence_level : 0.95,
      iterations: Number.isFinite(flipRateCi.iterations) ? flipRateCi.iterations : 0,
    },
    meanDelta: Number.isFinite(aggregates.mean_delta) ? aggregates.mean_delta : 0,
    meanDeltaLabel: signedPp(aggregates.mean_delta),
    meanDeltaCi: {
      lower: Number.isFinite(meanDeltaCi.lower) ? meanDeltaCi.lower : 0,
      upper: Number.isFinite(meanDeltaCi.upper) ? meanDeltaCi.upper : 0,
      lowerLabel: signedPp(meanDeltaCi.lower),
      upperLabel: signedPp(meanDeltaCi.upper),
      confidence: Number.isFinite(meanDeltaCi.confidence_level)
        ? meanDeltaCi.confidence_level
        : 0.95,
    },
    biggestMoverIndex: aggregates.biggest_mover_index,
  };

  // Cherry-picking caveat: the CI is wide OR straddles zero — both are
  // signs the effect is shakier than the point estimate suggests.
  const ciStraddlesZero =
    Number.isFinite(meanDeltaCi.lower) &&
    Number.isFinite(meanDeltaCi.upper) &&
    meanDeltaCi.lower <= 0 &&
    meanDeltaCi.upper >= 0;
  const ciWide =
    Number.isFinite(flipRateCi.lower) &&
    Number.isFinite(flipRateCi.upper) &&
    flipRateCi.upper - flipRateCi.lower >= cherryWidthThreshold;

  let cherryPickingWarning = null;
  if (ciStraddlesZero) {
    cherryPickingWarning = "Mean-Δ confidence interval crosses zero — the average effect is not significantly different from no change.";
  } else if (ciWide) {
    cherryPickingWarning = "Flip-rate confidence interval is wider than 40 percentage points — the cohort is too small to call this stable.";
  }

  const bins = Array.isArray(aggregates.delta_histogram_bin_edges)
    ? aggregates.delta_histogram_bin_edges
    : [];
  const counts = Array.isArray(aggregates.delta_histogram_counts)
    ? aggregates.delta_histogram_counts
    : [];
  const maxCount = counts.reduce((acc, c) => (c > acc ? c : acc), 0);
  const histogram = bins.length > 1 && counts.length === bins.length - 1
    ? counts.map((count, index) => ({
        left: bins[index],
        right: bins[index + 1],
        count,
        heightPct: maxCount > 0 ? Math.round((count / maxCount) * 100) : 0,
        containsZero: bins[index] <= 0 && bins[index + 1] >= 0,
      }))
    : null;

  return {
    hasData: rows.length > 0,
    rows,
    summary,
    histogram,
    method: payload.method ?? "",
    reference: payload.reference ?? "",
    cherryPickingWarning,
  };
}
