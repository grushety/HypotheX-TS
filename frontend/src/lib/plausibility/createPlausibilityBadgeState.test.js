import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  STATUS,
  combineSignals,
  createPlausibilityBadgeState,
  evaluateManifoldSignal,
  evaluateRangeSignal,
  evaluateResidualSignal,
} from './createPlausibilityBadgeState.js';

describe('evaluateRangeSignal', () => {
  it('returns amber when range bounds are missing', () => {
    assert.equal(evaluateRangeSignal(null).status, STATUS.AMBER);
    assert.equal(evaluateRangeSignal({}).status, STATUS.AMBER);
    assert.equal(evaluateRangeSignal({ min: 0 }).status, STATUS.AMBER);
  });

  it('returns amber when bounds present but observed values missing', () => {
    const sig = evaluateRangeSignal({ min: 0, max: 100 });
    assert.equal(sig.status, STATUS.AMBER);
    assert.match(sig.text, /\[0, 100\]/);
  });

  it('returns green when observed values are within bounds', () => {
    const sig = evaluateRangeSignal({
      min: 0,
      max: 100,
      observedMin: 5,
      observedMax: 95,
    });
    assert.equal(sig.status, STATUS.GREEN);
    assert.match(sig.text, /within \[0, 100\]/);
  });

  it('returns red when observation exceeds max and reports the overshoot', () => {
    const sig = evaluateRangeSignal({
      min: 0,
      max: 100,
      observedMin: 5,
      observedMax: 105,
    });
    assert.equal(sig.status, STATUS.RED);
    assert.match(sig.text, /exceeds max by 5/);
  });

  it('returns red when observation falls below min', () => {
    const sig = evaluateRangeSignal({
      min: 0,
      max: 100,
      observedMin: -2,
      observedMax: 50,
    });
    assert.equal(sig.status, STATUS.RED);
    assert.match(sig.text, /below min by 2/);
  });

  it('handles non-finite bounds defensively', () => {
    assert.equal(
      evaluateRangeSignal({ min: NaN, max: 100, observedMin: 0, observedMax: 1 }).status,
      STATUS.AMBER,
    );
  });
});

describe('evaluateResidualSignal', () => {
  it('returns amber when residual is missing', () => {
    assert.equal(evaluateResidualSignal(null).status, STATUS.AMBER);
    assert.equal(evaluateResidualSignal({}).status, STATUS.AMBER);
  });

  it('returns green when residual is within tolerance', () => {
    const sig = evaluateResidualSignal({
      residual: 0.01,
      tolerance: 0.1,
      law: 'water_balance',
    });
    assert.equal(sig.status, STATUS.GREEN);
    assert.match(sig.text, /Residual:/);
  });

  it('returns red for hard-law residual over tolerance', () => {
    const sig = evaluateResidualSignal({
      residual: 0.5,
      tolerance: 0.1,
      law: 'phase_closure',
    });
    assert.equal(sig.status, STATUS.RED);
  });

  it('returns amber for soft-law residual over tolerance', () => {
    const sig = evaluateResidualSignal({
      residual: 0.5,
      tolerance: 0.1,
      law: 'water_balance',
    });
    assert.equal(sig.status, STATUS.AMBER);
  });

  it('falls back to default tolerance when not supplied', () => {
    const sig = evaluateResidualSignal({
      residual: 1e-7,
      law: 'water_balance',
    });
    assert.equal(sig.status, STATUS.GREEN);
  });
});

describe('evaluateManifoldSignal', () => {
  it('returns disabled when feature flag is off', () => {
    const sig = evaluateManifoldSignal({ sigma: 4.2 }, false);
    assert.equal(sig.status, STATUS.DISABLED);
    assert.equal(sig.text, 'Manifold: disabled');
  });

  it('returns green for ≤1σ when enabled', () => {
    const sig = evaluateManifoldSignal({ sigma: 0.3 }, true);
    assert.equal(sig.status, STATUS.GREEN);
    assert.match(sig.text, /0\.3σ/);
  });

  it('returns amber between 1σ and 3σ', () => {
    const sig = evaluateManifoldSignal({ sigma: 2 }, true);
    assert.equal(sig.status, STATUS.AMBER);
  });

  it('returns red beyond 3σ', () => {
    const sig = evaluateManifoldSignal({ sigma: 4.2 }, true);
    assert.equal(sig.status, STATUS.RED);
    assert.match(sig.text, /4\.2σ/);
  });

  it('returns amber when enabled but data missing', () => {
    assert.equal(evaluateManifoldSignal(null, true).status, STATUS.AMBER);
    assert.equal(evaluateManifoldSignal({}, true).status, STATUS.AMBER);
  });
});

describe('combineSignals', () => {
  const g = { status: STATUS.GREEN };
  const a = { status: STATUS.AMBER };
  const r = { status: STATUS.RED };
  const d = { status: STATUS.DISABLED };

  it('returns green when all contributing signals are green', () => {
    assert.equal(combineSignals([g, g, g]), STATUS.GREEN);
    assert.equal(combineSignals([g, g, d]), STATUS.GREEN);
  });

  it('returns amber when any signal is amber and none is red', () => {
    assert.equal(combineSignals([g, a, g]), STATUS.AMBER);
    assert.equal(combineSignals([g, a, d]), STATUS.AMBER);
  });

  it('returns red when any signal is red regardless of others', () => {
    assert.equal(combineSignals([g, a, r]), STATUS.RED);
    assert.equal(combineSignals([r, d, d]), STATUS.RED);
  });

  it('treats all-disabled as green (nothing to flag)', () => {
    assert.equal(combineSignals([d, d, d]), STATUS.GREEN);
  });

  it('ignores null entries', () => {
    assert.equal(combineSignals([null, g, null]), STATUS.GREEN);
  });
});

describe('createPlausibilityBadgeState — combinations', () => {
  function build(overrides = {}) {
    return createPlausibilityBadgeState({
      range: { min: 0, max: 100, observedMin: 5, observedMax: 95 },
      residual: { residual: 0.01, tolerance: 0.1, law: 'water_balance' },
      manifoldEnabled: false,
      ...overrides,
    });
  }

  it('green when all signals green and manifold disabled', () => {
    const state = build();
    assert.equal(state.status, STATUS.GREEN);
    assert.equal(state.glyph, '✓');
  });

  it('red when range exceeds max', () => {
    const state = build({
      range: { min: 0, max: 100, observedMin: 0, observedMax: 105 },
    });
    assert.equal(state.status, STATUS.RED);
    assert.equal(state.glyph, '✗');
  });

  it('amber when residual is over tolerance for a soft law', () => {
    const state = build({
      residual: { residual: 0.5, tolerance: 0.1, law: 'water_balance' },
    });
    assert.equal(state.status, STATUS.AMBER);
    assert.equal(state.glyph, '!');
  });

  it('red wins over amber and green', () => {
    const state = build({
      range: { min: 0, max: 100, observedMin: 0, observedMax: 200 },
      residual: { residual: 0.5, tolerance: 0.1, law: 'water_balance' },
    });
    assert.equal(state.status, STATUS.RED);
  });

  it('manifold red flips combined badge to red when feature flag on', () => {
    const state = build({
      manifold: { sigma: 4.2 },
      manifoldEnabled: true,
    });
    assert.equal(state.status, STATUS.RED);
    assert.match(state.signals.manifold.text, /4\.2σ/);
  });

  it('manifold disabled hides the value but keeps badge green', () => {
    const state = build({
      manifold: { sigma: 4.2 },
      manifoldEnabled: false,
    });
    assert.equal(state.status, STATUS.GREEN);
    assert.equal(state.signals.manifold.text, 'Manifold: disabled');
  });
});

describe('createPlausibilityBadgeState — accessibility & tooltip', () => {
  it('hoverText includes one line per signal', () => {
    const state = createPlausibilityBadgeState({
      range: { min: 0, max: 100, observedMin: 0, observedMax: 50 },
      residual: { residual: 0.01, tolerance: 0.1, law: 'water_balance' },
      manifold: { sigma: 0.3 },
      manifoldEnabled: true,
    });
    const lines = state.hoverText.split('\n');
    assert.equal(lines.length, 3);
    assert.match(lines[0], /Range:/);
    assert.match(lines[1], /Residual:/);
    assert.match(lines[2], /Manifold:/);
  });

  it('ariaLabel describes status and per-signal breakdown', () => {
    const state = createPlausibilityBadgeState({
      range: { min: 0, max: 100, observedMin: 0, observedMax: 200 },
      residual: { residual: 0.01, tolerance: 0.1, law: 'water_balance' },
    });
    assert.match(state.ariaLabel, /Plausibility red/);
    assert.match(state.ariaLabel, /Range:/);
    assert.match(state.ariaLabel, /Residual:/);
    assert.match(state.ariaLabel, /Manifold:/);
  });

  it('feature-flag off: manifold signal text is "disabled"', () => {
    const state = createPlausibilityBadgeState({
      range: null,
      residual: null,
      manifold: { sigma: 99 },
      manifoldEnabled: false,
    });
    assert.equal(state.signals.manifold.text, 'Manifold: disabled');
    assert.equal(state.signals.manifold.status, STATUS.DISABLED);
  });
});

describe('createPlausibilityBadgeState — defaults', () => {
  it('handles entirely missing input as amber (unknown plausibility)', () => {
    const state = createPlausibilityBadgeState({});
    assert.equal(state.status, STATUS.AMBER);
    assert.equal(state.signals.manifold.status, STATUS.DISABLED);
  });
});
