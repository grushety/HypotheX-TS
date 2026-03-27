import test from "node:test";
import assert from "node:assert/strict";

import { createBenchmarkSelectorState } from "./createBenchmarkSelectorState.js";

test("createBenchmarkSelectorState marks incompatible models as disabled", () => {
  const state = createBenchmarkSelectorState({
    datasets: [{ name: "GunPoint", train_shape: [50], test_shape: [150], series_type: "univariate" }],
    artifacts: [
      { artifact_id: "fcn-gunpoint", dataset: "GunPoint", display_name: "FCN" },
      { artifact_id: "fcn-ecg200", dataset: "ECG200", display_name: "FCN" },
    ],
    selectedDatasetName: "GunPoint",
    selectedArtifactId: "fcn-gunpoint",
    selectedSplit: "train",
    sampleIndex: 3,
    loading: false,
    error: "",
    compatibility: { is_compatible: true, messages: [] },
    compatibilityLoading: false,
    compatibilityError: "",
  });

  assert.equal(state.modelOptions[0].disabled, false);
  assert.equal(state.modelOptions[1].disabled, true);
  assert.equal(state.compatibilityTone, "ok");
  assert.equal(state.maxSampleIndex, 49);
});
