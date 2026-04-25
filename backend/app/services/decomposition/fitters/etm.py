"""ETM (Exponential Trend Model) fitter stub (SEG-013 placeholder).

Fits a linear trend via ordinary least squares.  Full exponential-family
generalisation to be implemented in SEG-013.
"""
from __future__ import annotations
import numpy as np
from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter


@register_fitter("ETM")
def fit_etm(X: np.ndarray, **kwargs) -> DecompositionBlob:
    """OLS linear trend stub for plateau/trend/step/transient segments."""
    arr = np.asarray(X, dtype=np.float64).ravel()
    n = len(arr)
    t = np.arange(n, dtype=np.float64)
    # OLS: slope and intercept
    t_mean = t.mean()
    slope = float(np.dot(t - t_mean, arr - arr.mean()) / (np.dot(t - t_mean, t - t_mean) + 1e-12))
    intercept = float(arr.mean() - slope * t_mean)
    trend = intercept + slope * t
    residual = arr - trend
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    return DecompositionBlob(
        method="ETM",
        components={"trend": trend, "residual": residual},
        coefficients={"slope": slope, "intercept": intercept},
        residual=residual,
        fit_metadata={"rmse": rmse, "rank": 2, "n_params": 2, "convergence": True, "version": "stub-1.0"},
    )
