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
