/**
 * API client for the REWORK-10 cohort confirmation endpoint.
 */

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

/**
 * POST /api/cohort/apply — apply a scalar op across N samples and return
 * per-series outcomes + aggregates with bootstrap CI.
 */
export async function applyCohort(
  { artifactId, dataset, split, sampleIndices, opName, opParams },
  fetchImpl = fetch,
) {
  const response = await fetchImpl("/api/cohort/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      artifact_id: artifactId,
      dataset,
      split,
      sample_indices: sampleIndices,
      op_name: opName,
      op_params: opParams ?? {},
    }),
  });
  const payload = await readJsonResponse(response, "Cohort apply");
  if (!Array.isArray(payload.per_series) || !payload.aggregates) {
    throw new Error("Cohort apply response must include per_series and aggregates.");
  }
  return payload;
}
