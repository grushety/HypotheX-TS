"""BFAST (Breaks for Additive Seasonal Trend) fitter stub (SEG-015 placeholder).

Full BFAST to be implemented in SEG-015.
"""
from __future__ import annotations
import numpy as np
from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter


@register_fitter("BFAST")
def fit_bfast(X: np.ndarray, period: int = 12, **kwargs) -> DecompositionBlob:
    """Stub: piecewise linear trend + seasonal component."""
    arr = np.asarray(X, dtype=np.float64).ravel()
    n = len(arr)
    period = max(2, min(period, n))
    t = np.arange(n, dtype=np.float64)

    # Simple piecewise-constant trend: split at midpoint
    mid = n // 2
    level_l = float(arr[:mid].mean())
    level_r = float(arr[mid:].mean())
    trend = np.concatenate([np.full(mid, level_l), np.full(n - mid, level_r)])

    detrended = arr - trend
    seasonal = np.zeros_like(arr)
    for p in range(period):
        indices = np.arange(p, n, period)
        seasonal[indices] = float(np.mean(detrended[indices]))
    seasonal -= seasonal[:period].mean()

    residual = arr - trend - seasonal
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    return DecompositionBlob(
        method="BFAST",
        components={"trend": trend, "seasonal": seasonal, "residual": residual},
        coefficients={"period": period, "breakpoint": mid, "level_left": level_l, "level_right": level_r},
        residual=residual,
        fit_metadata={"rmse": rmse, "rank": 3, "n_params": period + 3, "convergence": True, "version": "stub-1.0"},
    )
