import test from "node:test";
import assert from "node:assert/strict";

import {
  AUDIT_EVENT_SCHEMA_VERSION,
  appendAuditEvent,
  createEditAuditEvent,
  createOperationAuditEvent,
} from "./auditEvents.js";
import { executeMoveBoundaryAction } from "../segments/executeSegmentEditAction.js";
import { executeOperationAction } from "../operations/executeOperationAction.js";

const sample = {
  sampleId: "ECG200-001",
  seriesLength: 96,
  segments: [
    { id: "seg-001", start: 0, end: 17, label: "event" },
    { id: "seg-002", start: 18, end: 43, label: "trend" },
    { id: "seg-003", start: 44, end: 67, label: "trend" },
    { id: "seg-004", start: 68, end: 95, label: "other" },
  ],
};

test("createEditAuditEvent captures warned label edits in a stable schema", () => {
  const event = createEditAuditEvent(
    {
      type: "update-label",
      segmentId: "seg-003",
      nextLabel: "trend",
    },
    {
      ok: true,
      message: "Label updated with 1 warning.",
      constraintStatus: "WARN",
      warnings: [
        {
          code: "ADJACENT_SAME_LABEL_SEGMENTS",
          actionType: "update-label",
          segmentIds: ["seg-002", "seg-003"],
        },
      ],
      editResult: {
        updatedSegmentId: "seg-003",
      },
    },
    {
      sampleId: "ECG200-001",
      selectedSegmentId: "seg-003",
    },
  );

  assert.deepEqual(event, {
    schemaVersion: AUDIT_EVENT_SCHEMA_VERSION,
    kind: "edit",
    actionType: "update-label",
    actionStatus: "applied",
    constraintStatus: "WARN",
    warningCount: 1,
    warnings: [
      {
        code: "ADJACENT_SAME_LABEL_SEGMENTS",
        actionType: "update-label",
        segmentIds: ["seg-002", "seg-003"],
      },
    ],
    affectedSegmentIds: ["seg-003"],
    rejectionCode: null,
    message: "Label updated with 1 warning.",
    sampleId: "ECG200-001",
    selectedSegmentId: "seg-003",
    request: {
      type: "update-label",
      segmentId: "seg-003",
      nextLabel: "trend",
    },
    timestamp: null,
    sequence: null,
  });
});

test("createOperationAuditEvent captures clean operations in a stable schema", () => {
  const event = createOperationAuditEvent(
    {
      type: "merge",
      leftSegmentId: "seg-002",
      rightSegmentId: "seg-003",
    },
    {
      ok: true,
      message: "merge applied successfully.",
      constraintStatus: "PASS",
      warnings: [],
      selectedSegmentId: "seg-002",
      operationResult: {
        affectedSegmentIds: ["seg-002"],
      },
    },
    {
      sampleId: "ECG200-001",
      selectedSegmentId: "seg-002",
    },
  );

  assert.equal(event.kind, "operation");
  assert.equal(event.actionType, "merge");
  assert.equal(event.actionStatus, "applied");
  assert.equal(event.constraintStatus, "PASS");
  assert.equal(event.warningCount, 0);
  assert.deepEqual(event.affectedSegmentIds, ["seg-002"]);
  assert.equal(event.sampleId, "ECG200-001");
});

test("createOperationAuditEvent captures rejected operations with an explicit rejection code", () => {
  const event = createOperationAuditEvent(
    {
      type: "merge",
      leftSegmentId: "seg-001",
      rightSegmentId: "seg-002",
    },
    {
      ok: false,
      message: "Merge currently requires adjacent segments with the same label.",
      operationResult: {
        code: "INCOMPATIBLE_SEGMENTS",
      },
    },
    {
      sampleId: "ECG200-001",
      selectedSegmentId: "seg-001",
    },
  );

  assert.equal(event.actionStatus, "rejected");
  assert.equal(event.rejectionCode, "INCOMPATIBLE_SEGMENTS");
  assert.equal(event.warningCount, 0);
});

test("appendAuditEvent stamps timestamp and stable sequence order", () => {
  const events = appendAuditEvent(
    [],
    {
      schemaVersion: AUDIT_EVENT_SCHEMA_VERSION,
      kind: "edit",
      actionType: "move-boundary",
      actionStatus: "applied",
      constraintStatus: "PASS",
      warningCount: 0,
      warnings: [],
      affectedSegmentIds: ["seg-002", "seg-003"],
      rejectionCode: null,
      message: "Boundary updated successfully.",
      sampleId: "ECG200-001",
      selectedSegmentId: "seg-003",
      request: {
        type: "move-boundary",
        boundaryIndex: 1,
        nextBoundaryStart: 40,
      },
      timestamp: null,
      sequence: null,
    },
    {
      timestamp: "2026-03-27T10:00:00.000Z",
    },
  );

  assert.equal(events.length, 1);
  assert.equal(events[0].sequence, 1);
  assert.equal(events[0].timestamp, "2026-03-27T10:00:00.000Z");
});

test("manual edit actions remain audit-ready across boundary moves and merges", () => {
  const editResult = executeMoveBoundaryAction(sample, {
    boundaryIndex: 1,
    nextBoundaryStart: 40,
  });
  const editEvent = createEditAuditEvent(
    {
      type: "move-boundary",
      boundaryIndex: 1,
      nextBoundaryStart: 40,
    },
    editResult,
    {
      sampleId: sample.sampleId,
      selectedSegmentId: "seg-002",
    },
  );
  const mergeResult = executeOperationAction(sample, "seg-002", {
    type: "merge",
    leftSegmentId: "seg-002",
    rightSegmentId: "seg-003",
  });
  const mergeEvent = createOperationAuditEvent(
    {
      type: "merge",
      leftSegmentId: "seg-002",
      rightSegmentId: "seg-003",
    },
    mergeResult,
    {
      sampleId: sample.sampleId,
      selectedSegmentId: "seg-002",
    },
  );

  assert.equal(editEvent.actionType, "move-boundary");
  assert.deepEqual(editEvent.affectedSegmentIds, ["seg-002", "seg-003"]);
  assert.equal(mergeEvent.actionType, "merge");
  assert.deepEqual(mergeEvent.affectedSegmentIds, ["seg-002"]);
  assert.equal(mergeEvent.actionStatus, "applied");
});
