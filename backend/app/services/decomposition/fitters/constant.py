"""Constant (plateau) fitter stub (SEG-013 placeholder)."""
from __future__ import annotations
import numpy as np
from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter


@register_fitter("Constant")
def fit_constant(X: np.ndarray, **kwargs) -> DecompositionBlob:
    """Model a plateau segment as a constant level plus residual."""
    arr = np.asarray(X, dtype=np.float64).ravel()
    level = float(np.mean(arr))
    trend = np.full_like(arr, level)
    residual = arr - trend
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    return DecompositionBlob(
        method="Constant",
        components={"trend": trend, "residual": residual},
        coefficients={"level": level},
        residual=residual,
        fit_metadata={"rmse": rmse, "rank": 1, "n_params": 1, "convergence": True, "version": "stub-1.0"},
    )
