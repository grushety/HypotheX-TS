import test from "node:test";
import assert from "node:assert/strict";

import { OUTPUT_STATE, createOutputPanelState } from "./createOutputPanelState.js";

const sampleBaseline = {
  predicted_label: "Gun",
  task: "classification",
  scores: [
    { label: "Gun", probability: 0.86, score: 1.2 },
    { label: "Point", probability: 0.14, score: -0.4 },
  ],
};

const sampleCurrentNoFlip = {
  predicted_label: "Gun",
  task: "classification",
  scores: [
    { label: "Gun", probability: 0.62, score: 0.7 },
    { label: "Point", probability: 0.38, score: -0.1 },
  ],
};

const sampleCurrentFlipped = {
  predicted_label: "Point",
  task: "classification",
  scores: [
    { label: "Gun", probability: 0.30, score: -0.2 },
    { label: "Point", probability: 0.70, score: 0.6 },
  ],
};

test("empty state when there is no baseline", () => {
  const state = createOutputPanelState({});
  assert.equal(state.state, OUTPUT_STATE.EMPTY);
  assert.equal(state.classification, null);
  assert.equal(state.freshChip.label, "NO RUN");
});

test("loading state takes precedence over empty when a request is in flight", () => {
  const state = createOutputPanelState({ loading: true });
  assert.equal(state.state, OUTPUT_STATE.LOADING);
  assert.equal(state.classification, null);
  assert.equal(state.freshChip.label, "RUNNING");
});

test("error state beats loading", () => {
  const state = createOutputPanelState({
    loading: true,
    baseline: sampleBaseline,
    error: "Prediction failed: dataset not compatible.",
  });
  assert.equal(state.state, OUTPUT_STATE.ERROR);
  assert.equal(state.error, "Prediction failed: dataset not compatible.");
  assert.equal(state.freshChip.label, "ERROR");
});

test("normal state when current matches the latest series version", () => {
  const state = createOutputPanelState({
    baseline: sampleBaseline,
    current: sampleCurrentNoFlip,
    seriesVersion: 3,
    currentVersion: 3,
  });
  assert.equal(state.state, OUTPUT_STATE.NORMAL);
  assert.equal(state.freshChip.label, "FRESH");
  assert.ok(state.classification);
  assert.equal(state.classification.flip, false);
  assert.equal(state.classification.basePred, "Gun");
  assert.equal(state.classification.curPred, "Gun");
});

test("stale state when current is older than the latest series version", () => {
  const state = createOutputPanelState({
    baseline: sampleBaseline,
    current: sampleCurrentNoFlip,
    seriesVersion: 4,
    currentVersion: 3,
  });
  assert.equal(state.state, OUTPUT_STATE.STALE);
  assert.equal(state.freshChip.label, "STALE");
  // Body still renders so the user can see what the last run looked like.
  assert.ok(state.classification);
});

test("stale state when baseline exists but current was never scored", () => {
  const state = createOutputPanelState({
    baseline: sampleBaseline,
    current: null,
    seriesVersion: 0,
    currentVersion: null,
  });
  assert.equal(state.state, OUTPUT_STATE.STALE);
  // Falls back to rendering the baseline on both sides until current arrives.
  assert.equal(state.classification.basePred, "Gun");
  assert.equal(state.classification.curPred, "Gun");
});

test("class flip is detected when argmax changes between baseline and current", () => {
  const state = createOutputPanelState({
    baseline: sampleBaseline,
    current: sampleCurrentFlipped,
    seriesVersion: 5,
    currentVersion: 5,
  });
  assert.equal(state.state, OUTPUT_STATE.NORMAL);
  assert.equal(state.classification.flip, true);
  assert.equal(state.classification.basePred, "Gun");
  assert.equal(state.classification.curPred, "Point");
});

test("predDelta is the signed shift of the originally-predicted class", () => {
  const state = createOutputPanelState({
    baseline: sampleBaseline,
    current: sampleCurrentFlipped,
    seriesVersion: 1,
    currentVersion: 1,
  });
  // Gun went from 0.86 → 0.30: predDelta = -0.56
  assert.ok(state.classification.predDelta < -0.55 && state.classification.predDelta > -0.57);
});

test("per-class delta aligns baseline and current by label, preserving baseline order", () => {
  const baseline = {
    predicted_label: "alpha",
    task: "classification",
    scores: [
      { label: "alpha", probability: 0.5, score: 0 },
      { label: "beta", probability: 0.3, score: 0 },
      { label: "gamma", probability: 0.2, score: 0 },
    ],
  };
  // Current returns classes in a different order.
  const current = {
    predicted_label: "beta",
    task: "classification",
    scores: [
      { label: "gamma", probability: 0.1, score: 0 },
      { label: "beta", probability: 0.6, score: 0 },
      { label: "alpha", probability: 0.3, score: 0 },
    ],
  };
  const state = createOutputPanelState({
    baseline,
    current,
    seriesVersion: 7,
    currentVersion: 7,
  });
  assert.equal(state.classification.classes[0].name, "alpha");
  assert.equal(state.classification.classes[1].name, "beta");
  assert.equal(state.classification.classes[2].name, "gamma");
  assert.equal(state.classification.classes[0].delta.toFixed(2), "-0.20");
  assert.equal(state.classification.classes[1].delta.toFixed(2), "0.30");
  assert.equal(state.classification.classes[2].delta.toFixed(2), "-0.10");
});

test("probabilities are clamped to [0, 1] to defend against bad backend payloads", () => {
  const state = createOutputPanelState({
    baseline: {
      predicted_label: "alpha",
      task: "classification",
      scores: [
        { label: "alpha", probability: 1.7, score: 0 },
        { label: "beta", probability: -0.4, score: 0 },
      ],
    },
    current: {
      predicted_label: "alpha",
      task: "classification",
      scores: [
        { label: "alpha", probability: 0.6, score: 0 },
        { label: "beta", probability: 0.4, score: 0 },
      ],
    },
    seriesVersion: 1,
    currentVersion: 1,
  });
  assert.equal(state.classification.classes[0].base, 1);
  assert.equal(state.classification.classes[1].base, 0);
});

test("mode follows the baseline task field", () => {
  const state = createOutputPanelState({
    baseline: { ...sampleBaseline, task: "regression" },
    current: { ...sampleBaseline, task: "regression" },
    seriesVersion: 0,
    currentVersion: 0,
  });
  assert.equal(state.mode, "regression");
});
