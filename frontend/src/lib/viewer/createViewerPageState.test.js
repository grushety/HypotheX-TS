import test from "node:test";
import assert from "node:assert/strict";

import { createViewerPageState } from "./createViewerPageState.js";

test("createViewerPageState exposes loading placeholders before sample load", () => {
  const pageState = createViewerPageState(null);

  assert.deepEqual(pageState.statusItems[0], { label: "Load state", value: "Loading" });
  assert.deepEqual(pageState.sidebarItems[0], {
    label: "Benchmark",
    value: "Waiting for sample",
  });
  assert.deepEqual(pageState.sidebarItems[4], { label: "Segments", value: "--" });
  assert.deepEqual(pageState.sidebarItems[5], { label: "Active segment", value: "--" });
});

test("createViewerPageState maps loaded sample into viewer shell fields", () => {
  const pageState = createViewerPageState({
    datasetId: "ECG200",
    datasetName: "ECG200",
    taskType: "classification",
    sourceSplit: "train",
    channelCount: 1,
    seriesLength: 96,
    segments: [{ id: "seg-1" }, { id: "seg-2" }],
  }, {
    id: "seg-2",
    label: "trend",
    start: 12,
    end: 47,
  });

  assert.deepEqual(pageState.statusItems[1], { label: "Dataset", value: "ECG200" });
  assert.deepEqual(pageState.sidebarItems[2], { label: "Source split", value: "train" });
  assert.deepEqual(pageState.sidebarItems[4], { label: "Segments", value: "2" });
  assert.deepEqual(pageState.sidebarItems[5], {
    label: "Active segment",
    value: "trend (seg-2)",
  });
  assert.deepEqual(pageState.sidebarItems[6], { label: "Active range", value: "12-47" });
});
