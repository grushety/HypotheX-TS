/**
 * createDeltaProvenanceModel — turn the backend's per-op contribution
 * payload into ready-to-render rows for the EVIDENCE-zone Δ-sources panel.
 *
 * Rows preserve the application order (the user wants to read down the
 * session timeline), but each row gets a bar width relative to the
 * largest |contribution| in the list so the visual scale is meaningful
 * even when one op dominates.
 *
 * The residual is included as a synthetic trailing row tagged
 * `isResidual: true` when its magnitude is non-trivial. Surfacing the
 * residual is load-bearing — it's the ticket's order-dependence /
 * interaction caveat made visible.
 */

const DEFAULT_RESIDUAL_VISIBILITY_THRESHOLD = 0.005; // 0.5 percentage points

export function createDeltaProvenanceModel(provenance, options = {}) {
  if (!provenance || !Array.isArray(provenance.contributions)) {
    return {
      hasData: false,
      totalDelta: 0,
      residual: 0,
      rows: [],
      method: "",
      reference: "",
      baselineClass: null,
      maxMagnitude: 0,
      showResidualRow: false,
    };
  }

  const residualVisibilityThreshold =
    typeof options.residualVisibilityThreshold === "number"
      ? options.residualVisibilityThreshold
      : DEFAULT_RESIDUAL_VISIBILITY_THRESHOLD;

  const contributions = provenance.contributions
    .filter((c) => c && typeof c.op_id === "string")
    .map((c) => ({
      opId: c.op_id,
      opLabel: typeof c.op_label === "string" && c.op_label.length > 0 ? c.op_label : c.op_id,
      contribution: Number.isFinite(c.contribution) ? c.contribution : 0,
      isResidual: false,
    }));

  const totalDelta = Number.isFinite(provenance.total_delta) ? provenance.total_delta : 0;
  const residual = Number.isFinite(provenance.residual) ? provenance.residual : 0;
  const showResidualRow = Math.abs(residual) >= residualVisibilityThreshold;

  const candidates = showResidualRow
    ? [...contributions, { opId: "__residual__", opLabel: "Residual (interactions)", contribution: residual, isResidual: true }]
    : contributions;

  let maxMagnitude = 0;
  for (const row of candidates) {
    const m = Math.abs(row.contribution);
    if (m > maxMagnitude) maxMagnitude = m;
  }
  const denominator = maxMagnitude > 0 ? maxMagnitude : 1;

  const rows = candidates.map((row) => ({
    ...row,
    barWidthPct: Math.min(100, Math.round((Math.abs(row.contribution) / denominator) * 100)),
    sign: row.contribution >= 0 ? "positive" : "negative",
  }));

  return {
    hasData: contributions.length > 0,
    totalDelta,
    residual,
    rows,
    method: provenance.method ?? "",
    reference: provenance.reference ?? "",
    baselineClass: provenance.baseline_class ?? null,
    maxMagnitude,
    showResidualRow,
  };
}
