import test from "node:test";
import assert from "node:assert/strict";

import { moveSegmentBoundary } from "./moveSegmentBoundary.js";

const baseSegments = [
  { id: "seg-001", start: 0, end: 17, label: "event" },
  { id: "seg-002", start: 18, end: 43, label: "trend" },
  { id: "seg-003", start: 44, end: 67, label: "anomaly" },
];

test("moveSegmentBoundary updates only the two adjacent segments for a valid move", () => {
  const result = moveSegmentBoundary(baseSegments, 0, 20);

  assert.equal(result.ok, true);
  assert.deepEqual(result.updatedSegmentIds, ["seg-001", "seg-002"]);
  assert.deepEqual(result.segments[0], { id: "seg-001", start: 0, end: 19, label: "event" });
  assert.deepEqual(result.segments[1], { id: "seg-002", start: 20, end: 43, label: "trend" });
  assert.deepEqual(result.segments[2], baseSegments[2]);
  assert.deepEqual(baseSegments[0], { id: "seg-001", start: 0, end: 17, label: "event" });
});

test("moveSegmentBoundary rejects out-of-range moves without mutating state", () => {
  const result = moveSegmentBoundary(baseSegments, 0, 0);

  assert.deepEqual(result, {
    ok: false,
    code: "BOUNDARY_OUT_OF_RANGE",
    message: "Boundary move would violate segment length or ordering constraints.",
  });
  assert.deepEqual(baseSegments[0], { id: "seg-001", start: 0, end: 17, label: "event" });
  assert.deepEqual(baseSegments[1], { id: "seg-002", start: 18, end: 43, label: "trend" });
});

test("moveSegmentBoundary enforces minimum segment length on both sides", () => {
  const result = moveSegmentBoundary(baseSegments, 1, 67, { minSegmentLength: 3 });

  assert.deepEqual(result, {
    ok: false,
    code: "BOUNDARY_OUT_OF_RANGE",
    message: "Boundary move would violate segment length or ordering constraints.",
  });
});

test("moveSegmentBoundary rejects invalid boundary indexes", () => {
  const result = moveSegmentBoundary(baseSegments, 4, 20);

  assert.deepEqual(result, {
    ok: false,
    code: "INVALID_BOUNDARY_INDEX",
    message: "Boundary index must reference adjacent segments.",
  });
});

test("moveSegmentBoundary rejects non-contiguous input segment state", () => {
  const result = moveSegmentBoundary(
    [
      { id: "seg-001", start: 0, end: 17, label: "event" },
      { id: "seg-002", start: 19, end: 43, label: "trend" },
    ],
    0,
    20,
  );

  assert.deepEqual(result, {
    ok: false,
    code: "NON_CONTIGUOUS_SEGMENTS",
    message: "Segments must remain ordered, contiguous, and non-overlapping.",
  });
});
