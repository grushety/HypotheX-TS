/**
 * createOutputPanelState — pure state machine for the OUTPUT zone.
 *
 * Combines a locked baseline prediction, a current prediction (over the
 * possibly-edited series), loading/error flags, and a monotonic seriesVersion
 * counter into one flat structure that OutputPanel.vue renders without further
 * logic. State precedence: error > loading > empty > stale > normal.
 */

export const OUTPUT_STATE = Object.freeze({
  EMPTY: "empty",
  LOADING: "loading",
  NORMAL: "normal",
  STALE: "stale",
  ERROR: "error",
});

const FRESH_CHIP = Object.freeze({
  empty: { label: "NO RUN", tone: "none" },
  loading: { label: "RUNNING", tone: "none" },
  normal: { label: "FRESH", tone: "ok" },
  stale: { label: "STALE", tone: "stale" },
  error: { label: "ERROR", tone: "err" },
});

function clampProb(value) {
  if (!Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

function indexByLabel(scores) {
  const map = new Map();
  if (!Array.isArray(scores)) return map;
  for (const entry of scores) {
    if (entry && typeof entry.label === "string") {
      map.set(entry.label, clampProb(entry.probability));
    }
  }
  return map;
}

/**
 * Build the per-class classification payload by aligning baseline and current
 * probabilities on label. Preserves baseline order so the bars don't shuffle
 * across runs.
 */
function buildClassification(baseline, current) {
  if (!baseline || !Array.isArray(baseline.scores)) return null;
  const baselineMap = indexByLabel(baseline.scores);
  const currentMap = indexByLabel(current?.scores);

  const classes = baseline.scores
    .filter((entry) => entry && typeof entry.label === "string")
    .map((entry) => {
      const name = entry.label;
      const base = clampProb(entry.probability);
      const cur = currentMap.has(name) ? currentMap.get(name) : base;
      return { name, base, cur, delta: cur - base };
    });

  const basePred = baseline.predicted_label ?? null;
  const curPred = current?.predicted_label ?? basePred;
  const flip = basePred != null && curPred != null && basePred !== curPred;

  const baselinePredBase = basePred != null ? baselineMap.get(basePred) ?? 0 : 0;
  const baselinePredCur = basePred != null && currentMap.has(basePred)
    ? currentMap.get(basePred)
    : baselinePredBase;
  const predDelta = baselinePredCur - baselinePredBase;

  return { classes, basePred, curPred, flip, predDelta };
}

export function createOutputPanelState({
  baseline = null,
  current = null,
  loading = false,
  error = null,
  seriesVersion = 0,
  currentVersion = null,
} = {}) {
  const safeError = typeof error === "string" && error.length > 0 ? error : null;

  let state;
  if (safeError) {
    state = OUTPUT_STATE.ERROR;
  } else if (loading) {
    state = OUTPUT_STATE.LOADING;
  } else if (!baseline) {
    state = OUTPUT_STATE.EMPTY;
  } else if (!current || currentVersion == null || currentVersion !== seriesVersion) {
    state = OUTPUT_STATE.STALE;
  } else {
    state = OUTPUT_STATE.NORMAL;
  }

  const mode = (baseline?.task ?? current?.task ?? "classification") === "regression"
    ? "regression"
    : "classification";

  // Build classification only when there is something to render; loading shows a skeleton.
  const showsBody = state === OUTPUT_STATE.NORMAL || state === OUTPUT_STATE.STALE;
  const classification = showsBody && mode === "classification"
    ? buildClassification(baseline, current ?? baseline)
    : null;

  return {
    state,
    mode,
    classification,
    baseline,
    current,
    error: safeError,
    seriesVersion,
    currentVersion,
    freshChip: FRESH_CHIP[state],
  };
}
