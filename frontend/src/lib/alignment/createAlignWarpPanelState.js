/**
 * Pure state for the align/warp panel (UI-009).
 *
 * Drives the Tier-3 ``align_warp`` operation (OP-031): user picks a
 * reference segment, picks a method (DTW / soft-DTW / ShapeDBA), sets a
 * Sakoe-Chiba warping band, and presses Apply.  The state module
 * computes the view model and the OP-031 ``op-invoked`` payload.
 *
 * Compatibility table mirrors the OP-031 backend exactly (per
 * ``backend/app/services/operations/tier3/align_warp.py``):
 *   cycle / spike / transient → ✓
 *   plateau / trend           → ✓ with "approx" warning in audit
 *   noise                     → refused (Apply disabled, tooltip)
 *
 * The Sakoe-Chiba slider range is the UI-spec [0.01, 0.30] — narrower
 * than OP-031's accepted (0, 1] domain so the user can't accidentally
 * pick a "no constraint" band that defeats the algorithm's purpose.
 */

export const ALIGN_METHODS = Object.freeze(['dtw', 'soft_dtw', 'shapedba']);

export const METHOD_LABELS = Object.freeze({
  dtw: 'DTW',
  soft_dtw: 'soft-DTW',
  shapedba: 'ShapeDBA',
});

export const METHOD_DESCRIPTIONS = Object.freeze({
  dtw: 'Sakoe-Chiba constrained DTW (Sakoe & Chiba 1978)',
  soft_dtw: 'Differentiable soft-DTW (Cuturi & Blondel 2017)',
  shapedba: 'Soft-DTW barycenter (Petitjean 2011 / Holder 2023)',
});

export const COMPATIBLE_SHAPES = Object.freeze(new Set(['cycle', 'spike', 'transient']));
export const APPROX_SHAPES = Object.freeze(new Set(['plateau', 'trend']));
export const INCOMPATIBLE_SHAPES = Object.freeze(new Set(['noise']));

export const MIN_WARPING_BAND = 0.01;
export const MAX_WARPING_BAND = 0.30;
export const DEFAULT_WARPING_BAND = 0.10;
export const DEFAULT_METHOD = 'dtw';

export const COMPAT_STATUS = Object.freeze({
  COMPATIBLE: 'compatible',
  APPROX: 'approx',
  INCOMPATIBLE: 'incompatible',
});

/**
 * Clamp the user-supplied warping band into the UI-spec range.
 *
 * Returns ``{ value, clamped }`` so the slider can render a brief
 * "clamped" feedback on out-of-range input.
 */
export function clampWarpingBand(value) {
  const v = Number(value);
  if (!Number.isFinite(v)) {
    return { value: DEFAULT_WARPING_BAND, clamped: true };
  }
  if (v < MIN_WARPING_BAND) return { value: MIN_WARPING_BAND, clamped: true };
  if (v > MAX_WARPING_BAND) return { value: MAX_WARPING_BAND, clamped: true };
  return { value: v, clamped: false };
}

/**
 * Inspect the labels of the segments the user wants to align (NOT the
 * reference) and decide whether Apply can fire.
 *
 * Returns a frozen-shape result with:
 *   ``status``                — overall verdict (worst-case across segments)
 *   ``incompatibleSegmentIds``— ids that block Apply
 *   ``approxSegmentIds``      — ids that proceed with the audit "approx" flag
 *   ``unknownLabels``         — labels not in any of the three sets
 *   ``message``               — single user-facing summary string
 */
export function classifyAlignCompat(segments = []) {
  const incompatible = [];
  const approx = [];
  const unknown = [];

  for (const seg of segments) {
    if (!seg || typeof seg.label !== 'string') continue;
    if (INCOMPATIBLE_SHAPES.has(seg.label)) {
      incompatible.push(seg.id);
    } else if (APPROX_SHAPES.has(seg.label)) {
      approx.push(seg.id);
    } else if (!COMPATIBLE_SHAPES.has(seg.label)) {
      unknown.push(seg.label);
    }
  }

  let status = COMPAT_STATUS.COMPATIBLE;
  if (incompatible.length > 0) status = COMPAT_STATUS.INCOMPATIBLE;
  else if (approx.length > 0 || unknown.length > 0) status = COMPAT_STATUS.APPROX;

  let message = '';
  if (incompatible.length > 0) {
    message = `Cannot warp noise segments (${incompatible.length}). Pick non-noise segments to align.`;
  } else if (approx.length > 0) {
    const s = approx.length === 1 ? '' : 's';
    message = `Approximate alignment for ${approx.length} plateau/trend segment${s}.`;
  } else if (unknown.length > 0) {
    message = `Unrecognised shape label${unknown.length === 1 ? '' : 's'}: ${[...new Set(unknown)].join(', ')}. Treated as approximate.`;
  }

  return Object.freeze({
    status,
    incompatibleSegmentIds: Object.freeze(incompatible),
    approxSegmentIds: Object.freeze(approx),
    unknownLabels: Object.freeze([...new Set(unknown)]),
    message,
  });
}

/**
 * Build the OP-031 ``op-invoked`` payload.
 *
 * Returns ``{ tier: 3, op_name: 'align_warp', params: {...} }``.  The
 * caller (BenchmarkViewerPage / palette) is responsible for translating
 * ``reference_seg_id`` and ``segment_ids`` into ``AlignableSegment``
 * objects when forwarding to the backend.
 */
export function buildAlignWarpPayload({
  referenceSegmentId,
  segmentIds,
  method = DEFAULT_METHOD,
  warpingBand = DEFAULT_WARPING_BAND,
}) {
  if (!referenceSegmentId) {
    throw new Error('buildAlignWarpPayload requires referenceSegmentId.');
  }
  if (!Array.isArray(segmentIds) || segmentIds.length === 0) {
    throw new Error('buildAlignWarpPayload requires non-empty segmentIds.');
  }
  if (!ALIGN_METHODS.includes(method)) {
    throw new Error(`buildAlignWarpPayload: unknown method '${method}'.`);
  }
  const { value: width } = clampWarpingBand(warpingBand);
  return {
    tier: 3,
    op_name: 'align_warp',
    params: {
      reference_seg_id: referenceSegmentId,
      segment_ids: [...segmentIds],
      method,
      warping_band: width,
    },
  };
}

/**
 * Compose the full panel view model.
 *
 * Inputs:
 *   segments              — every segment in the current sample (with .id and .label)
 *   referenceSegmentId    — id of the picked reference, or null
 *   selectedSegmentIds    — ids of segments the user wants to align (excluding reference)
 *   method                — current method ('dtw' | 'soft_dtw' | 'shapedba')
 *   warpingBand           — current band fraction
 *   templateOptions       — pre-stored references (empty for MVP)
 *
 * Returns:
 *   {
 *     methods, methodLabels, methodDescriptions,
 *     methodKey,
 *     warpingBand, warpingBandPercent,
 *     referenceSegment, referenceSegmentId,
 *     segmentsToAlign,
 *     compat: { status, incompatibleSegmentIds, approxSegmentIds, message },
 *     templateOptions,
 *     canApply,
 *     applyDisabledReason,   // tooltip when canApply=false
 *   }
 */
export function createAlignWarpPanelState({
  segments = [],
  referenceSegmentId = null,
  selectedSegmentIds = [],
  method = DEFAULT_METHOD,
  warpingBand = DEFAULT_WARPING_BAND,
  templateOptions = [],
} = {}) {
  const segMap = new Map(segments.map((s) => [s.id, s]));
  const referenceSegment = referenceSegmentId ? segMap.get(referenceSegmentId) ?? null : null;

  // Don't try to align the reference against itself; if the user multi-selected
  // it alongside other segments, drop it silently from segmentsToAlign.
  const dedupedIds = selectedSegmentIds.filter(
    (id) => id && id !== referenceSegmentId,
  );
  const segmentsToAlign = dedupedIds
    .map((id) => segMap.get(id))
    .filter(Boolean);

  const compat = classifyAlignCompat(segmentsToAlign);
  const { value: clampedBand } = clampWarpingBand(warpingBand);
  const methodKey = ALIGN_METHODS.includes(method) ? method : DEFAULT_METHOD;

  let canApply = true;
  let applyDisabledReason = null;
  if (!referenceSegment) {
    canApply = false;
    applyDisabledReason = 'Pick a reference segment first.';
  } else if (segmentsToAlign.length === 0) {
    canApply = false;
    applyDisabledReason = 'Select at least one segment to align.';
  } else if (compat.status === COMPAT_STATUS.INCOMPATIBLE) {
    canApply = false;
    applyDisabledReason = compat.message;
  }

  return Object.freeze({
    methods: ALIGN_METHODS,
    methodLabels: METHOD_LABELS,
    methodDescriptions: METHOD_DESCRIPTIONS,
    methodKey,
    warpingBand: clampedBand,
    warpingBandPercent: Math.round(clampedBand * 100),
    referenceSegment,
    referenceSegmentId: referenceSegment?.id ?? null,
    segmentsToAlign: Object.freeze(segmentsToAlign),
    compat,
    templateOptions: Object.freeze([...templateOptions]),
    canApply,
    applyDisabledReason,
  });
}

/**
 * Sample-the-warp helper for the live preview.
 *
 * Returns the schematic alignment overlay coordinates for each method
 * — NOT a real DTW solve.  The preview is decorative; the actual warp
 * runs on the backend when Apply fires.
 *
 *   ``dtw``       Diagonal stripe of half-width = warping_band × min_len
 *                 (Sakoe-Chiba band shape on the cost matrix grid).
 *   ``soft_dtw``  Smooth diagonal — soft DTW relaxes the hard band.
 *   ``shapedba``  Single midpoint diagonal — barycenter aligns to the
 *                 average path.
 *
 * Output is normalised to the [0, 1] × [0, 1] unit square so the
 * component can scale it into any preview viewport.
 */
export function buildPreviewModel({ method, warpingBand }) {
  const { value: band } = clampWarpingBand(warpingBand);
  const m = ALIGN_METHODS.includes(method) ? method : DEFAULT_METHOD;
  const points = [];
  const N = 32;
  for (let i = 0; i <= N; i += 1) {
    const t = i / N;
    points.push({ x: t, y: t });
  }
  return Object.freeze({
    method: m,
    diagonal: Object.freeze(points),
    bandHalfWidth: m === 'dtw' ? band : 0,
    smooth: m === 'soft_dtw',
    barycenter: m === 'shapedba',
  });
}
