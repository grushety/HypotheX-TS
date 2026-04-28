# OP-024 — Cycle Tier-2 ops (7 ops)

**Status:** [x] Done
**Depends on:** SEG-014 (STL/MSTL blob), OP-040 (relabeler)

---

## Goal

Implement the 7 Cycle-specific Tier-2 ops: `deseasonalise_remove`, `amplify_amplitude`, `dampen_amplitude`, `phase_shift`, `change_period`, `change_harmonic_content`, `replace_with_flat`.

**How it fits:** Gated when active shape is `cycle`. `deseasonalise_remove` → RECLASSIFY (residual-dependent). `replace_with_flat` → DETERMINISTIC(plateau). Others preserve cycle.

---

## Paper references (for `algorithm-auditor`)

- Cleveland et al. (1990) — STL seasonal component editing.
- Bandara et al. (2021) — MSTL.
- Oppenheim & Schafer (2010) Ch. 11 — Hilbert transform for phase shift.
- Verhoef (1996) — HANTS harmonic coefficients (amplitude/phase).

---

## Acceptance Criteria

- [x] `backend/app/services/operations/tier2/cycle.py` with all 7 ops
- [x] `phase_shift` offers Hilbert analytic rotation (default) and explicit harmonic rotation (fallback for numerical stability)
- [x] `deseasonalise_remove` emits OP-040 RECLASSIFY (shape depends on residual)
- [x] `replace_with_flat` emits OP-040 DETERMINISTIC(plateau)
- [x] `change_period(β=1)` is identity (asserted by test)
- [x] Works with both STL (single `seasonal`) and MSTL (multiple `seasonal_T`) blobs
- [x] Boundary-effect documentation for `phase_shift`: Hilbert edge artifacts tapered
- [x] Tests cover: amplitude scaling; phase shift by π/2; period change by factor 2; harmonic content edit; deseasonalise round-trip; MSTL multi-period handling
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-024: Cycle Tier-2 ops (7 ops)"` ← hook auto-moves this file to `done/` on commit

## Result Report

67 tests in `test_cycle_ops.py`. Reviewer found 1 blocking issue fixed: `replace_with_flat` did not zero the residual component, so for real STL/MSTL blobs with non-zero residuals the output was non-constant despite emitting `DETERMINISTIC('plateau')`. Fixed by zeroing residual, with a regression test using a non-zero residual fixture. Dead test code also cleaned up. All 67 tests pass.
