import test from "node:test";
import assert from "node:assert/strict";

import { SOFT_CONSTRAINT_STATUS } from "../constraints/evaluateSoftConstraints.js";
import {
  executeMoveBoundaryAction,
  executeUpdateSegmentLabelAction,
} from "./executeSegmentEditAction.js";

const sample = {
  seriesLength: 96,
  segments: [
    { id: "seg-001", start: 0, end: 17, label: "event" },
    { id: "seg-002", start: 18, end: 43, label: "trend" },
    { id: "seg-003", start: 44, end: 67, label: "anomaly" },
    { id: "seg-004", start: 68, end: 95, label: "other" },
  ],
};

test("executeMoveBoundaryAction applies a clean edit with PASS constraint status", () => {
  const result = executeMoveBoundaryAction(sample, {
    boundaryIndex: 1,
    nextBoundaryStart: 40,
  });

  assert.equal(result.ok, true);
  assert.equal(result.constraintStatus, SOFT_CONSTRAINT_STATUS.PASS);
  assert.deepEqual(result.warnings, []);
  assert.equal(result.message, "Boundary updated successfully.");
  assert.equal(result.sample.segments[1].end, 39);
  assert.equal(result.sample.segments[2].start, 40);
});

test("executeUpdateSegmentLabelAction applies warned edits without blocking the update", () => {
  const result = executeUpdateSegmentLabelAction(sample, "seg-003", "trend");

  assert.equal(result.ok, true);
  assert.equal(result.constraintStatus, SOFT_CONSTRAINT_STATUS.WARN);
  assert.equal(result.warnings.length, 1);
  assert.equal(result.message, "Label updated with 1 warning.");
  assert.equal(result.sample.segments[2].label, "trend");
});

test("executeUpdateSegmentLabelAction keeps warning context attached to the edit action", () => {
  const result = executeUpdateSegmentLabelAction(sample, "seg-003", "trend");

  assert.equal(result.ok, true);
  assert.equal(result.constraintResult.action.type, "update-label");
  assert.equal(result.warnings[0].actionType, "update-label");
});
