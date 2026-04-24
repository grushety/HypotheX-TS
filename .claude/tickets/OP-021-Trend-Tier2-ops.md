# OP-021 — Trend Tier-2 ops (6 ops)

**Status:** [ ] Done
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

- [ ] `backend/app/services/operations/tier2/trend.py` with all 6 ops
- [ ] `linearise` uses Theil–Sen robust slope (scipy.stats.theilslopes), not OLS
- [ ] `flatten` and `change_slope(α=0)` produce identical reassembled series (asserted by test)
- [ ] `extrapolate` accepts `t_extended` that may extend beyond the original segment
- [ ] `add_acceleration` preserves trend shape unless sign flip at boundary (relabeler checks); chooses `trend` as PRESERVED default
- [ ] Works with both ETM blob (SEG-013) and LandTrendr blob (SEG-017): dispatcher selects by `blob.method`
- [ ] For LandTrendr blobs, slope edits apply to the per-segment slope list; `linearise` collapses vertices to 2 endpoints
- [ ] Tests cover each op with synthetic trend fixtures; assert coefficient edits match expected; `linearise` robustness test with outliers
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper references: Sen 1968 (Theil-Sen formula), Kennedy 2010 (piecewise editing). Confirm `linearise` uses robust slope estimate; LandTrendr vertices retained when editable
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "OP-021: Trend Tier-2 ops (6 ops)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
