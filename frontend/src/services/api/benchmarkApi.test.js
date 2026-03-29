import test from "node:test";
import assert from "node:assert/strict";

import {
  fetchBenchmarkCompatibility,
  fetchBenchmarkDatasets,
  fetchBenchmarkModels,
  fetchBenchmarkOperationRegistry,
  fetchBenchmarkPrediction,
} from "./benchmarkApi.js";

test("fetchBenchmarkDatasets returns dataset array from backend payload", async () => {
  const datasets = await fetchBenchmarkDatasets(async () => ({
    ok: true,
    async json() {
      return { datasets: [{ name: "GunPoint" }] };
    },
  }));

  assert.deepEqual(datasets, [{ name: "GunPoint" }]);
});

test("fetchBenchmarkModels rejects malformed payloads", async () => {
  await assert.rejects(
    () =>
      fetchBenchmarkModels(async () => ({
        ok: true,
        async json() {
          return { artifacts: [] };
        },
      })),
    /families and artifacts arrays/,
  );
});

test("fetchBenchmarkOperationRegistry returns the backend operation catalog", async () => {
  const registry = await fetchBenchmarkOperationRegistry(async () => ({
    ok: true,
    async json() {
      return {
        schemaVersion: "1.0.0",
        ontologyName: "mvp-core",
        operationsByChunk: {
          trend: ["split", "merge"],
        },
      };
    },
  }));

  assert.deepEqual(registry.operationsByChunk.trend, ["split", "merge"]);
});

test("fetchBenchmarkCompatibility surfaces backend errors", async () => {
  await assert.rejects(
    () =>
      fetchBenchmarkCompatibility("GunPoint", "fcn-gunpoint", async () => ({
        ok: false,
        status: 400,
        async json() {
          return { error: "pair is invalid" };
        },
      })),
    /pair is invalid/,
  );
});

test("fetchBenchmarkPrediction returns normalized prediction payload", async () => {
  const prediction = await fetchBenchmarkPrediction("GunPoint", "fcn-gunpoint", "test", 2, async () => ({
    ok: true,
    async json() {
      return {
        predicted_label: "class-1",
        true_label: "class-0",
        scores: [{ label: "class-1", score: 2.5, probability: 0.81 }],
      };
    },
  }));

  assert.equal(prediction.predicted_label, "class-1");
  assert.equal(prediction.scores.length, 1);
});

test("fetchBenchmarkPrediction rejects malformed payloads", async () => {
  await assert.rejects(
    () =>
      fetchBenchmarkPrediction("GunPoint", "fcn-gunpoint", "test", 2, async () => ({
        ok: true,
        async json() {
          return { scores: [] };
        },
      })),
    /predicted_label and scores/,
  );
});
