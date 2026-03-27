import test from "node:test";
import assert from "node:assert/strict";

import { SOFT_CONSTRAINT_STATUS } from "../constraints/evaluateSoftConstraints.js";
import { executeOperationAction } from "./executeOperationAction.js";

const sample = {
  seriesLength: 96,
  segments: [
    { id: "seg-001", start: 0, end: 17, label: "event" },
    { id: "seg-002", start: 18, end: 43, label: "trend" },
    { id: "seg-003", start: 44, end: 67, label: "trend" },
    { id: "seg-004", start: 68, end: 95, label: "other" },
  ],
};

test("executeOperationAction applies split and selects the first resulting segment", () => {
  const result = executeOperationAction(sample, "seg-002", {
    type: "split",
    segmentId: "seg-002",
    splitIndex: 30,
  });

  assert.equal(result.ok, true);
  assert.equal(result.selectedSegmentId, "seg-002-a");
  assert.equal(result.sample.segments.length, 5);
  assert.equal(result.constraintStatus, SOFT_CONSTRAINT_STATUS.WARN);
  assert.equal(result.warnings.length, 2);
  assert.equal(result.message, "split applied with 2 warnings.");
});

test("executeOperationAction applies merge and selects the merged segment", () => {
  const result = executeOperationAction(sample, "seg-002", {
    type: "merge",
    leftSegmentId: "seg-002",
    rightSegmentId: "seg-003",
  });

  assert.equal(result.ok, true);
  assert.equal(result.selectedSegmentId, "seg-002");
  assert.equal(result.sample.segments.length, 3);
  assert.equal(result.constraintStatus, SOFT_CONSTRAINT_STATUS.PASS);
  assert.deepEqual(result.warnings, []);
  assert.equal(result.message, "merge applied successfully.");
});

test("executeOperationAction surfaces explicit domain failures", () => {
  const result = executeOperationAction(sample, "seg-001", {
    type: "merge",
    leftSegmentId: "seg-001",
    rightSegmentId: "seg-002",
  });

  assert.deepEqual(result, {
    ok: false,
    message: "Merge currently requires adjacent segments with the same label.",
    operationResult: {
      ok: false,
      type: "merge",
      code: "INCOMPATIBLE_SEGMENTS",
      message: "Merge currently requires adjacent segments with the same label.",
      request: { type: "merge", leftSegmentId: "seg-001", rightSegmentId: "seg-002" },
      event: {
        type: "merge",
        status: "rejected",
        code: "INCOMPATIBLE_SEGMENTS",
        request: { type: "merge", leftSegmentId: "seg-001", rightSegmentId: "seg-002" },
      },
    },
  });
});
