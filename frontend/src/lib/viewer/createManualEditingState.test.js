import test from "node:test";
import assert from "node:assert/strict";

import { createManualEditingState } from "./createManualEditingState.js";

const segments = [
  { id: "seg-001", start: 0, end: 17, label: "event" },
  { id: "seg-002", start: 18, end: 43, label: "trend" },
  { id: "seg-003", start: 44, end: 45, label: "other" },
];

test("createManualEditingState exposes split and merge targets for a selected middle segment", () => {
  const state = createManualEditingState(segments, segments[1]);

  assert.equal(state.hasSelection, true);
  assert.equal(state.canSplit, true);
  assert.equal(state.splitMin, 19);
  assert.equal(state.splitMax, 43);
  assert.equal(state.suggestedSplitIndex, "31");
  assert.equal(state.leftMergeTarget.id, "seg-001");
  assert.equal(state.rightMergeTarget.id, "seg-003");
  assert.equal(state.canMergeLeft, true);
  assert.equal(state.canMergeRight, true);
});

test("createManualEditingState disables split when the selected segment is too short", () => {
  const state = createManualEditingState(segments, segments[2]);

  assert.equal(state.canSplit, true);
  assert.equal(state.splitMin, 45);
  assert.equal(state.splitMax, 45);
  assert.equal(state.suggestedSplitIndex, "45");
});

test("createManualEditingState falls back safely without a valid selection", () => {
  const state = createManualEditingState(segments, null);

  assert.equal(state.hasSelection, false);
  assert.equal(state.canSplit, false);
  assert.equal(state.canMergeLeft, false);
  assert.equal(state.canMergeRight, false);
  assert.equal(state.splitHint, "Select a segment to enable manual editing controls.");
});
