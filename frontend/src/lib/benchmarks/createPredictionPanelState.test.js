import test from "node:test";
import assert from "node:assert/strict";

import { createPredictionPanelState } from "./createPredictionPanelState.js";

test("createPredictionPanelState returns ready state for compatible sample and model", () => {
  const state = createPredictionPanelState({
    prediction: {
      predicted_label: "class-1",
      true_label: "class-0",
      scores: [
        { label: "class-1", score: 3.25, probability: 0.72 },
        { label: "class-0", score: 1.12, probability: 0.28 },
      ],
    },
    loading: false,
    error: "",
    sample: {
      datasetName: "GunPoint",
      sampleId: "test-4",
      sourceSplit: "test",
      sourceSampleIndex: 4,
      label: "class-0",
      channelCount: 1,
      seriesType: "univariate",
    },
    selectedArtifact: {
      artifact_id: "fcn-gunpoint",
      display_name: "FCN",
      family: "fcn",
      dataset: "GunPoint",
    },
    compatibility: { is_compatible: true, messages: [] },
    compatibilityLoading: false,
    selectorError: "",
  });

  assert.equal(state.tone, "ok");
  assert.equal(state.buttonDisabled, false);
  assert.equal(state.hasPrediction, true);
  assert.equal(state.predictionSummary.predictedLabel, "class-1");
  assert.equal(state.scores[0].probabilityDisplay, "72.0%");
  assert.equal(state.scores[1].scoreDisplay, "1.120");
});

test("createPredictionPanelState exposes error state when prediction request fails", () => {
  const state = createPredictionPanelState({
    prediction: null,
    loading: false,
    error: "artifact is incompatible",
    sample: {
      datasetName: "GunPoint",
      sampleId: "test-1",
      sourceSplit: "test",
      sourceSampleIndex: 1,
      label: "class-1",
      channelCount: 1,
      seriesType: "univariate",
    },
    selectedArtifact: {
      artifact_id: "fcn-gunpoint",
      display_name: "FCN",
      family: "fcn",
      dataset: "GunPoint",
    },
    compatibility: { is_compatible: true, messages: [] },
    compatibilityLoading: false,
    selectorError: "",
  });

  assert.equal(state.tone, "error");
  assert.match(state.message, /artifact is incompatible/);
  assert.equal(state.hasPrediction, false);
});
