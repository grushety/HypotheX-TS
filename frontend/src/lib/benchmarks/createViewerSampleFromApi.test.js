import test from "node:test";
import assert from "node:assert/strict";

import { createViewerSampleFromApi } from "./createViewerSampleFromApi.js";

test("createViewerSampleFromApi maps univariate backend payload into viewer sample", () => {
  const sample = createViewerSampleFromApi({
    dataset_id: "GunPoint",
    dataset_name: "GunPoint",
    split: "test",
    sample_index: 2,
    task_type: "classification",
    series_type: "univariate",
    channel_count: 1,
    series_length: 6,
    label: "class-1",
    values: [[0, 1, 2, 3, 4, 5]],
  });

  assert.equal(sample.datasetName, "GunPoint");
  assert.equal(sample.sampleId, "test-2");
  assert.equal(sample.channelCount, 1);
  assert.equal(sample.values.length, 6);
  assert.equal(sample.segments.length, 4);
  assert.equal(sample.segments[0].start, 0);
  assert.equal(sample.segments.at(-1).end, 5);
});

test("createViewerSampleFromApi preserves multivariate channel values and exposes a primary channel", () => {
  const sample = createViewerSampleFromApi({
    dataset_id: "BasicMotions",
    dataset_name: "BasicMotions",
    split: "train",
    sample_index: 0,
    task_type: "classification",
    series_type: "multivariate",
    channel_count: 2,
    series_length: 4,
    label: "Walking",
    values: [
      [1, 2, 3, 4],
      [5, 6, 7, 8],
    ],
  });

  assert.equal(sample.seriesType, "multivariate");
  assert.deepEqual(sample.values, [1, 2, 3, 4]);
  assert.deepEqual(sample.channelValues, [
    [1, 2, 3, 4],
    [5, 6, 7, 8],
  ]);
});
