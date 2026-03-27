import test from "node:test";
import assert from "node:assert/strict";

import { loadBenchmarkSample } from "./benchmarkSamples.js";

test("loadBenchmarkSample returns the ECG200 scaffold sample", async () => {
  const sample = await loadBenchmarkSample();

  assert.equal(sample.datasetId, "ECG200");
  assert.equal(sample.sampleId, "train-001");
  assert.equal(sample.seriesLength, 96);
  assert.equal(sample.values.length, 96);
  assert.equal(sample.segments.length, 4);
  assert.equal(sample.segments[0].label, "event");
  assert.equal(sample.previewValues.length, 24);
});
