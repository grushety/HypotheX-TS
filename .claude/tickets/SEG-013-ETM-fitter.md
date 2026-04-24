# SEG-013 — Decomposition fitter: ETM (Extended Trajectory Model)

**Status:** [ ] Done
**Depends on:** SEG-019 (decomposition blob schema)

---

## Goal

Fit the Bevis–Brown Extended Trajectory Model (ETM) decomposition to a segment labeled `trend`, `step`, or `transient` — the standard parametric model for GNSS and geodesy-type series. Emit into the decomposition blob (SEG-019) so downstream Tier-2 operations (OP-021, OP-022, OP-025) can edit coefficients directly.

Model (Bevis & Brown 2014, Eq. 1):

```
x(t) = x₀ + v · t
     + Σ Hᵢ(t − t_s,i) · Δᵢ                         (Heaviside steps)
     + Σⱼ [aⱼ · log(1 + (t − t_r,j)/τⱼ) + bⱼ · exp(-(t − t_r,j)/τⱼ)]   (transients)
     + Σₖ [cₖ · sin(2πt/Tₖ) + dₖ · cos(2πt/Tₖ)]      (harmonics)
     + ε(t)
```

**Why:** ETM is the canonical parametric decomposition for geodesy; by storing the coefficients explicitly in the decomposition blob, every Tier-2 op becomes a named coefficient edit ("raise interseismic rate v", "add Heaviside offset at t_s", "extend transient τ"). This is the mechanism behind the decomposition-first CF architecture.

**How it fits:** Dispatched by SEG-019's shape-driven fitter registry: `trend` or `step` or `transient` + domain_hint ∈ {'geodesy', 'seismo-geodesy', default} → ETM. Used by OP-021 (Trend ops), OP-022 (Step ops), and OP-025 (Transient ops).

---

## Paper references (for `algorithm-auditor`)

- Bevis & Brown (2014) "Trajectory models and reference frames for crustal motion geodesy" — *J. Geodesy* 88:283–311. DOI 10.1007/s00190-013-0685-5.
- Bedford & Bevis (2018) "Greedy Automatic Signal Decomposition" — *JGR Solid Earth* 123:6901 (related; see SEG-018).

---

## Pseudocode

```python
def fit_etm(X_seg, t, known_steps=None, known_transients=None,
            harmonic_periods=(365.25, 182.625)):
    """
    known_steps: list of t_s (step epochs; user-provided or from change-point detector)
    known_transients: list of (t_ref, tau, basis in {'log', 'exp', 'both'})
    """
    cols = [np.ones_like(t), t]          # x_0, v
    labels = ['x0', 'linear_rate']

    for t_s in (known_steps or []):
        cols.append(heaviside(t - t_s))
        labels.append(f'step_at_{t_s}')

    for (t_ref, tau, basis) in (known_transients or []):
        if basis in ('log', 'both'):
            cols.append(np.log1p(np.maximum(0, (t - t_ref) / tau)))
            labels.append(f'log_{t_ref}_tau{tau}')
        if basis in ('exp', 'both'):
            cols.append(np.exp(-np.maximum(0, t - t_ref) / tau))
            labels.append(f'exp_{t_ref}_tau{tau}')

    for T in harmonic_periods:
        cols.append(np.sin(2 * np.pi * t / T))
        cols.append(np.cos(2 * np.pi * t / T))
        labels.extend([f'sin_{T}', f'cos_{T}'])

    A = np.column_stack(cols)
    coeffs, residuals, rank, _ = np.linalg.lstsq(A, X_seg, rcond=None)
    fitted = A @ coeffs
    residual = X_seg - fitted

    return DecompositionBlob(
        method='ETM',
        components={label: coeffs[i] * A[:, i] for i, label in enumerate(labels)},
        coefficients={labels[i]: float(coeffs[i]) for i in range(len(labels))},
        residual=residual,
        fit_metadata={'rmse': float(np.sqrt(np.mean(residual**2))),
                      'rank': int(rank),
                      'n_params': len(labels)}
    )
```

---

## Acceptance Criteria

- [ ] `backend/app/services/decomposition/etm_fitter.py` with:
  - `fit_etm(X_seg, t, known_steps=None, known_transients=None, harmonic_periods=(365.25, 182.625)) -> DecompositionBlob`
  - Pure function; no hidden state
  - Handles multivariate `X_seg` by fitting per-component and stacking coefficients
- [ ] Reassembled signal `sum(blob.components.values())` matches original within `blob.fit_metadata.rmse`
- [ ] Coefficients named per Bevis–Brown Eq. 1 terms: `x0`, `linear_rate`, `step_at_{t}`, `log_{t}_tau{τ}`, `exp_{t}_tau{τ}`, `sin_{T}`, `cos_{T}`
- [ ] Unit test: synthetic series `3 + 0.5·t + H(t−50)·2 + 1.2·log(1 + (t−60)/20)` + annual harmonic + Gaussian noise → coefficients recovered within 5 % of true values
- [ ] Residual is stored in the blob (not discarded); Tier-2 ops that touch residual (e.g. add_uncertainty) read it directly
- [ ] `harmonic_periods` configurable; default is annual + semi-annual (geodesy convention)
- [ ] Known steps and transients provided by SEG-009 boundary proposer output or SEG-018 GrAtSiD detection; if None, design matrix has only linear + harmonic terms
- [ ] `DecompositionBlob.fit_metadata` includes RMSE, rank, n_params for auditability
- [ ] Tests cover: perfect recovery of synthetic signal (RMSE < 1e-6 noise-free), graceful handling of ill-conditioned design matrix (too few samples), multivariate input, reassembly round-trip
- [ ] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper reference: Bevis & Brown 2014 Eq. 1 and §2. Verify each component term (linear, Heaviside step, log/exp transient, harmonic) implemented per paper and coefficient names match paper convention
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-013: ETM decomposition fitter (Bevis-Brown 2014)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
