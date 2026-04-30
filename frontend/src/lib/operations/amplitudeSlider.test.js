import test from 'node:test';
import assert from 'node:assert/strict';

import {
  MIN_ALPHA,
  MAX_ALPHA,
  IDENTITY,
  SNAP_POINTS,
  positionToAlpha,
  alphaToPosition,
  snapToCommon,
  classify,
  formatMultiplier,
  stepAlpha,
  isIdentity,
} from './amplitudeSlider.js';

// ─── log-scale mapping ─────────────────────────────────────────────────────

test('positionToAlpha: t=0 → MIN_ALPHA', () => {
  assert.ok(Math.abs(positionToAlpha(0) - MIN_ALPHA) < 1e-9);
});

test('positionToAlpha: t=1 → MAX_ALPHA', () => {
  assert.ok(Math.abs(positionToAlpha(1) - MAX_ALPHA) < 1e-9);
});

test('positionToAlpha: t=0.5 → IDENTITY', () => {
  assert.ok(Math.abs(positionToAlpha(0.5) - IDENTITY) < 1e-9);
});

test('alphaToPosition: identity round-trip for many points', () => {
  for (const a of [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 100.0]) {
    const t = alphaToPosition(a);
    const back = positionToAlpha(t);
    assert.ok(Math.abs(back - a) / a < 1e-9, `round-trip failed for ${a}`);
  }
});

test('positionToAlpha: clamps below 0 to MIN_ALPHA', () => {
  assert.ok(Math.abs(positionToAlpha(-0.5) - MIN_ALPHA) < 1e-9);
});

test('positionToAlpha: clamps above 1 to MAX_ALPHA', () => {
  assert.ok(Math.abs(positionToAlpha(1.5) - MAX_ALPHA) < 1e-9);
});

// ─── classification (the disambiguation contract) ─────────────────────────

test('classify: 0.5 → dampen', () => {
  assert.equal(classify(0.5), 'dampen');
});

test('classify: 2.0 → amplify', () => {
  assert.equal(classify(2.0), 'amplify');
});

test('classify: 1.0 → identity (no API call expected)', () => {
  assert.equal(classify(1.0), 'identity');
});

test('classify: tiny floating-point noise around 1 still identity', () => {
  assert.equal(classify(1.0 + 1e-12), 'identity');
  assert.equal(classify(1.0 - 1e-12), 'identity');
});

test('isIdentity: 1.0 → true; 0.5 → false; 2.0 → false', () => {
  assert.equal(isIdentity(1.0), true);
  assert.equal(isIdentity(0.5), false);
  assert.equal(isIdentity(2.0), false);
});

// ─── snap behaviour ───────────────────────────────────────────────────────

test('snapToCommon: within 5 % of 1.0 snaps to 1.0', () => {
  assert.equal(snapToCommon(1.04), 1.0);
  assert.equal(snapToCommon(0.96), 1.0);
});

test('snapToCommon: within 5 % of 2.0 snaps to 2.0', () => {
  assert.equal(snapToCommon(2.05), 2.0);
  assert.equal(snapToCommon(1.95), 2.0);
});

test('snapToCommon: within 5 % of 0.5 snaps to 0.5', () => {
  assert.equal(snapToCommon(0.51), 0.5);
  assert.equal(snapToCommon(0.49), 0.5);
});

test('snapToCommon: within 5 % of 10.0 snaps to 10.0', () => {
  assert.equal(snapToCommon(10.4), 10.0);
  assert.equal(snapToCommon(9.6), 10.0);
});

test('snapToCommon: outside ±5 % of any common value returns alpha unchanged', () => {
  assert.equal(snapToCommon(1.5), 1.5);
  assert.equal(snapToCommon(3.0), 3.0);
  assert.equal(snapToCommon(0.7), 0.7);
});

test('snapToCommon: covers all SNAP_POINTS', () => {
  for (const p of SNAP_POINTS) {
    assert.equal(snapToCommon(p), p, `snap point ${p} should map to itself`);
  }
});

// ─── keyboard step ────────────────────────────────────────────────────────

test('stepAlpha: +1 from identity moves alpha above 1 (amplify side)', () => {
  const next = stepAlpha(1.0, +1);
  assert.ok(next > 1.0, `expected > 1, got ${next}`);
});

test('stepAlpha: −1 from identity moves alpha below 1 (dampen side)', () => {
  const next = stepAlpha(1.0, -1);
  assert.ok(next < 1.0, `expected < 1, got ${next}`);
});

test('stepAlpha: clamps at MAX_ALPHA when stepping above', () => {
  const next = stepAlpha(MAX_ALPHA, +1);
  assert.ok(Math.abs(next - MAX_ALPHA) < 1e-9);
});

test('stepAlpha: clamps at MIN_ALPHA when stepping below', () => {
  const next = stepAlpha(MIN_ALPHA, -1);
  assert.ok(Math.abs(next - MIN_ALPHA) < 1e-9);
});

test('stepAlpha: 100 steps from identity reach close to MAX_ALPHA', () => {
  let a = 1.0;
  for (let i = 0; i < 50; i++) a = stepAlpha(a, +1);
  // 50 × 1 % log-step = 50 % up the log range, so a >> 1
  assert.ok(a > 5, `50 +1 % log-steps from 1 should be > 5, got ${a}`);
});

// ─── formatting ───────────────────────────────────────────────────────────

test('formatMultiplier: 2.0 → "×2.00"', () => {
  assert.equal(formatMultiplier(2.0), '×2.00');
});

test('formatMultiplier: 0.5 → "×0.50"', () => {
  assert.equal(formatMultiplier(0.5), '×0.50');
});

test('formatMultiplier: 10.0 → "×10.0"', () => {
  assert.equal(formatMultiplier(10.0), '×10.0');
});

test('formatMultiplier: 1.0 → "×1.00"', () => {
  assert.equal(formatMultiplier(1.0), '×1.00');
});
