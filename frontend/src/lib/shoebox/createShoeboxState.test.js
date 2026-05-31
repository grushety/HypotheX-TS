import test from "node:test";
import assert from "node:assert/strict";

import {
  addPin,
  buildPin,
  clearShoebox,
  emptyShoebox,
  exportShoeboxAsJson,
  exportShoeboxAsMarkdown,
  fromPersistedJson,
  removePin,
  reorderPin,
  setFreeNotes,
  setNote,
  SHOEBOX_SCHEMA_VERSION,
  toPersistedJson,
} from "./createShoeboxState.js";

function fixedPin(overrides = {}) {
  return {
    id: overrides.id ?? "pin-1",
    kind: overrides.kind ?? "prediction",
    title: overrides.title ?? "Prediction · Gun 86%",
    summary: overrides.summary ?? "baseline class held",
    capturedAt: overrides.capturedAt ?? "2026-05-30T12:00:00Z",
    provenance: overrides.provenance ?? { sampleId: "test-0" },
    payload: overrides.payload ?? { predicted_label: "Gun" },
    note: overrides.note ?? "",
  };
}

test("emptyShoebox returns a clean state with no items and empty notes", () => {
  const state = emptyShoebox();
  assert.deepEqual(state.items, []);
  assert.equal(state.freeNotes, "");
});

test("buildPin produces an id and ISO capturedAt automatically", () => {
  const pin = buildPin({
    kind: "min-flip",
    title: "Minimal flip · Gun → Point",
    summary: "distance 0.18",
    provenance: { sampleId: "abc" },
    payload: { distance: 0.18 },
  });
  assert.ok(typeof pin.id === "string" && pin.id.length > 0);
  assert.match(pin.capturedAt, /^\d{4}-\d{2}-\d{2}T/);
  assert.equal(pin.kind, "min-flip");
  assert.equal(pin.note, "");
});

test("addPin appends without mutating the input state", () => {
  const before = emptyShoebox();
  const after = addPin(before, fixedPin());
  assert.equal(before.items.length, 0);
  assert.equal(after.items.length, 1);
  assert.equal(after.items[0].id, "pin-1");
});

test("addPin is a no-op when the pin lacks an id", () => {
  const before = emptyShoebox();
  const after = addPin(before, { kind: "broken" });
  assert.equal(after.items.length, 0);
});

test("removePin filters by id", () => {
  const state = addPin(addPin(emptyShoebox(), fixedPin({ id: "a" })), fixedPin({ id: "b" }));
  const after = removePin(state, "a");
  assert.deepEqual(after.items.map((i) => i.id), ["b"]);
});

test("reorderPin moves the item up and down without changing the count", () => {
  const state = ["a", "b", "c"].reduce(
    (acc, id) => addPin(acc, fixedPin({ id })),
    emptyShoebox(),
  );
  const movedDown = reorderPin(state, "a", "down");
  assert.deepEqual(movedDown.items.map((i) => i.id), ["b", "a", "c"]);
  const movedUp = reorderPin(state, "c", "up");
  assert.deepEqual(movedUp.items.map((i) => i.id), ["a", "c", "b"]);
});

test("reorderPin clamps at the edges (top can't go up, bottom can't go down)", () => {
  const state = ["a", "b"].reduce(
    (acc, id) => addPin(acc, fixedPin({ id })),
    emptyShoebox(),
  );
  assert.deepEqual(reorderPin(state, "a", "up").items.map((i) => i.id), ["a", "b"]);
  assert.deepEqual(reorderPin(state, "b", "down").items.map((i) => i.id), ["a", "b"]);
});

test("setNote updates only the matching item", () => {
  const state = ["a", "b"].reduce(
    (acc, id) => addPin(acc, fixedPin({ id })),
    emptyShoebox(),
  );
  const after = setNote(state, "b", "look at this");
  assert.equal(after.items[0].note, "");
  assert.equal(after.items[1].note, "look at this");
});

test("setFreeNotes is plain string assignment", () => {
  const after = setFreeNotes(emptyShoebox(), "wrap-up thoughts");
  assert.equal(after.freeNotes, "wrap-up thoughts");
});

test("clearShoebox returns a fresh empty state", () => {
  const populated = addPin(emptyShoebox(), fixedPin());
  assert.equal(clearShoebox().items.length, 0);
  // Original is unchanged.
  assert.equal(populated.items.length, 1);
});

test("exportShoeboxAsMarkdown writes one section per pin with provenance bullets", () => {
  const state = addPin(emptyShoebox(), fixedPin({ note: "the key result" }));
  const md = exportShoeboxAsMarkdown(state, { generatedAt: new Date("2026-05-31T00:00:00Z") });
  assert.match(md, /# HypotheX-TS shoebox export/);
  assert.match(md, /1\. Prediction · Gun 86%/);
  assert.match(md, /\*\*Kind:\*\* prediction/);
  assert.match(md, /sampleId: test-0/);
  assert.match(md, /\*\*Note:\*\* the key result/);
});

test("exportShoeboxAsMarkdown surfaces an honest empty-state message", () => {
  const md = exportShoeboxAsMarkdown(emptyShoebox());
  assert.match(md, /no items pinned/i);
});

test("exportShoeboxAsJson wraps items in a meta envelope", () => {
  const state = addPin(emptyShoebox(), fixedPin());
  const json = exportShoeboxAsJson(state, { generatedAt: new Date("2026-05-31T00:00:00Z") });
  assert.equal(json.schema, "hypothex.shoebox");
  assert.equal(json.version, SHOEBOX_SCHEMA_VERSION);
  assert.equal(json.itemCount, 1);
  assert.equal(json.items[0].kind, "prediction");
});

test("persistence roundtrip preserves items, ids, and notes", () => {
  const state = addPin(
    addPin(emptyShoebox(), fixedPin({ id: "a", note: "" })),
    fixedPin({ id: "b", note: "remember this" }),
  );
  const stored = toPersistedJson(state);
  const rehydrated = fromPersistedJson(stored);
  assert.equal(rehydrated.items.length, 2);
  assert.equal(rehydrated.items[1].id, "b");
  assert.equal(rehydrated.items[1].note, "remember this");
});

test("fromPersistedJson refuses payloads from a different schema version", () => {
  const future = JSON.stringify({ version: 999, items: [fixedPin()], freeNotes: "x" });
  const rehydrated = fromPersistedJson(future);
  assert.deepEqual(rehydrated.items, []);
  assert.equal(rehydrated.freeNotes, "");
});

test("fromPersistedJson tolerates malformed strings without throwing", () => {
  assert.deepEqual(fromPersistedJson("not json").items, []);
  assert.deepEqual(fromPersistedJson("").items, []);
  assert.deepEqual(fromPersistedJson(null).items, []);
});
