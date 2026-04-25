"""LandTrendr fitter stub (SEG-017 placeholder).

Full LandTrendr to be implemented in SEG-017.
"""
from __future__ import annotations
import numpy as np
from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter


@register_fitter("LandTrendr")
def fit_landtrendr(X: np.ndarray, **kwargs) -> DecompositionBlob:
    """Stub: segmented linear regression (two-segment piecewise linear)."""
    arr = np.asarray(X, dtype=np.float64).ravel()
    n = len(arr)
    t = np.arange(n, dtype=np.float64)

    # Find the breakpoint that minimises total residual sum of squares
    best_rss = np.inf
    best_break = n // 2
    for brk in range(2, n - 2):
        t1, y1 = t[:brk], arr[:brk]
        t2, y2 = t[brk:], arr[brk:]
        def _ols_rss(tx, yx):
            if len(tx) < 2:
                return np.inf
            tm = tx.mean()
            denom = np.dot(tx - tm, tx - tm) + 1e-12
            s = np.dot(tx - tm, yx - yx.mean()) / denom
            i_ = yx.mean() - s * tm
            return float(np.sum((yx - (i_ + s * tx)) ** 2))
        rss = _ols_rss(t1, y1) + _ols_rss(t2, y2)
        if rss < best_rss:
            best_rss = rss
            best_break = brk

    def _ols(tx, yx):
        tm = tx.mean()
        denom = np.dot(tx - tm, tx - tm) + 1e-12
        s = float(np.dot(tx - tm, yx - yx.mean()) / denom)
        i_ = float(yx.mean() - s * tm)
        return s, i_

    s1, i1 = _ols(t[:best_break], arr[:best_break])
    s2, i2 = _ols(t[best_break:], arr[best_break:])
    trend = np.concatenate([i1 + s1 * t[:best_break], i2 + s2 * t[best_break:]])
    residual = arr - trend
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    return DecompositionBlob(
        method="LandTrendr",
        components={"trend": trend, "residual": residual},
        coefficients={"breakpoint": best_break, "slope_1": s1, "intercept_1": i1, "slope_2": s2, "intercept_2": i2},
        residual=residual,
        fit_metadata={"rmse": rmse, "rank": 2, "n_params": 4, "convergence": True, "version": "stub-1.0"},
    )
