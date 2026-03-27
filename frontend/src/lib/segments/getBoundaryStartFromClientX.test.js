import test from "node:test";
import assert from "node:assert/strict";

import { getBoundaryStartFromClientX } from "./getBoundaryStartFromClientX.js";

const rect = {
  left: 100,
  width: 400,
};

test("getBoundaryStartFromClientX maps pointer position into a series boundary start", () => {
  assert.equal(getBoundaryStartFromClientX(100, rect, 96), 1);
  assert.equal(getBoundaryStartFromClientX(300, rect, 96), 48);
  assert.equal(getBoundaryStartFromClientX(500, rect, 96), 95);
});

test("getBoundaryStartFromClientX clamps out-of-bounds positions safely", () => {
  assert.equal(getBoundaryStartFromClientX(50, rect, 96), 1);
  assert.equal(getBoundaryStartFromClientX(999, rect, 96), 95);
});
