"""Eckhardt baseflow fitter stub (SEG-016 placeholder).

Full Eckhardt recursive digital filter to be implemented in SEG-016.
"""
from __future__ import annotations
import numpy as np
from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter


@register_fitter("Eckhardt")
def fit_eckhardt(X: np.ndarray, alpha: float = 0.925, bfi_max: float = 0.80, **kwargs) -> DecompositionBlob:
    """Stub: Eckhardt recursive filter separating baseflow from quickflow.

    Ref: Eckhardt (2005) How to construct recursive digital bandpass filters
    for baseflow separation. Hydrological Processes 19(2):507-515.
    """
    arr = np.asarray(X, dtype=np.float64).ravel()
    n = len(arr)
    baseflow = np.zeros(n)
    baseflow[0] = arr[0] * bfi_max
    for i in range(1, n):
        baseflow[i] = ((1.0 - bfi_max) * alpha * baseflow[i - 1] + (1.0 - alpha) * bfi_max * arr[i]) / (1.0 - alpha * bfi_max)
        baseflow[i] = min(baseflow[i], arr[i])

    quickflow = arr - baseflow
    residual = np.zeros_like(arr)  # exact split, no residual
    rmse = 0.0
    return DecompositionBlob(
        method="Eckhardt",
        components={"baseflow": baseflow, "quickflow": quickflow, "residual": residual},
        coefficients={"alpha": alpha, "bfi_max": bfi_max},
        residual=residual,
        fit_metadata={"rmse": rmse, "rank": 2, "n_params": 2, "convergence": True, "version": "stub-1.0"},
    )
