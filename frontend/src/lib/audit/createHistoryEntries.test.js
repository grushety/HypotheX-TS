import test from "node:test";
import assert from "node:assert/strict";

import { createHistoryEntries } from "./createHistoryEntries.js";

test("createHistoryEntries orders newest events first and formats warned summaries", () => {
  const entries = createHistoryEntries([
    {
      sequence: 1,
      kind: "edit",
      actionType: "move-boundary",
      actionStatus: "applied",
      constraintStatus: "PASS",
      message: "Boundary updated successfully.",
      warningCount: 0,
      affectedSegmentIds: ["seg-002", "seg-003"],
    },
    {
      sequence: 2,
      kind: "operation",
      actionType: "split",
      actionStatus: "applied",
      constraintStatus: "WARN",
      message: "split applied with 2 warnings.",
      warningCount: 2,
      affectedSegmentIds: ["seg-002-a", "seg-002-b"],
    },
  ]);

  assert.equal(entries.length, 2);
  assert.equal(entries[0].title, "Split operation");
  assert.equal(entries[0].statusLabel, "Warned");
  assert.equal(entries[0].summary, "split applied with 2 warnings.");
  assert.deepEqual(entries[0].affectedSegmentIds, ["seg-002-a", "seg-002-b"]);
  assert.equal(entries[1].title, "Boundary edit");
});

test("createHistoryEntries formats rejected actions distinctly", () => {
  const entries = createHistoryEntries([
    {
      sequence: 3,
      kind: "operation",
      actionType: "merge",
      actionStatus: "rejected",
      constraintStatus: null,
      message: "Merge currently requires adjacent segments with the same label.",
      warningCount: 0,
      affectedSegmentIds: [],
    },
  ]);

  assert.equal(entries[0].statusLabel, "Rejected");
  assert.equal(entries[0].summary, "Merge currently requires adjacent segments with the same label.");
});
