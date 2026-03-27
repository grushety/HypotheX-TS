import test from "node:test";
import assert from "node:assert/strict";

import {
  applySemanticOperation,
  createSemanticOperationSuccess,
  requestMergeOperation,
  requestReclassifyOperation,
  requestSplitOperation,
  validateSemanticOperationRequest,
} from "./semanticOperations.js";

const segments = [
  { id: "seg-001", start: 0, end: 17, label: "event" },
  { id: "seg-002", start: 18, end: 43, label: "trend" },
  { id: "seg-003", start: 44, end: 67, label: "anomaly" },
];

test("validateSemanticOperationRequest rejects unsupported operations explicitly", () => {
  const result = validateSemanticOperationRequest(segments, { type: "warp" });

  assert.deepEqual(result, {
    ok: false,
    type: "warp",
    code: "UNSUPPORTED_OPERATION",
    message: "Operation type must be split, merge, or reclassify.",
    request: { type: "warp" },
    event: {
      type: "warp",
      status: "rejected",
      code: "UNSUPPORTED_OPERATION",
      request: { type: "warp" },
    },
  });
});

test("requestSplitOperation exposes an explicit not-implemented failure contract", () => {
  const result = requestSplitOperation(segments, { segmentId: "seg-002", splitIndex: 30 });

  assert.equal(result.ok, true);
  assert.equal(result.type, "split");
  assert.deepEqual(result.affectedSegmentIds, ["seg-002-a", "seg-002-b"]);
  assert.deepEqual(result.segments[1], {
    id: "seg-002-a",
    start: 18,
    end: 29,
    label: "trend",
  });
  assert.deepEqual(result.segments[2], {
    id: "seg-002-b",
    start: 30,
    end: 43,
    label: "trend",
  });
});

test("requestMergeOperation validates merge request shape before returning a contract", () => {
  const result = requestMergeOperation(segments, { leftSegmentId: "seg-001" });

  assert.deepEqual(result, {
    ok: false,
    type: "merge",
    code: "INVALID_REQUEST",
    message: "Merge operations require leftSegmentId and rightSegmentId.",
    request: { type: "merge", leftSegmentId: "seg-001" },
    event: {
      type: "merge",
      status: "rejected",
      code: "INVALID_REQUEST",
      request: { type: "merge", leftSegmentId: "seg-001" },
    },
  });
});

test("requestMergeOperation merges only the intended adjacent segments", () => {
  const result = requestMergeOperation(
    [
      { id: "seg-001", start: 0, end: 17, label: "event" },
      { id: "seg-002", start: 18, end: 43, label: "trend" },
      { id: "seg-003", start: 44, end: 67, label: "trend" },
      { id: "seg-004", start: 68, end: 95, label: "other" },
    ],
    { leftSegmentId: "seg-002", rightSegmentId: "seg-003" },
  );

  assert.equal(result.ok, true);
  assert.equal(result.type, "merge");
  assert.deepEqual(result.affectedSegmentIds, ["seg-002"]);
  assert.deepEqual(result.segments[1], {
    id: "seg-002",
    start: 18,
    end: 67,
    label: "trend",
  });
  assert.deepEqual(result.segments[2], {
    id: "seg-004",
    start: 68,
    end: 95,
    label: "other",
  });
});

test("requestReclassifyOperation validates supported labels", () => {
  const result = requestReclassifyOperation(segments, {
    segmentId: "seg-003",
    nextLabel: "invalid",
  });

  assert.deepEqual(result, {
    ok: false,
    type: "reclassify",
    code: "INVALID_REQUEST",
    message: "Reclassify operations require a segmentId and supported nextLabel.",
    request: { type: "reclassify", segmentId: "seg-003", nextLabel: "invalid" },
    event: {
      type: "reclassify",
      status: "rejected",
      code: "INVALID_REQUEST",
      request: { type: "reclassify", segmentId: "seg-003", nextLabel: "invalid" },
    },
  });
});

test("applySemanticOperation dispatches through the shared operation entry points", () => {
  const result = applySemanticOperation(segments, {
    type: "split",
    segmentId: "seg-002",
    splitIndex: 30,
  });

  assert.equal(result.ok, true);
  assert.equal(result.type, "split");
  assert.equal(result.segments.length, 4);
});

test("createSemanticOperationSuccess provides an explicit applied contract shape", () => {
  const result = createSemanticOperationSuccess(
    "reclassify",
    segments,
    { type: "reclassify", segmentId: "seg-003", nextLabel: "event" },
    { affectedSegmentIds: ["seg-003"] },
  );

  assert.deepEqual(result.event, {
    type: "reclassify",
    status: "applied",
    affectedSegmentIds: ["seg-003"],
    request: { type: "reclassify", segmentId: "seg-003", nextLabel: "event" },
  });
  assert.equal(result.ok, true);
});

test("requestSplitOperation rejects boundary-near split indexes safely", () => {
  const result = requestSplitOperation(segments, { segmentId: "seg-002", splitIndex: 18 });

  assert.deepEqual(result, {
    ok: false,
    type: "split",
    code: "INVALID_SPLIT_INDEX",
    message: "Split index must leave at least one valid point on both sides of the segment.",
    request: { type: "split", segmentId: "seg-002", splitIndex: 18 },
    event: {
      type: "split",
      status: "rejected",
      code: "INVALID_SPLIT_INDEX",
      request: { type: "split", segmentId: "seg-002", splitIndex: 18 },
    },
  });
});

test("requestSplitOperation rejects unknown segments safely", () => {
  const result = requestSplitOperation(segments, { segmentId: "missing", splitIndex: 30 });

  assert.deepEqual(result, {
    ok: false,
    type: "split",
    code: "SEGMENT_NOT_FOUND",
    message: "Split target segment was not found.",
    request: { type: "split", segmentId: "missing", splitIndex: 30 },
    event: {
      type: "split",
      status: "rejected",
      code: "SEGMENT_NOT_FOUND",
      request: { type: "split", segmentId: "missing", splitIndex: 30 },
    },
  });
});

test("requestMergeOperation rejects non-adjacent segments safely", () => {
  const result = requestMergeOperation(segments, {
    leftSegmentId: "seg-001",
    rightSegmentId: "seg-003",
  });

  assert.deepEqual(result, {
    ok: false,
    type: "merge",
    code: "NON_ADJACENT_SEGMENTS",
    message: "Merge requires two adjacent segments in left-to-right order.",
    request: { type: "merge", leftSegmentId: "seg-001", rightSegmentId: "seg-003" },
    event: {
      type: "merge",
      status: "rejected",
      code: "NON_ADJACENT_SEGMENTS",
      request: { type: "merge", leftSegmentId: "seg-001", rightSegmentId: "seg-003" },
    },
  });
});

test("requestMergeOperation rejects incompatible labels safely", () => {
  const result = requestMergeOperation(segments, {
    leftSegmentId: "seg-001",
    rightSegmentId: "seg-002",
  });

  assert.deepEqual(result, {
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
  });
});
