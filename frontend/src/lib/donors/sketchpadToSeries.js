/**
 * Convert raw sketchpad input (canvas-space points) into a uniform-time
 * sample-space time series for the UserDrawn donor backend (UI-008).
 *
 * Pipeline:
 *   1. Drop duplicate-x points so a vertical line near the start doesn't
 *      collapse the interpolation.
 *   2. Sort by x ascending so retraced strokes still produce a monotone
 *      time axis.
 *   3. Linearly interpolate y(x) onto a uniform grid of ``targetLength``
 *      samples spanning the original segment's x-range.
 *   4. Min-max rescale the result to the original segment's amplitude
 *      range so the donor can be crossfaded into the segment without a
 *      level mismatch.
 */

const MIN_POINTS = 2;

function dedupeMonotone(points) {
  const sorted = [...points].sort((a, b) => a.x - b.x);
  const out = [];
  let lastX = -Infinity;
  for (const p of sorted) {
    if (p.x > lastX) {
      out.push(p);
      lastX = p.x;
    } else if (p.x === lastX && out.length > 0) {
      out[out.length - 1] = { x: p.x, y: p.y };
    }
  }
  return out;
}

function rescaleToRange(values, targetMin, targetMax) {
  if (values.length === 0) return values;
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  if (!(targetMax > targetMin) || hi === lo) {
    const mid = (Number.isFinite(targetMin) && Number.isFinite(targetMax))
      ? (targetMin + targetMax) / 2
      : 0;
    return values.map(() => mid);
  }
  const span = hi - lo;
  const targetSpan = targetMax - targetMin;
  return values.map((v) => targetMin + ((v - lo) / span) * targetSpan);
}

/**
 * @param {{x:number,y:number}[]} points     Raw canvas points (any order).
 * @param {number}                targetLength  Output sample count.
 * @param {{min:number,max:number}} amplitudeRange  Target [min, max] for output.
 * @returns {number[] | null}  Time series, or null if input is too short.
 */
export function sketchpadToSeries(points, targetLength, amplitudeRange) {
  if (!Array.isArray(points) || points.length < MIN_POINTS) return null;
  if (!Number.isInteger(targetLength) || targetLength < 2) return null;
  if (
    !amplitudeRange ||
    !Number.isFinite(Number(amplitudeRange.min)) ||
    !Number.isFinite(Number(amplitudeRange.max))
  ) {
    return null;
  }

  const monotone = dedupeMonotone(points);
  if (monotone.length < MIN_POINTS) return null;

  const xMin = monotone[0].x;
  const xMax = monotone[monotone.length - 1].x;
  if (!(xMax > xMin)) return null;

  const out = new Array(targetLength);
  let cursor = 1;
  for (let i = 0; i < targetLength; i += 1) {
    const x = xMin + ((xMax - xMin) * i) / (targetLength - 1);
    while (cursor < monotone.length - 1 && monotone[cursor].x < x) cursor += 1;
    const left = monotone[cursor - 1];
    const right = monotone[cursor];
    if (right.x === left.x) {
      out[i] = right.y;
    } else {
      const t = (x - left.x) / (right.x - left.x);
      out[i] = left.y + t * (right.y - left.y);
    }
  }

  // Canvas y-axis grows downward; flip so "drawing higher = larger value".
  const flipped = out.map((v) => -v);
  return rescaleToRange(
    flipped,
    Number(amplitudeRange.min),
    Number(amplitudeRange.max),
  );
}
