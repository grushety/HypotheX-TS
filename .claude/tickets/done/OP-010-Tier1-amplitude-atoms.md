# OP-010 — Tier 1 amplitude atoms: scale, offset, mute_zero

**Status:** [x] Done
**Depends on:** SEG-019 (blob), OP-040 (relabeler)

---

## Goal

Implement the three Tier-1 amplitude-level atoms. Each is label-agnostic: applies to any shape. When a decomposition blob exists, the op edits the appropriate component coefficient; when not, it falls back to raw-value edit.

**Why:** Amplitude atoms are the most elementary semantic edits: "make this bigger", "shift it up", "blank it out". They are label-agnostic building blocks used as primitives by several Tier-2 ops (e.g. `raise_lower` on Plateau is a scale or offset with the plateau's constant component).

**How it fits:** Tier 1, called directly from UI-005 palette. Decomposition-aware by default: if blob is present, edit the right coefficient; else edit raw values. Emits relabel event because `scale α=0` collapses any shape to plateau (DETERMINISTIC rule).

---

## Paper references

N/A (elementary). Design follows [[HypotheX-TS - Operation Vocabulary Research]] §3.1–§3.4.

---

## Pseudocode

```python
def scale(X_seg, blob, alpha: float, pivot: Literal['mean', 'min', 'zero'] = 'mean'):
    if blob is not None:
        # Decomposition-aware: scale the amplitude component in place
        if blob.method in ('STL', 'MSTL'):
            blob.components['seasonal'] *= alpha
        elif blob.method == 'ETM':
            for h in harmonics_of(blob): scale_coefficient(blob, h, alpha)
        # ... method-specific dispatch
        return blob.reassemble()
    p = {'mean': np.mean(X_seg), 'min': np.min(X_seg), 'zero': 0.0}[pivot]
    return p + alpha * (X_seg - p)

def offset(X_seg, blob, delta: float):
    if blob is not None:
        if 'constant' in blob.coefficients:  blob.coefficients['constant'] += delta
        elif 'x0' in blob.coefficients:      blob.coefficients['x0']       += delta
        return blob.reassemble()
    return X_seg + delta

def mute_zero(X_seg, blob, fill: Literal['zero', 'global_mean'] = 'zero', mu_global=None):
    out = np.full_like(X_seg, 0.0 if fill == 'zero' else mu_global)
    if blob is not None:
        blob.components = {'zero': out}
        blob.coefficients = {'fill': fill}
    return out
```

---

## Acceptance Criteria

- [x] `backend/app/services/operations/tier1/amplitude.py` with `scale`, `offset`, `mute_zero`
- [x] Each is a pure function: `(X_seg, blob, params) -> X_seg_edited` (blob mutated in-place when present; deepcopy in tests to verify)
- [x] Pivot options honoured for `scale`: `mean`, `min`, `zero`; unknown pivot raises
- [x] Identity properties under unit-test: `scale(X, α=1) ≈ X`; `offset(X, Δ=0) ≈ X`; `mute_zero + offset(μ) ≈ μ·ones`
- [x] Decomposition-aware variants dispatch by `blob.method`; unknown method falls back to raw-value edit with a warning log
- [x] `scale(α=0)` triggers OP-040 with `DETERMINISTIC(plateau)` rule
- [x] `mute_zero` triggers OP-040 with `DETERMINISTIC(plateau)` for both fill modes
- [x] Audit entries emitted via OP-041 carry tier=1, op name, params, pre/post shape
- [x] Tests cover: all three ops on plateau/trend/cycle/transient blobs; identity cases; pivot variants; fallback path; α=0 relabel
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-010: Tier-1 amplitude atoms (scale/offset/mute_zero)"` ← hook auto-moves this file to `done/` on commit

## Result Report

`scale`, `offset`, `mute_zero` implemented in `backend/app/services/operations/tier1/amplitude.py`. All three return `AmplitudeOpResult(values, relabel, op_name, tier=1)`. Blob-aware dispatch handles Constant, ETM, STL, MSTL; unknown methods fall back to raw-value arithmetic with a WARNING log. Relabeling is inline (OP-040 full table is a separate ticket): `scale(α=0)` → DETERMINISTIC('plateau'); `scale(α≠0)` / `offset` → PRESERVED; `mute_zero` → DETERMINISTIC('plateau'). Scale pivot options: 'mean', 'min', 'zero'. 39 tests in `test_amplitude_ops.py`; all pass.
