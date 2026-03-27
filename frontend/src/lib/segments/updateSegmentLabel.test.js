import test from "node:test";
import assert from "node:assert/strict";

import { AVAILABLE_SEGMENT_LABELS, updateSegmentLabel } from "./updateSegmentLabel.js";

const baseSegments = [
  { id: "seg-001", start: 0, end: 17, label: "event" },
  { id: "seg-002", start: 18, end: 43, label: "trend" },
];

test("updateSegmentLabel updates only the selected segment label", () => {
  const result = updateSegmentLabel(baseSegments, "seg-002", "anomaly");

  assert.equal(result.ok, true);
  assert.equal(result.updatedSegmentId, "seg-002");
  assert.equal(result.segments[0].label, "event");
  assert.equal(result.segments[1].label, "anomaly");
  assert.equal(result.segments[1].start, 18);
  assert.equal(baseSegments[1].label, "trend");
});

test("updateSegmentLabel rejects unsupported labels", () => {
  const result = updateSegmentLabel(baseSegments, "seg-001", "invalid");

  assert.deepEqual(result, {
    ok: false,
    code: "INVALID_LABEL",
    message: "Segment label must be one of the supported semantic labels.",
  });
});

test("available segment labels match the formal semantic vocabulary", () => {
  assert.deepEqual(AVAILABLE_SEGMENT_LABELS, ["event", "trend", "anomaly", "other"]);
});
