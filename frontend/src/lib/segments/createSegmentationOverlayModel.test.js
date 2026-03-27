import test from "node:test";
import assert from "node:assert/strict";

import { createSegmentationOverlayModel } from "./createSegmentationOverlayModel.js";

test("createSegmentationOverlayModel maps segments into aligned spans", () => {
  const model = createSegmentationOverlayModel(
    [
      { id: "s1", start: 0, end: 23, label: "event" },
      { id: "s2", start: 24, end: 47, label: "trend" },
      { id: "s3", start: 48, end: 95, label: "other" },
    ],
    96,
  );

  assert.equal(model.spans.length, 3);
  assert.equal(model.spans[0].left, "0.00%");
  assert.equal(model.spans[0].width, "25.00%");
  assert.equal(model.spans[2].width, "50.00%");
});

test("createSegmentationOverlayModel creates one boundary per segment edge", () => {
  const model = createSegmentationOverlayModel(
    [
      { id: "s1", start: 0, end: 11, label: "event" },
      { id: "s2", start: 12, end: 31, label: "trend" },
      { id: "s3", start: 32, end: 63, label: "anomaly" },
      { id: "s4", start: 64, end: 95, label: "other" },
    ],
    96,
  );

  assert.equal(model.boundaries.length, 3);
  assert.equal(model.boundaries[0].left, "12.50%");
  assert.equal(model.boundaries[2].left, "66.67%");
});
