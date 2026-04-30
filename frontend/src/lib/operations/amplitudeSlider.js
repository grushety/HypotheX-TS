/**
 * Pure logic for AmplitudeSlider (UI-016).
 *
 * Maps a log-scaled position [0..1] on the slider track to an alpha factor in
 * [MIN_ALPHA..MAX_ALPHA] with identity (1.0) at the center.  Provides
 * snap-to-common-values, classification (dampen/identity/amplify), and a
 * 1 % log step suitable for keyboard adjustment.
 *
 * No DOM, no Vue — testable in isolation.
 */

export const MIN_ALPHA = 0.01;
export const MAX_ALPHA = 100;
export const IDENTITY = 1.0;

export const SNAP_POINTS = [0.5, 1.0, 2.0, 10.0];
export const SNAP_THRESHOLD = 0.05; // ±5 %

const LOG_MIN = Math.log(MIN_ALPHA);
const LOG_MAX = Math.log(MAX_ALPHA);

function clamp(value, lo, hi) {
  if (Number.isNaN(value)) return lo;
  return Math.min(hi, Math.max(lo, value));
}

/**
 * Map a track position t in [0..1] to alpha in [MIN_ALPHA..MAX_ALPHA] log-scaled.
 * t=0 → MIN_ALPHA, t=0.5 → IDENTITY, t=1 → MAX_ALPHA.
 */
export function positionToAlpha(t) {
  const tt = clamp(Number(t), 0, 1);
  return Math.exp(LOG_MIN + tt * (LOG_MAX - LOG_MIN));
}

/**
 * Inverse of positionToAlpha — alpha → track position [0..1].
 */
export function alphaToPosition(alpha) {
  const a = clamp(Number(alpha), MIN_ALPHA, MAX_ALPHA);
  return (Math.log(a) - LOG_MIN) / (LOG_MAX - LOG_MIN);
}

/**
 * Snap alpha to the nearest common value within ±SNAP_THRESHOLD (relative).
 * Returns the snapped value, or alpha unchanged if no snap point is in range.
 */
export function snapToCommon(alpha, threshold = SNAP_THRESHOLD, points = SNAP_POINTS) {
  for (const p of points) {
    if (Math.abs(alpha - p) / p <= threshold) return p;
  }
  return alpha;
}

/**
 * Classify alpha as 'dampen' (< 1), 'identity' (== 1), or 'amplify' (> 1).
 * Uses a small tolerance so floating-point noise near 1 still classifies as identity.
 */
export function classify(alpha, identityTolerance = 1e-9) {
  const a = Number(alpha);
  if (Math.abs(a - IDENTITY) <= identityTolerance) return 'identity';
  return a < IDENTITY ? 'dampen' : 'amplify';
}

/**
 * Format alpha as a multiplicative label such as "×2.0" or "×0.50".
 */
export function formatMultiplier(alpha) {
  const a = Number(alpha);
  if (a >= 10) return `×${a.toFixed(1)}`;
  if (a >= 1) return `×${a.toFixed(2)}`;
  return `×${a.toFixed(2)}`;
}

/**
 * Compute the next alpha after a 1 % log-step in `direction` (+1 or −1).
 * Used by ArrowRight/ArrowLeft and ArrowUp/ArrowDown keys.
 */
export function stepAlpha(alpha, direction, stepFraction = 0.01) {
  const dir = direction >= 0 ? 1 : -1;
  const t = alphaToPosition(alpha);
  const nextT = clamp(t + dir * stepFraction, 0, 1);
  return positionToAlpha(nextT);
}

/**
 * Return whether two alphas are close enough that the slider should treat them
 * as identical (no-op on commit).
 */
export function isIdentity(alpha) {
  return classify(alpha) === 'identity';
}

/**
 * Return the "amplify-only" lower bound (used for spike single-direction mode).
 */
export const AMPLIFY_ONLY_MIN = IDENTITY;
