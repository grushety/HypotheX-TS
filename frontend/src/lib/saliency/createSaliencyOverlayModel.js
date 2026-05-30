/**
 * createSaliencyOverlayModel — turn a per-timestep attribution vector into
 * a set of color-banded segments ready for SVG rendering.
 *
 * Visual contract:
 *
 *   - Heatmap is rendered as a horizontal band BENEATH the chart's main
 *     line, so it is visually distinct from segment bands (which colour
 *     the chart background) and from the line itself.
 *   - Hue is fixed (amber); intensity (alpha) tracks |attribution[t]| /
 *     max|attribution|. Saturated bins == "the model looked here most."
 *   - Sign is also encoded by hue: positive attribution → amber
 *     (informative for the baseline class); negative → indigo (this
 *     timestep argues against the baseline class). Surfacing the sign is
 *     load-bearing — naive "absolute saliency" hides the case where the
 *     model is fighting an outlier point.
 *
 * The pure helper does NO DOM work; the component reads the returned
 * `cells` and draws them as `<rect>` elements scaled to the chart frame.
 */

const POSITIVE_HUE = "#e8870c"; // amber — matches --st-warn for sign=+
const NEGATIVE_HUE = "#2b4ad6"; // accent indigo for sign=-

export function createSaliencyOverlayModel(attribution, { width = 720, height = 14, bounds } = {}) {
  if (!Array.isArray(attribution) || attribution.length === 0) {
    return {
      cells: [],
      maxMagnitude: 0,
      positiveCount: 0,
      negativeCount: 0,
      width,
      height,
    };
  }

  const safeBounds = bounds ?? { left: 52, right: width - 18 };
  const innerWidth = safeBounds.right - safeBounds.left;
  const stepWidth = innerWidth / attribution.length;

  let maxMagnitude = 0;
  for (const value of attribution) {
    if (!Number.isFinite(value)) continue;
    const m = Math.abs(value);
    if (m > maxMagnitude) maxMagnitude = m;
  }

  const denominator = maxMagnitude > 0 ? maxMagnitude : 1;
  let positiveCount = 0;
  let negativeCount = 0;

  const cells = attribution.map((rawValue, index) => {
    const value = Number.isFinite(rawValue) ? rawValue : 0;
    if (value > 0) positiveCount += 1;
    else if (value < 0) negativeCount += 1;
    // Square-root scaling so mid-range importance is still readable;
    // matches the perceptual scaling used by most off-the-shelf
    // attribution colour ramps.
    const intensity = Math.sqrt(Math.abs(value) / denominator);
    return {
      index,
      value,
      x: safeBounds.left + index * stepWidth,
      width: stepWidth,
      fill: value >= 0 ? POSITIVE_HUE : NEGATIVE_HUE,
      opacity: maxMagnitude === 0 ? 0 : Math.max(0, Math.min(1, intensity)),
    };
  });

  return {
    cells,
    maxMagnitude,
    positiveCount,
    negativeCount,
    width,
    height,
  };
}
