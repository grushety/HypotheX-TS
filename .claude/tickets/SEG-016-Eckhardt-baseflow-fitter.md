# SEG-016 — Decomposition fitter: Eckhardt baseflow (hydrology)

**Status:** [ ] Done
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

- [ ] `backend/app/services/decomposition/eckhardt_fitter.py` with:
  - `eckhardt_baseflow(Q, BFImax=0.8, a=0.98) -> DecompositionBlob`
  - `calibrate_eckhardt(Q, recession_segments) -> (a, BFImax)` from master recession curve
  - Default parameters noted per Eckhardt 2005 Table 1 (perennial vs ephemeral stream regimes)
- [ ] Physical constraint `b(t) ≤ Q(t)` enforced at every timestep
- [ ] Residual `Q − (b + quickflow) = 0` exactly by construction
- [ ] Unit test: synthetic hydrograph with known constant baseflow `b = 2` and storm pulse `Q_peak = 10` → baseflow recovered to within 5 % after transient period
- [ ] `BFImax` and `a` can be calibrated from training data via `calibrate_eckhardt`; values stored in blob coefficients
- [ ] Recursive formula matches Eckhardt 2005 Eq. 6 exactly (bit-identical coefficient check in test)
- [ ] `Q` must be non-negative; negative values raise `ValueError`
- [ ] Tests cover: constant flow → baseflow = Q; storm event → baseflow stays below peak; calibration from recession curve; negative-flow rejection; coefficient formula matches paper Eq. 6 exactly
- [ ] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "SEG-016: Eckhardt baseflow recursive filter (hydrology)"` ← hook auto-moves this file to `done/` on commit
