import test from "node:test";
import assert from "node:assert/strict";

import { createCohortResultModel } from "./createCohortResultModel.js";

const samplePayload = {
  method: "scalar-op cohort with iid percentile bootstrap",
  reference: "Efron 1979",
  per_series: [
    {
      sample_index: 0,
      baseline_class: "Gun",
      current_class: "Gun",
      baseline_prob: 0.86,
      current_prob: 0.62,
      delta: -0.24,
      flipped: false,
    },
    {
      sample_index: 1,
      baseline_class: "Gun",
      current_class: "Point",
      baseline_prob: 0.86,
      current_prob: 0.30,
      delta: -0.56,
      flipped: true,
    },
  ],
  aggregates: {
    total: 2,
    flipped_count: 1,
    flip_rate: 0.5,
    flip_rate_ci: { lower: 0.2, upper: 0.8, confidence_level: 0.95, iterations: 1000 },
    mean_delta: -0.4,
    mean_delta_ci: { lower: -0.6, upper: -0.2, confidence_level: 0.95, iterations: 1000 },
    delta_histogram_bin_edges: [-0.6, -0.3, 0.0, 0.3, 0.6],
    delta_histogram_counts: [1, 1, 0, 0],
    biggest_mover_index: 1,
  },
};

test("hasData is false when no payload is given", () => {
  const model = createCohortResultModel(null);
  assert.equal(model.hasData, false);
  assert.deepEqual(model.rows, []);
  assert.equal(model.summary, null);
});

test("rows are sorted by signed delta descending (positive movers first)", () => {
  const model = createCohortResultModel({
    ...samplePayload,
    per_series: [
      { sample_index: 0, baseline_class: "G", current_class: "G", baseline_prob: 0.8, current_prob: 0.9, delta: 0.1, flipped: false },
      { sample_index: 1, baseline_class: "G", current_class: "P", baseline_prob: 0.8, current_prob: 0.2, delta: -0.6, flipped: true },
      { sample_index: 2, baseline_class: "G", current_class: "G", baseline_prob: 0.8, current_prob: 0.6, delta: -0.2, flipped: false },
    ],
  });
  const deltas = model.rows.map((r) => r.delta);
  assert.deepEqual(deltas, [0.1, -0.2, -0.6]);
});

test("biggest mover is flagged on the corresponding row", () => {
  const model = createCohortResultModel(samplePayload);
  const flagged = model.rows.find((r) => r.isBiggestMover);
  assert.equal(flagged.sampleIndex, 1);
});

test("summary surfaces flip rate + mean delta + CI labels", () => {
  const model = createCohortResultModel(samplePayload);
  assert.equal(model.summary.flipRateLabel, "50%");
  assert.equal(model.summary.meanDeltaLabel, "−40.0");
  assert.equal(model.summary.flipRateCi.lowerLabel, "20%");
  assert.equal(model.summary.flipRateCi.upperLabel, "80%");
  assert.equal(model.summary.meanDeltaCi.lowerLabel, "−60.0");
  assert.equal(model.summary.meanDeltaCi.upperLabel, "−20.0");
});

test("cherry-picking caveat fires when the mean-delta CI crosses zero", () => {
  const model = createCohortResultModel({
    ...samplePayload,
    aggregates: {
      ...samplePayload.aggregates,
      mean_delta: -0.05,
      mean_delta_ci: { lower: -0.2, upper: 0.1, confidence_level: 0.95, iterations: 1000 },
    },
  });
  assert.match(model.cherryPickingWarning ?? "", /crosses zero/);
});

test("cherry-picking caveat fires when the flip-rate CI is wider than 40pp", () => {
  const model = createCohortResultModel({
    ...samplePayload,
    aggregates: {
      ...samplePayload.aggregates,
      mean_delta_ci: { lower: -0.5, upper: -0.3, confidence_level: 0.95, iterations: 1000 },
      flip_rate_ci: { lower: 0.05, upper: 0.85, confidence_level: 0.95, iterations: 1000 },
    },
  });
  assert.match(model.cherryPickingWarning ?? "", /wider than 40/);
});

test("cherry-picking caveat stays quiet when CIs are tight and one-sided", () => {
  const model = createCohortResultModel({
    ...samplePayload,
    aggregates: {
      ...samplePayload.aggregates,
      flip_rate_ci: { lower: 0.4, upper: 0.6, confidence_level: 0.95, iterations: 1000 },
      mean_delta_ci: { lower: -0.45, upper: -0.35, confidence_level: 0.95, iterations: 1000 },
    },
  });
  assert.equal(model.cherryPickingWarning, null);
});

test("histogram bins map count → height percentage relative to the tallest bin", () => {
  const model = createCohortResultModel({
    ...samplePayload,
    aggregates: {
      ...samplePayload.aggregates,
      delta_histogram_bin_edges: [-0.5, -0.25, 0.0, 0.25, 0.5],
      delta_histogram_counts: [4, 2, 1, 0],
    },
  });
  assert.equal(model.histogram.length, 4);
  assert.equal(model.histogram[0].heightPct, 100);
  assert.equal(model.histogram[1].heightPct, 50);
  assert.equal(model.histogram[3].heightPct, 0);
  // The bin that spans zero is flagged for the legend (light up the
  // "no change" centre column).
  assert.equal(model.histogram[1].containsZero || model.histogram[2].containsZero, true);
});

test("histogram is null when bin/count shapes disagree (defensive)", () => {
  const model = createCohortResultModel({
    ...samplePayload,
    aggregates: {
      ...samplePayload.aggregates,
      delta_histogram_bin_edges: [-0.5, 0.5],
      delta_histogram_counts: [1, 1],
    },
  });
  assert.equal(model.histogram, null);
});
