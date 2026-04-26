# OP-030 — decompose (Tier-3)

**Status:** [ ] Done
**Depends on:** SEG-019 (dispatcher), SEG-013..018 (fitters)

---

## Goal

Expose the SEG-019 dispatcher as a user-invocable Tier-3 operation that refits decomposition across one or more selected segments. This is the user-facing entry point to "re-fit the underlying model of this region."

**Why:** Users occasionally need to force a re-fit — e.g. after noticing a missed transient or a wrong period. A Tier-3 `decompose` operation gives them a single button that runs the appropriate fitter(s) fresh, with optional domain-hint override.

**How it fits:** Tier 3; user selects one or more segments, picks optional domain hint, clicks "decompose" in UI-005 Tier-3 toolbar. Dispatcher selects fitter per segment; each blob is refit and replaced.

---

## Paper references

Aggregates paper references from SEG-013..018 fitters.

---

## Pseudocode

```python
def decompose(X, segments_selected, domain_hint=None):
    for s in segments_selected:
        fitter = dispatch_fitter(s.label, domain_hint or s.scope.get('domain_hint'))
        s.decomposition = fitter(X[s.b : s.e + 1], t=np.arange(s.b, s.e + 1))
        s.decomposition.fit_metadata['refit_reason'] = 'user_tier3_decompose'
    emit_audit(op='decompose', tier=3, segment_ids=[s.id for s in segments_selected],
               methods_used=[s.decomposition.method for s in segments_selected],
               domain_hint=domain_hint)
    return segments_selected
```

---

## Acceptance Criteria

- [ ] `backend/app/services/operations/tier3/decompose.py` with `decompose(X, segments, domain_hint)`
- [ ] User-invocable on single or multiple selected segments
- [ ] Respects `domain_hint` override from UI-014 (or per-segment scope attribute)
- [ ] Produces valid `DecompositionBlob` per segment (validator from SEG-019 invoked)
- [ ] Idempotent at the blob level: `decompose(decompose(X, S), S)` produces blobs with the same coefficients (within numerical tolerance)
- [ ] Audit entry records all segment IDs, method used per segment, domain hint
- [ ] Tests cover: single-segment decompose; multi-segment decompose; domain-hint override; idempotence; error if segment outside X bounds
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "OP-030: decompose (Tier-3)"` ← hook auto-moves this file to `done/` on commit
