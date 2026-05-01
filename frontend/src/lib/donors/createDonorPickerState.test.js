import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  BACKEND_OPTIONS,
  DEFAULT_BACKEND,
  DEFAULT_CROSSFADE_WIDTH,
  USER_DRAWN_BACKEND,
  buildAcceptPayload,
  clampCrossfadeWidth,
  createDonorPickerState,
  formatDistance,
} from './createDonorPickerState.js';

describe('BACKEND_OPTIONS', () => {
  it('exposes exactly six backends per the AC', () => {
    assert.equal(BACKEND_OPTIONS.length, 6);
    const keys = BACKEND_OPTIONS.map((o) => o.key);
    assert.deepEqual(keys, [
      'NativeGuide',
      'SETSDonor',
      'DiscordDonor',
      'TimeGAN',
      'ShapeDBA',
      'UserDrawn',
    ]);
  });

  it('flags TimeGAN and ShapeDBA as not yet supported', () => {
    const unsupported = BACKEND_OPTIONS.filter((o) => !o.supported).map((o) => o.key);
    assert.deepEqual(unsupported, ['TimeGAN', 'ShapeDBA']);
  });
});

describe('clampCrossfadeWidth', () => {
  it('returns clamped=true for non-finite input', () => {
    assert.deepEqual(clampCrossfadeWidth(NaN), {
      value: DEFAULT_CROSSFADE_WIDTH,
      clamped: true,
    });
    assert.deepEqual(clampCrossfadeWidth('not-a-number'), {
      value: DEFAULT_CROSSFADE_WIDTH,
      clamped: true,
    });
  });

  it('clamps below 0 and above 0.5', () => {
    assert.deepEqual(clampCrossfadeWidth(-0.2), { value: 0, clamped: true });
    assert.deepEqual(clampCrossfadeWidth(0.9), { value: 0.5, clamped: true });
  });

  it('passes through valid values', () => {
    assert.deepEqual(clampCrossfadeWidth(0.15), { value: 0.15, clamped: false });
  });
});

describe('buildAcceptPayload', () => {
  const candidate = {
    donor_id: 'native_guide:0',
    values: [0, 1, 2],
    distance: 1.2,
    backend: 'NativeGuide',
  };

  it('emits the OP-012 payload shape with tier=1 and op_name', () => {
    const payload = buildAcceptPayload({
      backend: 'NativeGuide',
      candidate,
      crossfadeWidth: 0.1,
    });
    assert.equal(payload.tier, 1);
    assert.equal(payload.op_name, 'replace_from_library');
    assert.equal(payload.params.backend, 'NativeGuide');
    assert.equal(payload.params.donor_id, 'native_guide:0');
    assert.equal(payload.params.crossfade_width, 0.1);
  });

  it('clamps an out-of-range crossfade_width', () => {
    const payload = buildAcceptPayload({
      backend: 'NativeGuide',
      candidate,
      crossfadeWidth: 5,
    });
    assert.equal(payload.params.crossfade_width, 0.5);
  });

  it('inlines donor_values for UserDrawn', () => {
    const sketch = { donor_id: 'user-drawn', values: [0.1, 0.2, 0.3] };
    const payload = buildAcceptPayload({
      backend: USER_DRAWN_BACKEND,
      candidate: sketch,
      crossfadeWidth: 0.1,
    });
    assert.deepEqual(payload.params.donor_values, [0.1, 0.2, 0.3]);
  });

  it('throws when backend or candidate is missing', () => {
    assert.throws(() => buildAcceptPayload({ backend: 'NativeGuide', candidate: null, crossfadeWidth: 0.1 }));
    assert.throws(() => buildAcceptPayload({ backend: null, candidate, crossfadeWidth: 0.1 }));
  });
});

describe('createDonorPickerState', () => {
  it('selects NativeGuide by default', () => {
    const state = createDonorPickerState();
    assert.equal(state.backendKey, DEFAULT_BACKEND);
    assert.equal(state.metricLabel, 'DTW distance');
    assert.equal(state.backendSupported, true);
    assert.equal(state.isUserDrawn, false);
  });

  it('falls back to NativeGuide when given an unknown backend key', () => {
    const state = createDonorPickerState({ selectedBackend: 'no-such' });
    assert.equal(state.backendKey, DEFAULT_BACKEND);
  });

  it('reports backendSupported=false for TimeGAN and ShapeDBA', () => {
    for (const k of ['TimeGAN', 'ShapeDBA']) {
      const s = createDonorPickerState({ selectedBackend: k });
      assert.equal(s.backendSupported, false, k);
    }
  });

  it('selects the first candidate when none is explicitly chosen', () => {
    const cands = [
      { donor_id: 'a', values: [1, 2], distance: 0.5 },
      { donor_id: 'b', values: [3, 4], distance: 1.0 },
    ];
    const s = createDonorPickerState({ candidates: cands });
    assert.equal(s.selectedCandidateId, 'a');
    assert.equal(s.selectedCandidate.donor_id, 'a');
  });

  it('honours an explicit selectedCandidateId', () => {
    const cands = [
      { donor_id: 'a', values: [1], distance: 1 },
      { donor_id: 'b', values: [2], distance: 2 },
    ];
    const s = createDonorPickerState({ candidates: cands, selectedCandidateId: 'b' });
    assert.equal(s.selectedCandidate.donor_id, 'b');
  });

  it('UserDrawn surfaces the sketchpad values as the only candidate when valid', () => {
    const s = createDonorPickerState({
      selectedBackend: USER_DRAWN_BACKEND,
      sketchpadValues: [0.1, 0.2, 0.3, 0.4],
    });
    assert.equal(s.candidates.length, 1);
    assert.equal(s.selectedCandidate.donor_id, 'user-drawn');
  });

  it('UserDrawn with no sketchpad data has no candidates', () => {
    const s = createDonorPickerState({
      selectedBackend: USER_DRAWN_BACKEND,
      sketchpadValues: null,
    });
    assert.deepEqual(s.candidates, []);
    assert.equal(s.selectedCandidate, null);
    assert.equal(s.canAccept, false);
  });

  it('canAccept is false while loading or with an error', () => {
    const cands = [{ donor_id: 'a', values: [1], distance: 1 }];
    assert.equal(
      createDonorPickerState({ candidates: cands, loading: true }).canAccept,
      false,
    );
    assert.equal(
      createDonorPickerState({ candidates: cands, error: 'boom' }).canAccept,
      false,
    );
    assert.equal(
      createDonorPickerState({ candidates: cands }).canAccept,
      true,
    );
  });

  it('canReject is false for UserDrawn (no backend k-th iteration)', () => {
    const s = createDonorPickerState({
      selectedBackend: USER_DRAWN_BACKEND,
      sketchpadValues: [0.1, 0.2, 0.3],
    });
    assert.equal(s.canReject, false);
  });

  it('exposes the full options array for the dropdown', () => {
    const s = createDonorPickerState();
    assert.equal(s.options.length, 6);
  });
});

describe('formatDistance', () => {
  it('renders em-dash for null/undefined/non-finite', () => {
    assert.equal(formatDistance(null), '—');
    assert.equal(formatDistance(undefined), '—');
    assert.equal(formatDistance(NaN), '—');
  });

  it('uses 0 decimals above 100, 2 between 1 and 100, 4 below 1', () => {
    assert.equal(formatDistance(123.4), '123');
    assert.equal(formatDistance(1.234), '1.23');
    assert.equal(formatDistance(0.123), '0.1230');
  });

  it('uses scientific notation below 0.001', () => {
    assert.match(formatDistance(0.00012), /e/);
  });
});
