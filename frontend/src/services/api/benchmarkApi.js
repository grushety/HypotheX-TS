function ensureObjectPayload(payload, label) {
  if (!payload || typeof payload !== "object") {
    throw new Error(`${label} response must be an object.`);
  }

  return payload;
}

async function readJsonResponse(response, label) {
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error(`${label} response was not valid JSON.`);
  }

  if (!response.ok) {
    const message =
      payload && typeof payload.error === "string"
        ? payload.error
        : `${label} request failed with status ${response.status}.`;
    throw new Error(message);
  }

  return ensureObjectPayload(payload, label);
}

export async function fetchBenchmarkDatasets(fetchImpl = fetch) {
  const response = await fetchImpl("/api/benchmarks/datasets");
  const payload = await readJsonResponse(response, "Dataset list");

  if (!Array.isArray(payload.datasets)) {
    throw new Error("Dataset list response must include a datasets array.");
  }

  return payload.datasets;
}

export async function fetchBenchmarkModels(fetchImpl = fetch) {
  const response = await fetchImpl("/api/benchmarks/models");
  const payload = await readJsonResponse(response, "Model list");

  if (!Array.isArray(payload.families) || !Array.isArray(payload.artifacts)) {
    throw new Error("Model list response must include families and artifacts arrays.");
  }

  return payload;
}

export async function fetchBenchmarkOperationRegistry(fetchImpl = fetch) {
  const response = await fetchImpl("/api/benchmarks/operation-registry");
  const payload = await readJsonResponse(response, "Operation registry");

  if (!payload.operationsByChunk || typeof payload.operationsByChunk !== "object") {
    throw new Error("Operation registry response must include an operationsByChunk object.");
  }

  return payload;
}

export async function fetchBenchmarkCompatibility(datasetName, artifactId, fetchImpl = fetch) {
  const params = new URLSearchParams({
    dataset: datasetName,
    artifact_id: artifactId,
  });
  const response = await fetchImpl(`/api/benchmarks/compatibility?${params.toString()}`);
  const payload = await readJsonResponse(response, "Compatibility");

  if (typeof payload.is_compatible !== "boolean" || !Array.isArray(payload.messages)) {
    throw new Error("Compatibility response must include is_compatible and messages.");
  }

  return payload;
}

export async function fetchBenchmarkSample(datasetName, split, sampleIndex, fetchImpl = fetch) {
  const params = new URLSearchParams({
    dataset: datasetName,
    split,
    sample_index: String(sampleIndex),
  });
  const response = await fetchImpl(`/api/benchmarks/sample?${params.toString()}`);
  const payload = await readJsonResponse(response, "Benchmark sample");

  if (
    !Array.isArray(payload.values) ||
    typeof payload.series_length !== "number" ||
    typeof payload.channel_count !== "number"
  ) {
    throw new Error("Benchmark sample response must include values, series_length, and channel_count.");
  }

  return payload;
}

export async function fetchBenchmarkPrediction(
  datasetName,
  artifactId,
  split,
  sampleIndex,
  fetchImpl = fetch,
) {
  const params = new URLSearchParams({
    dataset: datasetName,
    artifact_id: artifactId,
    split,
    sample_index: String(sampleIndex),
  });
  const response = await fetchImpl(`/api/benchmarks/prediction?${params.toString()}`);
  const payload = await readJsonResponse(response, "Benchmark prediction");

  if (typeof payload.predicted_label !== "string" || !Array.isArray(payload.scores)) {
    throw new Error("Benchmark prediction response must include predicted_label and scores.");
  }

  return payload;
}

export async function fetchBenchmarkSuggestion(datasetName, split, sampleIndex, labeler = "prototype", fetchImpl = fetch) {
  const params = new URLSearchParams({
    dataset: datasetName,
    split,
    sample_index: String(sampleIndex),
    labeler,
  });
  const response = await fetchImpl(`/api/benchmarks/suggestion?${params.toString()}`);
  const payload = await readJsonResponse(response, "Benchmark suggestion");

  if (!Array.isArray(payload.provisionalSegments) || !Array.isArray(payload.candidateBoundaries)) {
    throw new Error(
      "Benchmark suggestion response must include provisionalSegments and candidateBoundaries.",
    );
  }

  return payload;
}

export async function fetchBenchmarkUncertainty(datasetName, split, sampleIndex, fetchImpl = fetch) {
  const params = new URLSearchParams({
    dataset: datasetName,
    split,
    sample_index: String(sampleIndex),
  });
  const response = await fetchImpl(`/api/benchmarks/suggestion/uncertainty?${params.toString()}`);
  const payload = await readJsonResponse(response, "Benchmark uncertainty");

  if (!Array.isArray(payload.boundaryUncertainty) || !Array.isArray(payload.segmentUncertainty)) {
    throw new Error(
      "Benchmark uncertainty response must include boundaryUncertainty and segmentUncertainty.",
    );
  }

  return payload;
}

export async function adaptModel(sessionId, supportSegments, fetchImpl = fetch) {
  const response = await fetchImpl("/api/benchmarks/suggestion/adapt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, support_segments: supportSegments }),
  });
  const payload = await readJsonResponse(response, "Adapt model");

  if (typeof payload.model_version_id !== "string" || !Array.isArray(payload.prototypes_updated)) {
    throw new Error("Adapt model response must include model_version_id and prototypes_updated.");
  }

  return payload;
}

export async function submitSuggestionDecision(sessionId, suggestionDecision, fetchImpl = fetch) {
  const response = await fetchImpl(`/api/audit/sessions/${sessionId}/suggestions/decision`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(suggestionDecision),
  });
  const payload = await readJsonResponse(response, "Suggestion decision");

  if (typeof payload.eventType !== "string" || !payload.suggestion || typeof payload.suggestion !== "object") {
    throw new Error("Suggestion decision response must include eventType and suggestion.");
  }

  return payload;
}
