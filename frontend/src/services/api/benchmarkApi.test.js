import test from "node:test";
import assert from "node:assert/strict";

import {
  adaptModel,
  fetchBenchmarkCompatibility,
  fetchBenchmarkDatasets,
  fetchBenchmarkModels,
  fetchBenchmarkOperationRegistry,
  fetchBenchmarkPrediction,
  fetchBenchmarkSuggestion,
  fetchBenchmarkUncertainty,
  submitSuggestionDecision,
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

test("fetchBenchmarkSuggestion returns normalized suggestion payload", async () => {
  const suggestion = await fetchBenchmarkSuggestion("GunPoint", "test", 0, "prototype", async () => ({
    ok: true,
    async json() {
      return {
        provisionalSegments: [{ segmentId: "segment-001", startIndex: 0, endIndex: 11 }],
        candidateBoundaries: [{ boundaryIndex: 12, score: 0.9, confidence: 0.9 }],
      };
    },
  }));

  assert.equal(suggestion.provisionalSegments.length, 1);
  assert.equal(suggestion.candidateBoundaries[0].boundaryIndex, 12);
});

test("fetchBenchmarkSuggestion passes labeler param in query string", async () => {
  let capturedUrl = "";
  const suggestion = await fetchBenchmarkSuggestion("GunPoint", "test", 0, "llm", async (url) => {
    capturedUrl = url;
    return {
      ok: true,
      async json() {
        return {
          provisionalSegments: [],
          candidateBoundaries: [],
          labeler: "llm",
        };
      },
    };
  });

  assert.ok(capturedUrl.includes("labeler=llm"));
  assert.equal(suggestion.labeler, "llm");
});

test("fetchBenchmarkSuggestion defaults labeler to prototype", async () => {
  let capturedUrl = "";
  await fetchBenchmarkSuggestion("GunPoint", "test", 0, "prototype", async (url) => {
    capturedUrl = url;
    return {
      ok: true,
      async json() {
        return { provisionalSegments: [], candidateBoundaries: [] };
      },
    };
  });

  assert.ok(capturedUrl.includes("labeler=prototype"));
});

test("fetchBenchmarkUncertainty returns boundary and segment uncertainty arrays", async () => {
  const result = await fetchBenchmarkUncertainty("GunPoint", "test", 0, async () => ({
    ok: true,
    async json() {
      return {
        boundaryUncertainty: [0.2, 0.8],
        segmentUncertainty: [0.1, 0.5, 0.3],
      };
    },
  }));

  assert.deepEqual(result.boundaryUncertainty, [0.2, 0.8]);
  assert.deepEqual(result.segmentUncertainty, [0.1, 0.5, 0.3]);
});

test("fetchBenchmarkUncertainty rejects malformed payloads", async () => {
  await assert.rejects(
    () =>
      fetchBenchmarkUncertainty("GunPoint", "test", 0, async () => ({
        ok: true,
        async json() {
          return { boundaryUncertainty: [0.1] };
        },
      })),
    /boundaryUncertainty and segmentUncertainty/,
  );
});

test("fetchBenchmarkUncertainty surfaces backend errors", async () => {
  await assert.rejects(
    () =>
      fetchBenchmarkUncertainty("GunPoint", "test", 0, async () => ({
        ok: false,
        status: 500,
        async json() {
          return { error: "uncertainty computation failed" };
        },
      })),
    /uncertainty computation failed/,
  );
});

test("adaptModel returns model_version_id and prototypes_updated", async () => {
  const result = await adaptModel(
    "session-001",
    [{ label: "trend", values: [0.1, 0.2, 0.3] }],
    async () => ({
      ok: true,
      async json() {
        return {
          model_version_id: "suggestion-model-v1+adapt-1",
          prototypes_updated: ["trend"],
          drift_report: { trend: 0.02 },
        };
      },
    }),
  );

  assert.equal(result.model_version_id, "suggestion-model-v1+adapt-1");
  assert.deepEqual(result.prototypes_updated, ["trend"]);
});

test("adaptModel rejects malformed payloads", async () => {
  await assert.rejects(
    () =>
      adaptModel("session-001", [], async () => ({
        ok: true,
        async json() {
          return { prototypes_updated: [] };
        },
      })),
    /model_version_id and prototypes_updated/,
  );
});

test("adaptModel surfaces backend 400 errors", async () => {
  await assert.rejects(
    () =>
      adaptModel("session-001", [], async () => ({
        ok: false,
        status: 400,
        async json() {
          return { error: "support_segments must contain at least one segment" };
        },
      })),
    /support_segments must contain at least one segment/,
  );
});

test("submitSuggestionDecision returns the backend audit event payload", async () => {
  const payload = await submitSuggestionDecision(
    "session-test-001",
    {
      seriesId: "series-001",
      segmentationId: "segmentation-001",
      suggestionId: "suggestion-001",
      decision: "accepted",
      targetSegmentIds: ["segment-001"],
    },
    async () => ({
      ok: true,
      async json() {
        return {
          eventType: "suggestion_accepted",
          suggestion: {
            suggestionId: "suggestion-001",
            decision: "accepted",
          },
        };
      },
    }),
  );

  assert.equal(payload.eventType, "suggestion_accepted");
  assert.equal(payload.suggestion.decision, "accepted");
});
