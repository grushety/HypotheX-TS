import { SOFT_CONSTRAINT_STATUS } from "../constraints/evaluateSoftConstraints.js";

const ACTION_LABELS = {
  "move-boundary": "Boundary edit",
  "update-label": "Label edit",
  split: "Split operation",
  merge: "Merge operation",
  reclassify: "Reclassify operation",
};

function getActionLabel(actionType) {
  return ACTION_LABELS[actionType] ?? "Action";
}

function createReasonLine(warning) {
  if (warning.segmentIds?.length) {
    return `${warning.message} (${warning.segmentIds.join(", ")})`;
  }

  return warning.message;
}

export function createWarningDisplayModel(constraintResult, feedback = "") {
  if (!constraintResult || constraintResult.status !== SOFT_CONSTRAINT_STATUS.WARN) {
    return null;
  }

  const actionType = constraintResult.action?.type ?? "unknown";
  const actionLabel = getActionLabel(actionType);

  return {
    status: SOFT_CONSTRAINT_STATUS.WARN,
    title: `${actionLabel} warning`,
    summary: feedback || `${actionLabel} completed with ${constraintResult.warnings.length} warning(s).`,
    actionType,
    reasons: constraintResult.warnings.map((warning) => ({
      code: warning.code,
      text: createReasonLine(warning),
    })),
  };
}
