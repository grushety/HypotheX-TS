"""MSTL (Multiple Seasonal-Trend via LOESS) fitter stub (SEG-014 placeholder).

Full MSTL via statsmodels to be implemented in SEG-014.
"""
from __future__ import annotations
import numpy as np
from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter


@register_fitter("MSTL")
def fit_mstl(X: np.ndarray, periods: list[int] | None = None, **kwargs) -> DecompositionBlob:
    """Stub: two-period seasonal decomposition (primary + harmonic)."""
    arr = np.asarray(X, dtype=np.float64).ravel()
    n = len(arr)
    periods = periods or [12, 4]
    t = np.arange(n, dtype=np.float64)
    t_mean = t.mean()
    denom = float(np.dot(t - t_mean, t - t_mean)) + 1e-12
    slope = float(np.dot(t - t_mean, arr - arr.mean()) / denom)
    intercept = float(arr.mean() - slope * t_mean)
    trend = intercept + slope * t

    detrended = arr - trend
    seasonal_components: dict[str, np.ndarray] = {}
    remainder = detrended.copy()
    for i, period in enumerate(periods):
        period = max(2, min(period, n))
        seas = np.zeros_like(arr)
        for p in range(period):
            indices = np.arange(p, n, period)
            seas[indices] = float(np.mean(remainder[indices]))
        seas -= seas[:period].mean()
        seasonal_components[f"seasonal_{i}"] = seas
        remainder -= seas

    residual = remainder
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    components = {"trend": trend, **seasonal_components, "residual": residual}
    return DecompositionBlob(
        method="MSTL",
        components=components,
        coefficients={"periods": periods, "slope": slope, "intercept": intercept},
        residual=residual,
        fit_metadata={"rmse": rmse, "rank": len(periods) + 2, "n_params": sum(periods) + 2, "convergence": True, "version": "stub-1.0"},
    )
