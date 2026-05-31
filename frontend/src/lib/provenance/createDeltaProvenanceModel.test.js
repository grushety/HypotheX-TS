import test from "node:test";
import assert from "node:assert/strict";

import { createDeltaProvenanceModel } from "./createDeltaProvenanceModel.js";

const samplePayload = {
  artifact_id: "fcn-gunpoint",
  baseline_class: "Gun",
  total_delta: -0.5,
  residual: -0.02,
  method: "leave-one-out over operations",
  reference: "Štrumbelj & Kononenko, JMLR 11 (2010)",
  contributions: [
    { op_id: "op-1", op_label: "amplify ×2", contribution: -0.18 },
    { op_id: "op-2", op_label: "stretch", contribution: -0.30 },
  ],
};

test("hasData is false when no provenance has been fetched", () => {
  const model = createDeltaProvenanceModel(null);
  assert.equal(model.hasData, false);
  assert.deepEqual(model.rows, []);
  assert.equal(model.totalDelta, 0);
});

test("rows preserve application order and carry signed contribution", () => {
  const model = createDeltaProvenanceModel(samplePayload);
  assert.equal(model.hasData, true);
  assert.equal(model.rows[0].opId, "op-1");
  assert.equal(model.rows[1].opId, "op-2");
  assert.equal(model.rows[0].sign, "negative");
  assert.equal(model.rows[1].contribution, -0.30);
});

test("bar width is normalised to the largest |contribution|", () => {
  const model = createDeltaProvenanceModel(samplePayload);
  // op-2 has the largest magnitude (0.30) → 100%; op-1 = 0.18 / 0.30 = 60%
  assert.equal(model.rows[1].barWidthPct, 100);
  assert.equal(model.rows[0].barWidthPct, 60);
});

test("residual row appears only when its magnitude is non-trivial", () => {
  const model = createDeltaProvenanceModel(samplePayload);
  assert.equal(model.showResidualRow, true);
  const residualRow = model.rows.at(-1);
  assert.equal(residualRow.isResidual, true);
  assert.equal(residualRow.opId, "__residual__");
});

test("residual row is suppressed when residual is below the visibility threshold", () => {
  const model = createDeltaProvenanceModel(
    { ...samplePayload, residual: 0.001 },
    { residualVisibilityThreshold: 0.005 },
  );
  assert.equal(model.showResidualRow, false);
  assert.equal(model.rows.length, 2);
});

test("op_label falls back to op_id when missing", () => {
  const model = createDeltaProvenanceModel({
    ...samplePayload,
    contributions: [{ op_id: "bare-op", op_label: "", contribution: -0.1 }],
  });
  assert.equal(model.rows[0].opLabel, "bare-op");
});

test("malformed contributions are filtered, never crash", () => {
  const model = createDeltaProvenanceModel({
    ...samplePayload,
    contributions: [
      { op_id: "op-1", op_label: "x", contribution: -0.18 },
      null,
      {},
      { op_id: "op-3", op_label: "y", contribution: Number.NaN },
    ],
  });
  // op-1 and op-3 pass the op_id check; the NaN contribution clamps to 0.
  assert.equal(model.rows.filter((r) => !r.isResidual).length, 2);
  assert.equal(model.rows[1].contribution, 0);
});

test("method and reference flow through verbatim", () => {
  const model = createDeltaProvenanceModel(samplePayload);
  assert.match(model.method, /leave-one-out/);
  assert.match(model.reference, /Štrumbelj/);
});
