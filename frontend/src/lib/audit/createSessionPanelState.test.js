import test from "node:test";
import assert from "node:assert/strict";

import { createSessionPanelState } from "./createSessionPanelState.js";

test("createSessionPanelState derives stable session metadata from events and sample", () => {
  const state = createSessionPanelState(
    [
      { sequence: 2, timestamp: "2026-03-29T11:05:00.000Z" },
      { sequence: 1, timestamp: "2026-03-29T11:00:00.000Z" },
    ],
    {
      sampleId: "test-3",
      datasetName: "GunPoint",
    },
  );

  assert.equal(state.sessionId, "session-test-3");
  assert.equal(state.seriesId, "test-3");
  assert.equal(state.segmentationId, "segmentation-test-3");
  assert.equal(state.startedAt, "2026-03-29T11:00:00.000Z");
  assert.equal(state.endedAt, "2026-03-29T11:05:00.000Z");
  assert.equal(state.eventCount, 2);
});

test("createSessionPanelState tolerates an empty session", () => {
  const state = createSessionPanelState([], null);

  assert.equal(state.sessionId, "session-unloaded");
  assert.equal(state.startedAt, null);
  assert.equal(state.endedAt, null);
  assert.equal(state.eventCount, 0);
});
