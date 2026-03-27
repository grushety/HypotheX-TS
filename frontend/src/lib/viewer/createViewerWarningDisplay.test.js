import test from "node:test";
import assert from "node:assert/strict";

import { SOFT_CONSTRAINT_STATUS } from "../constraints/evaluateSoftConstraints.js";
import { createViewerWarningDisplay } from "./createViewerWarningDisplay.js";

test("createViewerWarningDisplay prefers operation warning context over edit warning context", () => {
  const result = createViewerWarningDisplay({
    editConstraintResult: {
      status: SOFT_CONSTRAINT_STATUS.WARN,
      action: { type: "update-label" },
      warnings: [
        {
          code: "ADJACENT_SAME_LABEL_SEGMENTS",
          message: "Adjacent trend segments may indicate a missed merge opportunity.",
          segmentIds: ["seg-002", "seg-003"],
        },
      ],
    },
    editFeedback: "Label updated with 1 warning.",
    operationConstraintResult: {
      status: SOFT_CONSTRAINT_STATUS.WARN,
      action: { type: "split" },
      warnings: [
        {
          code: "ADJACENT_SAME_LABEL_SEGMENTS",
          message: "Adjacent trend segments may indicate a missed merge opportunity.",
          segmentIds: ["seg-002-a", "seg-002-b"],
        },
      ],
    },
    operationFeedback: "split applied with 1 warning.",
  });

  assert.equal(result.title, "Split operation warning");
  assert.equal(result.summary, "split applied with 1 warning.");
});

test("createViewerWarningDisplay hides stale warning UI when the latest operation is PASS", () => {
  const result = createViewerWarningDisplay({
    editConstraintResult: {
      status: SOFT_CONSTRAINT_STATUS.WARN,
      action: { type: "update-label" },
      warnings: [
        {
          code: "ADJACENT_SAME_LABEL_SEGMENTS",
          message: "Adjacent trend segments may indicate a missed merge opportunity.",
          segmentIds: ["seg-002", "seg-003"],
        },
      ],
    },
    editFeedback: "Label updated with 1 warning.",
    operationConstraintResult: {
      status: SOFT_CONSTRAINT_STATUS.PASS,
      action: { type: "merge" },
      warnings: [],
    },
    operationFeedback: "merge applied successfully.",
  });

  assert.equal(result, null);
});
