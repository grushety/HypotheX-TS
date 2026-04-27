# OP-013 — Tier 1 stochastic atoms: suppress, add_uncertainty

**Status:** [x] Done
**Depends on:** SEG-014 (STL trend fill), SEG-016 (Eckhardt baseflow fill)

---

## Goal

Implement `suppress` (replace segment with an inferred baseline via one of 5 fill strategies) and `add_uncertainty` (inject calibrated colored noise).

**Why:** These two atoms together let users express "what if this segment were missing / typical / noisier?" — both common what-if questions that no single shape primitive covers. Separating them as Tier-1 atoms avoids duplication across shape-specific ops.

**How it fits:** Called from UI-005 palette directly, and composed into Tier-2 ops like Spike `remove` (uses `suppress`) and Noise `inject_synthetic` (uses `add_uncertainty`).

---

## Paper references (for `algorithm-auditor`)

- Timmer & König (1995) "On generating power law noise" — *A&A* 300:707 (colored-noise PSD generator). Library: `colorednoise`.
- Cleveland, Cleveland, McRae, Terpenning (1990) — STL (trend-as-fill strategy).
- Eckhardt (2005) — baseflow (baseline-as-fill strategy for hydrology).

---

## Pseudocode

```python
def suppress(X_seg, ctx_pre, ctx_post, strategy, aux=None):
    if strategy == 'linear':
        return np.linspace(X_seg[0] if len(ctx_pre) == 0 else np.mean(ctx_pre[-3:]),
                           X_seg[-1] if len(ctx_post) == 0 else np.mean(ctx_post[:3]),
                           len(X_seg))
    if strategy == 'spline':
        from scipy.interpolate import CubicSpline
        t_known = np.concatenate([np.arange(-len(ctx_pre), 0), np.arange(len(X_seg), len(X_seg) + len(ctx_post))])
        y_known = np.concatenate([ctx_pre, ctx_post])
        return CubicSpline(t_known, y_known)(np.arange(len(X_seg)))
    if strategy == 'stl_trend':
        from statsmodels.tsa.seasonal import STL
        full = np.concatenate([ctx_pre, X_seg, ctx_post])
        trend = STL(full, period=aux['period']).fit().trend
        return trend[len(ctx_pre) : len(ctx_pre) + len(X_seg)]
    if strategy == 'climatology':
        return aux['doy_climatology'][aux['dates_in_segment']]
    if strategy == 'baseflow':
        from backend.app.services.decomposition.eckhardt_fitter import eckhardt_baseflow
        full = np.concatenate([ctx_pre, X_seg, ctx_post])
        b = eckhardt_baseflow(full, **aux).components['baseflow']
        return b[len(ctx_pre) : len(ctx_pre) + len(X_seg)]
    raise ValueError(f"unknown fill strategy: {strategy}")

def add_uncertainty(X_seg, sigma: float, color: Literal['white', 'pink', 'red'] = 'white',
                    seed: int | None = None):
    rng = np.random.default_rng(seed)
    if color == 'white':
        noise = rng.normal(0, sigma, len(X_seg))
    else:
        import colorednoise                        # Timmer & König 1995
        beta = {'pink': 1.0, 'red': 2.0}[color]
        noise = colorednoise.powerlaw_psd_gaussian(beta, len(X_seg), random_state=rng) * sigma
    return X_seg + noise
```

---

## Acceptance Criteria

- [x] `backend/app/services/operations/tier1/stochastic.py` with `suppress` and `add_uncertainty`
- [x] `suppress` supports all 5 fill strategies: `linear`, `spline`, `stl_trend`, `climatology`, `baseflow`
- [x] `add_uncertainty` supports white (normal), pink (1/f), red (Brownian) via Timmer–König power-law-PSD generator
- [x] Deterministic mode: when `seed` is provided, output is bit-identical across runs
- [x] Fill strategy `stl_trend` delegates to SEG-014; `baseflow` delegates to SEG-016 — no fill logic duplicated
- [x] Default fill strategy per domain hint: `climatology` for remote-sensing, `baseflow` for hydrology, `linear` otherwise
- [x] `colorednoise` added to `backend/requirements.txt`
- [x] Tests cover: each fill strategy reproduces expected output on fixture; `add_uncertainty` white-noise variance matches σ²; seed reproducibility; spectral test for pink/red noise (slope of log-log PSD)
- [x] `pytest backend/tests/ -x` passes

## Known gaps / deferred

- **AuditEvent emission**: `suppress` and `add_uncertainty` do not emit `AuditEvent` directly. All Tier-1 atoms are pure functions; audit emission is the responsibility of the orchestration layer. This is consistent with `amplitude.py` and `time.py` (OP-010/011). Tracked for resolution in OP-041 (relabeler + label chip), which wires the orchestration layer that calls Tier-1 atoms and emits events.

## Definition of Done
- [x] Run `tester` agent — all tests pass (53 passed, 758 full suite)
- [x] Run `code-reviewer` agent — no blocking issues (3 fixed: frozen DTO, climatology error handling, audit deferral recorded)
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-013: Tier-1 stochastic atoms (suppress/add_uncertainty)"` ← hook auto-moves this file to `done/` on commit

## Result Report

Implemented `suppress` (5 fill strategies) and `add_uncertainty` (white/pink/red noise) in `tier1/stochastic.py`. 53 tests pass. Reviewer fixes applied: `StochasticOpResult` is now `frozen=True, eq=False`; climatology dict/array lookups raise `ValueError` on missing key/OOB; zero-fill in colored-noise path logs a WARNING. AuditEvent emission deferred to OP-041 (consistent with sibling OP-010/011/012 atoms).
