# OP-021 — Trend Tier-2 ops (6 ops)

**Status:** [x] Done
**Depends on:** SEG-013 (ETM) or SEG-017 (LandTrendr) blob, OP-040 (relabeler)

---

## Goal

Implement the 6 Trend-specific Tier-2 ops: `flatten`, `reverse_direction`, `change_slope`, `linearise`, `extrapolate`, `add_acceleration`. Each edits the blob's `linear_rate` coefficient (ETM) or per-segment slopes (LandTrendr) directly.

**How it fits:** Gated in UI-005 when active shape is `trend`. `flatten` → plateau (DETERMINISTIC); `change_slope(α=0)` → plateau; all others preserve trend.

---

## Paper references (for `algorithm-auditor`)

- Sen (1968) "Estimates of the regression coefficient based on Kendall's tau" — *JASA* 63(324):1379 (Theil–Sen for robust `linearise`).
- Kennedy et al. (2010) — LandTrendr piecewise coefficients.
- Bevis & Brown (2014) — ETM linear-rate coefficient.

---

## Pseudocode

```python
def flatten(blob, t):
    beta = blob.coefficients['linear_rate']
    blob.coefficients['linear_rate'] = 0.0
    blob.components['linear_rate'] = np.zeros_like(t)
    return blob.reassemble()     # → plateau (DETERMINISTIC)

def reverse_direction(blob, t):
    blob.coefficients['linear_rate'] *= -1
    blob.components['linear_rate']   *= -1
    return blob.reassemble()     # → trend (PRESERVED)

def change_slope(blob, alpha, t):
    blob.coefficients['linear_rate'] *= alpha
    blob.components['linear_rate']   *= alpha
    return blob.reassemble()     # → trend, or plateau if alpha == 0

def linearise(blob, X_orig, t):
    from scipy.stats import theilslopes
    slope, intercept, _, _ = theilslopes(X_orig, t)
    blob.method = 'ETM'
    blob.coefficients = {'x0': intercept, 'linear_rate': slope}
    blob.components   = {'x0': np.full_like(t, intercept),
                         'linear_rate': slope * (t - t[0])}
    return blob.reassemble()

def extrapolate(blob, t_extended):
    beta = blob.coefficients['linear_rate']
    x0   = blob.coefficients['x0']
    return x0 + beta * (t_extended - t_extended[0])

def add_acceleration(blob, c, t):
    accel = c * (t - t[0]) ** 2
    blob.coefficients['acceleration'] = c
    blob.components['acceleration']   = accel
    return blob.reassemble()
```

---

## Acceptance Criteria

- [x] `backend/app/services/operations/tier2/trend.py` with all 6 ops
- [x] `linearise` uses Theil–Sen robust slope (scipy.stats.theilslopes), not OLS
- [x] `flatten` and `change_slope(α=0)` produce identical reassembled series (asserted by test)
- [x] `extrapolate` accepts `t_extended` that may extend beyond the original segment; uses absolute t convention
- [x] `add_acceleration` preserves trend shape; PRESERVED('trend') default
- [x] Works with both ETM blob (SEG-013) and LandTrendr blob (SEG-017): dispatcher selects by `blob.method`
- [x] For LandTrendr blobs, slope edits apply to the per-segment slope list; `linearise` collapses vertices to 2 endpoints
- [x] Tests cover each op with synthetic trend fixtures; `linearise` robustness test with outliers; non-zero t_extended extrapolation tests
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass (47 new, 857 full suite)
- [x] Run `code-reviewer` agent — 2 blocking issues fixed (extrapolate absolute-t formula, _scale fallback)
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-021: Trend Tier-2 ops (6 ops)"` ← hook auto-moves this file to `done/` on commit

## Result Report

Created `backend/app/services/operations/tier2/trend.py` with `flatten`, `change_slope`, `reverse_direction`, `linearise`, `extrapolate`, `add_acceleration`. `flatten` delegates to `change_slope(alpha=0)` guaranteeing identical output. `linearise` uses Theil-Sen (Sen 1968) via `scipy.stats.theilslopes`; residual excluded from components so `reassemble()` returns the clean fitted line. `extrapolate` uses absolute-t convention (`x0 + rate*t_ext`, not `t_ext - t_ext[0]`) for both ETM and LandTrendr. LandTrendr `change_slope(0)` / `flatten` collapses to Constant method to avoid intercept step artifact. All ops deepcopy internally. 47 tests including non-zero-start extrapolation and Theil-Sen outlier robustness. AuditEvent deferred to OP-041.
