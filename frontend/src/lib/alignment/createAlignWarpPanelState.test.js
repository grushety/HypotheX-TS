import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  ALIGN_METHODS,
  COMPAT_STATUS,
  DEFAULT_METHOD,
  DEFAULT_WARPING_BAND,
  MAX_WARPING_BAND,
  MIN_WARPING_BAND,
  buildAlignWarpPayload,
  buildPreviewModel,
  clampWarpingBand,
  classifyAlignCompat,
  createAlignWarpPanelState,
} from './createAlignWarpPanelState.js';

describe('ALIGN_METHODS', () => {
  it('exports the three OP-031 methods in canonical order', () => {
    assert.deepEqual([...ALIGN_METHODS], ['dtw', 'soft_dtw', 'shapedba']);
  });
});

describe('clampWarpingBand', () => {
  it('returns clamped=true and the default for non-finite input', () => {
    assert.deepEqual(clampWarpingBand(NaN), {
      value: DEFAULT_WARPING_BAND,
      clamped: true,
    });
    assert.deepEqual(clampWarpingBand('not-a-number'), {
      value: DEFAULT_WARPING_BAND,
      clamped: true,
    });
  });

  it('clamps below 0.01 and above 0.30', () => {
    assert.deepEqual(clampWarpingBand(0), {
      value: MIN_WARPING_BAND,
      clamped: true,
    });
    assert.deepEqual(clampWarpingBand(0.5), {
      value: MAX_WARPING_BAND,
      clamped: true,
    });
  });

  it('passes through valid values without clamping', () => {
    assert.deepEqual(clampWarpingBand(0.15), { value: 0.15, clamped: false });
  });
});

describe('classifyAlignCompat', () => {
  it('returns COMPATIBLE for cycle/spike/transient', () => {
    const r = classifyAlignCompat([
      { id: 'a', label: 'cycle' },
      { id: 'b', label: 'spike' },
      { id: 'c', label: 'transient' },
    ]);
    assert.equal(r.status, COMPAT_STATUS.COMPATIBLE);
    assert.deepEqual([...r.incompatibleSegmentIds], []);
    assert.deepEqual([...r.approxSegmentIds], []);
    assert.equal(r.message, '');
  });

  it('returns APPROX with the offending segment ids for plateau/trend', () => {
    const r = classifyAlignCompat([
      { id: 'a', label: 'cycle' },
      { id: 'b', label: 'plateau' },
      { id: 'c', label: 'trend' },
    ]);
    assert.equal(r.status, COMPAT_STATUS.APPROX);
    assert.deepEqual([...r.approxSegmentIds], ['b', 'c']);
    assert.match(r.message, /Approximate alignment for 2 plateau\/trend segments/);
  });

  it('returns INCOMPATIBLE when any segment is noise', () => {
    const r = classifyAlignCompat([
      { id: 'a', label: 'cycle' },
      { id: 'b', label: 'noise' },
    ]);
    assert.equal(r.status, COMPAT_STATUS.INCOMPATIBLE);
    assert.deepEqual([...r.incompatibleSegmentIds], ['b']);
    assert.match(r.message, /Cannot warp noise/);
  });

  it('treats unknown labels as approx and surfaces them', () => {
    const r = classifyAlignCompat([
      { id: 'a', label: 'cycle' },
      { id: 'b', label: 'fictional_shape' },
    ]);
    assert.equal(r.status, COMPAT_STATUS.APPROX);
    assert.ok(r.unknownLabels.includes('fictional_shape'));
    assert.match(r.message, /Unrecognised shape label/);
  });

  it('returns COMPATIBLE for an empty input', () => {
    const r = classifyAlignCompat([]);
    assert.equal(r.status, COMPAT_STATUS.COMPATIBLE);
    assert.equal(r.message, '');
  });
});

describe('buildAlignWarpPayload', () => {
  it('throws when reference id is missing', () => {
    assert.throws(
      () => buildAlignWarpPayload({ segmentIds: ['a'], method: 'dtw', warpingBand: 0.1 }),
      /referenceSegmentId/,
    );
  });

  it('throws on empty segmentIds', () => {
    assert.throws(
      () => buildAlignWarpPayload({ referenceSegmentId: 'r', segmentIds: [], method: 'dtw' }),
      /segmentIds/,
    );
  });

  it('throws on unknown method', () => {
    assert.throws(
      () => buildAlignWarpPayload({
        referenceSegmentId: 'r',
        segmentIds: ['a'],
        method: 'bogus',
      }),
      /unknown method/,
    );
  });

  it('produces the OP-031 op-invoked shape', () => {
    const payload = buildAlignWarpPayload({
      referenceSegmentId: 'ref-1',
      segmentIds: ['a', 'b'],
      method: 'soft_dtw',
      warpingBand: 0.2,
    });
    assert.equal(payload.tier, 3);
    assert.equal(payload.op_name, 'align_warp');
    assert.equal(payload.params.reference_seg_id, 'ref-1');
    assert.deepEqual(payload.params.segment_ids, ['a', 'b']);
    assert.equal(payload.params.method, 'soft_dtw');
    assert.equal(payload.params.warping_band, 0.2);
  });

  it('clamps an out-of-range warping band', () => {
    const payload = buildAlignWarpPayload({
      referenceSegmentId: 'r',
      segmentIds: ['a'],
      method: 'dtw',
      warpingBand: 0.9,
    });
    assert.equal(payload.params.warping_band, MAX_WARPING_BAND);
  });

  it('copies the segmentIds array (callers may mutate the original)', () => {
    const ids = ['a', 'b'];
    const payload = buildAlignWarpPayload({
      referenceSegmentId: 'r',
      segmentIds: ids,
      method: 'dtw',
      warpingBand: 0.1,
    });
    ids.push('c');
    assert.deepEqual(payload.params.segment_ids, ['a', 'b']);
  });
});

describe('createAlignWarpPanelState', () => {
  const segments = [
    { id: 'r', label: 'cycle' },
    { id: 's1', label: 'cycle' },
    { id: 's2', label: 'plateau' },
    { id: 'noise-1', label: 'noise' },
  ];

  it('selects the reference and surfaces it in the view model', () => {
    const state = createAlignWarpPanelState({
      segments,
      referenceSegmentId: 'r',
      selectedSegmentIds: ['s1'],
    });
    assert.equal(state.referenceSegmentId, 'r');
    assert.equal(state.referenceSegment.label, 'cycle');
    assert.equal(state.segmentsToAlign.length, 1);
    assert.equal(state.segmentsToAlign[0].id, 's1');
  });

  it('drops the reference id from segmentsToAlign even if multi-selected', () => {
    const state = createAlignWarpPanelState({
      segments,
      referenceSegmentId: 'r',
      selectedSegmentIds: ['r', 's1'],
    });
    assert.deepEqual(
      state.segmentsToAlign.map((s) => s.id),
      ['s1'],
    );
  });

  it('canApply=false when no reference is picked', () => {
    const state = createAlignWarpPanelState({
      segments,
      selectedSegmentIds: ['s1'],
    });
    assert.equal(state.canApply, false);
    assert.match(state.applyDisabledReason, /reference segment/);
  });

  it('canApply=false when no segments-to-align are selected', () => {
    const state = createAlignWarpPanelState({
      segments,
      referenceSegmentId: 'r',
      selectedSegmentIds: [],
    });
    assert.equal(state.canApply, false);
    assert.match(state.applyDisabledReason, /at least one segment/);
  });

  it('canApply=false with the noise tooltip when any segment is noise', () => {
    const state = createAlignWarpPanelState({
      segments,
      referenceSegmentId: 'r',
      selectedSegmentIds: ['s1', 'noise-1'],
    });
    assert.equal(state.canApply, false);
    assert.match(state.applyDisabledReason, /noise/);
    assert.equal(state.compat.status, COMPAT_STATUS.INCOMPATIBLE);
  });

  it('canApply=true with approx warning when plateau/trend are picked', () => {
    const state = createAlignWarpPanelState({
      segments,
      referenceSegmentId: 'r',
      selectedSegmentIds: ['s2'],
    });
    assert.equal(state.canApply, true);
    assert.equal(state.compat.status, COMPAT_STATUS.APPROX);
    assert.match(state.compat.message, /Approximate alignment/);
  });

  it('falls back to the default method on an unknown key', () => {
    const state = createAlignWarpPanelState({
      segments,
      referenceSegmentId: 'r',
      selectedSegmentIds: ['s1'],
      method: 'no-such',
    });
    assert.equal(state.methodKey, DEFAULT_METHOD);
  });

  it('returns warping band as a percentage for the slider readout', () => {
    const state = createAlignWarpPanelState({
      segments,
      referenceSegmentId: 'r',
      selectedSegmentIds: ['s1'],
      warpingBand: 0.15,
    });
    assert.equal(state.warpingBand, 0.15);
    assert.equal(state.warpingBandPercent, 15);
  });

  it('passes through templateOptions (extension point for the library picker)', () => {
    const opts = [{ id: 't1', label: 'gold-standard cycle', values: [0.1, 0.2] }];
    const state = createAlignWarpPanelState({
      segments,
      referenceSegmentId: 'r',
      selectedSegmentIds: ['s1'],
      templateOptions: opts,
    });
    assert.deepEqual([...state.templateOptions], opts);
  });
});

describe('buildPreviewModel', () => {
  it('emits a diagonal in the unit square for every method', () => {
    for (const m of ALIGN_METHODS) {
      const p = buildPreviewModel({ method: m, warpingBand: 0.1 });
      assert.equal(p.method, m);
      assert.equal(p.diagonal[0].x, 0);
      assert.equal(p.diagonal[0].y, 0);
      assert.equal(p.diagonal[p.diagonal.length - 1].x, 1);
      assert.equal(p.diagonal[p.diagonal.length - 1].y, 1);
    }
  });

  it('only DTW carries a band half-width', () => {
    assert.equal(buildPreviewModel({ method: 'dtw', warpingBand: 0.2 }).bandHalfWidth, 0.2);
    assert.equal(buildPreviewModel({ method: 'soft_dtw', warpingBand: 0.2 }).bandHalfWidth, 0);
    assert.equal(buildPreviewModel({ method: 'shapedba', warpingBand: 0.2 }).bandHalfWidth, 0);
  });

  it('falls back to default method on unknown', () => {
    assert.equal(
      buildPreviewModel({ method: 'no-such', warpingBand: 0.1 }).method,
      DEFAULT_METHOD,
    );
  });
});
