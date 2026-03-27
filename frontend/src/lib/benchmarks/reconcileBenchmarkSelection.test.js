import test from "node:test";
import assert from "node:assert/strict";

import { reconcileBenchmarkSelection } from "./reconcileBenchmarkSelection.js";

test("reconcileBenchmarkSelection defaults to first dataset and compatible artifact", () => {
  const selection = reconcileBenchmarkSelection({
    datasets: [
      { name: "GunPoint", train_shape: [50], test_shape: [150] },
      { name: "ECG200", train_shape: [100], test_shape: [100] },
    ],
    artifacts: [
      { artifact_id: "fcn-gunpoint", dataset: "GunPoint" },
      { artifact_id: "fcn-ecg200", dataset: "ECG200" },
    ],
    selectedDatasetName: "",
    selectedArtifactId: "",
    selectedSplit: "train",
    sampleIndex: 20,
  });

  assert.deepEqual(selection, {
    selectedDatasetName: "GunPoint",
    selectedArtifactId: "fcn-gunpoint",
    selectedSplit: "train",
    sampleIndex: 20,
  });
});

test("reconcileBenchmarkSelection clamps split and sample index", () => {
  const selection = reconcileBenchmarkSelection({
    datasets: [{ name: "BasicMotions", train_shape: [40], test_shape: [40] }],
    artifacts: [{ artifact_id: "fcn-basicmotions", dataset: "BasicMotions" }],
    selectedDatasetName: "BasicMotions",
    selectedArtifactId: "fcn-basicmotions",
    selectedSplit: "invalid",
    sampleIndex: 99,
  });

  assert.deepEqual(selection, {
    selectedDatasetName: "BasicMotions",
    selectedArtifactId: "fcn-basicmotions",
    selectedSplit: "train",
    sampleIndex: 39,
  });
});
