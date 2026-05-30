import test from "node:test";
import assert from "node:assert/strict";

import { createFidelityStripState } from "./createFidelityStripState.js";

const datasetPathPrediction = {
  predicted_label: "Gun",
  scores: [],
  model_input_length: 150,
  transforms: [
    {
      name: "cast_float64",
      params: { from_dtype: "float32", to_dtype: "float64" },
      before_shape: [1, 150],
      after_shape: [1, 150],
    },
    {
      name: "flatten",
      params: { order: "C" },
      before_shape: [1, 150],
      after_shape: [150],
    },
  ],
};

const adHocPrediction = {
  predicted_label: "Gun",
  scores: [],
  model_input_length: 150,
  transforms: [],
};

test("status is empty when no prediction has been requested yet", () => {
  const state = createFidelityStripState();
  assert.equal(state.status, "empty");
  assert.equal(state.transformCount, 0);
  assert.equal(state.modelInputLength, null);
  assert.match(state.headline, /run a prediction/);
});

test("dataset-path prediction lists cast + flatten with human-readable captions", () => {
  const state = createFidelityStripState({
    prediction: datasetPathPrediction,
    compatibility: { is_compatible: true, messages: [] },
    rawInputLength: 150,
  });
  assert.equal(state.status, "ok");
  assert.equal(state.transformCount, 2);
  assert.equal(state.transforms[0].name, "cast_float64");
  assert.equal(state.transforms[0].label, "Cast to float64");
  assert.match(state.transforms[0].caption, /float32 → float64/);
  assert.equal(state.transforms[1].name, "flatten");
  assert.equal(state.transforms[1].label, "Flatten to 1-D");
  assert.match(state.transforms[1].caption, /\(1, 150\) → \(150\)/);
});

test("ad-hoc 1-D prediction is described as identity (0 transforms)", () => {
  const state = createFidelityStripState({
    prediction: adHocPrediction,
    compatibility: { is_compatible: true, messages: [] },
    rawInputLength: 150,
  });
  assert.equal(state.status, "ok");
  assert.equal(state.transformCount, 0);
  assert.match(state.headline, /identity \(0 transforms\)/);
  assert.match(state.headline, /150 values/);
});

test("compatibility warning escalates status and surfaces messages", () => {
  const state = createFidelityStripState({
    prediction: datasetPathPrediction,
    compatibility: {
      is_compatible: false,
      messages: ["Model expects 1 channel; dataset has 3."],
    },
  });
  assert.equal(state.status, "warn");
  assert.match(state.headline, /1 issue/);
  assert.deepEqual(state.compatibility.messages, [
    "Model expects 1 channel; dataset has 3.",
  ]);
});

test("missing compatibility data falls back to trusting the prediction succeeded", () => {
  const state = createFidelityStripState({
    prediction: adHocPrediction,
  });
  // No compatibility payload (e.g. predict-values flow) — we trust the model
  // since it ran; the dataset-level checks live on the GET prediction path.
  assert.equal(state.status, "ok");
  assert.equal(state.compatibility.ok, true);
});

test("malformed transforms array does not throw", () => {
  const state = createFidelityStripState({
    prediction: {
      predicted_label: "x",
      scores: [],
      model_input_length: 4,
      transforms: [
        { name: "weird_op", params: { mode: "test" }, before_shape: [4], after_shape: [4] },
        null,
        undefined,
      ],
    },
    compatibility: { is_compatible: true, messages: [] },
  });
  assert.equal(state.transformCount, 3);
  assert.equal(state.transforms[0].label, "weird_op");
  assert.equal(state.transforms[1].label, "Unknown transform");
  assert.equal(state.transforms[2].label, "Unknown transform");
});

test("model_input_length defaults to null when backend omits it", () => {
  const state = createFidelityStripState({
    prediction: { predicted_label: "x", scores: [], transforms: [] },
    compatibility: { is_compatible: true, messages: [] },
  });
  assert.equal(state.modelInputLength, null);
  assert.match(state.headline, /—/);
});
