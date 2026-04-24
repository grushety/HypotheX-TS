# SEG-018 — Decomposition fitter: GrAtSiD (geodesy transients)

**Status:** [ ] Done
**Depends on:** SEG-019, SEG-013 (ETM complementary)

---

## Goal

Fit Bedford–Bevis Greedy Automatic Signal Decomposition (GrAtSiD) to extract overlapping transient features from GNSS-like series. Output is a named list of basis features `(type, t_ref, τ, amplitude)` editable by OP-025 Tier-2 transient operations.

**Why:** Transient segments in geodesy often overlap (SSEs, postseismic relaxation, volcanic inflation) and cannot be resolved by a single ETM fit. GrAtSiD's greedy basis-selection loop iteratively extracts the strongest residual-reducing basis function, producing a clean feature list that OP-025 can edit directly (amplify, shift_time, change_decay_constant, etc.).

**How it fits:** Dispatched by SEG-019 when `shape='transient'` and `domain_hint='seismo-geodesy'`. Complements SEG-013 ETM: ETM fits the linear + seasonal + known-step skeleton; GrAtSiD fills in the transient features against the residual.

---

## Paper references (for `algorithm-auditor`)

- Bedford & Bevis (2018) "Greedy Automatic Signal Decomposition and Its Application to Daily GPS Time Series" — *JGR Solid Earth* 123:6901–6919. DOI 10.1029/2017JB014765.
- Klos, Olivares, Teferle, Hunegnaw, Bogusz (2018) "On the combined effect of periodic signals and colored noise on velocity uncertainties" — *GPS Solutions* 22:1 (context for colored-noise treatment).

---

## Pseudocode

```python
def fit_gratsid(X_seg, t,
                basis_types=('log', 'exp', 'step'),
                tau_grid=None,
                max_features=30,
                residual_threshold=0.05):
    if tau_grid is None:
        tau_grid = np.logspace(0, 3, 20)   # 1 to 1000 days

    # Subtract linear + seasonal skeleton first
    skeleton = fit_linear_plus_seasonal(X_seg, t)
    residual = X_seg - skeleton

    features = []
    for iteration in range(max_features):
        best_basis = None
        best_score = 0
        for btype in basis_types:
            for t_ref in candidate_t_refs(residual):
                for tau in tau_grid:
                    b = basis(btype, t_ref, tau, t)
                    amplitude = np.dot(b, residual) / (np.dot(b, b) + 1e-12)
                    score = abs(amplitude) * np.linalg.norm(b)
                    if score > best_score:
                        best_score = score
                        best_basis = (btype, t_ref, tau, amplitude)

        if best_score / np.linalg.norm(residual) < residual_threshold:
            break

        btype, t_ref, tau, amplitude = best_basis
        features.append({'type': btype, 't_ref': t_ref, 'tau': tau, 'amplitude': amplitude})
        residual -= amplitude * basis(btype, t_ref, tau, t)

    return DecompositionBlob(
        method='GrAtSiD',
        components={
            'skeleton': skeleton,
            'features': features,
            'residual': residual,
        },
        coefficients={'features': features, 'n_features': len(features)},
        residual=residual,
        fit_metadata={'rmse': float(np.sqrt(np.mean(residual**2))),
                      'n_features': len(features)}
    )
```

---

## Acceptance Criteria

- [ ] `backend/app/services/decomposition/gratsid_fitter.py` with:
  - `fit_gratsid(X_seg, t, basis_types, tau_grid, max_features, residual_threshold) -> DecompositionBlob`
  - Helper `basis(btype, t_ref, tau, t)` supporting 'log', 'exp', 'step' types
  - `candidate_t_refs(residual)` generator returning timesteps in top-k residual-energy regions
- [ ] Greedy loop stops when residual-reduction below `residual_threshold` OR `max_features` reached
- [ ] Returns named features `{type, t_ref, tau, amplitude}` — each editable by OP-025
- [ ] Unit test: synthetic signal with 3 superposed log transients at known `(t_ref, τ, A)` → recovers all 3 within 10 % amplitude tolerance and ±5 timesteps on t_ref
- [ ] Compatible with ETM output format (SEG-013): if SEG-013 already ran, GrAtSiD takes `X_seg − ETM_skeleton` as input and appends features
- [ ] Prevents duplicate basis selection (same `(t_ref, τ)` family within ±10 % τ) per Bedford 2018 §3 guidance
- [ ] Tests cover: recovery of synthetic features, stopping-rule (max_features and residual_threshold), no duplicate features, empty-input handling
- [ ] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper reference: Bedford & Bevis 2018 §3 (greedy selection criterion, basis library, stopping rule, duplicate-feature suppression). Confirm greedy does not produce duplicate basis functions from the same (t_ref, τ) family beyond paper's guidance
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-018: GrAtSiD fitter for geodesy transients (Bedford-Bevis 2018)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
