import test from "node:test";
import assert from "node:assert/strict";

import { getSelectedSegment, reconcileSelectedSegmentId } from "./reconcileSelectedSegmentId.js";

const segments = [
  { id: "seg-001", start: 0, end: 10, label: "event" },
  { id: "seg-002", start: 11, end: 20, label: "trend" },
];

test("reconcileSelectedSegmentId falls back to the first segment", () => {
  assert.equal(reconcileSelectedSegmentId(segments, null), "seg-001");
  assert.equal(reconcileSelectedSegmentId(segments, "missing"), "seg-001");
});

test("reconcileSelectedSegmentId preserves a valid selection across rerenders", () => {
  assert.equal(reconcileSelectedSegmentId(segments, "seg-002"), "seg-002");
});

test("getSelectedSegment returns the active segment metadata", () => {
  assert.deepEqual(getSelectedSegment(segments, "seg-002"), segments[1]);
  assert.equal(getSelectedSegment(segments, "missing"), null);
});
