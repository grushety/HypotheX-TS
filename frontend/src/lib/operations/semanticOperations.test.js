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

  assert.deepEqual(result, {
    ok: false,
    type: "split",
    code: "NOT_IMPLEMENTED",
    message: "Split operation behavior will be implemented in HTS-010.",
    request: { type: "split", segmentId: "seg-002", splitIndex: 30 },
    event: {
      type: "split",
      status: "rejected",
      code: "NOT_IMPLEMENTED",
      request: { type: "split", segmentId: "seg-002", splitIndex: 30 },
    },
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
    type: "merge",
    leftSegmentId: "seg-001",
    rightSegmentId: "seg-002",
  });

  assert.equal(result.ok, false);
  assert.equal(result.type, "merge");
  assert.equal(result.code, "NOT_IMPLEMENTED");
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
