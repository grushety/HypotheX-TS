/**
 * HTTP client for segment-mutation routes (HTS-106).
 *
 * Today: only ``POST /api/segments/<id>/scope`` is implemented backend-side.
 * Future: split / merge / boundary mutations will move here too once they
 * leave the legacy benchmark-routes file.
 */

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
    const err = new Error(message);
    err.status = response.status;
    throw err;
  }
  if (!payload || typeof payload !== 'object') {
    throw new Error(`${label} response must be an object.`);
  }
  return payload;
}

export async function updateSegmentScope(
  { segmentId, scope, previousScope = null, triggerReclassify = false },
  fetchImpl = fetch,
) {
  if (!segmentId) throw new Error('updateSegmentScope requires segmentId.');
  if (!scope || typeof scope !== 'object') {
    throw new Error('updateSegmentScope requires a scope object.');
  }
  const response = await fetchImpl(
    `/api/segments/${encodeURIComponent(segmentId)}/scope`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scope, previousScope, triggerReclassify }),
    },
  );
  return readJsonResponse(response, 'Segment scope update');
}
