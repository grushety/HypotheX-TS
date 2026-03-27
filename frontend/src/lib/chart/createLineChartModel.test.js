import test from "node:test";
import assert from "node:assert/strict";

import { createLineChartModel } from "./createLineChartModel.js";

test("createLineChartModel builds a visible path for a short series", () => {
  const model = createLineChartModel([0.2, 0.8, -0.1, 0.4]);

  assert.equal(model.points.length, 4);
  assert.match(model.linePath, /^M /);
  assert.equal(model.xTicks.length, 3);
  assert.equal(model.yTicks.length, 4);
});

test("createLineChartModel spans the full chart width for a longer series", () => {
  const values = Array.from({ length: 96 }, (_, index) => Math.sin(index / 8));
  const model = createLineChartModel(values);

  assert.equal(model.points.length, 96);
  assert.equal(model.points[0].x, model.bounds.left);
  assert.equal(model.points.at(-1).x, model.bounds.right);
  assert.ok(model.areaPath.endsWith("Z"));
});
