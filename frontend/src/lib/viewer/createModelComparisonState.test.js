import test from "node:test";
import assert from "node:assert/strict";

import { createModelComparisonState } from "./createModelComparisonState.js";

test("createModelComparisonState highlights boundary and label disagreements", () => {
  const state = createModelComparisonState({
    currentSegments: [
      { id: "seg-001", start: 0, end: 19, label: "event" },
      { id: "seg-002", start: 20, end: 39, label: "trend" },
    ],
    proposalSegments: [
      { id: "prop-001", start: 0, end: 17, label: "event" },
      { id: "prop-002", start: 18, end: 39, label: "plateau" },
    ],
    selectedArtifact: {
      artifact_id: "fcn-gunpoint",
      display_name: "FCN",
    },
  });

  assert.equal(state.heading, "FCN comparison");
  assert.equal(state.disagreementCount, 2);
  assert.equal(state.rows[0].boundaryChanged, true);
  assert.equal(state.rows[1].labelChanged, true);
});

test("createModelComparisonState reports a clean match when segments align", () => {
  const segments = [
    { id: "seg-001", start: 0, end: 17, label: "event" },
    { id: "seg-002", start: 18, end: 39, label: "trend" },
  ];
  const state = createModelComparisonState({
    currentSegments: segments,
    proposalSegments: segments,
    selectedArtifact: null,
  });

  assert.equal(state.disagreementCount, 0);
  assert.equal(state.message, "Current segmentation matches the loaded proposal baseline.");
});

test("createModelComparisonState defaults selectedLabeler to prototype", () => {
  const state = createModelComparisonState({
    currentSegments: [],
    proposalSegments: [],
    selectedArtifact: null,
  });

  assert.equal(state.selectedLabeler, "prototype");
});

test("createModelComparisonState passes through selectedLabeler", () => {
  const state = createModelComparisonState({
    currentSegments: [],
    proposalSegments: [],
    selectedArtifact: null,
    selectedLabeler: "llm",
  });

  assert.equal(state.selectedLabeler, "llm");
});

test("createModelComparisonState passes through suggestionLabeler", () => {
  const state = createModelComparisonState({
    currentSegments: [],
    proposalSegments: [{ id: "seg-001", start: 0, end: 9, label: "trend" }],
    selectedArtifact: null,
    suggestionLabeler: "llm",
  });

  assert.equal(state.suggestionLabeler, "llm");
});

test("createModelComparisonState suggestionLabeler defaults to null", () => {
  const state = createModelComparisonState({
    currentSegments: [],
    proposalSegments: [],
    selectedArtifact: null,
  });

  assert.equal(state.suggestionLabeler, null);
});

test("createModelComparisonState exposes suggestion action availability", () => {
  const state = createModelComparisonState({
    currentSegments: [],
    proposalSegments: [{ id: "seg-001", start: 0, end: 9, label: "event" }],
    selectedArtifact: {
      artifact_id: "fcn-gunpoint",
      display_name: "FCN",
    },
    suggestionStatus: "pending",
    suggestionLoading: false,
    suggestionError: "",
  });

  assert.equal(state.hasProposal, true);
  assert.equal(state.canRequestSuggestion, true);
  assert.equal(state.canAcceptSuggestion, true);
  assert.equal(state.canOverrideSuggestion, true);
});
