# OP-051 — Compensation-mode projection (naive / local / coupled)

**Status:** [ ] Done
**Depends on:** OP-032 (law definitions)

---

## Goal

Project a perturbed series to satisfy a conservation law using one of three modes:
- **naive** — no projection; residual reported only
- **local** — distribute residual within the edited segment
- **coupled** — distribute residual across all segments via conservation coupling (QP projection)

**Why:** The compensation-mode selector is the **atomic novelty** of the conservation-enforcement claim (per [[_project HypotheX-TS/HypotheX-TS - Originality Assessment]] — no existing CF-XAI tool exposes naive/local/coupled as a user choice). It gives domain experts control over *how* physical balance is re-established after a what-if edit.

**How it fits:** Called by OP-050 (CF coordinator) and OP-032 (enforce_conservation). Takes the edited series, the law, and the mode; returns the projected series.

---

## Paper references (for `algorithm-auditor`)

- Nocedal & Wright (2006) "Numerical Optimization" 2nd ed., Ch. 17 (projected-gradient, KKT for equality-constrained QP).
- Eckhardt (2005) — water-balance coupling.
- Ansari, De Zan, Bamler (2018) — InSAR triplet closure projection.

---

## Pseudocode

```python
def project(X_edit, constraint, compensation_mode: Literal['naive', 'local', 'coupled'],
            segment_mask=None):
    residual = constraint.residual(X_edit)

    if compensation_mode == 'naive':
        # Report only; do not project
        log_info(f"naive mode: residual {residual} reported but not corrected")
        return X_edit

    if compensation_mode == 'local':
        # Distribute residual within the current segment only
        assert segment_mask is not None, "local mode requires segment_mask"
        allocation = allocate_local(residual, segment_mask, constraint)
        return X_edit - allocation

    if compensation_mode == 'coupled':
        # Solve QP: minimize ||X' - X_edit||² s.t. constraint(X') = 0 across all segments
        # Null-space projection (equality-constrained QP closed-form) when Jacobian is linear
        J = constraint.jacobian(X_edit)
        # Project via J^T (J J^T)^{-1} residual
        import scipy.linalg
        correction = scipy.linalg.lstsq(J, residual)[0]
        return X_edit - correction

    raise ValueError(f"unknown compensation mode: {compensation_mode}")
```

---

## Acceptance Criteria

- [ ] `backend/app/services/operations/tier3/compensation.py` with `project(X_edit, constraint, compensation_mode, segment_mask)`
- [ ] Three modes selectable: `naive`, `local`, `coupled`
- [ ] Default mode per domain:
  - `local` for hydrology ops
  - `coupled` for geodesy ops (moment balance, NNR)
  - `naive` for other (with warning log)
- [ ] `coupled` mode solves the equality-constrained QP via null-space projection for linear constraints; falls back to iterative projected-gradient for nonlinear constraints
- [ ] `naive` mode: reports residual but does not project; UI-010 shows the gap in red
- [ ] `local` mode: residual allocated only within `segment_mask`; asserted by test that values outside mask are byte-identical pre/post
- [ ] Post-projection residual ≤ tolerance `1e-6` for linear constraints; ≤ tolerance × 100 for nonlinear (documented)
- [ ] Tests cover each mode on water-balance fixture; each mode on moment-balance fixture; `naive` reports residual correctly without modifying X; `local` preserves segments outside mask; `coupled` satisfies constraint within tolerance
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "OP-051: compensation-mode projection (naive/local/coupled)"` ← hook auto-moves this file to `done/` on commit
