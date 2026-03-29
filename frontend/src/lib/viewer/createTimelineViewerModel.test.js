import test from "node:test";
import assert from "node:assert/strict";

import { createTimelineViewerModel } from "./createTimelineViewerModel.js";

const sample = {
  datasetName: "GunPoint",
  sampleId: "test-4",
  seriesLength: 320,
  values: Array.from({ length: 320 }, (_, index) => Math.sin(index / 16)),
  segments: [
    { id: "seg-001", start: 0, end: 63, label: "event" },
    { id: "seg-002", start: 64, end: 159, label: "trend" },
    { id: "seg-003", start: 160, end: 319, label: "other" },
  ],
};

test("createTimelineViewerModel exposes selected segment summary and overview window", () => {
  const model = createTimelineViewerModel(sample, "seg-002");

  assert.equal(model.title, "GunPoint sample test-4");
  assert.equal(model.pointCountLabel, "320 points");
  assert.equal(model.segmentCountLabel, "3 segments");
  assert.equal(model.overviewLabel, "Overview enabled for longer series");
  assert.equal(model.selectedSummary, "Selected trend");
  assert.equal(model.selectedRangeLabel, "64-159");
  assert.equal(model.minimapSpans[1].isSelected, true);
  assert.notEqual(model.overviewWindow.width, "100.00%");
});

test("createTimelineViewerModel falls back safely when no sample is loaded", () => {
  const model = createTimelineViewerModel(null, null);

  assert.equal(model.title, "Time-series timeline");
  assert.equal(model.pointCountLabel, "-- points");
  assert.equal(model.selectedSummary, "No segment selected");
  assert.deepEqual(model.minimapSpans, []);
});
