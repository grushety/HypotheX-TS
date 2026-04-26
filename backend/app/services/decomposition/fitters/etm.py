"""ETM (Extended Trajectory Model) fitter — Bevis & Brown (2014), Eq. 1.

Models a segment as:

    x(t) = x₀ + v·t
          + Σᵢ Δᵢ · H(t − t_s,i)
          + Σⱼ [aⱼ · log(1 + max(0, (t−t_r,j)/τⱼ))
               + bⱼ · exp(−max(0, (t−t_r,j)/τⱼ))]
          + Σₖ [cₖ · sin(2πt/Tₖ) + dₖ · cos(2πt/Tₖ)]
          + ε(t)

Reference
---------
Bevis, M. & Brown, S. (2014). Trajectory models and reference frames for
crustal motion geodesy. J. Geodesy 88:283–311.
DOI 10.1007/s00190-013-0685-5.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter


# ---------------------------------------------------------------------------
# Design-matrix builders
# ---------------------------------------------------------------------------


def _heaviside(t: np.ndarray, t_s: float) -> np.ndarray:
    """Unit Heaviside step: H(t − t_s)."""
    return (t >= t_s).astype(np.float64)


def build_etm_design_matrix(
    t: np.ndarray,
    known_steps: list[float] | None,
    known_transients: list[tuple[float, float, str]] | None,
    harmonic_periods: Sequence[float],
) -> tuple[np.ndarray, list[str]]:
    """Build the ETM design matrix and coefficient labels.

    Bevis & Brown (2014) Eq. 1.  Returns (A, labels) where A has
    shape (n, p) and len(labels) == p.
    """
    cols: list[np.ndarray] = []
    labels: list[str] = []

    # x₀ and v·t — always present
    cols.append(np.ones_like(t))
    labels.append("x0")
    cols.append(t.copy())
    labels.append("linear_rate")

    # Heaviside steps: Δᵢ · H(t − t_s,i)
    for t_s in (known_steps or []):
        cols.append(_heaviside(t, float(t_s)))
        labels.append(f"step_at_{float(t_s):.6g}")

    # Transients: aⱼ·log(1 + (t-t_r)/τ) and/or bⱼ·exp(-(t-t_r)/τ)
    for t_ref, tau, basis in (known_transients or []):
        t_ref, tau = float(t_ref), max(float(tau), 1e-12)
        pos = np.maximum(0.0, (t - t_ref) / tau)
        if basis in ("log", "both"):
            cols.append(np.log1p(pos))
            labels.append(f"log_{t_ref:.6g}_tau{tau:.6g}")
        if basis in ("exp", "both"):
            cols.append(np.exp(-pos))
            labels.append(f"exp_{t_ref:.6g}_tau{tau:.6g}")

    # Harmonics: cₖ·sin(2πt/Tₖ) + dₖ·cos(2πt/Tₖ)
    for T in harmonic_periods:
        T = max(float(T), 1e-12)
        phase = 2.0 * np.pi * t / T
        cols.append(np.sin(phase))
        labels.append(f"sin_{T:.6g}")
        cols.append(np.cos(phase))
        labels.append(f"cos_{T:.6g}")

    return np.column_stack(cols), labels


# ---------------------------------------------------------------------------
# Single-channel fitting
# ---------------------------------------------------------------------------


def _fit_1d(
    X: np.ndarray,
    t: np.ndarray,
    known_steps: list[float] | None,
    known_transients: list[tuple[float, float, str]] | None,
    harmonic_periods: Sequence[float],
) -> tuple[dict[str, np.ndarray], dict[str, float], np.ndarray, dict]:
    """OLS fit of the ETM to a single 1-D segment.

    Returns (components, coefficients, residual, fit_metadata).
    component arrays sum to X (fitted + residual).
    """
    A, labels = build_etm_design_matrix(t, known_steps, known_transients, harmonic_periods)
    n, p = A.shape

    # Under-determined: too few samples for the design matrix
    if n < p:
        level = float(np.mean(X))
        fitted = np.full(n, level, dtype=np.float64)
        residual = X - fitted
        return (
            {"x0": fitted, "residual": residual},
            {"x0": level, "linear_rate": 0.0},
            residual,
            {
                "rmse": float(np.sqrt(np.mean(residual ** 2))),
                "rank": 1,
                "n_params": 1,
                "convergence": True,
                "version": "1.0",
                "underdetermined": True,
            },
        )

    coeffs, _, rank, _ = np.linalg.lstsq(A, X, rcond=None)

    # Named additive components (each coefficient × its basis column)
    components: dict[str, np.ndarray] = {
        label: float(coeffs[i]) * A[:, i]
        for i, label in enumerate(labels)
    }

    fitted = A @ coeffs
    residual = X - fitted
    components["residual"] = residual

    return (
        components,
        {label: float(coeffs[i]) for i, label in enumerate(labels)},
        residual,
        {
            "rmse": float(np.sqrt(np.mean(residual ** 2))),
            "rank": int(rank),
            "n_params": p,
            "convergence": True,
            "version": "1.0",
        },
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


@register_fitter("ETM")
def fit_etm(
    X: np.ndarray,
    t: np.ndarray | None = None,
    known_steps: list[float] | None = None,
    known_transients: list[tuple[float, float, str]] | None = None,
    harmonic_periods: Sequence[float] = (365.25, 182.625),
    **kwargs,
) -> DecompositionBlob:
    """Fit the Bevis-Brown ETM to a time-series segment (Eq. 1).

    Each named component (e.g. ``'linear_rate'``, ``'step_at_50'``,
    ``'sin_365.25'``) is stored in blob.components so that Tier-2 ops can
    edit individual coefficients directly.  blob.reassemble() reproduces X
    within floating-point rounding.

    Args:
        X: Segment values, shape (n,) or (n, d) for multivariate input.
        t: Time axis, shape (n,).  Defaults to np.arange(n, dtype=float).
        known_steps: Step epochs (t_s values) for Heaviside columns.
        known_transients: List of (t_ref, tau, basis) tuples; basis ∈
            {'log', 'exp', 'both'}.
        harmonic_periods: Sinusoidal periods (same units as t).
            Default: annual + semi-annual in days (geodesy convention).

    Returns:
        DecompositionBlob.  Component names follow Bevis-Brown Eq. 1:
        ``x0``, ``linear_rate``, ``step_at_{t_s}``, ``log_{t_r}_tau{τ}``,
        ``exp_{t_r}_tau{τ}``, ``sin_{T}``, ``cos_{T}``, ``residual``.
    """
    X_arr = np.asarray(X, dtype=np.float64)
    multivariate = X_arr.ndim == 2

    if multivariate:
        n, d = X_arr.shape
    else:
        X_arr = X_arr.ravel()
        n = len(X_arr)

    t_arr = np.arange(n, dtype=np.float64) if t is None else np.asarray(t, dtype=np.float64).ravel()

    if not multivariate:
        comps, coeffs, residual, meta = _fit_1d(
            X_arr, t_arr, known_steps, known_transients, harmonic_periods,
        )
        return DecompositionBlob(
            method="ETM",
            components=comps,
            coefficients=coeffs,
            residual=residual,
            fit_metadata=meta,
        )

    # Multivariate: fit per channel; stack component arrays to (n, d)
    results = [
        _fit_1d(X_arr[:, j], t_arr, known_steps, known_transients, harmonic_periods)
        for j in range(d)
    ]

    all_labels = list(results[0][0].keys())
    stacked_components: dict[str, np.ndarray] = {
        lbl: np.column_stack([results[j][0][lbl] for j in range(d)])
        for lbl in all_labels
    }
    stacked_coefficients: dict[str, np.ndarray] = {
        lbl: np.array([results[j][1].get(lbl, 0.0) for j in range(d)])
        for lbl in results[0][1].keys()
    }
    stacked_residual = stacked_components["residual"]
    mean_rmse = float(np.mean([results[j][3]["rmse"] for j in range(d)]))

    return DecompositionBlob(
        method="ETM",
        components=stacked_components,
        coefficients=stacked_coefficients,
        residual=stacked_residual,
        fit_metadata={
            "rmse": mean_rmse,
            "rank": results[0][3]["rank"],
            "n_params": results[0][3]["n_params"],
            "convergence": True,
            "version": "1.0",
            "n_channels": d,
        },
    )
