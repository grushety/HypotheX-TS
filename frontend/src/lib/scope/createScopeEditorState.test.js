import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_SCOPE_MODE,
  DEFAULT_WINDOW_SIZE,
  DOMAIN_HINTS,
  DOMAIN_HINT_OPTIONS,
  INHERIT_DOMAIN_KEY,
  SCOPE_MODES,
  VALIDATION_ERRORS,
  buildScopeUpdatePayload,
  createScopeEditorState,
  defaultScopeForDomain,
  draftFromScope,
  resolveDomainHint,
  validateScope,
} from './createScopeEditorState.js';

describe('DOMAIN_HINT_OPTIONS', () => {
  it('exposes all four packs plus the inherit sentinel as the first option', () => {
    assert.equal(DOMAIN_HINT_OPTIONS[0].key, INHERIT_DOMAIN_KEY);
    const keys = DOMAIN_HINT_OPTIONS.map((o) => o.key);
    for (const hint of DOMAIN_HINTS) assert.ok(keys.includes(hint), hint);
  });
});

describe('defaultScopeForDomain', () => {
  it('hydrology → sliding window 30 samples', () => {
    const s = defaultScopeForDomain('hydrology');
    assert.equal(s.domain_hint, 'hydrology');
    assert.equal(s.mode, 'sliding');
    assert.equal(s.window_size, 30);
    assert.equal(s.reference, null);
  });

  it('seismo-geodesy → fixed mode without a default reference', () => {
    const s = defaultScopeForDomain('seismo-geodesy');
    assert.equal(s.mode, 'fixed');
    assert.equal(s.reference, null);
  });

  it('remote-sensing → sliding window 365 samples', () => {
    const s = defaultScopeForDomain('remote-sensing');
    assert.equal(s.window_size, 365);
    assert.equal(s.mode, 'sliding');
  });

  it('unknown / null domain → sliding window default', () => {
    const s = defaultScopeForDomain(null);
    assert.equal(s.mode, DEFAULT_SCOPE_MODE);
    assert.equal(s.window_size, DEFAULT_WINDOW_SIZE);
  });
});

describe('validateScope', () => {
  it('passes for a valid sliding scope', () => {
    const r = validateScope({
      windowSize: 30,
      mode: 'sliding',
      seriesLength: 100,
    });
    assert.deepEqual(r, { ok: true, errors: {} });
  });

  it('passes for a valid fixed scope with a reference', () => {
    const r = validateScope({
      windowSize: 30,
      mode: 'fixed',
      reference: '2026-04-01T00:00:00Z',
      seriesLength: 100,
    });
    assert.equal(r.ok, true);
  });

  it('rejects window_size <= 0', () => {
    const r = validateScope({ windowSize: 0, mode: 'sliding' });
    assert.equal(r.ok, false);
    assert.equal(r.errors.window_size, VALIDATION_ERRORS.WINDOW_NON_POSITIVE);
  });

  it('rejects non-integer window_size', () => {
    const r = validateScope({ windowSize: 1.5, mode: 'sliding' });
    assert.equal(r.errors.window_size, VALIDATION_ERRORS.WINDOW_NOT_INTEGER);
  });

  it('rejects NaN / null / undefined window_size', () => {
    for (const bad of [null, undefined, NaN, 'not-a-number']) {
      const r = validateScope({ windowSize: bad, mode: 'sliding' });
      assert.equal(r.ok, false, `bad=${String(bad)}`);
      assert.equal(r.errors.window_size, VALIDATION_ERRORS.WINDOW_NON_POSITIVE);
    }
  });

  it('rejects window_size > series length', () => {
    const r = validateScope({
      windowSize: 200,
      mode: 'sliding',
      seriesLength: 100,
    });
    assert.equal(r.errors.window_size, VALIDATION_ERRORS.WINDOW_EXCEEDS_SERIES);
  });

  it('rejects unknown mode', () => {
    const r = validateScope({ windowSize: 10, mode: 'bogus' });
    assert.equal(r.errors.mode, VALIDATION_ERRORS.MODE_UNKNOWN);
  });

  it('rejects fixed mode without a reference', () => {
    const r = validateScope({ windowSize: 10, mode: 'fixed', reference: null });
    assert.equal(r.errors.reference, VALIDATION_ERRORS.REFERENCE_REQUIRED);
  });

  it('does not require a reference for sliding mode', () => {
    const r = validateScope({ windowSize: 10, mode: 'sliding', reference: null });
    assert.equal(r.errors.reference, undefined);
  });
});

describe('resolveDomainHint', () => {
  it('returns the project hint for the inherit sentinel', () => {
    assert.equal(resolveDomainHint(INHERIT_DOMAIN_KEY, 'hydrology'), 'hydrology');
    assert.equal(resolveDomainHint(INHERIT_DOMAIN_KEY, null), null);
  });

  it('passes through known hints unchanged', () => {
    for (const hint of DOMAIN_HINTS) {
      assert.equal(resolveDomainHint(hint, 'something-else'), hint);
    }
  });

  it('returns null for unknown keys', () => {
    assert.equal(resolveDomainHint('not-a-pack', 'hydrology'), null);
  });
});

describe('buildScopeUpdatePayload', () => {
  const draft = {
    windowSize: 45,
    mode: 'sliding',
    reference: null,
    domainHintKey: 'hydrology',
  };

  it('throws when segmentId is missing', () => {
    assert.throws(
      () => buildScopeUpdatePayload({ segmentId: '', draft }),
      /segmentId/,
    );
  });

  it('emits a scope dict with the resolved domain_hint and triggerReclassify=true', () => {
    const payload = buildScopeUpdatePayload({
      segmentId: 'seg-1',
      draft,
      previousScope: { domain_hint: null, window_size: 30, mode: 'sliding', reference: null },
    });
    assert.equal(payload.segmentId, 'seg-1');
    assert.equal(payload.scope.domain_hint, 'hydrology');
    assert.equal(payload.scope.window_size, 45);
    assert.equal(payload.scope.mode, 'sliding');
    assert.equal(payload.scope.reference, null);
    assert.equal(payload.triggerReclassify, true);
    assert.deepEqual(payload.previousScope, {
      domain_hint: null,
      window_size: 30,
      mode: 'sliding',
      reference: null,
    });
  });

  it('drops the reference for sliding mode even if the draft carries one', () => {
    const slidingDraft = { ...draft, mode: 'sliding', reference: '2026-04-01' };
    const payload = buildScopeUpdatePayload({
      segmentId: 'seg-1',
      draft: slidingDraft,
    });
    assert.equal(payload.scope.reference, null);
  });

  it('keeps the reference for fixed mode', () => {
    const fixedDraft = { ...draft, mode: 'fixed', reference: '2026-04-01' };
    const payload = buildScopeUpdatePayload({ segmentId: 'seg-1', draft: fixedDraft });
    assert.equal(payload.scope.reference, '2026-04-01');
  });

  it('resolves the inherit sentinel using projectDomainHint', () => {
    const inheritDraft = { ...draft, domainHintKey: INHERIT_DOMAIN_KEY };
    const payload = buildScopeUpdatePayload({
      segmentId: 'seg-1',
      draft: inheritDraft,
      projectDomainHint: 'remote-sensing',
    });
    assert.equal(payload.scope.domain_hint, 'remote-sensing');
  });
});

describe('draftFromScope', () => {
  it('seeds a new draft from a domain default when scope is null', () => {
    const draft = draftFromScope(null, 'hydrology');
    assert.equal(draft.windowSize, 30);
    assert.equal(draft.mode, 'sliding');
    // No domain hint stored on the segment yet → inherit sentinel.
    assert.equal(draft.domainHintKey, INHERIT_DOMAIN_KEY);
  });

  it('mirrors an existing scope back into a draft', () => {
    const draft = draftFromScope({
      domain_hint: 'remote-sensing',
      window_size: 365,
      mode: 'sliding',
      reference: null,
    });
    assert.equal(draft.windowSize, 365);
    assert.equal(draft.mode, 'sliding');
    assert.equal(draft.domainHintKey, 'remote-sensing');
  });

  it('falls back to inherit when the stored hint is unknown', () => {
    const draft = draftFromScope({ domain_hint: 'no-such-pack', mode: 'sliding' });
    assert.equal(draft.domainHintKey, INHERIT_DOMAIN_KEY);
  });

  it('falls back to default mode if stored mode is bogus', () => {
    const draft = draftFromScope({ mode: 'flying', window_size: 10 });
    assert.equal(draft.mode, DEFAULT_SCOPE_MODE);
  });
});

describe('createScopeEditorState', () => {
  const segment = {
    id: 'seg-1',
    scope: { domain_hint: 'hydrology', window_size: 30, mode: 'sliding', reference: null },
  };

  it('exposes options, modes, draft and validation result', () => {
    const state = createScopeEditorState({ segment, seriesLength: 1000 });
    assert.equal(state.segmentId, 'seg-1');
    assert.equal(state.scopeModes.length, 2);
    assert.equal(state.options.length, DOMAIN_HINT_OPTIONS.length);
    assert.equal(state.canSave, true);
    assert.equal(state.draft.windowSize, 30);
    assert.equal(state.draft.domainHintKey, 'hydrology');
    assert.deepEqual(state.previousScope, segment.scope);
  });

  it('canSave=false when the draft window exceeds series length', () => {
    const state = createScopeEditorState({
      segment,
      seriesLength: 10,
      draft: {
        windowSize: 30,
        mode: 'sliding',
        reference: null,
        domainHintKey: 'hydrology',
      },
    });
    assert.equal(state.canSave, false);
    assert.equal(
      state.validation.errors.window_size,
      VALIDATION_ERRORS.WINDOW_EXCEEDS_SERIES,
    );
  });

  it('canSave=false when no segment is provided', () => {
    const state = createScopeEditorState({ seriesLength: 100 });
    assert.equal(state.canSave, false);
  });

  it('isFixedMode reflects the draft mode', () => {
    const state = createScopeEditorState({
      segment,
      seriesLength: 1000,
      draft: {
        windowSize: 30,
        mode: 'fixed',
        reference: '2026-04-01T00:00:00Z',
        domainHintKey: 'seismo-geodesy',
      },
    });
    assert.equal(state.isFixedMode, true);
  });

  it('seeds a fresh draft from project domain when segment has no scope', () => {
    const state = createScopeEditorState({
      segment: { id: 'seg-2', scope: null },
      seriesLength: 1000,
      projectDomainHint: 'remote-sensing',
    });
    assert.equal(state.draft.windowSize, 365);
    assert.equal(state.draft.mode, 'sliding');
    assert.equal(state.draft.domainHintKey, INHERIT_DOMAIN_KEY);
  });
});
