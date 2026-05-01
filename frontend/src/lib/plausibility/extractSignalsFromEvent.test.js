import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { extractSignalsFromEvent } from './extractSignalsFromEvent.js';

describe('extractSignalsFromEvent', () => {
  it('returns all-null for empty / non-object inputs', () => {
    assert.deepEqual(extractSignalsFromEvent(null), { range: null, residual: null, manifold: null });
    assert.deepEqual(extractSignalsFromEvent(undefined), { range: null, residual: null, manifold: null });
    assert.deepEqual(extractSignalsFromEvent('not-an-event'), { range: null, residual: null, manifold: null });
  });

  it('passes through residual payload from constraintResidual', () => {
    const sig = extractSignalsFromEvent({
      constraintResidual: { residual: 0.05, tolerance: 0.1, law: 'water_balance' },
    });
    assert.deepEqual(sig.residual, { residual: 0.05, tolerance: 0.1, law: 'water_balance' });
  });

  it('also accepts snake_case constraint_residual', () => {
    const sig = extractSignalsFromEvent({
      constraint_residual: { residual: 0.05, tolerance: 0.1, law: 'water_balance' },
    });
    assert.equal(sig.residual.residual, 0.05);
  });

  it('returns null residual when the field is an array (legacy warnings list)', () => {
    const sig = extractSignalsFromEvent({
      constraintResidual: [{ code: 'WARN', message: 'soft' }],
    });
    assert.equal(sig.residual, null);
  });

  it('forwards plausibilityRange and plausibilityManifold when present', () => {
    const sig = extractSignalsFromEvent({
      plausibilityRange: { min: 0, max: 1, observedMin: 0, observedMax: 1 },
      plausibilityManifold: { sigma: 0.5 },
    });
    assert.equal(sig.range.min, 0);
    assert.equal(sig.manifold.sigma, 0.5);
  });

  it('rejects non-finite residual values', () => {
    assert.equal(
      extractSignalsFromEvent({ constraintResidual: { residual: NaN, law: 'phase_closure' } }).residual,
      null,
    );
  });
});
