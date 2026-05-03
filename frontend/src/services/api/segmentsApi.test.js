import { test } from 'node:test';
import assert from 'node:assert/strict';

import { updateSegmentScope } from './segmentsApi.js';

function fakeFetch(captured, response) {
  return async (url, init) => {
    captured.url = url;
    captured.init = init;
    return {
      ok: response.ok,
      status: response.status ?? 200,
      json: async () => response.body,
    };
  };
}

test('updateSegmentScope POSTs to /api/segments/<id>/scope and returns parsed body', async () => {
  const captured = {};
  const body = {
    segment_id: 'seg-1',
    scope: { window_size: 30, mode: 'sliding', reference: null, domain_hint: 'hydrology' },
    audit_id: 'audit-uuid',
    trigger_reclassify: true,
  };
  const result = await updateSegmentScope(
    {
      segmentId: 'seg-1',
      scope: { window_size: 30, mode: 'sliding', reference: null, domain_hint: 'hydrology' },
      previousScope: null,
      triggerReclassify: true,
    },
    fakeFetch(captured, { ok: true, body }),
  );
  assert.equal(captured.url, '/api/segments/seg-1/scope');
  assert.equal(captured.init.method, 'POST');
  const sent = JSON.parse(captured.init.body);
  assert.equal(sent.scope.window_size, 30);
  assert.equal(sent.triggerReclassify, true);
  assert.equal(result.segment_id, 'seg-1');
});

test('updateSegmentScope surfaces backend errors with the message', async () => {
  const captured = {};
  const body = { error: 'scope.window_size must be >= 1.' };
  await assert.rejects(
    () =>
      updateSegmentScope(
        { segmentId: 'seg-bad', scope: { window_size: 0, mode: 'sliding' } },
        fakeFetch(captured, { ok: false, status: 400, body }),
      ),
    /scope.window_size must be >= 1\./,
  );
});

test('updateSegmentScope rejects when segmentId or scope is missing', async () => {
  await assert.rejects(() => updateSegmentScope({ scope: { window_size: 30 } }), /segmentId/);
  await assert.rejects(() => updateSegmentScope({ segmentId: 'seg-1' }), /scope/);
});
