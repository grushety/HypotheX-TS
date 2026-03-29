import test from "node:test";
import assert from "node:assert/strict";

import { createOperationPaletteState } from "./createOperationPaletteState.js";

const registry = {
  operationsByChunk: {
    trend: ["change_slope", "split", "merge"],
    event: ["split", "merge", "duplicate"],
  },
};

const segments = [
  { id: "seg-001", start: 0, end: 17, label: "event" },
  { id: "seg-002", start: 18, end: 43, label: "trend" },
  { id: "seg-003", start: 44, end: 67, label: "trend" },
];

test("createOperationPaletteState filters the palette to server-provided legal operations", () => {
  const state = createOperationPaletteState({
    segments,
    selectedSegment: segments[1],
    operationRegistry: registry,
    feedback: "merge applied successfully.",
  });

  assert.equal(state.showSplit, true);
  assert.equal(state.showMerge, true);
  assert.equal(state.canMergeLeft, true);
  assert.equal(state.canMergeRight, true);
  assert.deepEqual(state.supportedOperations, ["split", "merge"]);
  assert.deepEqual(state.futureOperations, ["change_slope"]);
  assert.equal(state.helperText, "trend allows 3 semantic operations in the active ontology.");
});

test("createOperationPaletteState disables controls when the chunk type has no legal operations", () => {
  const state = createOperationPaletteState({
    segments,
    selectedSegment: { id: "seg-900", start: 68, end: 95, label: "other" },
    operationRegistry: registry,
  });

  assert.equal(state.showSplit, false);
  assert.equal(state.showMerge, false);
  assert.equal(state.canSplit, false);
  assert.equal(state.legalOperations.length, 0);
});
