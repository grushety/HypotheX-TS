import test from "node:test";
import assert from "node:assert/strict";

import { executeOperationAction } from "./executeOperationAction.js";

const baseSample = {
  seriesLength: 96,
  segments: [
    { id: "seg-001", start: 0, end: 17, label: "event" },
    { id: "seg-002", start: 18, end: 43, label: "trend" },
    { id: "seg-003", start: 44, end: 67, label: "trend" },
    { id: "seg-004", start: 68, end: 95, label: "other" },
  ],
};

test("operation flow remains stable across split then reclassify", () => {
  const splitResult = executeOperationAction(baseSample, "seg-002", {
    type: "split",
    segmentId: "seg-002",
    splitIndex: 30,
  });

  assert.equal(splitResult.ok, true);
  assert.equal(splitResult.selectedSegmentId, "seg-002-a");
  assert.equal(splitResult.sample.segments.length, 5);

  const reclassifyResult = executeOperationAction(splitResult.sample, splitResult.selectedSegmentId, {
    type: "reclassify",
    segmentId: splitResult.selectedSegmentId,
    nextLabel: "event",
  });

  assert.equal(reclassifyResult.ok, true);
  assert.equal(reclassifyResult.selectedSegmentId, "seg-002-a");
  assert.deepEqual(reclassifyResult.sample.segments[1], {
    id: "seg-002-a",
    start: 18,
    end: 29,
    label: "event",
  });
});

test("operation flow remains stable after a successful merge", () => {
  const mergeResult = executeOperationAction(baseSample, "seg-002", {
    type: "merge",
    leftSegmentId: "seg-002",
    rightSegmentId: "seg-003",
  });

  assert.equal(mergeResult.ok, true);
  assert.equal(mergeResult.selectedSegmentId, "seg-002");
  assert.equal(mergeResult.sample.segments.length, 3);
  assert.deepEqual(mergeResult.sample.segments[1], {
    id: "seg-002",
    start: 18,
    end: 67,
    label: "trend",
  });
  assert.deepEqual(mergeResult.sample.segments[2], {
    id: "seg-004",
    start: 68,
    end: 95,
    label: "other",
  });
});

test("failed operation attempts do not mutate sample state or selection", () => {
  const result = executeOperationAction(baseSample, "seg-001", {
    type: "merge",
    leftSegmentId: "seg-001",
    rightSegmentId: "seg-002",
  });

  assert.equal(result.ok, false);
  assert.equal(result.message, "Merge currently requires adjacent segments with the same label.");
  assert.deepEqual(baseSample.segments[0], {
    id: "seg-001",
    start: 0,
    end: 17,
    label: "event",
  });
  assert.deepEqual(baseSample.segments[1], {
    id: "seg-002",
    start: 18,
    end: 43,
    label: "trend",
  });
});
