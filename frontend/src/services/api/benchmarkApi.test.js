import test from "node:test";
import assert from "node:assert/strict";

import {
  fetchBenchmarkCompatibility,
  fetchBenchmarkDatasets,
  fetchBenchmarkModels,
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
