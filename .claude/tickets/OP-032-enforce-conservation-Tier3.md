# OP-032 — enforce_conservation (Tier-3)

**Status:** [ ] Done
**Depends on:** OP-051 (compensation mode projection), OP-050 (CF coordinator)

---

## Goal

Project a multi-segment perturbation onto the manifold satisfying a named conservation law. Four laws in scope for MVP: **water balance** (P − ET − Q − ΔS = 0), **seismic moment balance** (Σ Mᵢᵢ = 0 + finite-fault budget), **InSAR phase-triplet closure** (arg(φ₁₂ + φ₂₃ − φ₁₃) = 0), **GNSS no-net-rotation reference frame**.

**Why:** First-class user-exposed conservation enforcement is the flagship differentiator (novelty score 4.5/5 per [[_project HypotheX-TS/HypotheX-TS - Originality Assessment]]). Reviewers will compare this against backend-loss physics-informed ML (Patil 2026, Jiang 2024) — the novelty is surfacing it as a user operation with a compensation-mode selector.

**How it fits:** Tier 3; user clicks `enforce_conservation` in UI-005 Tier-3 toolbar, picks law + compensation mode via UI-011. OP-032 computes the residual, calls OP-051 to project, and surfaces residual-budget via UI-010.

---

## Paper references (for `algorithm-auditor`)

- Eckhardt (2005) — water balance decomposition.
- Aki & Richards (2002) "Quantitative Seismology" 2nd ed., Ch. 3 (moment tensor).
- De Zan, Zonno, López-Dekker (2015) "Phase inconsistencies and multiple scattering in SAR interferometry" — *IEEE TGRS* 53(12):6608 (triplet closure).
- Ansari, De Zan, Bamler (2018) "Efficient phase estimation for interferogram stacks" — *IEEE TGRS* 56:4109.
- Altamimi, Collilieux, Métivier (2011) "ITRF2008: an improved solution of the international terrestrial reference frame" — *J. Geodesy* 85:457–473 (NNR).

---

## Pseudocode

```python
def enforce_conservation(X_all_segments, law: str, compensation_mode: str = 'local', aux: dict = None):
    initial_residual = compute_residual(X_all_segments, law, aux)

    if law == 'water_balance':
        # P - ET - Q - ΔS = 0
        X_edit = project_water_balance(X_all_segments, initial_residual,
                                        compensation_mode=compensation_mode, aux=aux)
    elif law == 'moment_balance':
        X_edit = project_moment_tensor(X_all_segments, initial_residual,
                                        compensation_mode=compensation_mode, aux=aux)
    elif law == 'phase_closure':
        X_edit = enforce_triplet_closure(X_all_segments, initial_residual, aux=aux)
    elif law == 'nnr_frame':
        X_edit = enforce_nnr(X_all_segments, initial_residual, aux=aux)
    else:
        raise UnknownLaw(law)

    final_residual = compute_residual(X_edit, law, aux)
    emit_audit(op='enforce_conservation', tier=3, law=law,
               compensation_mode=compensation_mode,
               initial_residual=initial_residual, final_residual=final_residual)

    return X_edit, ConservationResult(initial_residual, final_residual)
```

---

## Acceptance Criteria

- [ ] `backend/app/services/operations/tier3/enforce_conservation.py` with `enforce_conservation(X_all, law, compensation_mode, aux)`
- [ ] Four laws implemented: `water_balance`, `moment_balance`, `phase_closure`, `nnr_frame`
- [ ] Law registry extensible at import time: `@register_law('water_balance')` decorator
- [ ] `compensation_mode` consumed (delegates to OP-051 for the actual projection math)
- [ ] Residual budget (`initial_residual`, `final_residual`) surfaced to UI-010 via `ConservationResult` return value
- [ ] Post-projection residual ≤ configured tolerance for hard laws (`phase_closure`, `nnr_frame`); logged-as-warning-but-not-blocked for soft laws (`water_balance`, `moment_balance`)
- [ ] Audit entry records both residuals for before/after comparison
- [ ] Unit tests per law:
  - water_balance: synthetic (P, ET, Q, dS) with known residual; post-projection residual < 1e-6
  - moment_balance: Mxx + Myy + Mzz != 0; post-projection == 0 within tolerance
  - phase_closure: three interferograms with deliberate closure error; post-projection closure ≤ 0.1 rad
  - nnr_frame: three stations with net rotation; post-projection NNR satisfied
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "OP-032: enforce_conservation (Tier-3) with 4 laws"` ← hook auto-moves this file to `done/` on commit
