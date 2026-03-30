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
  assert.equal(entries[0].timestampLabel, "Pending");
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

test("createHistoryEntries formats timestamps for readable session display", () => {
  const entries = createHistoryEntries([
    {
      sequence: 1,
      kind: "edit",
      actionType: "move-boundary",
      actionStatus: "applied",
      timestamp: "2026-03-29T12:15:00.000Z",
    },
  ]);

  assert.equal(entries[0].timestampLabel, "2026-03-29 12:15:00Z");
});

test("createHistoryEntries formats suggestion decisions distinctly", () => {
  const entries = createHistoryEntries([
    {
      sequence: 4,
      kind: "suggestion",
      actionType: "accept-suggestion",
      actionStatus: "applied",
      decision: "accepted",
      message: "Suggestion accepted and applied to the current segmentation.",
      affectedSegmentIds: ["seg-001", "seg-002"],
    },
  ]);

  assert.equal(entries[0].title, "Suggestion accepted");
  assert.equal(entries[0].statusLabel, "Applied");
  assert.equal(entries[0].summary, "Suggestion accepted and applied to the current segmentation.");
});
