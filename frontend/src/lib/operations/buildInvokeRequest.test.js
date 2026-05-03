import { test } from 'node:test';
import assert from 'node:assert/strict';

import { buildInvokeRequest, UnknownOpError } from './buildInvokeRequest.js';

const SAMPLE = {
  sampleId: 'sample-1',
  values: [0.0, 1.0, 2.0, 3.0, 4.0],
  segments: [
    { id: 's0', start: 0, end: 4, label: 'trend' },
  ],
};

const SELECTED = SAMPLE.segments[0];

test('Tier-1 op with slider params builds a complete request body', () => {
  const plan = buildInvokeRequest({
    tier: 1,
    op_name: 'scale',
    params: { alpha: 1.5 },
    sample: SAMPLE,
    selectedSegment: SELECTED,
  });
  assert.equal(plan.kind, 'request');
  assert.equal(plan.body.tier, 1);
  assert.equal(plan.body.op_name, 'scale');
  assert.equal(plan.body.params.alpha, 1.5);
  assert.equal(plan.body.segment_id, 's0');
  assert.equal(plan.body.series_id, 'sample-1');
  assert.deepEqual(plan.body.sample_values, [0.0, 1.0, 2.0, 3.0, 4.0]);
  assert.deepEqual(plan.body.segments, [{ id: 's0', start: 0, end: 4, label: 'trend' }]);
});

test('Tier-2 shape op routes through the dispatcher', () => {
  const plan = buildInvokeRequest({
    tier: 2,
    op_name: 'trend_change_slope',
    params: { alpha: 0.5 },
    sample: SAMPLE,
    selectedSegment: SELECTED,
  });
  assert.equal(plan.kind, 'request');
  assert.equal(plan.body.op_name, 'trend_change_slope');
  assert.equal(plan.body.params.alpha, 0.5);
});

test('Tier-3 picker-free op (aggregate) gets default params and dispatches', () => {
  const plan = buildInvokeRequest({
    tier: 3,
    op_name: 'aggregate',
    sample: SAMPLE,
    selectedSegment: SELECTED,
  });
  assert.equal(plan.kind, 'request');
  assert.equal(plan.body.op_name, 'aggregate');
  assert.equal(plan.body.params.metric, 'peak');
});

test('suppress on a gap-heavy segment falls through to picker-pending', () => {
  const plan = buildInvokeRequest({
    tier: 1,
    op_name: 'suppress',
    sample: SAMPLE,
    selectedSegment: SELECTED,
    gapInfo: { exceedsThreshold: true, isFilled: false, missingnessPct: 60 },
  });
  assert.equal(plan.kind, 'picker-pending');
  assert.match(plan.message, /GapFillPicker pending/);
});

test('suppress on a non-gap segment dispatches normally', () => {
  const plan = buildInvokeRequest({
    tier: 1,
    op_name: 'suppress',
    sample: SAMPLE,
    selectedSegment: SELECTED,
    gapInfo: { exceedsThreshold: false, isFilled: false },
  });
  assert.equal(plan.kind, 'request');
  assert.equal(plan.body.op_name, 'suppress');
});

test('replace_from_library / decompose / align_warp are picker-pending', () => {
  for (const opName of ['replace_from_library', 'decompose', 'align_warp']) {
    const tier = opName === 'replace_from_library' ? 1 : 3;
    const plan = buildInvokeRequest({
      tier,
      op_name: opName,
      sample: SAMPLE,
      selectedSegment: SELECTED,
    });
    assert.equal(plan.kind, 'picker-pending', `${opName} should be picker-pending`);
    assert.match(plan.message, /picker pending/);
  }
});

test('unknown op throws UnknownOpError', () => {
  assert.throws(
    () =>
      buildInvokeRequest({
        tier: 2,
        op_name: 'warp_to_doom',
        sample: SAMPLE,
        selectedSegment: SELECTED,
      }),
    UnknownOpError,
  );
});

test('mute_zero default fill is "zero"', () => {
  const plan = buildInvokeRequest({
    tier: 1,
    op_name: 'mute_zero',
    sample: SAMPLE,
    selectedSegment: SELECTED,
  });
  assert.equal(plan.kind, 'request');
  assert.equal(plan.body.params.fill, 'zero');
});

test('bypassPickerCheck=true lets replace_from_library through to a real request (HTS-104)', () => {
  const plan = buildInvokeRequest({
    tier: 1,
    op_name: 'replace_from_library',
    params: {
      backend: 'NativeGuide',
      donor_id: 'native_guide:0',
      donor_values: [0.1, 0.2, 0.3, 0.4, 0.5],
      crossfade_width: 0.1,
    },
    sample: SAMPLE,
    selectedSegment: SELECTED,
    bypassPickerCheck: true,
  });
  assert.equal(plan.kind, 'request');
  assert.equal(plan.body.op_name, 'replace_from_library');
  assert.deepEqual(plan.body.params.donor_values, [0.1, 0.2, 0.3, 0.4, 0.5]);
});

test('amplify_amplitude (slider commit alias) dispatches as Tier-2', () => {
  const plan = buildInvokeRequest({
    tier: 2,
    op_name: 'amplify_amplitude',
    params: { alpha: 1.2 },
    sample: SAMPLE,
    selectedSegment: SELECTED,
  });
  assert.equal(plan.kind, 'request');
  assert.equal(plan.body.op_name, 'amplify_amplitude');
});
