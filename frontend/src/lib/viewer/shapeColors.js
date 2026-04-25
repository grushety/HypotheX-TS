/**
 * Colour tokens for the 7 shape primitives (UI-004).
 * All colour values live here — no hard-coded colour strings elsewhere.
 */

export const SHAPE_COLORS = {
  plateau:   '#9e9e9e',
  trend:     '#1565c0',
  step:      '#e65100',
  spike:     '#c62828',
  cycle:     '#00695c',
  transient: '#6a1b9a',
  noise:     '#bdbdbd',
};

/** Ordered list of all 7 shape primitive names. */
export const SHAPE_LABELS = Object.keys(SHAPE_COLORS);

const FALLBACK_COLOR = '#757575';

/**
 * Return the registered colour for the given shape, or a neutral fallback for
 * unknown / undefined shapes.
 *
 * @param {string|null|undefined} shape
 * @returns {string} CSS colour string
 */
export function getShapeColor(shape) {
  return SHAPE_COLORS[shape] ?? FALLBACK_COLOR;
}
