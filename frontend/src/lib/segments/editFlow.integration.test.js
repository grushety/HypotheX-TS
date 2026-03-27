import test from "node:test";
import assert from "node:assert/strict";

import { createSegmentationOverlayModel } from "./createSegmentationOverlayModel.js";
import { moveSegmentBoundary } from "./moveSegmentBoundary.js";
import { updateSegmentLabel } from "./updateSegmentLabel.js";
import { reconcileSelectedSegmentId } from "../viewer/reconcileSelectedSegmentId.js";

test("manual edit flow keeps selection and overlay state stable after boundary and label edits", () => {
  const originalSegments = [
    { id: "seg-001", start: 0, end: 17, label: "event" },
    { id: "seg-002", start: 18, end: 43, label: "trend" },
    { id: "seg-003", start: 44, end: 67, label: "anomaly" },
    { id: "seg-004", start: 68, end: 95, label: "other" },
  ];

  const boundaryResult = moveSegmentBoundary(originalSegments, 1, 40, { seriesLength: 96 });
  assert.equal(boundaryResult.ok, true);

  const selectedSegmentId = reconcileSelectedSegmentId(boundaryResult.segments, "seg-003");
  assert.equal(selectedSegmentId, "seg-003");

  const labelResult = updateSegmentLabel(boundaryResult.segments, selectedSegmentId, "event", {
    seriesLength: 96,
  });
  assert.equal(labelResult.ok, true);

  const overlayModel = createSegmentationOverlayModel(labelResult.segments, 96);

  assert.equal(labelResult.segments[1].end, 39);
  assert.equal(labelResult.segments[2].start, 40);
  assert.equal(labelResult.segments[2].label, "event");
  assert.equal(overlayModel.spans.length, 4);
  assert.equal(overlayModel.boundaries.length, 3);
});
