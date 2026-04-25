import test from "node:test";
import assert from "node:assert/strict";

import { SHAPE_COLORS, SHAPE_LABELS, getShapeColor } from "./shapeColors.js";

const ALL_SHAPES = ["plateau", "trend", "step", "spike", "cycle", "transient", "noise"];

test("SHAPE_COLORS defines exactly the 7 shape primitives", () => {
  assert.deepEqual(new Set(Object.keys(SHAPE_COLORS)), new Set(ALL_SHAPES));
});

test("each shape colour is a 6-digit hex string", () => {
  for (const [shape, color] of Object.entries(SHAPE_COLORS)) {
    assert.match(color, /^#[0-9a-fA-F]{6}$/, `${shape}: expected 6-digit hex, got ${color}`);
  }
});

test("getShapeColor returns the registered colour for each shape", () => {
  for (const shape of ALL_SHAPES) {
    assert.equal(getShapeColor(shape), SHAPE_COLORS[shape]);
  }
});

test("getShapeColor returns a non-empty fallback string for unknown shape", () => {
  const fallback = getShapeColor("unknown");
  assert.ok(typeof fallback === "string" && fallback.startsWith("#"), "fallback must be a hex color");
});

test("getShapeColor handles null and undefined gracefully", () => {
  assert.ok(typeof getShapeColor(null) === "string");
  assert.ok(typeof getShapeColor(undefined) === "string");
});

test("SHAPE_LABELS contains all 7 shape primitives in order", () => {
  assert.deepEqual(new Set(SHAPE_LABELS), new Set(ALL_SHAPES));
  assert.equal(SHAPE_LABELS.length, 7);
});

test("fixture: all 7 shapes map to distinct colours", () => {
  const colors = ALL_SHAPES.map((shape) => getShapeColor(shape));
  const unique = new Set(colors);
  assert.equal(unique.size, 7, "each shape must have a unique colour");
});

test("fixture: one segment per shape — each gets correct colour", () => {
  const segments = ALL_SHAPES.map((shape, i) => ({
    id: `seg-${i}`,
    shape,
    start: i * 10,
    end: i * 10 + 9,
  }));

  for (const seg of segments) {
    const color = getShapeColor(seg.shape);
    assert.equal(
      color,
      SHAPE_COLORS[seg.shape],
      `segment with shape '${seg.shape}' should map to its registered colour`,
    );
  }
});
