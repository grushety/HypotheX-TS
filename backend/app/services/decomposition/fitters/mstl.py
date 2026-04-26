"""MSTL (Multiple Seasonal-Trend via LOESS) fitter — Bandara et al. (2021).

Models a multi-period cycle segment as:

    x(t) = T(t) + Σₖ Sₖ(t) + R(t)

where T is the LOESS trend, Sₖ are the per-period seasonal components,
and R is the residual.  Fitting delegates to statsmodels MSTL.

References
----------
Bandara, K., Hyndman, R. J., & Bergmeir, C. (2021).
MSTL: A Seasonal-Trend Decomposition Algorithm for Time Series with
Multiple Seasonal Patterns.  Proceedings of IJCNN 2021. arXiv 2107.13462.

Cleveland, R. B., Cleveland, W. S., McRae, J. E., & Terpenning, I. (1990).
STL: A Seasonal-Trend Decomposition Procedure Based on Loess.
*Journal of Official Statistics*, 6(1), 3–73.
"""
from __future__ import annotations

import warnings

import numpy as np
from statsmodels.tsa.seasonal import MSTL

from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter
from app.services.decomposition.fitters.stl import detect_dominant_period


# ---------------------------------------------------------------------------
# Single-channel fitting
# ---------------------------------------------------------------------------


def _fit_mstl_1d(
    X: np.ndarray,
    periods: list[int],
) -> tuple[dict[str, np.ndarray], dict, dict]:
    """Fit MSTL to a 1-D array.

    Periods larger than n // 2 are silently filtered before calling
    statsmodels to avoid a UserWarning and ensure predictable column ordering.

    Returns (components, coefficients, fit_metadata).
    trend + Σ seasonal_T + residual == X exactly (Bandara et al. 2021).
    """
    n = len(X)
    # statsmodels rejects period >= n/2 (i.e. 2*period >= n); sort so column
    # indices align with statsmodels' internal sorted ordering.
    valid_periods = sorted(p for p in periods if 2 <= p and 2 * p < n)
    if not valid_periods:
        # Underdetermined: segment too short for any requested period.
        level = float(np.mean(X))
        fitted = np.full(n, level, dtype=np.float64)
        residual = X - fitted
        seas_key = f"seasonal_{periods[0]}" if periods else "seasonal_2"
        return (
            {"trend": fitted, seas_key: np.zeros(n, dtype=np.float64), "residual": residual},
            {"periods": periods, "valid_periods": []},
            {
                "rmse": float(np.sqrt(np.mean(residual ** 2))),
                "rank": 1,
                "n_params": 1,
                "convergence": True,
                "version": "1.0",
                "periods": periods,
                "valid_periods": [],
                "underdetermined": True,
            },
        )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = MSTL(X, periods=valid_periods).fit()

    trend = np.asarray(result.trend, dtype=np.float64)
    resid = np.asarray(result.resid, dtype=np.float64)
    seasonal_raw = np.asarray(result.seasonal, dtype=np.float64)

    components: dict[str, np.ndarray] = {"trend": trend}

    # seasonal_raw is (n, k) for k valid periods (sorted ascending), or (n,)
    # if only one period survived.  valid_periods is already sorted to match.
    if seasonal_raw.ndim == 2:
        for idx, T in enumerate(valid_periods):
            components[f"seasonal_{T}"] = seasonal_raw[:, idx]
    else:
        components[f"seasonal_{valid_periods[0]}"] = seasonal_raw

    components["residual"] = resid
    rmse = float(np.sqrt(np.mean(resid ** 2)))
    meta = {
        "rmse": rmse,
        "rank": len(valid_periods) + 2,
        "n_params": sum(valid_periods) + 2,
        "convergence": True,
        "version": "1.0",
        "periods": periods,
        "valid_periods": valid_periods,
    }
    coefficients = {"periods": periods, "valid_periods": valid_periods}
    return components, coefficients, meta


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


@register_fitter("MSTL")
def fit_mstl(
    X: np.ndarray,
    periods: list[int] | None = None,
    **kwargs,
) -> DecompositionBlob:
    """Fit MSTL (Bandara et al. 2021) to a multi-period cycle segment.

    Decomposes x(t) = trend(t) + Σₖ seasonal_Tₖ(t) + residual(t) via
    iterated LOESS per seasonal period (Bandara et al. 2021, Algorithm 1).
    Component sum reproduces X within floating-point rounding.

    Args:
        X: Segment values, shape (n,) or (n, d) for multivariate input.
        periods: Dominant seasonal periods (each ≥ 2).  Auto-detected via
                 FFT + ACF if None.

    Returns:
        DecompositionBlob with components ``'trend'``, ``'seasonal_{T}'``
        for each period T, and ``'residual'``.  blob.reassemble() reproduces X
        within float tolerance.
    """
    X_arr = np.asarray(X, dtype=np.float64)
    multivariate = X_arr.ndim == 2

    if multivariate:
        n, d = X_arr.shape
    else:
        X_arr = X_arr.ravel()
        n = len(X_arr)

    # Period resolution
    if periods is not None:
        _periods = [max(2, int(p)) for p in periods]
    else:
        detected = detect_dominant_period(X_arr)
        _periods = detected if isinstance(detected, list) else [detected]
        _periods = [max(2, int(p)) for p in _periods]

    if not multivariate:
        comps, coeffs, meta = _fit_mstl_1d(X_arr, _periods)
        return DecompositionBlob(
            method="MSTL",
            components=comps,
            coefficients=coeffs,
            residual=comps["residual"],
            fit_metadata=meta,
        )

    # Multivariate: fit per channel, stack arrays to (n, d)
    results = [_fit_mstl_1d(X_arr[:, j], _periods) for j in range(d)]
    all_keys = list(results[0][0].keys())
    stacked_components = {
        k: np.column_stack([results[j][0][k] for j in range(d)])
        for k in all_keys
    }
    mean_rmse = float(np.mean([results[j][2]["rmse"] for j in range(d)]))
    first_meta = results[0][2]
    return DecompositionBlob(
        method="MSTL",
        components=stacked_components,
        coefficients=results[0][1],
        residual=stacked_components["residual"],
        fit_metadata={
            "rmse": mean_rmse,
            "rank": first_meta["rank"],
            "n_params": first_meta["n_params"],
            "convergence": True,
            "version": "1.0",
            "periods": _periods,
            "n_channels": d,
        },
    )
