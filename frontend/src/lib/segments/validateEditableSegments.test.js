import test from "node:test";
import assert from "node:assert/strict";

import { validateEditableSegments } from "./validateEditableSegments.js";

test("validateEditableSegments accepts contiguous labeled segments", () => {
  const result = validateEditableSegments(
    [
      { id: "seg-001", start: 0, end: 9, label: "event" },
      { id: "seg-002", start: 10, end: 19, label: "trend" },
      { id: "seg-003", start: 20, end: 29, label: "other" },
    ],
    { seriesLength: 30 },
  );

  assert.deepEqual(result, { ok: true });
});

test("validateEditableSegments rejects gaps and overlaps", () => {
  const result = validateEditableSegments(
    [
      { id: "seg-001", start: 0, end: 9, label: "event" },
      { id: "seg-002", start: 11, end: 19, label: "trend" },
    ],
    { seriesLength: 20 },
  );

  assert.deepEqual(result, {
    ok: false,
    code: "NON_CONTIGUOUS_SEGMENTS",
    message: "Segments must remain ordered, contiguous, and non-overlapping.",
  });
});

test("validateEditableSegments rejects unsupported labels", () => {
  const result = validateEditableSegments([{ id: "seg-001", start: 0, end: 9, label: "invalid" }], {
    seriesLength: 10,
  });

  assert.deepEqual(result, {
    ok: false,
    code: "INVALID_LABEL",
    message: "Segment label must be one of the supported semantic labels.",
  });
});
