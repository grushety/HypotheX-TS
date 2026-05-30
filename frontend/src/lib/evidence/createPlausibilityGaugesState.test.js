import test from "node:test";
import assert from "node:assert/strict";

import { SOFT_CONSTRAINT_STATUS } from "../constraints/evaluateSoftConstraints.js";
import {
  GAUGE_TONES,
  createPlausibilityGaugesState,
} from "./createPlausibilityGaugesState.js";

function passEvent() {
  return { payload: { constraintStatus: SOFT_CONSTRAINT_STATUS.PASS } };
}

function warnEvent() {
  return { payload: { constraintStatus: SOFT_CONSTRAINT_STATUS.WARN } };
}

// Note: SOFT_CONSTRAINT_STATUS only has PASS and WARN — there is no FAIL
// constant in evaluateSoftConstraints. A WARN event counts toward `total`
// but not `passes`, so a series of WARNs drags the gauge below the confident
// tier, which is the right glance-level cue.

test("with no events and no plausibility payload, every gauge is null", () => {
  const state = createPlausibilityGaugesState();
  assert.equal(state.hasEdit, false);
  for (const gauge of state.gauges) {
    assert.equal(gauge.value, null);
    assert.equal(gauge.displayValue, "—");
    assert.equal(gauge.tone, null);
  }
});

test("pass rate counts only events that carry a constraintStatus", () => {
  const state = createPlausibilityGaugesState({
    events: [
      passEvent(),
      warnEvent(),
      { payload: {} }, // structural-only event, ignored
      passEvent(),
    ],
  });
  const validity = state.gauges.find((g) => g.key === "pass_rate");
  assert.equal(validity.value, 2 / 3);
  assert.equal(validity.displayValue, "67%");
  assert.equal(validity.tone, GAUGE_TONES.CONFIDENT);
});

test("pass rate is null until at least one constraint-bearing event lands", () => {
  const state = createPlausibilityGaugesState({
    events: [{ payload: {} }, { payload: {} }],
  });
  const validity = state.gauges.find((g) => g.key === "pass_rate");
  assert.equal(validity.value, null);
});

test("pass-rate tone drops to uncertain when most edits raise WARN", () => {
  const state = createPlausibilityGaugesState({
    events: [passEvent(), warnEvent(), warnEvent(), warnEvent()],
  });
  const validity = state.gauges.find((g) => g.key === "pass_rate");
  assert.equal(validity.value, 0.25);
  assert.equal(validity.tone, GAUGE_TONES.UNCERTAIN);
});

test("proximity gauge surfaces proximity_pct when calibration is loaded", () => {
  const state = createPlausibilityGaugesState({
    plausibility: { proximity: 1.234, proximity_pct: 0.42, sparsity: 0.8 },
  });
  const proximity = state.gauges.find((g) => g.key === "proximity");
  assert.equal(proximity.value, 0.42);
  assert.equal(proximity.displayValue, "42%");
  assert.match(proximity.hint, /DTW distance 1\.23/);
});

test("proximity gauge is n/a with an explanation when calibration is missing", () => {
  const state = createPlausibilityGaugesState({
    plausibility: { proximity: 1.234, proximity_pct: null, sparsity: 0.8 },
  });
  const proximity = state.gauges.find((g) => g.key === "proximity");
  assert.equal(proximity.value, null);
  assert.equal(proximity.displayValue, "—");
  assert.match(proximity.hint, /no dataset calibration loaded/);
});

test("sparsity gauge fills directly from the backend value in [0, 1]", () => {
  const state = createPlausibilityGaugesState({
    plausibility: { proximity: 0.5, proximity_pct: 0.7, sparsity: 0.91 },
  });
  const sparsity = state.gauges.find((g) => g.key === "sparsity");
  assert.equal(sparsity.value, 0.91);
  assert.equal(sparsity.displayValue, "91%");
  assert.equal(sparsity.tone, GAUGE_TONES.CONFIDENT);
});

test("plausibility gauge surfaces yNN fraction with neighbour-count hint", () => {
  const state = createPlausibilityGaugesState({
    plausibility: { plausibility: 0.6, plausibility_k: 5 },
    hasEdit: true,
  });
  const ynn = state.gauges.find((g) => g.key === "plausibility");
  assert.equal(ynn.value, 0.6);
  assert.equal(ynn.displayValue, "60%");
  assert.match(ynn.hint, /3\/5 neighbours/);
});

test("plausibility gauge reports honest n/a when no yNN index is available", () => {
  const state = createPlausibilityGaugesState({
    plausibility: { proximity: 1.2, sparsity: 0.7, plausibility: null, plausibility_k: null },
    hasEdit: true,
  });
  const ynn = state.gauges.find((g) => g.key === "plausibility");
  assert.equal(ynn.value, null);
  assert.equal(ynn.displayValue, "—");
  assert.match(ynn.hint, /No yNN index/);
});

test("source field cites the backing service so the UI can show provenance", () => {
  const state = createPlausibilityGaugesState();
  const passRateSource = state.gauges.find((g) => g.key === "pass_rate").source;
  assert.match(passRateSource, /constraint engine/);
  assert.match(passRateSource, /not VAL-012 yet/);
  assert.match(state.gauges.find((g) => g.key === "proximity").source, /VAL-004/);
  assert.match(state.gauges.find((g) => g.key === "sparsity").source, /VAL-004/);
  assert.match(state.gauges.find((g) => g.key === "plausibility").source, /VAL-003/);
});

test("malformed plausibility payload yields honest n/a (never fabricated 0%)", () => {
  const state = createPlausibilityGaugesState({
    plausibility: {
      proximity: "oops",
      proximity_pct: NaN,
      sparsity: undefined,
      plausibility: -1,
      plausibility_k: 0,
    },
  });
  for (const gauge of state.gauges) {
    assert.equal(gauge.value, null);
    assert.equal(gauge.displayValue, "—");
    assert.equal(gauge.tone, null);
  }
});
