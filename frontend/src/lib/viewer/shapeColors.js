/**
 * Colour tokens for the 7 shape primitives (UI-004).
 * All colour values live here — no hard-coded colour strings elsewhere.
 */

export const SHAPE_COLORS = {
  plateau:   '#e8870c',
  trend:     '#1f6fd6',
  step:      '#0c8599',
  spike:     '#e03131',
  cycle:     '#2f9e44',
  transient: '#7048e8',
  noise:     '#939db0',
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
