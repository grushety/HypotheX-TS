import test from "node:test";
import assert from "node:assert/strict";

import { SOFT_CONSTRAINT_STATUS } from "../constraints/evaluateSoftConstraints.js";
import { createWarningDisplayModel } from "./createWarningDisplayModel.js";

test("createWarningDisplayModel returns null for PASS results", () => {
  const result = createWarningDisplayModel({
    status: SOFT_CONSTRAINT_STATUS.PASS,
    action: { type: "merge" },
    warnings: [],
  });

  assert.equal(result, null);
});

test("createWarningDisplayModel formats warn results for display", () => {
  const result = createWarningDisplayModel(
    {
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
    "split applied with 1 warning.",
  );

  assert.deepEqual(result, {
    status: SOFT_CONSTRAINT_STATUS.WARN,
    title: "Split operation warning",
    summary: "split applied with 1 warning.",
    actionType: "split",
    reasons: [
      {
        code: "ADJACENT_SAME_LABEL_SEGMENTS",
        text: "Adjacent trend segments may indicate a missed merge opportunity. (seg-002-a, seg-002-b)",
      },
    ],
  });
});
