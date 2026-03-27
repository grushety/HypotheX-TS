import { evaluateEditSoftConstraints } from "../constraints/evaluateSoftConstraints.js";
import { moveSegmentBoundary } from "./moveSegmentBoundary.js";
import { updateSegmentLabel } from "./updateSegmentLabel.js";

function createError(message, editResult = null) {
  return {
    ok: false,
    message,
    editResult,
  };
}

function createSuccess(sample, editResult, constraintResult, message) {
  return {
    ok: true,
    sample: {
      ...sample,
      segments: editResult.segments,
    },
    message,
    editResult,
    constraintResult,
    constraintStatus: constraintResult.status,
    warnings: constraintResult.warnings,
  };
}

export function executeMoveBoundaryAction(sample, request) {
  if (!sample?.segments?.length) {
    return createError("A loaded sample is required before editing boundaries.");
  }

  const editResult = moveSegmentBoundary(sample.segments, request.boundaryIndex, request.nextBoundaryStart, {
    seriesLength: sample.seriesLength,
  });

  if (!editResult.ok) {
    return createError(editResult.message, editResult);
  }

  const constraintResult = evaluateEditSoftConstraints(sample.segments, editResult.segments, {
    type: "move-boundary",
    boundaryIndex: request.boundaryIndex,
    nextBoundaryStart: request.nextBoundaryStart,
  });

  if (!constraintResult.ok) {
    return createError(constraintResult.message, editResult);
  }

  const message =
    constraintResult.status === "WARN"
      ? `Boundary updated with ${constraintResult.warnings.length} warning${constraintResult.warnings.length === 1 ? "" : "s"}.`
      : "Boundary updated successfully.";

  return createSuccess(sample, editResult, constraintResult, message);
}

export function executeUpdateSegmentLabelAction(sample, segmentId, nextLabel) {
  if (!sample?.segments?.length) {
    return createError("A loaded sample is required before updating labels.");
  }

  const editResult = updateSegmentLabel(sample.segments, segmentId, nextLabel);

  if (!editResult.ok) {
    return createError(editResult.message, editResult);
  }

  const constraintResult = evaluateEditSoftConstraints(sample.segments, editResult.segments, {
    type: "update-label",
    segmentId,
    nextLabel,
  });

  if (!constraintResult.ok) {
    return createError(constraintResult.message, editResult);
  }

  const message =
    constraintResult.status === "WARN"
      ? `Label updated with ${constraintResult.warnings.length} warning${constraintResult.warnings.length === 1 ? "" : "s"}.`
      : "Label updated successfully.";

  return createSuccess(sample, editResult, constraintResult, message);
}
