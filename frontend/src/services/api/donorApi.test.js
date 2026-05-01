import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { proposeDonor } from './donorApi.js';

function makeFetchImpl(responseInit, capture = {}) {
  return async (url, init) => {
    capture.url = url;
    capture.init = init;
    return {
      ok: responseInit.ok ?? true,
      status: responseInit.status ?? 200,
      json: async () => responseInit.json,
    };
  };
}

describe('proposeDonor', () => {
  it('rejects when backend is missing', async () => {
    await assert.rejects(
      () => proposeDonor({ segmentValues: [1], targetClass: 'a' }),
      /backend/,
    );
  });

  it('rejects when segmentValues is empty', async () => {
    await assert.rejects(
      () => proposeDonor({ backend: 'NativeGuide', segmentValues: [], targetClass: 'a' }),
      /segmentValues/,
    );
  });

  it('rejects when targetClass is empty', async () => {
    await assert.rejects(
      () => proposeDonor({ backend: 'NativeGuide', segmentValues: [1], targetClass: '' }),
      /targetClass/,
    );
  });

  it('posts the canonical payload shape', async () => {
    const cap = {};
    const fetchImpl = makeFetchImpl(
      { json: { backend: 'NativeGuide', candidates: [] } },
      cap,
    );
    await proposeDonor(
      {
        backend: 'NativeGuide',
        segmentValues: [0.1, 0.2, 0.3],
        targetClass: 'class-A',
        k: 2,
        excludeIds: ['x', 'y'],
      },
      fetchImpl,
    );
    assert.equal(cap.url, '/api/donors/propose');
    assert.equal(cap.init.method, 'POST');
    const body = JSON.parse(cap.init.body);
    assert.equal(body.backend, 'NativeGuide');
    assert.deepEqual(body.segment_values, [0.1, 0.2, 0.3]);
    assert.equal(body.target_class, 'class-A');
    assert.equal(body.k, 2);
    assert.deepEqual(body.exclude_ids, ['x', 'y']);
  });

  it('returns the parsed candidates array', async () => {
    const fetchImpl = makeFetchImpl({
      json: {
        backend: 'NativeGuide',
        candidates: [
          { donor_id: 'x', values: [0, 1], distance: 0.5, metric: 'dtw' },
        ],
      },
    });
    const out = await proposeDonor(
      { backend: 'NativeGuide', segmentValues: [1], targetClass: 'a' },
      fetchImpl,
    );
    assert.equal(out.candidates.length, 1);
    assert.equal(out.candidates[0].donor_id, 'x');
  });

  it('throws when candidates is not an array', async () => {
    const fetchImpl = makeFetchImpl({ json: { backend: 'NativeGuide' } });
    await assert.rejects(
      () => proposeDonor(
        { backend: 'NativeGuide', segmentValues: [1], targetClass: 'a' },
        fetchImpl,
      ),
      /candidates array/,
    );
  });

  it('attaches status code on backend errors (501 for unimplemented)', async () => {
    const fetchImpl = makeFetchImpl({
      ok: false,
      status: 501,
      json: { error: 'TimeGAN backend not yet implemented' },
    });
    try {
      await proposeDonor(
        { backend: 'TimeGAN', segmentValues: [1], targetClass: 'a' },
        fetchImpl,
      );
      assert.fail('should have thrown');
    } catch (err) {
      assert.equal(err.status, 501);
      assert.match(err.message, /TimeGAN/);
    }
  });
});
