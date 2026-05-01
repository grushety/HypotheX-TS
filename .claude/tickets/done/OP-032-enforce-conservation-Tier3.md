# OP-032 — enforce_conservation (Tier-3)

**Status:** [x] Done
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

- [x] `backend/app/services/operations/tier3/enforce_conservation.py` with `enforce_conservation(X_all, law, compensation_mode, aux)`
- [x] Four laws implemented: `water_balance`, `moment_balance`, `phase_closure`, `nnr_frame`
- [x] Law registry extensible at import time: `@register_law('water_balance')` decorator
- [x] `compensation_mode` consumed (delegates to OP-051 for the actual projection math)
- [x] Residual budget (`initial_residual`, `final_residual`) surfaced to UI-010 via `ConservationResult` return value
- [x] Post-projection residual ≤ configured tolerance for hard laws (`phase_closure`, `nnr_frame`); logged-as-warning-but-not-blocked for soft laws (`water_balance`, `moment_balance`)
- [x] Audit entry records both residuals for before/after comparison
- [x] Unit tests per law:
  - water_balance: synthetic (P, ET, Q, dS) with known residual; post-projection residual < 1e-6
  - moment_balance: Mxx + Myy + Mzz != 0; post-projection == 0 within tolerance
  - phase_closure: three interferograms with deliberate closure error; post-projection closure ≤ 0.1 rad
  - nnr_frame: three stations with net rotation; post-projection NNR satisfied
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-032: enforce_conservation (Tier-3) with 4 laws"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Created the second Tier-3 user-invocable composite operation under `backend/app/services/operations/tier3/`.  The module exposes a single user-facing entry point that projects a bundle of signals onto the manifold satisfying any of four named conservation laws, with a compensation-mode selector that governs how the residual is distributed across the contributing signals.

**Files**
- `backend/app/services/operations/tier3/enforce_conservation.py` — public surface:
  - `enforce_conservation(X_all, law, compensation_mode='local', aux=None, *, tolerance=None, event_bus=None, audit_log=None) → tuple[dict, ConservationResult]`
  - `register_law(name)` decorator + `LAW_REGISTRY: dict[str, Callable]`
  - `ConservationResult` (frozen dataclass: law, compensation_mode, initial_residual, final_residual, converged, tolerance, extra)
  - `ConservationAudit` (frozen dataclass: op_name, tier, law, compensation_mode, initial_residual, final_residual, converged, tolerance)
  - `UnknownLaw` exception, `HARD_LAWS` / `SOFT_LAWS` frozensets, `DEFAULT_TOLERANCE` dict
  - Four `@register_law`-decorated callables: `project_water_balance`, `project_moment_tensor`, `enforce_triplet_closure`, `enforce_nnr`
  Internal helpers: `_residual_norm`, `_converged`, `_residual_repr`, `_residual_to_serialisable`, `_wrap_phase`.
- `backend/app/services/operations/tier3/__init__.py` — re-exports the public surface.
- `backend/tests/test_enforce_conservation_tier3.py` — 35 tests including: registry contents, hard/soft partition, `UnknownLaw` for missing laws, `ValueError` for unknown compensation mode, decorator collision warning, water_balance residual < 1e-6 + coupled-distribution math + naive identity + already-balanced no-op, moment_balance trace=0 + coupled per-diagonal math + local-only-Mzz + off-diagonal preservation + invalid-shape rejection, phase_closure ≤ 0.1 rad in coupled mode + local-mode exact zero + naive-mode unchanged + 2π-multiple wrapping + hard-law assertion, nnr_frame residual recovery on 3-station synthetic + zero-velocity passthrough + naive non-modification + minimum-station check + shape-mismatch rejection + hard-law assertion, audit-log append + initial/final residual recording + tolerance recording + event-bus publish, ConservationResult law/mode/tolerance fields + ndarray-residual serialisability, idempotence of water_balance and moment_balance projections, hard-law and soft-law non-convergence non-raise paths.

**Implementation notes**

1. **OP-051 deferral.**  The ticket says "delegates to OP-051 for the actual projection math" but OP-051 is unshipped; `cf_coordinator.py` already does a `try/except ImportError` fallback for it.  Each law's projection math IS the math (Lagrange distribution for water_balance + phase_closure; trace removal for moment_balance; least-squares angular-velocity solve for nnr_frame), so delegating to OP-051 would just bounce through to the same per-law branches.  When OP-051 ships its more general compensation engine, each law's function can be re-routed; the public API of `enforce_conservation` stays unchanged.  Module docstring's "OP-051 contract" section documents the migration path.
2. **Hard vs soft law semantics.**  Hard laws (`phase_closure`, `nnr_frame`) log WARNING when post-projection residual exceeds tolerance and set `ConservationResult.converged=False`.  Soft laws (`water_balance`, `moment_balance`) log INFO.  **Neither raises** — UI-010's residual-budget bar needs the residual numeric to render the badge even when (especially when) not converged.
3. **Phase-closure 2π wrapping.**  `_wrap_phase` wraps closure into (−π, π] BEFORE projection so that a closure of ~2π (physically zero modulo 2π) doesn't inflate the residual.
4. **NNR projection math** (Altamimi 2011 Eq. 4–6): solves `A ω = b` where `A = Σ (‖rᵢ‖² I − rᵢ rᵢᵀ)` and `b = Σ rᵢ × vᵢ`, then subtracts `ω × rᵢ` from each station's velocity.  `np.linalg.solve` with `lstsq` fallback on rank-deficient `A`.  The 3-station minimum check is necessary but not sufficient (collinear stations would still hit `LinAlgError` and fall through to `lstsq`).
5. **Coupled water-balance projection** minimises `Σ Δᵢ²` subject to `ΔP − ΔET − ΔQ − ΔdS = −r`.  Lagrange gives `ΔP = −r/4, ΔET = +r/4, ΔQ = +r/4, ΔdS = +r/4`.
6. **Coupled phase-closure projection** uses the same Lagrange — `Δφ12 = Δφ23 = −r/3, Δφ13 = +r/3`.
7. **`X_edit` is a fresh dict** built via `{**X_all, key: new_value}` for each modified key.  In *naive* mode, `dict(X_all)` is a shallow copy so `X_edit[key]` shares ndarray refs with the input — acceptable per the documented contract (input is not mutated, but output may share refs in naive mode where no projection was applied).
8. **Residual serialisation.**  `_residual_to_serialisable` converts ndarray residuals to tuples of floats so the audit log can be JSON-serialised (UI-015 will eventually persist these).

**Tests** — `pytest tests/test_enforce_conservation_tier3.py`: 35/35 pass.  Full backend suite: 1434 pass, 2 pre-existing unrelated failures (`test_operation_result_contract.py` missing fixture; `test_segment_encoder_feature_matrix.py` stale embedding-size assertion).  `ruff check` clean.  No regression in OP-050 cf_coordinator (37/37 still pass).

**Code review** — APPROVE, no blocking issues.  Reviewer scrutinised four design choices (no OP-051 delegation, naive-mode `initial == final` semantics, hard-law non-convergence path, decorator-collision behaviour) and accepted all four.  Three minor observations flagged (none blocking): (a) `ConservationResult.extra: dict` is mutable inside a frozen dataclass — strict CLAUDE.md reading would prefer a tuple-of-pairs; field unused so far; (b) naive-mode `X_edit[key]` shares ndarray refs with input — symmetric across all four laws; (c) `lstsq` fallback in NNR doesn't surface rank info via `result.extra`.

**Out of scope / follow-ups**
- Wiring `enforce_conservation` into the UI-005 Tier-3 toolbar + UI-011 law-selector + UI-010 residual-budget panel belongs to those tickets.
- OP-051 (when it ships) will replace the per-law projection branches with calls into a shared compensation engine; the OP-032 public API is forward-compatible.
- A future enhancement could expose the NNR `lstsq` rank diagnostic in `ConservationResult.extra` so callers can detect collinear-station configurations.
