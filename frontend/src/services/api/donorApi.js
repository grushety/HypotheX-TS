/**
 * HTTP client for the donor-proposal route (UI-008 / OP-012).
 *
 * Backend contract (the route is part of a separate ticket; this client
 * defines the on-the-wire shape):
 *
 *   POST /api/donors/propose
 *   Request:
 *     {
 *       backend: 'NativeGuide' | 'SETSDonor' | 'DiscordDonor'
 *                | 'TimeGAN' | 'ShapeDBA',
 *       segment_values: number[],
 *       target_class:   string,
 *       k:              number,        // 0-indexed: 0 = closest, 1 = next, ...
 *       exclude_ids:    string[],      // donor ids already rejected
 *     }
 *   Response (200):
 *     {
 *       backend: string,
 *       candidates: [
 *         {
 *           donor_id: string,
 *           values:   number[],
 *           distance: number,
 *           metric:   'dtw' | 'shapelet_distance' | 'matrix_profile' | ...
 *         },
 *         ...
 *       ]
 *     }
 *   Response (501): backend not implemented (TimeGAN / ShapeDBA today)
 *
 * The ``UserDrawn`` backend never reaches this client — its donor is
 * synthesised in the browser by ``sketchpadToSeries``.
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

export async function proposeDonor(
  { backend, segmentValues, targetClass, k = 0, excludeIds = [] },
  fetchImpl = fetch,
) {
  if (!backend) throw new Error('proposeDonor requires backend.');
  if (!Array.isArray(segmentValues) || segmentValues.length === 0) {
    throw new Error('proposeDonor requires segmentValues array.');
  }
  if (typeof targetClass !== 'string' || !targetClass) {
    throw new Error('proposeDonor requires targetClass.');
  }
  const body = {
    backend,
    segment_values: segmentValues,
    target_class: targetClass,
    k: Number(k) || 0,
    exclude_ids: Array.isArray(excludeIds) ? excludeIds : [],
  };
  const response = await fetchImpl('/api/donors/propose', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = await readJsonResponse(response, 'Donor proposal');
  if (!Array.isArray(payload.candidates)) {
    throw new Error('Donor proposal response must include a candidates array.');
  }
  return payload;
}
