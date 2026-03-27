import test from "node:test";
import assert from "node:assert/strict";

import {
  evaluateEditSoftConstraints,
  evaluateOperationSoftConstraints,
  evaluateSoftConstraints,
  SOFT_CONSTRAINT_STATUS,
  SOFT_CONSTRAINT_WARNING_CODES,
} from "./evaluateSoftConstraints.js";

const baseSegments = [
  { id: "seg-001", start: 0, end: 17, label: "event" },
  { id: "seg-002", start: 18, end: 43, label: "trend" },
  { id: "seg-003", start: 44, end: 67, label: "anomaly" },
  { id: "seg-004", start: 68, end: 95, label: "other" },
];

test("evaluateSoftConstraints returns PASS when no soft warning rules are violated", () => {
  const nextSegments = [
    baseSegments[0],
    { id: "seg-002", start: 18, end: 67, label: "trend" },
    baseSegments[3],
  ];

  const result = evaluateSoftConstraints(baseSegments, nextSegments, {
    type: "merge",
    leftSegmentId: "seg-002",
    rightSegmentId: "seg-003",
  });

  assert.deepEqual(result, {
    ok: true,
    status: SOFT_CONSTRAINT_STATUS.PASS,
    warnings: [],
    action: {
      type: "merge",
      leftSegmentId: "seg-002",
      rightSegmentId: "seg-003",
    },
  });
});

test("evaluateOperationSoftConstraints returns WARN with structured reasons for adjacent same-label split results", () => {
  const nextSegments = [
    baseSegments[0],
    { id: "seg-002-a", start: 18, end: 29, label: "trend" },
    { id: "seg-002-b", start: 30, end: 43, label: "trend" },
    baseSegments[2],
    baseSegments[3],
  ];

  const result = evaluateOperationSoftConstraints(baseSegments, nextSegments, {
    type: "split",
    segmentId: "seg-002",
    splitIndex: 30,
  });

  assert.equal(result.ok, true);
  assert.equal(result.status, SOFT_CONSTRAINT_STATUS.WARN);
  assert.equal(result.warnings.length, 1);
  assert.deepEqual(result.warnings[0], {
    code: SOFT_CONSTRAINT_WARNING_CODES.ADJACENT_SAME_LABEL_SEGMENTS,
    message: "Adjacent trend segments may indicate a missed merge opportunity.",
    constraintId: "adjacentSameLabelSegments",
    actionType: "split",
    segmentIds: ["seg-002-a", "seg-002-b"],
    labels: ["trend"],
    details: {
      label: "trend",
      boundaryIndex: 1,
    },
  });
});

test("evaluateEditSoftConstraints returns WARN for label edits that create adjacent same-label segments", () => {
  const nextSegments = [
    baseSegments[0],
    { id: "seg-002", start: 18, end: 43, label: "trend" },
    { id: "seg-003", start: 44, end: 67, label: "trend" },
    baseSegments[3],
  ];

  const result = evaluateEditSoftConstraints(baseSegments, nextSegments, {
    type: "update-label",
    segmentId: "seg-003",
    nextLabel: "trend",
  });

  assert.equal(result.ok, true);
  assert.equal(result.status, SOFT_CONSTRAINT_STATUS.WARN);
  assert.equal(result.warnings.length, 1);
  assert.equal(result.warnings[0].actionType, "update-label");
  assert.deepEqual(result.warnings[0].segmentIds, ["seg-002", "seg-003"]);
});

test("evaluateOperationSoftConstraints returns one warning per adjacent same-label pair", () => {
  const previousSegments = [
    { id: "seg-001", start: 0, end: 17, label: "event" },
    { id: "seg-002", start: 18, end: 43, label: "trend" },
    { id: "seg-003", start: 44, end: 67, label: "trend" },
    { id: "seg-004", start: 68, end: 95, label: "other" },
  ];
  const nextSegments = [
    previousSegments[0],
    { id: "seg-002-a", start: 18, end: 29, label: "event" },
    { id: "seg-002-b", start: 30, end: 43, label: "trend" },
    { id: "seg-003", start: 44, end: 67, label: "trend" },
    previousSegments[3],
  ];

  const result = evaluateOperationSoftConstraints(previousSegments, nextSegments, {
    type: "reclassify",
    segmentId: "seg-002-a",
    nextLabel: "event",
  });

  assert.equal(result.ok, true);
  assert.equal(result.status, SOFT_CONSTRAINT_STATUS.WARN);
  assert.equal(result.warnings.length, 2);
  assert.deepEqual(
    result.warnings.map((warning) => warning.segmentIds),
    [
      ["seg-001", "seg-002-a"],
      ["seg-002-b", "seg-003"],
    ],
  );
});
