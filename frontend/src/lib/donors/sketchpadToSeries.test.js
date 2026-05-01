import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { sketchpadToSeries } from './sketchpadToSeries.js';

const RANGE = { min: 0, max: 1 };

describe('sketchpadToSeries', () => {
  it('returns null on too few points', () => {
    assert.equal(sketchpadToSeries([], 50, RANGE), null);
    assert.equal(sketchpadToSeries([{ x: 0, y: 0 }], 50, RANGE), null);
  });

  it('returns null on a degenerate (zero-width) x-range', () => {
    const points = [
      { x: 5, y: 0 },
      { x: 5, y: 100 },
    ];
    assert.equal(sketchpadToSeries(points, 10, RANGE), null);
  });

  it('returns null on missing or non-finite amplitude bounds', () => {
    const points = [{ x: 0, y: 0 }, { x: 1, y: 1 }];
    assert.equal(sketchpadToSeries(points, 10, null), null);
    assert.equal(
      sketchpadToSeries(points, 10, { min: NaN, max: 1 }),
      null,
    );
  });

  it('returns a series of length targetLength', () => {
    const points = [
      { x: 0, y: 0 },
      { x: 50, y: 100 },
      { x: 100, y: 50 },
    ];
    const out = sketchpadToSeries(points, 25, RANGE);
    assert.equal(out.length, 25);
  });

  it('rescales the output to the target amplitude range', () => {
    // Canvas y grows downward, so we flip — the LARGEST drawn y becomes
    // the smallest output value, the SMALLEST drawn y becomes the largest.
    const points = [
      { x: 0, y: 100 }, // bottom of canvas → output min
      { x: 50, y: 50 },
      { x: 100, y: 0 }, // top of canvas → output max
    ];
    const out = sketchpadToSeries(points, 11, { min: -1, max: 1 });
    const lo = Math.min(...out);
    const hi = Math.max(...out);
    assert.ok(Math.abs(lo - -1) < 1e-9, `min ${lo} != -1`);
    assert.ok(Math.abs(hi - 1) < 1e-9, `max ${hi} != 1`);
  });

  it('handles retraced strokes by sorting on x', () => {
    const points = [
      { x: 0, y: 0 },
      { x: 40, y: 40 },
      { x: 20, y: 20 }, // out-of-order — must be re-sorted
      { x: 60, y: 60 },
    ];
    const out = sketchpadToSeries(points, 10, RANGE);
    assert.equal(out.length, 10);
    assert.ok(Number.isFinite(out[0]));
    assert.ok(Number.isFinite(out[out.length - 1]));
  });

  it('produces a constant signal at the midpoint when input has no y-range', () => {
    const points = [
      { x: 0, y: 5 },
      { x: 50, y: 5 },
      { x: 100, y: 5 },
    ];
    const out = sketchpadToSeries(points, 10, { min: 0, max: 2 });
    for (const v of out) assert.equal(v, 1); // (0+2)/2
  });

  it('endpoints land at the supplied amplitude min/max for a monotone stroke', () => {
    // Draw a strictly decreasing canvas-y (= rising in flipped output).
    const points = [];
    for (let i = 0; i <= 10; i += 1) points.push({ x: i, y: 10 - i });
    const out = sketchpadToSeries(points, 11, { min: 0, max: 1 });
    assert.ok(Math.abs(out[0] - 0) < 1e-9);
    assert.ok(Math.abs(out[out.length - 1] - 1) < 1e-9);
    // Monotone increase.
    for (let i = 1; i < out.length; i += 1) assert.ok(out[i] >= out[i - 1] - 1e-12);
  });
});
