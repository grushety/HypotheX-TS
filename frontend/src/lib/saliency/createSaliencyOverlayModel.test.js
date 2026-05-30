import test from "node:test";
import assert from "node:assert/strict";

import { createSaliencyOverlayModel } from "./createSaliencyOverlayModel.js";

test("empty attribution returns no cells and zero magnitude", () => {
  const model = createSaliencyOverlayModel([]);
  assert.deepEqual(model.cells, []);
  assert.equal(model.maxMagnitude, 0);
  assert.equal(model.positiveCount, 0);
  assert.equal(model.negativeCount, 0);
});

test("each cell carries the index, value, x, width, fill and opacity", () => {
  const model = createSaliencyOverlayModel([0.1, -0.05, 0.0]);
  assert.equal(model.cells.length, 3);
  for (const cell of model.cells) {
    assert.ok(Number.isInteger(cell.index));
    assert.ok(Number.isFinite(cell.value));
    assert.ok(Number.isFinite(cell.x));
    assert.ok(Number.isFinite(cell.width));
    assert.ok(typeof cell.fill === "string");
    assert.ok(cell.opacity >= 0 && cell.opacity <= 1);
  }
});

test("positive and negative attributions get distinct fills", () => {
  const model = createSaliencyOverlayModel([0.2, -0.2, 0.4]);
  assert.equal(model.cells[0].fill, model.cells[2].fill);
  assert.notEqual(model.cells[0].fill, model.cells[1].fill);
  assert.equal(model.positiveCount, 2);
  assert.equal(model.negativeCount, 1);
});

test("opacity is square-root scaled to peak magnitude", () => {
  const model = createSaliencyOverlayModel([0, 1.0, 0.25]);
  // peak magnitude == 1, sqrt(1/1) == 1, sqrt(0.25/1) == 0.5
  assert.equal(model.maxMagnitude, 1);
  assert.equal(model.cells[0].opacity, 0);
  assert.equal(model.cells[1].opacity, 1);
  assert.equal(model.cells[2].opacity, 0.5);
});

test("non-finite values are treated as zero attribution", () => {
  const model = createSaliencyOverlayModel([NaN, 0.5, undefined, -0.5]);
  assert.equal(model.cells[0].value, 0);
  assert.equal(model.cells[2].value, 0);
  assert.equal(model.maxMagnitude, 0.5);
});

test("flat-zero attribution yields zero opacity everywhere (no fabricated heat)", () => {
  const model = createSaliencyOverlayModel([0, 0, 0, 0]);
  for (const cell of model.cells) {
    assert.equal(cell.opacity, 0);
  }
});

test("cells span the inner chart bounds left → right", () => {
  const model = createSaliencyOverlayModel([0.5, 0.5, 0.5, 0.5], {
    width: 720,
    bounds: { left: 52, right: 702 },
  });
  const innerWidth = 702 - 52;
  const stepWidth = innerWidth / 4;
  assert.equal(model.cells[0].x, 52);
  assert.equal(model.cells[0].width.toFixed(6), stepWidth.toFixed(6));
  assert.equal(model.cells[3].x.toFixed(6), (52 + 3 * stepWidth).toFixed(6));
});
