import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_DENSE_OPS_THRESHOLD_PCT,
  DEFAULT_SUPPRESS_STRATEGY,
  DENSE_DATA_OPS,
  SUPPRESS_STRATEGIES,
  applyGapGatingToButton,
  buildSuppressPayload,
  clampThresholdPct,
  classifyGap,
  computeMissingnessRatio,
  gapDisabledTooltip,
  isMissingValue,
  isOpBlockedByGap,
} from './createGapGatingState.js';

describe('isMissingValue', () => {
  it('treats null/undefined/NaN as missing and finite numbers as present', () => {
    assert.equal(isMissingValue(null), true);
    assert.equal(isMissingValue(undefined), true);
    assert.equal(isMissingValue(NaN), true);
    assert.equal(isMissingValue(0), false);
    assert.equal(isMissingValue(-1), false);
    assert.equal(isMissingValue(0.5), false);
  });
});

describe('computeMissingnessRatio', () => {
  it('returns 0 on empty / non-array input', () => {
    assert.equal(computeMissingnessRatio([]), 0);
    assert.equal(computeMissingnessRatio(null), 0);
  });

  it('computes the fraction of missing entries', () => {
    assert.equal(
      computeMissingnessRatio([1, NaN, 2, null, 3, undefined, NaN, 4]),
      4 / 8,
    );
    assert.equal(computeMissingnessRatio([1, 2, 3]), 0);
    assert.equal(computeMissingnessRatio([NaN, NaN]), 1);
  });
});

describe('clampThresholdPct', () => {
  it('clamps below 0 and above 100', () => {
    assert.equal(clampThresholdPct(-10), 0);
    assert.equal(clampThresholdPct(150), 100);
  });

  it('falls back to the default for non-finite input', () => {
    assert.equal(clampThresholdPct(NaN), DEFAULT_DENSE_OPS_THRESHOLD_PCT);
    assert.equal(clampThresholdPct('not-a-number'), DEFAULT_DENSE_OPS_THRESHOLD_PCT);
  });

  it('passes through valid values unchanged', () => {
    assert.equal(clampThresholdPct(45), 45);
  });
});

describe('classifyGap', () => {
  it('reports zero missingness for a clean segment', () => {
    const info = classifyGap({ segment: { id: 's1' }, segmentValues: [1, 2, 3] });
    assert.equal(info.missingnessPct, 0);
    assert.equal(info.exceedsThreshold, false);
    assert.equal(info.isCloudGap, false);
    assert.equal(info.isFilled, false);
  });

  it('rounds the missingness ratio to a percent', () => {
    const info = classifyGap({
      segment: { id: 's1' },
      segmentValues: [1, NaN, NaN, NaN, 2],
    });
    assert.equal(info.missingnessRatio, 3 / 5);
    assert.equal(info.missingnessPct, 60);
  });

  it('prefers explicit segment.missingness_ratio over computed values', () => {
    const info = classifyGap({
      segment: { id: 's1', missingness_ratio: 0.5 },
      segmentValues: [1, 2, 3], // would yield 0; the explicit 0.5 wins
    });
    assert.equal(info.missingnessPct, 50);
  });

  it('flags exceedsThreshold when above the configured threshold', () => {
    const info = classifyGap({
      segment: { id: 's1', missingnessRatio: 0.4 },
      thresholdPct: 30,
    });
    assert.equal(info.exceedsThreshold, true);
  });

  it('does not flag exceedsThreshold when at or below the threshold', () => {
    const at = classifyGap({
      segment: { id: 's1', missingnessRatio: 0.30 },
      thresholdPct: 30,
    });
    assert.equal(at.exceedsThreshold, false);
    const under = classifyGap({
      segment: { id: 's1', missingnessRatio: 0.10 },
      thresholdPct: 30,
    });
    assert.equal(under.exceedsThreshold, false);
  });

  it('compares against raw ratio not rounded percent (30.4% IS over 30)', () => {
    // 30.4% rounds to 30, but the strict AC threshold is "ratio > 30%", so
    // the segment should still be gated.
    const r = classifyGap({
      segment: { id: 's1', missingnessRatio: 0.304 },
      thresholdPct: 30,
    });
    assert.equal(r.missingnessPct, 30); // rounded display unchanged
    assert.equal(r.exceedsThreshold, true);
  });

  it('detects the cloud_gap semantic label (camelCase or snake_case)', () => {
    const camel = classifyGap({ segment: { semanticLabel: 'cloud_gap' } });
    const snake = classifyGap({ segment: { semantic_label: 'cloud_gap' } });
    assert.equal(camel.isCloudGap, true);
    assert.equal(snake.isCloudGap, true);
  });

  it('detects metadata.filled and surfaces the strategy', () => {
    const info = classifyGap({
      segment: { metadata: { filled: true, fill_strategy: 'spline' } },
    });
    assert.equal(info.isFilled, true);
    assert.equal(info.fillStrategy, 'spline');
  });
});

describe('isOpBlockedByGap', () => {
  const heavyGap = { exceedsThreshold: true, isFilled: false };
  const lightGap = { exceedsThreshold: false, isFilled: false };
  const filledGap = { exceedsThreshold: true, isFilled: true };

  it('blocks dense-data ops when the gap exceeds the threshold', () => {
    for (const opName of DENSE_DATA_OPS) {
      assert.equal(isOpBlockedByGap(opName, heavyGap), true, opName);
    }
  });

  it('does not block dense ops below the threshold', () => {
    assert.equal(isOpBlockedByGap('cycle_change_frequency', lightGap), false);
  });

  it('unblocks dense ops once the segment is filled', () => {
    assert.equal(isOpBlockedByGap('cycle_change_frequency', filledGap), false);
  });

  it('does not block non-dense ops even on heavy gaps', () => {
    assert.equal(isOpBlockedByGap('offset', heavyGap), false);
    assert.equal(isOpBlockedByGap('mute_zero', heavyGap), false);
    assert.equal(isOpBlockedByGap('suppress', heavyGap), false);
  });

  it('returns false for null gapInfo', () => {
    assert.equal(isOpBlockedByGap('cycle_change_frequency', null), false);
  });
});

describe('gapDisabledTooltip', () => {
  it('renders the AC-spec tooltip with the percentage', () => {
    const info = { exceedsThreshold: true, isFilled: false, missingnessPct: 42 };
    const text = gapDisabledTooltip('cycle_change_frequency', info);
    assert.match(text, /42% missing/);
    assert.match(text, /Fill via Tier-1 suppress first/);
  });

  it('returns null when the op is not blocked', () => {
    assert.equal(
      gapDisabledTooltip('cycle_change_frequency', {
        exceedsThreshold: false,
        isFilled: false,
      }),
      null,
    );
    assert.equal(gapDisabledTooltip('offset', null), null);
  });
});

describe('applyGapGatingToButton', () => {
  const heavyGap = { exceedsThreshold: true, isFilled: false, missingnessPct: 50 };

  it('passes through unblocked buttons unchanged', () => {
    const btn = { op_name: 'offset', enabled: true };
    assert.equal(applyGapGatingToButton(btn, heavyGap), btn);
  });

  it('disables a blocked button and attaches the tooltip', () => {
    const btn = { op_name: 'cycle_change_frequency', enabled: true };
    const out = applyGapGatingToButton(btn, heavyGap);
    assert.equal(out.enabled, false);
    assert.match(out.disabledTooltip, /50% missing/);
    // Returns a copy, not the same object.
    assert.notEqual(out, btn);
  });

  it('returns the input button unchanged when gapInfo is null', () => {
    const btn = { op_name: 'cycle_change_frequency', enabled: true };
    assert.equal(applyGapGatingToButton(btn, null), btn);
  });
});

describe('buildSuppressPayload', () => {
  it('emits the OP-013 suppress payload shape', () => {
    const payload = buildSuppressPayload({
      segmentId: 'seg-1',
      strategy: 'linear',
    });
    assert.equal(payload.tier, 1);
    assert.equal(payload.op_name, 'suppress');
    assert.equal(payload.params.segment_id, 'seg-1');
    assert.equal(payload.params.strategy, 'linear');
  });

  it('defaults to linear strategy when omitted', () => {
    const payload = buildSuppressPayload({ segmentId: 'seg-1' });
    assert.equal(payload.params.strategy, DEFAULT_SUPPRESS_STRATEGY);
  });

  it('throws on missing segmentId', () => {
    assert.throws(() => buildSuppressPayload({}), /segmentId/);
  });

  it('throws on unknown strategy', () => {
    assert.throws(
      () => buildSuppressPayload({ segmentId: 's', strategy: 'bogus' }),
      /unknown strategy/,
    );
  });
});

describe('module exports', () => {
  it('exports the canonical 3-strategy list (matching UI-005)', () => {
    assert.deepEqual([...SUPPRESS_STRATEGIES], ['linear', 'spline', 'climatology']);
  });

  it('exports the canonical dense-ops set (cycle FFT ops + decompose)', () => {
    const expected = [
      'cycle_change_frequency',
      'cycle_shift_phase',
      'cycle_add_harmonics',
      'cycle_remove_harmonics',
      'decompose',
    ];
    for (const op of expected) assert.ok(DENSE_DATA_OPS.has(op), op);
  });
});
