import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  fetchSemanticPacks,
  labelSemanticSegments,
  validateSemanticPackYaml,
} from './semanticPackApi.js';

function makeFetchImpl(responseInit) {
  return async () => ({
    ok: responseInit.ok ?? true,
    status: responseInit.status ?? 200,
    json: async () => responseInit.json,
  });
}

describe('fetchSemanticPacks', () => {
  it('returns the parsed payload', async () => {
    const fetchImpl = makeFetchImpl({ json: { packs: [{ name: 'hydrology', labels: [] }] } });
    const out = await fetchSemanticPacks(fetchImpl);
    assert.equal(out.packs[0].name, 'hydrology');
  });

  it('throws when packs array is missing', async () => {
    const fetchImpl = makeFetchImpl({ json: {} });
    await assert.rejects(() => fetchSemanticPacks(fetchImpl), /packs array/);
  });

  it('surfaces backend errors', async () => {
    const fetchImpl = makeFetchImpl({ ok: false, status: 500, json: { error: 'broken' } });
    await assert.rejects(() => fetchSemanticPacks(fetchImpl), /broken/);
  });
});

describe('labelSemanticSegments', () => {
  it('requires packName or customYaml', async () => {
    const fetchImpl = makeFetchImpl({ json: { results: [] } });
    await assert.rejects(
      () => labelSemanticSegments({ values: [], segments: [] }, fetchImpl),
      /requires packName or customYaml/,
    );
  });

  it('posts pack_name when given', async () => {
    let captured;
    const fetchImpl = async (url, init) => {
      captured = { url, init };
      return { ok: true, status: 200, json: async () => ({ results: [], pack_name: 'hydrology' }) };
    };
    await labelSemanticSegments(
      { packName: 'hydrology', values: [1], segments: [{ id: 's1', start: 0, end: 0, shape: 'plateau' }] },
      fetchImpl,
    );
    assert.match(captured.url, /label-segments$/);
    const body = JSON.parse(captured.init.body);
    assert.equal(body.pack_name, 'hydrology');
    assert.equal(body.values.length, 1);
  });

  it('posts custom_yaml when given', async () => {
    let captured;
    const fetchImpl = async (url, init) => {
      captured = init;
      return { ok: true, status: 200, json: async () => ({ results: [], pack_name: 'custom' }) };
    };
    await labelSemanticSegments(
      { customYaml: 'name: x', values: [], segments: [] },
      fetchImpl,
    );
    const body = JSON.parse(captured.body);
    assert.equal(body.custom_yaml, 'name: x');
  });

  it('throws when results is not an array', async () => {
    const fetchImpl = makeFetchImpl({ json: {} });
    await assert.rejects(
      () => labelSemanticSegments({ packName: 'h', values: [], segments: [] }, fetchImpl),
      /results array/,
    );
  });
});

describe('validateSemanticPackYaml', () => {
  it('returns the validation payload as-is', async () => {
    const fetchImpl = makeFetchImpl({
      json: { ok: false, error: { message: 'bad', line: 4, kind: 'yaml' } },
    });
    const out = await validateSemanticPackYaml('invalid', fetchImpl);
    assert.equal(out.ok, false);
    assert.equal(out.error.line, 4);
  });

  it('throws when ok is missing from payload', async () => {
    const fetchImpl = makeFetchImpl({ json: {} });
    await assert.rejects(
      () => validateSemanticPackYaml('x', fetchImpl),
      /ok boolean/,
    );
  });
});
