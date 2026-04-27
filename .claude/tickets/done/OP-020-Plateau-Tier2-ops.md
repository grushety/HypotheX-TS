# OP-020 — Plateau Tier-2 ops (5 ops)

**Status:** [x] Done
**Depends on:** SEG-019 (blob), OP-010 (scale/offset primitives), OP-040 (relabeler)

---

## Goal

Implement the 5 Plateau-specific Tier-2 ops: `raise_lower`, `invert`, `replace_with_trend`, `replace_with_cycle`, `tilt_detrend`. Each edits the plateau's decomposition blob (method='Constant') rather than raw values.

**Why:** Plateaus are the simplest semantic shape; their Tier-2 operations are where the decomposition-first architecture shows its minimum benefit — editing a single `constant` coefficient gives a named, reversible edit.

**How it fits:** Gated in UI-005 when the active segment has `shape='plateau'`. Each op emits a relabel event via OP-040; most cases preserve the plateau shape, but `replace_with_trend` → `trend` and `replace_with_cycle` → `cycle` are DETERMINISTIC rule-class changes.

---

## Paper references (for `algorithm-auditor`)

- Cleveland (1990) — residual structure after detrending.
- Bevis & Brown (2014) — ETM (constant + linear rate for `replace_with_trend`).

---

## Pseudocode

```python
def raise_lower(blob, delta=None, alpha=None, pivot_mean=None):
    if delta is not None:
        blob.coefficients['constant'] += delta
    elif alpha is not None:
        p = pivot_mean or blob.coefficients['constant']
        blob.coefficients['constant'] = p + (1 + alpha) * (blob.coefficients['constant'] - p)
    return blob.reassemble()    # → plateau (PRESERVED)

def invert(blob, mu_global):
    new = blob.reassemble()
    return 2 * mu_global - new  # → plateau (PRESERVED)

def replace_with_trend(blob, beta, t):
    blob.method = 'ETM'
    blob.coefficients = {'x0': blob.coefficients['constant'], 'linear_rate': beta}
    blob.components = {'x0': np.full_like(t, blob.coefficients['x0']),
                       'linear_rate': beta * (t - t[0])}
    return blob.reassemble()    # → trend (DETERMINISTIC)

def replace_with_cycle(blob, amplitude, period, phase, t):
    blob.method = 'STL'
    blob.components = {
        'trend':    np.full_like(t, blob.coefficients['constant']),
        'seasonal': amplitude * np.sin(2 * np.pi * (t - t[0]) / period + phase),
        'residual': np.zeros_like(t),
    }
    blob.coefficients = {'period': period, 'amplitude': amplitude, 'phase': phase}
    return blob.reassemble()    # → cycle (DETERMINISTIC)

def tilt_detrend(blob, beta_local, t):
    return blob.reassemble() - beta_local * (t - t[0])  # → plateau (PRESERVED)
```

---

## Acceptance Criteria

- [x] `backend/app/services/operations/tier2/plateau.py` with all 5 ops
- [x] `raise_lower` supports both additive `delta` and multiplicative `alpha` (exactly one required, else raise)
- [x] `replace_with_trend` mutates blob method to `'ETM'` and emits OP-040 DETERMINISTIC(trend)
- [x] `replace_with_cycle` mutates blob method to `'STL'` and emits OP-040 DETERMINISTIC(cycle)
- [x] `tilt_detrend` preserves plateau shape (residual has zero local slope post-op)
- [x] Each op is a pure function taking a `DecompositionBlob` (deepcopied internally; caller's blob unchanged) and returning the reassembled edited series
- [ ] UI-006 gates these ops visible only when active segment has `shape='plateau'` — deferred to UI-006 ticket
- [x] Tests per op: synthetic plateau blob, apply op with known params, reassembled signal matches expected
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass (50 new, 810 full suite)
- [x] Run `code-reviewer` agent — 2 blocking issues fixed (internal deepcopy, empty-components guard)
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-020: Plateau Tier-2 ops (5 ops)"` ← hook auto-moves this file to `done/` on commit

## Result Report

Created `backend/app/services/operations/tier2/plateau.py` and the new `tier2/` package. Implements `raise_lower` (delta or alpha), `invert`, `replace_with_trend` (ETM), `replace_with_cycle` (STL), `tilt_detrend`. All three mutating ops deepcopy the blob internally — caller's blob is never modified. `_level` helper guards against empty-components blobs. `replace_with_cycle` validates period > 0. Relabeling: raise_lower/invert/tilt_detrend → PRESERVED('plateau'); replace_with_trend → DETERMINISTIC('trend'); replace_with_cycle → DETERMINISTIC('cycle'). AuditEvent deferred to OP-041. UI gating deferred to UI-006. 50 tests in `test_plateau_ops.py`.
