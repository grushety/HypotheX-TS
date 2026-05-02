/**
 * Pure state for the Guardrails sidebar (VAL-014).
 *
 * The sidebar surfaces five session-level metrics and a settings dialog.
 * This module is the framework-agnostic state machine — it knows nothing
 * about Vue, the DOM, or the event bus. The Vue component subscribes to
 * the relevant event-bus topics and forwards each update through the
 * appropriate ``apply*Update`` method.
 *
 * Lisnic et al. CHI 2025 design constraints (ticket VAL-014):
 *   - non-blocking, never modal
 *   - users can dismiss the threshold-cross pulse
 *   - users can disable individual metrics
 *
 * Threshold-crossing rules are NOT hard-coded here — they live with the
 * metric trackers (VAL-010..013) and are reported on each update payload.
 * This module reads the ``tip_should_fire`` (and friends) flags directly
 * and derives a traffic-light colour from them. If a backend ticket adds
 * a new threshold, no UI change is needed.
 *
 * Sparkline buffer: last ``SPARKLINE_HISTORY`` numeric values per metric.
 * Older entries are discarded. Stored as a frozen array of numbers; the
 * sparkline renderer treats ``null`` / ``undefined`` as "no data yet"
 * and shows a placeholder.
 */

export const SPARKLINE_HISTORY = 20;

export const METRIC_KEYS = Object.freeze([
  'coverage',
  'diversity',
  'validity',
  'cherryPicking',
  'forkingPaths',
]);

/**
 * Static catalogue: per-metric paper attribution + label + topic name.
 * The hover tooltip reads ``citation``; the event-bus subscriber uses
 * ``topic``.
 */
export const METRIC_CATALOGUE = Object.freeze({
  coverage: Object.freeze({
    key: 'coverage',
    label: 'Shape-vocab coverage',
    topic: 'coverage_update',
    citation: 'Wall et al. IEEE TVCG 2022 (interaction-bias metrics)',
    valueLabel: 'fraction',
  }),
  diversity: Object.freeze({
    key: 'diversity',
    label: 'CF diversity (DPP log-det)',
    topic: 'diversity_update',
    citation: 'Mothilal et al. DiCE FAccT 2020 (DPP framework)',
    valueLabel: 'log det',
  }),
  validity: Object.freeze({
    key: 'validity',
    label: 'Validity rate',
    topic: 'validity_update',
    citation: 'Verma et al. ACM CSUR 56:312 (2024)',
    valueLabel: 'rate',
  }),
  cherryPicking: Object.freeze({
    key: 'cherryPicking',
    label: 'Cherry-picking risk',
    topic: 'cherry_picking_update',
    citation: 'TS adaptation of Hinns et al. arXiv:2601.04977 (2026)',
    valueLabel: 'risk',
  }),
  forkingPaths: Object.freeze({
    key: 'forkingPaths',
    label: 'Forking paths',
    topic: 'forking_paths_update',
    citation: 'Gelman & Loken 2013 (multiple comparisons)',
    valueLabel: 'count',
    pendingBackend: true, // No backend metric ships yet — VAL-014 reserves the row
  }),
});

export const TRAFFIC_LIGHT = Object.freeze({
  GREEN: 'green',
  AMBER: 'amber',
  RED: 'red',
  IDLE: 'idle', // metric has no data yet
  DISABLED: 'disabled', // user has disabled the metric in settings
});

/**
 * Default per-metric thresholds. Each entry mirrors the AC-default
 * thresholds documented in VAL-010..013; the user can override these
 * via the settings dialog. Values are *advisory* — the actual threshold
 * crossing is determined by the backend's ``tip_should_fire`` flag,
 * which the backend computes from its own (also-configurable) thresholds.
 *
 * The UI threshold values surface in the settings dialog so the user
 * can see and edit them; they don't drive the traffic-light colouring
 * directly. The colouring rule is below.
 */
export const DEFAULT_USER_THRESHOLDS = Object.freeze({
  coverage: Object.freeze({ amberBelow: 0.6, redBelow: 0.4 }),
  diversity: Object.freeze({ amberBelow: 0.0, redBelow: -10.0 }),
  validity: Object.freeze({ amberBelow: 0.5, redBelow: 0.3 }),
  cherryPicking: Object.freeze({ amberAbove: 0.5, redAbove: 0.7 }),
  forkingPaths: Object.freeze({ amberAbove: 5, redAbove: 10 }),
});

/**
 * Translate a current-value + threshold-spec pair into a traffic-light
 * colour. Direction is encoded in the threshold-spec keys
 * (``amberBelow`` / ``redBelow`` for "lower is worse";
 * ``amberAbove`` / ``redAbove`` for "higher is worse").
 *
 * Returns ``IDLE`` when value is ``null`` / ``undefined`` / ``NaN``.
 */
export function trafficLight(value, threshold) {
  if (value == null || Number.isNaN(value)) return TRAFFIC_LIGHT.IDLE;
  const numeric = Number(value);
  if ('redBelow' in threshold && numeric < threshold.redBelow) return TRAFFIC_LIGHT.RED;
  if ('amberBelow' in threshold && numeric < threshold.amberBelow) return TRAFFIC_LIGHT.AMBER;
  if ('redAbove' in threshold && numeric > threshold.redAbove) return TRAFFIC_LIGHT.RED;
  if ('amberAbove' in threshold && numeric > threshold.amberAbove) return TRAFFIC_LIGHT.AMBER;
  return TRAFFIC_LIGHT.GREEN;
}

function _initialMetricRow(key) {
  return {
    key,
    label: METRIC_CATALOGUE[key].label,
    citation: METRIC_CATALOGUE[key].citation,
    valueLabel: METRIC_CATALOGUE[key].valueLabel,
    pendingBackend: METRIC_CATALOGUE[key].pendingBackend === true,
    enabled: true,
    value: null,
    history: [], // sparkline buffer (numbers)
    tipShouldFire: false,
    recommendation: null,
    pulse: false, // true for one render cycle after a threshold cross
    pulseDismissed: false,
    foreground: false, // true when this row should bubble to the top of the panel
    rawPayload: null, // last update payload, for the hover tooltip details
  };
}

/**
 * Construct a fresh sidebar state object.
 *
 * Options:
 *   collapsed:        starting collapsed state; default false (open).
 *   dock:             'right' | 'bottom'; default 'right'.
 *   userThresholds:   override the default per-metric thresholds.
 *   disabledMetrics:  array of metric keys the user has disabled.
 */
export function createGuardrailsState(options = {}) {
  const {
    collapsed = false,
    dock = 'right',
    userThresholds = {},
    disabledMetrics = [],
  } = options;

  const thresholds = { ...DEFAULT_USER_THRESHOLDS };
  for (const key of METRIC_KEYS) {
    if (userThresholds[key]) {
      thresholds[key] = { ...DEFAULT_USER_THRESHOLDS[key], ...userThresholds[key] };
    }
  }

  const rows = {};
  for (const key of METRIC_KEYS) {
    rows[key] = _initialMetricRow(key);
    if (disabledMetrics.includes(key)) rows[key].enabled = false;
  }

  return {
    collapsed,
    dock,
    thresholds,
    rows,
    announcement: null, // most-recent aria-live message; cleared on next update
  };
}

// ---------------------------------------------------------------------------
// Update appliers
// ---------------------------------------------------------------------------


function _applyMetricUpdate(state, key, payload, valueExtractor) {
  if (!state.rows[key]) return state;
  const row = state.rows[key];
  if (!row.enabled) {
    row.rawPayload = payload;
    return state;
  }
  const value = valueExtractor(payload);
  row.value = value;
  row.rawPayload = payload;
  row.recommendation = payload?.recommendation ?? null;

  if (Number.isFinite(value)) {
    row.history = [...row.history, value].slice(-SPARKLINE_HISTORY);
  }

  const wasFiring = row.tipShouldFire;
  const willFire = Boolean(payload?.tipShouldFire ?? payload?.tip_should_fire);
  row.tipShouldFire = willFire;

  // Pulse only on the *transition* to firing — not while it stays firing.
  // pulseDismissed is reset whenever the metric drops back below threshold,
  // so the next crossing pulses again.
  if (!wasFiring && willFire) {
    row.pulse = true;
    row.pulseDismissed = false;
    row.foreground = true;
    state.announcement = `${row.label} threshold crossed: ${row.recommendation ?? ''}`.trim();
  } else if (wasFiring && !willFire) {
    row.pulse = false;
    row.pulseDismissed = false;
    row.foreground = false;
    state.announcement = null;
  } else {
    state.announcement = null;
  }
  return state;
}

export function applyCoverageUpdate(state, payload) {
  return _applyMetricUpdate(state, 'coverage', payload, p => p?.coverageFraction ?? p?.coverage_fraction ?? null);
}

export function applyDiversityUpdate(state, payload) {
  return _applyMetricUpdate(state, 'diversity', payload, p => p?.logDet ?? p?.log_det ?? null);
}

export function applyValidityUpdate(state, payload) {
  return _applyMetricUpdate(state, 'validity', payload, p => p?.rate ?? null);
}

export function applyCherryPickingUpdate(state, payload) {
  return _applyMetricUpdate(state, 'cherryPicking', payload, p => p?.score ?? null);
}

export function applyForkingPathsUpdate(state, payload) {
  return _applyMetricUpdate(state, 'forkingPaths', payload, p => p?.count ?? null);
}

// ---------------------------------------------------------------------------
// User actions
// ---------------------------------------------------------------------------


export function dismissPulse(state, key) {
  const row = state.rows?.[key];
  if (!row) return state;
  row.pulse = false;
  row.pulseDismissed = true;
  // Foregrounding stays — the user dismissed the pulse but the threshold is
  // still crossed; they can disable the metric entirely if they want it
  // hidden. This matches Lisnic 2025's "non-blocking" constraint: the user
  // acknowledges the alert without it disappearing entirely.
  return state;
}

export function setEnabled(state, key, enabled) {
  const row = state.rows?.[key];
  if (!row) return state;
  row.enabled = Boolean(enabled);
  if (!row.enabled) {
    row.foreground = false;
    row.pulse = false;
  }
  return state;
}

export function setUserThreshold(state, key, override) {
  if (!state.thresholds[key]) return state;
  state.thresholds[key] = { ...state.thresholds[key], ...override };
  return state;
}

export function resetMetric(state, key) {
  if (!state.rows[key]) return state;
  const enabledFlag = state.rows[key].enabled;
  state.rows[key] = _initialMetricRow(key);
  state.rows[key].enabled = enabledFlag;
  return state;
}

export function setCollapsed(state, collapsed) {
  state.collapsed = Boolean(collapsed);
  return state;
}

export function setDock(state, dock) {
  if (dock === 'right' || dock === 'bottom') state.dock = dock;
  return state;
}

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------


/**
 * Return the rows in render order. Foregrounded (threshold-crossing) rows
 * come first, in catalogue order; the rest stay in catalogue order behind.
 *
 * Disabled rows are hidden — the user opted them out, so we don't surface
 * them in the panel. They reappear as soon as ``setEnabled(state, key, true)``.
 */
export function visibleRows(state) {
  const enabled = METRIC_KEYS.map(k => state.rows[k]).filter(r => r.enabled);
  const fg = enabled.filter(r => r.foreground);
  const bg = enabled.filter(r => !r.foreground);
  return [...fg, ...bg];
}

export function rowTrafficLight(state, key) {
  const row = state.rows?.[key];
  if (!row) return TRAFFIC_LIGHT.IDLE;
  if (!row.enabled) return TRAFFIC_LIGHT.DISABLED;
  if (row.value == null) return TRAFFIC_LIGHT.IDLE;
  return trafficLight(row.value, state.thresholds[key]);
}
