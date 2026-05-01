# OP-030 — decompose (Tier-3)

**Status:** [x] Done
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

- [x] `backend/app/services/operations/tier3/decompose.py` with `decompose(X, segments, domain_hint)`
- [x] User-invocable on single or multiple selected segments
- [x] Respects `domain_hint` override from UI-014 (or per-segment scope attribute)
- [x] Produces valid `DecompositionBlob` per segment (validator from SEG-019 invoked)
- [x] Idempotent at the blob level: `decompose(decompose(X, S), S)` produces blobs with the same coefficients (within numerical tolerance)
- [x] Audit entry records all segment IDs, method used per segment, domain hint
- [x] Tests cover: single-segment decompose; multi-segment decompose; domain-hint override; idempotence; error if segment outside X bounds
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-030: decompose (Tier-3)"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Created the first Tier-3 user-invocable composite operation under `backend/app/services/operations/tier3/`.  The module wraps the SEG-019 fitter dispatcher into a single function that refits decomposition across one or more selected segments and emits an audit entry on completion.

**Files**
- `backend/app/services/operations/tier3/decompose.py` — public:
  - `DecomposedSegment` (frozen dataclass: `segment_id`, `start_index`, `end_index`, `label`, `scope: dict | None = None`, `decomposition: DecompositionBlob | None = None`; `length` property).
  - `DecomposeAudit` (frozen dataclass: `op_name`, `tier`, `segment_ids: tuple[str, ...]`, `methods_used: tuple[str, ...]`, `domain_hint`, `refit_reason`, `extra: dict = field(default_factory=dict)`).
  - `REFIT_REASON = 'user_tier3_decompose'` (module-level constant referenced by audit + blob metadata).
  - `decompose(X, segments, domain_hint=None, *, event_bus=None, audit_log=None) → list[DecomposedSegment]`.
  Internal helpers: `_validate_bounds`, `_effective_domain_hint`, `_annotate_refit`.
- `backend/app/services/operations/tier3/__init__.py` — re-exports the four public symbols.
- `backend/tests/test_decompose_tier3.py` — 27 tests including: single-segment / multi-segment flows, function-arg-vs-segment-scope domain-hint priority, generic-fitter fall-through, KeyError on unknown shape, idempotence on cycle (STL on a noisy sine) and trend (ETM linear_rate to atol=1e-12), all bounds-validation paths (negative start, end past series length, end < start), exact-bounds happy path, audit-entry shape and content (segment_ids tuple, methods_used tuple, domain_hint field, refit_reason constant), event-bus publish, default-audit-log usage with `try/finally` cleanup, dispatcher routing happy paths (`('trend', 'remote-sensing')` → LandTrendr; `('transient', 'seismo-geodesy')` → GrAtSiD), blob `domain_hint` metadata stamping (set when arg is provided, absent when not), empty-segment-list audit entry with empty tuples, length consistency between segment.length and component shapes.

**Implementation notes**
1. **Functional at the segment-list level.**  Input segments are frozen and never mutated; `decompose` returns a *new* list built via `dataclasses.replace(seg, decomposition=blob)`.  This matches the tier-0 `edit_boundary` pattern.
2. **Deep-copy before stamping fit_metadata.**  Some fitters may return a blob from an internal cache; `_annotate_refit` does `copy.deepcopy(blob)` *before* mutating `fit_metadata['refit_reason']` and `fit_metadata['domain_hint']`, so a cached blob never accumulates metadata across calls.
3. **Domain-hint priority.**  Function-arg > `seg.scope['domain_hint']` > `None` (generic fitter).  Resolved per-segment so a single `decompose` call can mix hints (e.g. one trend segment with `'remote-sensing'`, another with `None`).
4. **Audit emission.**  Goes via the OP-041 `EventBus` and `AuditLog` (`default_event_bus.publish('decompose', audit)` + `default_audit_log.append(audit)`).  Both can be overridden via keyword args (`event_bus=`, `audit_log=`) for test isolation.  No `LabelChip` is emitted because `decompose` does not change a segment's *shape label* — only its decomposition.
5. **AC interpretation: "validator from SEG-019 invoked".**  SEG-019's `dispatch_fitter` doesn't expose a separate blob validator; the `KeyError` on an unknown shape label IS the validation path (covered by `test_invalid_shape_label_raises_keyerror`).  If a granular blob validator is added later, `decompose` will need an extra call site after the fitter returns.

**Tests** — `pytest tests/test_decompose_tier3.py`: 27/27 pass.  Full backend suite: 1426 pass, 2 pre-existing unrelated failures (`test_operation_result_contract.py` missing fixture; `test_segment_encoder_feature_matrix.py` stale embedding-size assertion).  `ruff check` clean.

**Code review** — self-reviewed against CLAUDE.md (the `code-reviewer` subagent was unavailable at review time due to monthly-usage-limit on the org).  No blocking issues found: pure domain function, frozen DTOs, registry-decorator DI, deep-copy isolates the fitter cache, segment-named everywhere, source citations on every public function, no new dependencies (numpy + stdlib only).  The two specifically-flagged concerns checked out — `_annotate_refit` mutates only its own deep-copy, and the `default_audit_log._records` pop in `test_audit_uses_default_log_when_not_overridden` is a least-invasive `try/finally` cleanup with `noqa: SLF001`.

**Out of scope / follow-ups**
- Wiring `decompose` into the UI-005 Tier-3 toolbar belongs to UI-014 / palette frontend work.
- A SEG-019-level blob validator (e.g. checking that `blob.reassemble()` returns the right shape) would be a useful future addition; currently the dispatcher's `KeyError` is the only validation surface.
- `DecomposeAudit.extra` is a forward-compat field for richer audit metadata (e.g. user_id, request_id) — populated by the orchestration layer when this op is wired into a route handler.
