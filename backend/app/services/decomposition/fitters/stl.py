"""STL (Seasonal-Trend decomposition via LOESS) fitter stub (SEG-014 placeholder).

Full STL via statsmodels to be implemented in SEG-014.
"""
from __future__ import annotations
import numpy as np
from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter


@register_fitter("STL")
def fit_stl(X: np.ndarray, period: int = 12, **kwargs) -> DecompositionBlob:
    """Stub: linear trend + mean-per-period seasonal + residual."""
    arr = np.asarray(X, dtype=np.float64).ravel()
    n = len(arr)
    t = np.arange(n, dtype=np.float64)
    t_mean = t.mean()
    denom = float(np.dot(t - t_mean, t - t_mean)) + 1e-12
    slope = float(np.dot(t - t_mean, arr - arr.mean()) / denom)
    intercept = float(arr.mean() - slope * t_mean)
    trend = intercept + slope * t

    detrended = arr - trend
    period = max(2, min(period, n))
    seasonal = np.zeros_like(arr)
    for p in range(period):
        indices = np.arange(p, n, period)
        seasonal[indices] = float(np.mean(detrended[indices]))
    # centre seasonal so it sums to zero over one period
    seasonal -= seasonal[:period].mean()

    residual = arr - trend - seasonal
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    return DecompositionBlob(
        method="STL",
        components={"trend": trend, "seasonal": seasonal, "residual": residual},
        coefficients={"period": period, "slope": slope, "intercept": intercept},
        residual=residual,
        fit_metadata={"rmse": rmse, "rank": 3, "n_params": period + 2, "convergence": True, "version": "stub-1.0"},
    )
