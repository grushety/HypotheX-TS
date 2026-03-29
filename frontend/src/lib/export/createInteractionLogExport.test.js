import test from "node:test";
import assert from "node:assert/strict";

import {
  createInteractionLogExport,
  createInteractionLogFilename,
} from "./createInteractionLogExport.js";

test("createInteractionLogFilename produces a stable JSON filename", () => {
  const filename = createInteractionLogFilename(
    "ECG200-001",
    new Date("2026-03-27T10:15:30.000Z"),
  );

  assert.equal(filename, "session-log-ECG200-001-20260327T101530Z.json");
});

test("createInteractionLogExport serializes a session-shaped export payload", () => {
  const exportArtifact = createInteractionLogExport(
    [
      {
        schemaVersion: 1,
        kind: "operation",
        actionType: "split",
        actionStatus: "applied",
        constraintStatus: "WARN",
        warningCount: 2,
        warnings: [
          {
            code: "ADJACENT_SAME_LABEL_SEGMENTS",
            actionType: "split",
            segmentIds: ["seg-002-a", "seg-002-b"],
          },
        ],
        affectedSegmentIds: ["seg-002-a", "seg-002-b"],
        rejectionCode: null,
        message: "split applied with 2 warnings.",
        sampleId: "ECG200-001",
        selectedSegmentId: "seg-002-a",
        request: {
          type: "split",
          segmentId: "seg-002",
          splitIndex: 30,
        },
        timestamp: "2026-03-27T10:15:30.000Z",
        sequence: 2,
      },
    ],
    {
      sessionId: "session-ECG200-001",
      seriesId: "train-001",
      segmentationId: "segmentation-train-001",
      startedAt: "2026-03-27T10:15:30.000Z",
      endedAt: "2026-03-27T10:15:30.000Z",
      sampleId: "ECG200-001",
      datasetName: "ECG200",
    },
    new Date("2026-03-27T10:20:00.000Z"),
  );

  assert.equal(exportArtifact.mimeType, "application/json");
  assert.equal(exportArtifact.payload.eventCount, 1);
  assert.equal(exportArtifact.payload.sessionId, "session-ECG200-001");
  assert.equal(exportArtifact.payload.seriesId, "train-001");
  assert.equal(exportArtifact.payload.segmentationId, "segmentation-train-001");
  assert.equal(exportArtifact.payload.datasetName, "ECG200");
  assert.equal(exportArtifact.payload.events[0].eventType, "operation_applied");
  assert.equal(exportArtifact.payload.events[0].metadata.warningCount, 2);
  assert.match(exportArtifact.content, /"sessionId": "session-ECG200-001"/);
  assert.match(exportArtifact.content, /"actionType": "split"/);
});
