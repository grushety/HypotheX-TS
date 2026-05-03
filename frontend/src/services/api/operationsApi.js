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
