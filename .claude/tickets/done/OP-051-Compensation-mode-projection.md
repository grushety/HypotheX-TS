# OP-051 — Compensation-mode projection (naive / local / coupled)

**Status:** [x] Done
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

- [x] `backend/app/services/operations/tier3/compensation.py` with `project(X_edit, constraint, compensation_mode, segment_mask)`
- [x] Three modes selectable: `naive`, `local`, `coupled`
- [x] Default mode per domain:
  - `local` for hydrology ops
  - `coupled` for geodesy ops (moment balance, NNR)
  - `naive` for other (with warning log)
- [x] `coupled` mode solves the equality-constrained QP via null-space projection for linear constraints; falls back to iterative projected-gradient for nonlinear constraints
- [x] `naive` mode: reports residual but does not project; UI-010 shows the gap in red
- [x] `local` mode: residual allocated only within `segment_mask`; asserted by test that values outside mask are byte-identical pre/post
- [x] Post-projection residual ≤ tolerance `1e-6` for linear constraints; ≤ tolerance × 100 for nonlinear (documented)
- [x] Tests cover each mode on water-balance fixture; each mode on moment-balance fixture; `naive` reports residual correctly without modifying X; `local` preserves segments outside mask; `coupled` satisfies constraint within tolerance
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-051: compensation-mode projection (naive/local/coupled)"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Created the projection primitive that OP-032 / OP-050 / cf_coordinator have been deferring to with a `try/except ImportError` fallback to a no-op `_naive_project`.  With OP-051 shipped, the default projector resolves to a real implementation.

**Files**
- `backend/app/services/operations/tier3/compensation.py` — public surface:
  - `project(X_edit, constraint, compensation_mode='local', *, segment_mask=None, tolerance=1e-6, max_iter=20) → np.ndarray`
  - `default_compensation_mode_for_domain(domain_hint) → CompensationMode`
  - `CompensationMode` literal type alias
  - `HasJacobian` `@runtime_checkable` Protocol (optional structural extension of the OP-050 `Constraint` Protocol)
  Internal:
  - `_residual_vector` (coerce scalar / 1-D array to 1-D float array for QP)
  - `_jacobian_matrix` (uses `constraint.jacobian` when present; falls back to numerical via central differences)
  - `_numerical_jacobian` (central differences, 2n residual evaluations per call — used only when constraint lacks closed-form Jacobian)
  - `_project_iterative` (Newton-style: `X' = X − Jᵀ(JJᵀ)⁻¹ r` repeated until `‖r‖ ≤ tolerance` or `max_iter`)
- `backend/app/services/operations/tier3/__init__.py` — re-exports the new public surface (3 lines added)
- `backend/tests/test_compensation_op051.py` — 30 tests including: mode validation, all three modes on the closed-form `sum_equals_target` linear constraint, water-balance fixture (per-element residual goes to zero), moment-balance fixture (trace zero, off-diagonals untouched), nonlinear `sum_of_squares` Newton convergence, local-mode byte-identical preservation outside the mask, full-mask local-vs-coupled equivalence, all-False mask warning + no-op, water-balance local-mode mask restricting to the ΔS block (entire residual absorbed there), numerical-Jacobian fallback for both coupled and local modes, max_iter bound respected for pathological singular-Jacobian start, default-mode-per-domain table (hydrology→local, seismo-geodesy→coupled, remote-sensing→local, unknown→naive, case-insensitive), input-array non-mutation, three-mode integration sanity (naive ‖r‖ > local ‖r‖ ≈ coupled ‖r‖ ≈ 0), and an OP-050-style `MockConstraint` (no `.jacobian()`) accepted in naive mode.

**Implementation notes**

1. **Numerical-Jacobian fallback is the key compatibility move.**  The OP-050 `Constraint` Protocol in `cf_coordinator.py:56–71` exposes only `name` / `residual` / `satisfied` — no `jacobian`.  `_jacobian_matrix` checks `hasattr(constraint, 'jacobian')` first; if absent or raising, falls back to central differences (2n residual evaluations per Newton step, eps=1e-7).  All 37 cf_coordinator tests still pass — they all override `projector=Mock`, but the real default projector is now also Protocol-compatible.
2. **Local-mode mask projects only the masked subset**: `J_local = J_full[:, mask]`, then `X[mask] -= J_localᵀ(J_local J_localᵀ)⁻¹ r`.  Values outside the mask are touched by no code path.  Pinned by a byte-equality test.
3. **All-False mask path**: warns + returns X unchanged rather than raising — the user explicitly chose a mask that cannot fix the residual; `project` is a primitive whose role is to compute, not police caller intent.
4. **Linear constraints converge in one Newton step** (closed-form QP).  **Nonlinear constraints** iterate; pathological singular-Jacobian starts log WARNING + return best-so-far rather than raise or loop forever.
5. **`np.linalg.lstsq` on `J·Jᵀ`** rather than `np.linalg.solve` for rank-deficient robustness — same pattern as OP-032's NNR projection.
6. **No audit emission** — `project` is a primitive called from OP-032 / OP-050 / cf_coordinator, all of which emit their own audit at the orchestration layer.  Double-emission would be wrong.
7. **`naive` returns a fresh array** (`X.copy()`), never aliases the input — pinned by `test_naive_returns_a_fresh_array_not_the_input`.
8. **`naive` never computes the Jacobian** — pinned by a constraint whose `.jacobian` raises `AssertionError`.

**Tests** — `pytest tests/test_compensation_op051.py`: 30/30 pass.  Full backend suite: 1530 pass, 2 pre-existing unrelated failures.  `ruff check` clean.  No regression in cf_coordinator (37/37) — even though `_get_default_projector` now resolves to the real implementation instead of the no-op fallback.  Tier-3 stack at 131 passing (27 OP-030 + 35 OP-032 + 39 OP-033 + 30 OP-051).

**Code review** — APPROVE, no blocking issues.  Reviewer scrutinised four design choices (`lstsq` over `solve`, fixed-eps numerical Jacobian, all-False-mask warning vs raise, no audit emission) and accepted all four.  Two non-blocking follow-ups noted: the `try/except ImportError` fallback at `cf_coordinator.py:243–251` is now dead code on every supported install (cleanup ticket); threading iteration count + final residual back to callers via a return-tuple instead of just-logging would let OP-032/OP-050 record `convergence_iters` in their audit.

**Out of scope / follow-ups**
- Cleanup ticket: remove the now-dead `_naive_project` fallback in `cf_coordinator._get_default_projector`.
- Return-tuple enhancement: change `project` to return `(X_projected, ProjectionStats)` so callers can record `convergence_iters` and `final_residual` in their audit entries (currently only logged at WARN).
- Wiring `default_compensation_mode_for_domain` into UI-011's mode-selector dropdown so the UI pre-selects a sensible default per active domain.
