"""GrAtSiD (Geodetic transient/step detection) fitter stub (SEG-018 placeholder).

Full GrAtSiD to be implemented in SEG-018.
"""
from __future__ import annotations
import numpy as np
from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter


@register_fitter("GrAtSiD")
def fit_gratsid(X: np.ndarray, **kwargs) -> DecompositionBlob:
    """Stub: separates a transient geodetic signal into secular + transient + noise."""
    arr = np.asarray(X, dtype=np.float64).ravel()
    n = len(arr)
    t = np.arange(n, dtype=np.float64)

    # Secular (linear trend)
    t_mean = t.mean()
    denom = float(np.dot(t - t_mean, t - t_mean)) + 1e-12
    slope = float(np.dot(t - t_mean, arr - arr.mean()) / denom)
    intercept = float(arr.mean() - slope * t_mean)
    secular = intercept + slope * t

    # Transient: Gaussian bump at the segment's largest deviation from secular
    detrended = arr - secular
    peak_idx = int(np.argmax(np.abs(detrended)))
    sigma = max(1.0, n / 10.0)
    transient = detrended[peak_idx] * np.exp(-0.5 * ((t - t[peak_idx]) / sigma) ** 2)

    residual = arr - secular - transient
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    return DecompositionBlob(
        method="GrAtSiD",
        components={"secular": secular, "transient": transient, "residual": residual},
        coefficients={"slope": slope, "intercept": intercept, "peak_index": peak_idx, "sigma": sigma},
        residual=residual,
        fit_metadata={"rmse": rmse, "rank": 3, "n_params": 4, "convergence": True, "version": "stub-1.0"},
    )
