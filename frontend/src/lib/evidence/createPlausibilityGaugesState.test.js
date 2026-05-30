import test from "node:test";
import assert from "node:assert/strict";

import {
  GAUGE_TONES,
  OFF_DISTRIBUTION_THRESHOLD,
  createPlausibilityGaugesState,
} from "./createPlausibilityGaugesState.js";

function findGauge(state, key) {
  return state.gauges.find((g) => g.key === key);
}

test("with no validity runs and no plausibility payload, every gauge is null", () => {
  const state = createPlausibilityGaugesState();
  assert.equal(state.hasEdit, false);
  for (const gauge of state.gauges) {
    assert.equal(gauge.value, null);
    assert.equal(gauge.displayValue, "—");
    assert.equal(gauge.tone, null);
  }
  assert.equal(state.offDistribution, false);
});

test("validity is the fraction of reruns that flipped the prediction", () => {
  const state = createPlausibilityGaugesState({
    validityRuns: [
      { flipped: true },
      { flipped: false },
      { flipped: true },
      { flipped: true },
    ],
  });
  const validity = findGauge(state, "validity");
  assert.equal(validity.value, 0.75);
  assert.equal(validity.displayValue, "75%");
  assert.equal(validity.tone, GAUGE_TONES.CONFIDENT);
  assert.match(validity.hint, /3\/4 reruns flipped/);
});

test("validity is null until at least one rerun has been observed", () => {
  const state = createPlausibilityGaugesState({ validityRuns: [] });
  const validity = findGauge(state, "validity");
  assert.equal(validity.value, null);
  assert.match(validity.hint, /Rerun the prediction/);
});

test("validity tone goes uncertain when most reruns failed to flip", () => {
  const state = createPlausibilityGaugesState({
    validityRuns: [
      { flipped: false },
      { flipped: false },
      { flipped: false },
      { flipped: true },
    ],
  });
  const validity = findGauge(state, "validity");
  assert.equal(validity.value, 0.25);
  assert.equal(validity.tone, GAUGE_TONES.UNCERTAIN);
});

test("validity ignores malformed run entries rather than throwing", () => {
  const state = createPlausibilityGaugesState({
    validityRuns: [{ flipped: true }, null, { flipped: "yes" }, { flipped: false }],
  });
  const validity = findGauge(state, "validity");
  assert.equal(validity.value, 0.5);
  assert.match(validity.hint, /1\/2 reruns/);
});

test("proximity surfaces proximity_pct when calibration is loaded", () => {
  const state = createPlausibilityGaugesState({
    plausibility: { proximity: 1.234, proximity_pct: 0.42, sparsity: 0.8 },
  });
  const proximity = findGauge(state, "proximity");
  assert.equal(proximity.value, 0.42);
  assert.match(proximity.hint, /DTW distance 1\.23/);
});

test("proximity reports honest n/a + raw DTW when no calibration cache exists", () => {
  const state = createPlausibilityGaugesState({
    plausibility: { proximity: 1.234, proximity_pct: null, sparsity: 0.8 },
  });
  const proximity = findGauge(state, "proximity");
  assert.equal(proximity.value, null);
  assert.equal(proximity.displayValue, "—");
  assert.match(proximity.hint, /no dataset calibration loaded/);
});

test("sparsity fills directly from the backend value in [0, 1]", () => {
  const state = createPlausibilityGaugesState({
    plausibility: { proximity: 0.5, proximity_pct: 0.7, sparsity: 0.91 },
  });
  const sparsity = findGauge(state, "sparsity");
  assert.equal(sparsity.value, 0.91);
  assert.equal(sparsity.tone, GAUGE_TONES.CONFIDENT);
});

test("plausibility surfaces yNN with neighbour-count hint", () => {
  const state = createPlausibilityGaugesState({
    plausibility: { plausibility: 0.6, plausibility_k: 5 },
    hasEdit: true,
  });
  const ynn = findGauge(state, "plausibility");
  assert.equal(ynn.value, 0.6);
  assert.equal(ynn.displayValue, "60%");
  assert.match(ynn.hint, /3\/5 neighbours/);
});

test("plausibility reports honest n/a when no yNN index is available", () => {
  const state = createPlausibilityGaugesState({
    plausibility: { proximity: 1.2, sparsity: 0.7, plausibility: null, plausibility_k: null },
    hasEdit: true,
  });
  const ynn = findGauge(state, "plausibility");
  assert.equal(ynn.value, null);
  assert.equal(ynn.displayValue, "—");
  assert.match(ynn.hint, /No yNN index/);
});

test("every gauge carries a `source` (VAL-XXX) and a paper reference", () => {
  const state = createPlausibilityGaugesState();
  for (const gauge of state.gauges) {
    assert.ok(gauge.source && gauge.source.length > 0, `${gauge.key} missing source`);
    assert.ok(
      gauge.reference && gauge.reference.length > 0,
      `${gauge.key} missing reference`,
    );
  }
  // Concrete paper-name spot checks — REWORK-06 requires named references.
  assert.match(findGauge(state, "validity").reference, /Verma|Mothilal/);
  assert.match(findGauge(state, "proximity").reference, /Delaney/);
  assert.match(findGauge(state, "sparsity").reference, /Delaney/);
  assert.match(findGauge(state, "plausibility").reference, /Pawelczyk|Verma/);
});

test("off-distribution fires below the yNN threshold and explains why", () => {
  const state = createPlausibilityGaugesState({
    plausibility: { plausibility: OFF_DISTRIBUTION_THRESHOLD - 0.05, plausibility_k: 5 },
    hasEdit: true,
  });
  assert.equal(state.offDistribution, true);
  assert.match(state.offDistributionReason, /Few training neighbours/);
});

test("off-distribution stays quiet when plausibility is healthy", () => {
  const state = createPlausibilityGaugesState({
    plausibility: { plausibility: 0.8, plausibility_k: 5, sparsity: 0.9 },
    hasEdit: true,
  });
  assert.equal(state.offDistribution, false);
  assert.equal(state.offDistributionReason, null);
});

test("off-distribution does not fire on missing yNN — null is not a claim", () => {
  const state = createPlausibilityGaugesState({
    plausibility: { plausibility: null, plausibility_k: null, sparsity: 0.4 },
    hasEdit: true,
  });
  assert.equal(state.offDistribution, false);
});

test("off-distribution reason names low sparsity as a corroborating signal", () => {
  const state = createPlausibilityGaugesState({
    plausibility: { plausibility: 0.2, plausibility_k: 5, sparsity: 0.3 },
    hasEdit: true,
  });
  assert.equal(state.offDistribution, true);
  assert.match(state.offDistributionReason, /touches more than half/);
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
