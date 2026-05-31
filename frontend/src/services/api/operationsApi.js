/**
 * API client for the HTS-100 op-invocation route.
 *
 * Single endpoint: ``POST /api/operations/invoke``. Returns the parsed
 * response body on success; throws an Error carrying the backend's
 * error message on any non-2xx.
 */

function ensureObjectPayload(payload, label) {
  if (!payload || typeof payload !== 'object') {
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
      payload && typeof payload.error === 'string'
        ? payload.error
        : `${label} request failed with status ${response.status}.`;
    throw new Error(message);
  }
  return ensureObjectPayload(payload, label);
}

/**
 * Invoke a Tier-1, Tier-2, or Tier-3 operation on a segment.
 *
 * Required keys on ``request``: ``series_id``, ``segment_id``, ``tier``,
 * ``op_name``, ``sample_values``, ``segments``. All other keys map
 * straight through to the JSON body — see HTS-100's
 * ``schemas/operation-invoke.schema.json`` for the contract.
 */
export async function invokeOperation(request, fetchImpl = fetch) {
  const response = await fetchImpl('/api/operations/invoke', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return readJsonResponse(response, 'Invoke operation');
}

/**
 * REWORK-07. Find the smallest L2 edit that flips the prototype classifier
 * on the given baseline series. The backend returns the proposed edit
 * (already past the decision boundary), the distance, the flipped class,
 * and provenance (method + paper reference). When no flip is reachable
 * (degenerate prototypes), `found` is false with a `reason` string.
 */
/**
 * REWORK-09. Attribute the prediction Δ to each op in the session via
 * leave-one-out over op_deltas. Returns per-op signed contribution +
 * residual + method/reference for the caveat tooltip.
 */
export async function fetchDeltaProvenance(
  { artifactId, baselineValues, currentValues, ops },
  fetchImpl = fetch,
) {
  const response = await fetchImpl('/api/operations/provenance', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      artifact_id: artifactId,
      baseline_values: baselineValues,
      current_values: currentValues,
      ops,
    }),
  });
  const payload = await readJsonResponse(response, 'Δ provenance');
  if (!Array.isArray(payload.contributions)) {
    throw new Error('Δ provenance response must include a contributions array.');
  }
  return payload;
}

export async function findMinimalFlip({ artifactId, baselineValues }, fetchImpl = fetch) {
  const response = await fetchImpl('/api/operations/min-flip', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ artifact_id: artifactId, baseline_values: baselineValues }),
  });
  const payload = await readJsonResponse(response, 'Min-flip probe');
  if (typeof payload.found !== 'boolean') {
    throw new Error('Min-flip probe response must include a `found` boolean.');
  }
  return payload;
}
