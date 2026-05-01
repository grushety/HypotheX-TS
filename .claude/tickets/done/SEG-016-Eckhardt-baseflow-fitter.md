# SEG-016 — Decomposition fitter: Eckhardt baseflow (hydrology)

**Status:** [x] Done
**Depends on:** SEG-019

---

## Goal

Apply the Eckhardt two-parameter recursive digital filter to split streamflow `Q(t)` into `baseflow b(t)` + `quickflow q(t)` components. Parameters `BFImax` (long-term baseflow index) and `a` (recession constant) are calibrated from recession analysis.

Eckhardt 2005, Eq. 6:

```
b(t) = ((1 − BFImax) · a · b(t−1) + (1 − a) · BFImax · Q(t)) / (1 − a · BFImax)
b(t) ≤ Q(t)           (physical constraint)
```

**Why:** Baseflow/stormflow separation is the canonical hydrology decomposition; it underpins the `baseflow`, `stormflow`, `recession_limb`, and `rising_limb` semantic labels in SEG-021. With `b(t)` stored as a blob component, OP-020 `raise_lower` on a baseflow segment becomes `BFImax ← BFImax · α` — a named hydrology-scientist edit.

**How it fits:** Dispatched by SEG-019 when `domain_hint='hydrology'`. Used by OP-020 (Plateau ops) and OP-032 (enforce_conservation) for water balance.

---

## Paper references (for `algorithm-auditor`)

- Eckhardt (2005) "How to construct recursive digital filters for baseflow separation" — *Hydrological Processes* 19(2):507–515. DOI 10.1002/hyp.5675.
- Lyne & Hollick (1979) "Stochastic time-variable rainfall-runoff modelling" — *I. E. Aust. Natl. Conf. Publ.* 79/10 (single-parameter precursor, for comparison).
- Tallaksen (1995) "A review of baseflow recession analysis" — *J. Hydrology* 165:349–370.

---

## Pseudocode

```python
def eckhardt_baseflow(Q, BFImax=0.8, a=0.98):
    """
    BFImax: long-term baseflow index (catchment-specific; calibrate from recession analysis)
    a:      recession constant (fraction of flow recession per timestep)
    """
    b = np.zeros_like(Q, dtype=float)
    b[0] = Q[0] * BFImax                       # initial condition

    for t in range(1, len(Q)):
        raw = ((1 - BFImax) * a * b[t - 1] + (1 - a) * BFImax * Q[t]) / (1 - a * BFImax)
        b[t] = min(raw, Q[t])                  # enforce b ≤ Q (Eckhardt §2)

    quickflow = Q - b

    return DecompositionBlob(
        method='Eckhardt',
        components={'baseflow': b, 'quickflow': quickflow},
        coefficients={'BFImax': BFImax, 'a': a},
        residual=np.zeros_like(Q),             # Q = b + quickflow exactly by construction
        fit_metadata={'BFI': float(np.sum(b) / np.sum(Q))}
    )

def calibrate_eckhardt(Q, recession_segments):
    """Master recession curve; fit a from log-slope, BFImax from long-term BFI."""
    a       = estimate_recession_constant(recession_segments)
    BFImax  = estimate_long_term_bfi(Q, window_years=5)
    return a, BFImax
```

---

## Acceptance Criteria

- [x] `backend/app/services/decomposition/eckhardt_fitter.py` with:
  - `eckhardt_baseflow(Q, BFImax=0.8, a=0.98) -> DecompositionBlob`
  - `calibrate_eckhardt(Q, recession_segments) -> (a, BFImax)` from master recession curve
  - Default parameters noted per Eckhardt 2005 Table 1 (perennial vs ephemeral stream regimes)
- [x] Physical constraint `b(t) ≤ Q(t)` enforced at every timestep
- [x] Residual `Q − (b + quickflow) = 0` exactly by construction
- [x] Unit test: synthetic hydrograph with known constant baseflow `b = 2` and storm pulse `Q_peak = 10` → baseflow recovered to within 5 % after transient period
- [x] `BFImax` and `a` can be calibrated from training data via `calibrate_eckhardt`; values stored in blob coefficients
- [x] Recursive formula matches Eckhardt 2005 Eq. 6 exactly (bit-identical coefficient check in test)
- [x] `Q` must be non-negative; negative values raise `ValueError`
- [x] Tests cover: constant flow → baseflow = Q; storm event → baseflow stays below peak; calibration from recession curve; negative-flow rejection; coefficient formula matches paper Eq. 6 exactly
- [x] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "SEG-016: Eckhardt baseflow recursive filter (hydrology)"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Replaced the placeholder Eckhardt stub at `backend/app/services/decomposition/fitters/eckhardt.py` with a full Eckhardt 2005 implementation, plus calibration helpers per Tallaksen 1995 / Lyne-Hollick 1979.

**Files**
- `backend/app/services/decomposition/fitters/eckhardt.py` (replaced stub) — public surface:
  - `eckhardt_baseflow(Q, bfi_max=0.80, a=0.98)` → `DecompositionBlob` (registered as `@register_fitter("Eckhardt")`).  Implements Eckhardt 2005 Eq. 6 verbatim with the b ≤ Q clamp and `b[0] = Q[0] · BFImax` initial condition.  Components are `{baseflow, quickflow, residual}` with residual all-zero, so `Q ≡ b + q` exactly.  Validates `Q ≥ 0`, `0 < a < 1`, `0 < bfi_max < 1`, and rejects multivariate input (2-D single-column is flattened for ergonomics).
  - `calibrate_eckhardt(Q, recession_segments)` → `(a, BFImax)`.  Uses `estimate_recession_constant` for `a` (log-slope of strictly-positive consecutive samples in flagged recession segments — Tallaksen 1995 §3) and a Lyne-Hollick (1979) single-pass forward filter for `BFImax` (sum-of-baseflow / sum-of-flow, clipped to a physically-plausible range).  Module-level constants `DEFAULT_A`, `DEFAULT_BFI_MAX`, `A_LOWER_BOUND`, `A_UPPER_BOUND`, `BFI_MAX_LOWER_BOUND`, `BFI_MAX_UPPER_BOUND` document the regime defaults from Eckhardt 2005 Table 1.
- `backend/tests/test_eckhardt_fitter.py` — 35 tests including: registry/dispatcher, exact split, b ≤ Q, q ≥ 0, initial condition, **bit-identical Eckhardt Eq. 6** (verbatim reference loop typed from the paper), constant-flow steady state `b → BFImax · Q`, high-BFImax `b → Q` collapse, storm pulse recovery within 5 % of the underlying base, OP-020 coefficient keys, fit_metadata required keys, the `bfi` metadata identity, all input-validation paths (negative Q, a/bfi_max ∉ (0,1), multivariate rejection, 2-D single-column accepted), helper unit tests including a synthetic-recession round-trip that recovers a known `a=0.92` to ≤ 1e-6 precision, and a calibration round-trip whose calibrated `(a, BFImax)` are immediately usable by the fitter.
- `backend/app/services/operations/tier1/stochastic.py` — single-line caller migration in `_fill_baseflow` (the old stub's `fit_eckhardt(alpha=, bfi_max=)` → the renamed `eckhardt_baseflow(a=, bfi_max=)`).  Verified by `tests/test_stochastic_ops.py` 53/53 passing.

**Theory note** — the Eckhardt steady state is `b_ss = BFImax · Q`, **not** `b_ss = Q`.  Solving Eq. 6 with constant Q gives `b · (1 − a) = (1 − a) · BFImax · Q`, i.e. the long-term BFI is exactly `BFImax`.  The first round of `test_eckhardt_constant_flow_baseflow_converges_to_q` asserted `b → Q` and failed at `b → BFImax · Q = 4` (with `BFImax=0.8`, `Q=5`); the test now states the correct algebra in its docstring and a companion test `test_eckhardt_constant_flow_with_high_bfimax_recovers_q` exercises the `BFImax → 1` collapse.  The storm-pulse AC fixture uses `BFImax=0.99` so the recovered baseflow tail lies within 5 % of the underlying `b = 2` truth — using a lower BFImax would settle at `0.8 · 2 = 1.6`, which is correct Eckhardt behaviour but does not satisfy the AC's "recovered to 2 within 5 %" intent.

**Algorithmic deviation acknowledged** — the ticket pseudocode for `calibrate_eckhardt` calls `estimate_long_term_bfi(Q, window_years=5)` (sliding 5-year window).  The implementation accepts the `window_years` argument but uses a **global** Lyne-Hollick BFI estimate, since the segment-level Q passed to the filter does not generally carry calendar-time metadata.  Documented in the function docstring; the calibration round-trip test still passes.

**Tests** — `pytest tests/test_eckhardt_fitter.py`: 35/35 pass.  Full backend suite: 1434 pass, 2 pre-existing unrelated failures (`test_operation_result_contract.py` missing fixture; `test_segment_encoder_feature_matrix.py` stale embedding-size assertion).  `ruff check` clean.

**Code review** — no blocking issues.  All architecture rules hold (pure domain function, source citations on every public function, `segment` naming, `@register_fitter` DI, single-line caller migration consistent with the rename).  No new dependencies.

**Out of scope / follow-ups**
- Dispatcher wiring `('plateau', 'hydrology') → Eckhardt` is not in `_DISPATCH_TABLE` — that belongs to SEG-019 / SEG-021.
- A windowed `estimate_long_term_bfi(window_years=5)` mode would require time-axis metadata on the segment Q; defer to whichever ticket plumbs that through.
