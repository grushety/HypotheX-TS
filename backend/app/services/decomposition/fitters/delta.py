"""Delta (spike/impulse) fitter stub (SEG-013 placeholder)."""
from __future__ import annotations
import numpy as np
from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter


@register_fitter("Delta")
def fit_delta(X: np.ndarray, **kwargs) -> DecompositionBlob:
    """Model a spike segment as baseline + impulse at the peak index."""
    arr = np.asarray(X, dtype=np.float64).ravel()
    peak_idx = int(np.argmax(np.abs(arr - np.mean(arr))))
    baseline_val = float(np.mean(np.delete(arr, peak_idx)))
    baseline = np.full_like(arr, baseline_val)
    impulse = np.zeros_like(arr)
    impulse[peak_idx] = arr[peak_idx] - baseline_val
    residual = arr - baseline - impulse
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    return DecompositionBlob(
        method="Delta",
        components={"baseline": baseline, "impulse": impulse, "residual": residual},
        coefficients={"peak_index": peak_idx, "peak_amplitude": float(impulse[peak_idx]), "baseline": baseline_val},
        residual=residual,
        fit_metadata={"rmse": rmse, "rank": 2, "n_params": 2, "convergence": True, "version": "stub-1.0"},
    )
