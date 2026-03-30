import test from "node:test";
import assert from "node:assert/strict";

import { createProposalSegments } from "./createProposalSegments.js";

test("createProposalSegments maps backend suggestion payload into editable frontend segments", () => {
  const segments = createProposalSegments({
    provisionalSegments: [
      {
        segmentId: "segment-001",
        startIndex: 0,
        endIndex: 11,
        label: "spike",
        confidence: 0.91,
        labelScores: {
          trend: 0.02,
          plateau: 0.01,
          spike: 0.91,
          event: 0.03,
          transition: 0.02,
          periodic: 0.01,
        },
      },
    ],
  });

  assert.deepEqual(segments, [
    {
      id: "segment-001",
      start: 0,
      end: 11,
      label: "anomaly",
      sourceLabel: "spike",
      confidence: 0.91,
      labelScores: {
        trend: 0.02,
        plateau: 0.01,
        spike: 0.91,
        event: 0.03,
        transition: 0.02,
        periodic: 0.01,
      },
    },
  ]);
});
