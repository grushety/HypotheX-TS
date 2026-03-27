import { createWarningDisplayModel } from "./createWarningDisplayModel.js";

export function createViewerWarningDisplay({
  editConstraintResult = null,
  editFeedback = "",
  operationConstraintResult = null,
  operationFeedback = "",
} = {}) {
  if (operationConstraintResult) {
    return createWarningDisplayModel(operationConstraintResult, operationFeedback);
  }

  return createWarningDisplayModel(editConstraintResult, editFeedback);
}
