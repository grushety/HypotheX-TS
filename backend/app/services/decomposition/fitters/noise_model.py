"""NoiseModel fitter stub (SEG-013 placeholder)."""
from __future__ import annotations
import numpy as np
from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter


@register_fitter("NoiseModel")
def fit_noise_model(X: np.ndarray, **kwargs) -> DecompositionBlob:
    """Model a noise segment as mean level + white noise residual."""
    arr = np.asarray(X, dtype=np.float64).ravel()
    level = float(np.mean(arr))
    mean_component = np.full_like(arr, level)
    residual = arr - mean_component
    std = float(np.std(residual))
    rmse = std
    return DecompositionBlob(
        method="NoiseModel",
        components={"mean": mean_component, "residual": residual},
        coefficients={"level": level, "std": std},
        residual=residual,
        fit_metadata={"rmse": rmse, "rank": 1, "n_params": 2, "convergence": True, "version": "stub-1.0"},
    )
