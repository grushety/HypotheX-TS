import test from "node:test";
import assert from "node:assert/strict";

import {
  UNCERTAINTY_LEVELS,
  assessUncertainty,
  entropyNormalized,
  topPSet,
  topRunnerMargin,
} from "./computeUncertainty.js";

test("entropyNormalized is 1 for a uniform distribution", () => {
  assert.equal(entropyNormalized([0.25, 0.25, 0.25, 0.25]), 1);
});

test("entropyNormalized is 0 for a one-hot distribution", () => {
  assert.equal(entropyNormalized([1, 0, 0, 0]), 0);
});

test("entropyNormalized clamps malformed entries to a finite [0, 1] value", () => {
  const h = entropyNormalized([0.5, 0.5, NaN, -0.2]);
  assert.ok(h >= 0 && h <= 1, `expected H in [0,1]; got ${h}`);
});

test("topRunnerMargin returns p_(1) − p_(2)", () => {
  assert.equal(topRunnerMargin([0.86, 0.14]).toFixed(2), "0.72");
  assert.equal(topRunnerMargin([0.55, 0.45]).toFixed(2), "0.10");
  assert.equal(topRunnerMargin([0.4, 0.4, 0.2]).toFixed(2), "0.00");
});

test("topRunnerMargin returns 1 for a single class (no runner-up)", () => {
  assert.equal(topRunnerMargin([0.99]), 1);
});

test("topPSet picks the smallest cumulative-probability set covering the target", () => {
  const scores = [
    { label: "Gun", probability: 0.86 },
    { label: "Point", probability: 0.14 },
  ];
  // 0.86 alone is short of 0.9 → both classes needed.
  assert.deepEqual(topPSet(scores, 0.9), ["Gun", "Point"]);
  // 0.86 alone already covers ≥ 0.85 / ≥ 0.80 → smallest set is just Gun.
  assert.deepEqual(topPSet(scores, 0.85), ["Gun"]);
  assert.deepEqual(topPSet(scores, 0.8), ["Gun"]);
});

test("topPSet returns at least one label even when no entry hits the target", () => {
  const scores = [{ label: "a", probability: 0.4 }];
  assert.deepEqual(topPSet(scores, 0.9), ["a"]);
});

test("topPSet ranks by probability, not source order", () => {
  const scores = [
    { label: "c", probability: 0.10 },
    { label: "a", probability: 0.60 },
    { label: "b", probability: 0.30 },
  ];
  assert.deepEqual(topPSet(scores, 0.85), ["a", "b"]);
});

test("assessUncertainty flags a near-tie even when entropy is moderate", () => {
  const result = assessUncertainty([
    { label: "Gun", probability: 0.52 },
    { label: "Point", probability: 0.48 },
  ]);
  assert.equal(result.nearTie, true);
  assert.equal(result.isUncertain, true);
  assert.equal(result.level, UNCERTAINTY_LEVELS.NEAR_TIE);
  assert.deepEqual(result.set, ["Gun", "Point"]);
});

test("assessUncertainty stays quiet for a confident one-sided prediction", () => {
  const result = assessUncertainty([
    { label: "Gun", probability: 0.97 },
    { label: "Point", probability: 0.03 },
  ]);
  assert.equal(result.nearTie, false);
  assert.equal(result.isUncertain, false);
  assert.equal(result.level, UNCERTAINTY_LEVELS.CONFIDENT);
  assert.equal(result.setSize, 1);
});

test("assessUncertainty reports moderate when entropy is mid-range without a tie", () => {
  // p ≈ [0.92, 0.08] sits between the moderate and uncertain thresholds —
  // big enough margin to not be a tie, but enough spread that the user
  // shouldn't see a fully-quiet chip.
  const result = assessUncertainty([
    { label: "Gun", probability: 0.92 },
    { label: "Point", probability: 0.08 },
  ]);
  assert.equal(result.nearTie, false);
  assert.equal(result.isUncertain, false);
  assert.equal(result.level, UNCERTAINTY_LEVELS.MODERATE);
});

test("assessUncertainty flags high entropy on a many-class spread without a tight tie", () => {
  // 4 classes, top is 0.32 vs runner-up 0.24 — margin 0.08 ⇒ near-tie wins.
  const tieDriven = assessUncertainty([
    { label: "a", probability: 0.32 },
    { label: "b", probability: 0.24 },
    { label: "c", probability: 0.22 },
    { label: "d", probability: 0.22 },
  ]);
  assert.equal(tieDriven.level, UNCERTAINTY_LEVELS.NEAR_TIE);

  // 4 classes, top is 0.50 vs runner-up 0.20 — margin 0.30 (NOT near tie), but
  // entropy across the spread is high enough to escalate to UNCERTAIN.
  const spread = assessUncertainty([
    { label: "a", probability: 0.50 },
    { label: "b", probability: 0.20 },
    { label: "c", probability: 0.18 },
    { label: "d", probability: 0.12 },
  ]);
  assert.equal(spread.nearTie, false);
  assert.equal(spread.isUncertain, true);
  assert.equal(spread.level, UNCERTAINTY_LEVELS.UNCERTAIN);
});

test("assessUncertainty respects custom thresholds", () => {
  const probs = [
    { label: "a", probability: 0.7 },
    { label: "b", probability: 0.3 },
  ];
  // With a 0.5 margin threshold, 0.4 margin reads as near-tie.
  const strict = assessUncertainty(probs, { marginThreshold: 0.5 });
  assert.equal(strict.nearTie, true);
});

test("assessUncertainty defends against malformed scores arrays", () => {
  const result = assessUncertainty(undefined);
  assert.equal(result.set.length, 0);
  // No probabilities → defensive no-op: confident, not uncertain, no false
  // near-tie alarm from the 0-margin path.
  assert.equal(result.entropy, 0);
  assert.equal(result.margin, 0);
  assert.equal(result.nearTie, false);
  assert.equal(result.isUncertain, false);
  assert.equal(result.level, UNCERTAINTY_LEVELS.CONFIDENT);
});
