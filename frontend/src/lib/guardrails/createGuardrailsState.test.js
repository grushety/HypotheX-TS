import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_USER_THRESHOLDS,
  METRIC_CATALOGUE,
  METRIC_KEYS,
  SPARKLINE_HISTORY,
  TRAFFIC_LIGHT,
  applyCherryPickingUpdate,
  applyCoverageUpdate,
  applyDiversityUpdate,
  applyForkingPathsUpdate,
  applyValidityUpdate,
  createGuardrailsState,
  dismissPulse,
  resetMetric,
  rowTrafficLight,
  setCollapsed,
  setDock,
  setEnabled,
  setUserThreshold,
  trafficLight,
  visibleRows,
} from './createGuardrailsState.js';

// ---------------------------------------------------------------------------
// trafficLight
// ---------------------------------------------------------------------------

test('trafficLight: idle for null/undefined/NaN', () => {
  assert.equal(trafficLight(null, { redBelow: 0.4 }), TRAFFIC_LIGHT.IDLE);
  assert.equal(trafficLight(undefined, { redBelow: 0.4 }), TRAFFIC_LIGHT.IDLE);
  assert.equal(trafficLight(NaN, { redBelow: 0.4 }), TRAFFIC_LIGHT.IDLE);
});

test('trafficLight: lower-is-worse direction', () => {
  const t = { amberBelow: 0.6, redBelow: 0.4 };
  assert.equal(trafficLight(0.8, t), TRAFFIC_LIGHT.GREEN);
  assert.equal(trafficLight(0.5, t), TRAFFIC_LIGHT.AMBER);
  assert.equal(trafficLight(0.3, t), TRAFFIC_LIGHT.RED);
});

test('trafficLight: higher-is-worse direction', () => {
  const t = { amberAbove: 0.5, redAbove: 0.7 };
  assert.equal(trafficLight(0.2, t), TRAFFIC_LIGHT.GREEN);
  assert.equal(trafficLight(0.6, t), TRAFFIC_LIGHT.AMBER);
  assert.equal(trafficLight(0.9, t), TRAFFIC_LIGHT.RED);
});

test('trafficLight: red precedence over amber on same direction', () => {
  // Edge case: 0.4 is both below the amber threshold (0.6) and below the
  // red threshold (0.4). The `<` comparison means 0.4 is NOT strictly
  // below 0.4 → amber, not red. Verify this exact boundary.
  const t = { amberBelow: 0.6, redBelow: 0.4 };
  assert.equal(trafficLight(0.4, t), TRAFFIC_LIGHT.AMBER);
  assert.equal(trafficLight(0.39, t), TRAFFIC_LIGHT.RED);
});

// ---------------------------------------------------------------------------
// createGuardrailsState
// ---------------------------------------------------------------------------

test('createGuardrailsState: defaults', () => {
  const s = createGuardrailsState();
  assert.equal(s.collapsed, false);
  assert.equal(s.dock, 'right');
  assert.equal(s.announcement, null);
  for (const key of METRIC_KEYS) {
    const row = s.rows[key];
    assert.ok(row, `row ${key} exists`);
    assert.equal(row.enabled, true);
    assert.equal(row.value, null);
    assert.deepEqual(row.history, []);
    assert.equal(row.tipShouldFire, false);
    assert.equal(row.pulse, false);
  }
});

test('createGuardrailsState: applies user threshold overrides', () => {
  const s = createGuardrailsState({
    userThresholds: { coverage: { amberBelow: 0.8 } },
  });
  assert.equal(s.thresholds.coverage.amberBelow, 0.8);
  // redBelow not overridden — preserved from defaults
  assert.equal(s.thresholds.coverage.redBelow, DEFAULT_USER_THRESHOLDS.coverage.redBelow);
});

test('createGuardrailsState: applies disabled-metrics list', () => {
  const s = createGuardrailsState({ disabledMetrics: ['validity', 'forkingPaths'] });
  assert.equal(s.rows.validity.enabled, false);
  assert.equal(s.rows.forkingPaths.enabled, false);
  assert.equal(s.rows.coverage.enabled, true);
});

// ---------------------------------------------------------------------------
// applyCoverageUpdate (representative; other appliers share the path)
// ---------------------------------------------------------------------------

test('applyCoverageUpdate: stores value and pushes to sparkline', () => {
  const s = createGuardrailsState();
  applyCoverageUpdate(s, { coverageFraction: 0.42, tipShouldFire: false });
  assert.equal(s.rows.coverage.value, 0.42);
  assert.deepEqual(s.rows.coverage.history, [0.42]);
});

test('applyCoverageUpdate: snake_case payload also accepted', () => {
  const s = createGuardrailsState();
  applyCoverageUpdate(s, { coverage_fraction: 0.71, tip_should_fire: false });
  assert.equal(s.rows.coverage.value, 0.71);
});

test('applyCoverageUpdate: sparkline buffer caps at SPARKLINE_HISTORY', () => {
  const s = createGuardrailsState();
  for (let i = 0; i < SPARKLINE_HISTORY + 5; i++) {
    applyCoverageUpdate(s, { coverageFraction: i, tipShouldFire: false });
  }
  assert.equal(s.rows.coverage.history.length, SPARKLINE_HISTORY);
  // Oldest values dropped — the buffer holds the most recent SPARKLINE_HISTORY entries
  assert.equal(s.rows.coverage.history[0], 5);
  assert.equal(s.rows.coverage.history[SPARKLINE_HISTORY - 1], SPARKLINE_HISTORY + 4);
});

test('applyCoverageUpdate: no value (NaN) is stored but not pushed to sparkline', () => {
  const s = createGuardrailsState();
  applyCoverageUpdate(s, { coverageFraction: NaN, tipShouldFire: false });
  assert.ok(Number.isNaN(s.rows.coverage.value));
  assert.deepEqual(s.rows.coverage.history, []);
});

// ---------------------------------------------------------------------------
// Pulse + announcement on threshold crossing
// ---------------------------------------------------------------------------

test('threshold cross: pulse fires + foreground + aria announcement', () => {
  const s = createGuardrailsState();
  // First update: not firing → no pulse
  applyCoverageUpdate(s, { coverageFraction: 0.7, tipShouldFire: false });
  assert.equal(s.rows.coverage.pulse, false);
  assert.equal(s.rows.coverage.foreground, false);
  assert.equal(s.announcement, null);

  // Cross: firing → pulse on, foreground, announcement set
  applyCoverageUpdate(s, {
    coverageFraction: 0.1, tipShouldFire: true,
    recommendation: 'Try a different shape',
  });
  assert.equal(s.rows.coverage.pulse, true);
  assert.equal(s.rows.coverage.foreground, true);
  assert.ok(s.announcement);
  assert.match(s.announcement, /threshold crossed/);
  assert.match(s.announcement, /Try a different shape/);
});

test('threshold cross: stays firing → no re-pulse', () => {
  const s = createGuardrailsState();
  applyCoverageUpdate(s, { coverageFraction: 0.1, tipShouldFire: true });
  assert.equal(s.rows.coverage.pulse, true);
  // Reset pulse flag (simulating UI consuming the animation)
  s.rows.coverage.pulse = false;
  // Another update with tipShouldFire=true should NOT re-pulse
  applyCoverageUpdate(s, { coverageFraction: 0.1, tipShouldFire: true });
  assert.equal(s.rows.coverage.pulse, false);
});

test('threshold cross: drops back below → pulse cleared, foreground gone', () => {
  const s = createGuardrailsState();
  applyCoverageUpdate(s, { coverageFraction: 0.1, tipShouldFire: true });
  assert.equal(s.rows.coverage.foreground, true);
  applyCoverageUpdate(s, { coverageFraction: 0.8, tipShouldFire: false });
  assert.equal(s.rows.coverage.foreground, false);
  assert.equal(s.rows.coverage.pulse, false);
});

test('dismissPulse clears pulse but keeps foreground', () => {
  const s = createGuardrailsState();
  applyCoverageUpdate(s, { coverageFraction: 0.1, tipShouldFire: true });
  dismissPulse(s, 'coverage');
  assert.equal(s.rows.coverage.pulse, false);
  assert.equal(s.rows.coverage.pulseDismissed, true);
  // Foreground stays — Lisnic 2025 non-blocking: user acknowledged the
  // alert but the threshold is still crossed
  assert.equal(s.rows.coverage.foreground, true);
});

test('dismissPulse: unknown key is a no-op', () => {
  const s = createGuardrailsState();
  dismissPulse(s, 'nonexistent');
  // No throw, state unchanged
  assert.equal(s.rows.coverage.pulse, false);
});

// ---------------------------------------------------------------------------
// All metric appliers route through the same pipeline
// ---------------------------------------------------------------------------

test('applyDiversityUpdate: reads logDet field', () => {
  const s = createGuardrailsState();
  applyDiversityUpdate(s, { logDet: -3.2, tipShouldFire: false });
  assert.equal(s.rows.diversity.value, -3.2);
});

test('applyValidityUpdate: reads rate field', () => {
  const s = createGuardrailsState();
  applyValidityUpdate(s, { rate: 0.45, tipShouldFire: false });
  assert.equal(s.rows.validity.value, 0.45);
});

test('applyCherryPickingUpdate: reads score field', () => {
  const s = createGuardrailsState();
  applyCherryPickingUpdate(s, { score: 0.85, tipShouldFire: true,
                                  recommendation: 'all top utility' });
  assert.equal(s.rows.cherryPicking.value, 0.85);
  assert.equal(s.rows.cherryPicking.recommendation, 'all top utility');
});

test('applyForkingPathsUpdate: reads count field', () => {
  const s = createGuardrailsState();
  applyForkingPathsUpdate(s, { count: 7, tipShouldFire: false });
  assert.equal(s.rows.forkingPaths.value, 7);
});

// ---------------------------------------------------------------------------
// Disabled metrics
// ---------------------------------------------------------------------------

test('disabled metric: update payload stored but value not advanced', () => {
  const s = createGuardrailsState({ disabledMetrics: ['coverage'] });
  applyCoverageUpdate(s, { coverageFraction: 0.42, tipShouldFire: true });
  assert.equal(s.rows.coverage.value, null);
  assert.equal(s.rows.coverage.tipShouldFire, false);
  assert.equal(s.rows.coverage.foreground, false);
});

test('setEnabled: re-enabling resumes updates', () => {
  const s = createGuardrailsState({ disabledMetrics: ['coverage'] });
  setEnabled(s, 'coverage', true);
  applyCoverageUpdate(s, { coverageFraction: 0.42, tipShouldFire: false });
  assert.equal(s.rows.coverage.value, 0.42);
});

test('setEnabled: disabling clears foreground / pulse', () => {
  const s = createGuardrailsState();
  applyCoverageUpdate(s, { coverageFraction: 0.1, tipShouldFire: true });
  assert.equal(s.rows.coverage.foreground, true);
  setEnabled(s, 'coverage', false);
  assert.equal(s.rows.coverage.foreground, false);
  assert.equal(s.rows.coverage.pulse, false);
});

// ---------------------------------------------------------------------------
// rowTrafficLight selector
// ---------------------------------------------------------------------------

test('rowTrafficLight: disabled wins over value', () => {
  const s = createGuardrailsState({ disabledMetrics: ['coverage'] });
  assert.equal(rowTrafficLight(s, 'coverage'), TRAFFIC_LIGHT.DISABLED);
});

test('rowTrafficLight: idle when value is null', () => {
  const s = createGuardrailsState();
  assert.equal(rowTrafficLight(s, 'coverage'), TRAFFIC_LIGHT.IDLE);
});

test('rowTrafficLight: respects per-metric thresholds', () => {
  const s = createGuardrailsState();
  applyCoverageUpdate(s, { coverageFraction: 0.8, tipShouldFire: false });
  assert.equal(rowTrafficLight(s, 'coverage'), TRAFFIC_LIGHT.GREEN);
  applyCoverageUpdate(s, { coverageFraction: 0.5, tipShouldFire: false });
  assert.equal(rowTrafficLight(s, 'coverage'), TRAFFIC_LIGHT.AMBER);
  applyCoverageUpdate(s, { coverageFraction: 0.2, tipShouldFire: true });
  assert.equal(rowTrafficLight(s, 'coverage'), TRAFFIC_LIGHT.RED);
});

// ---------------------------------------------------------------------------
// visibleRows ordering
// ---------------------------------------------------------------------------

test('visibleRows: foreground rows surface first', () => {
  const s = createGuardrailsState();
  applyValidityUpdate(s, { rate: 0.1, tipShouldFire: true,
                            recommendation: 'low' });
  const rows = visibleRows(s);
  // Validity is now foregrounded → first
  assert.equal(rows[0].key, 'validity');
  // Other rows follow in catalogue order
  const tail = rows.slice(1).map(r => r.key);
  for (const k of tail) {
    assert.notEqual(k, 'validity');
  }
});

test('visibleRows: hides disabled metrics', () => {
  const s = createGuardrailsState({ disabledMetrics: ['forkingPaths'] });
  const keys = visibleRows(s).map(r => r.key);
  assert.ok(!keys.includes('forkingPaths'));
});

// ---------------------------------------------------------------------------
// Settings / lifecycle
// ---------------------------------------------------------------------------

test('setUserThreshold updates one direction without dropping the other', () => {
  const s = createGuardrailsState();
  setUserThreshold(s, 'coverage', { amberBelow: 0.9 });
  assert.equal(s.thresholds.coverage.amberBelow, 0.9);
  assert.equal(s.thresholds.coverage.redBelow, DEFAULT_USER_THRESHOLDS.coverage.redBelow);
});

test('setUserThreshold: unknown key is a no-op', () => {
  const s = createGuardrailsState();
  setUserThreshold(s, 'bogus', { amberBelow: 0.5 });
  // No throw; original thresholds preserved
  assert.deepEqual(
    Object.keys(s.thresholds).sort(),
    [...METRIC_KEYS].sort(),
  );
});

test('resetMetric clears history and value but preserves enabled flag', () => {
  const s = createGuardrailsState();
  applyCoverageUpdate(s, { coverageFraction: 0.1, tipShouldFire: true });
  setEnabled(s, 'coverage', false);
  resetMetric(s, 'coverage');
  assert.equal(s.rows.coverage.value, null);
  assert.deepEqual(s.rows.coverage.history, []);
  assert.equal(s.rows.coverage.enabled, false); // preserved
});

test('setCollapsed / setDock', () => {
  const s = createGuardrailsState();
  setCollapsed(s, true);
  assert.equal(s.collapsed, true);
  setDock(s, 'bottom');
  assert.equal(s.dock, 'bottom');
  // Invalid dock value is ignored
  setDock(s, 'left');
  assert.equal(s.dock, 'bottom');
});

// ---------------------------------------------------------------------------
// Catalogue invariants
// ---------------------------------------------------------------------------

test('METRIC_CATALOGUE has an entry for every METRIC_KEYS', () => {
  for (const key of METRIC_KEYS) {
    assert.ok(METRIC_CATALOGUE[key], `catalogue entry for ${key}`);
    assert.equal(METRIC_CATALOGUE[key].key, key);
    assert.ok(METRIC_CATALOGUE[key].label);
    assert.ok(METRIC_CATALOGUE[key].topic);
    assert.ok(METRIC_CATALOGUE[key].citation);
  }
});

test('forkingPaths flagged pendingBackend (no metric ships yet)', () => {
  assert.equal(METRIC_CATALOGUE.forkingPaths.pendingBackend, true);
  // Other rows are not pending
  assert.equal(METRIC_CATALOGUE.coverage.pendingBackend, undefined);
});
