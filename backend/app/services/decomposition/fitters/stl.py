"""STL (Seasonal-Trend Decomposition via LOESS) fitter — Cleveland et al. (1990).

Models a single-period cycle segment as:

    x(t) = T(t) + S(t) + R(t)

where T is the LOESS trend, S is the periodic seasonal component,
and R is the residual.  Fitting delegates to statsmodels STL.

References
----------
Cleveland, R. B., Cleveland, W. S., McRae, J. E., & Terpenning, I. (1990).
STL: A Seasonal-Trend Decomposition Procedure Based on Loess.
*Journal of Official Statistics*, 6(1), 3–73.

Bandara, K., Hyndman, R. J., & Bergmeir, C. (2021).
MSTL: A Seasonal-Trend Decomposition Algorithm for Time Series with
Multiple Seasonal Patterns.  arXiv 2107.13462.
"""
from __future__ import annotations

import warnings

import numpy as np
from statsmodels.tsa.seasonal import STL

from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter


# ---------------------------------------------------------------------------
# Period detection — FFT power spectrum + ACF refinement
# ---------------------------------------------------------------------------


def detect_dominant_period(
    X: np.ndarray,
    min_period: int = 2,
    max_periods: int = 5,
) -> int | list[int]:
    """Detect dominant period(s) via FFT power spectrum + ACF confirmation.

    Algorithm (Bandara, Hyndman & Bergmeir 2021 §3):
    1. Compute FFT power spectrum; collect candidate periods with power
       ≥ 10 % of the maximum.
    2. Round each candidate to the nearest integer and deduplicate.
    3. Refine each integer candidate by searching for the local ACF
       maximum within ±5 lags.
    4. Confirm candidates where the refined ACF value > 0.10.

    Returns an ``int`` when exactly one dominant period is confirmed;
    a ``list[int]`` (sorted ascending) when multiple periods are confirmed.
    """
    X_1d = np.asarray(X, dtype=np.float64)
    if X_1d.ndim > 1:
        X_1d = X_1d[:, 0]
    n = len(X_1d)
    if n < 2 * min_period:
        return min_period

    X_c = X_1d - X_1d.mean()

    # FFT power (one-sided)
    power = np.abs(np.fft.rfft(X_c)) ** 2
    freqs = np.fft.rfftfreq(n)
    power[0] = 0.0  # discard DC component

    with np.errstate(divide="ignore", invalid="ignore"):
        period_f = np.where(freqs > 0, 1.0 / freqs, 0.0)

    valid = (period_f >= min_period) & (period_f <= n // 2)
    if not valid.any():
        return min_period

    pw_valid = power[valid]
    pf_valid = period_f[valid]
    top_pw = pw_valid.max()

    # Keep candidates with power >= 10 % of the spectral maximum
    above = pw_valid >= 0.10 * top_pw
    candidate_periods = pf_valid[above]
    candidate_powers = pw_valid[above]

    # Round to nearest integer; deduplicate (keep max power per rounded period)
    period_to_power: dict[int, float] = {}
    for p, pw in zip(candidate_periods, candidate_powers):
        T = int(round(p))
        if T >= min_period:
            if T not in period_to_power or pw > period_to_power[T]:
                period_to_power[T] = pw

    if not period_to_power:
        return min_period

    top_cands = sorted(period_to_power, key=lambda t: -period_to_power[t])[:max_periods]

    # Circular ACF via FFT self-correlation — O(n log n)
    max_lag = min(n // 2, max(top_cands) + 10)
    x_pad = np.zeros(2 * n)
    x_pad[:n] = X_c
    ac_raw = np.fft.irfft(np.abs(np.fft.rfft(x_pad)) ** 2)[: max_lag + 1]
    ac = ac_raw / (ac_raw[0] + 1e-12)

    confirmed: list[int] = []
    for T in top_cands:
        lo = max(min_period, T - 5)
        hi = min(max_lag, T + 5)
        if lo > hi or hi >= len(ac):
            if 0 < T < len(ac) and ac[T] > 0.10:
                confirmed.append(T)
            continue
        window = ac[lo : hi + 1]
        best_lag = lo + int(np.argmax(window))
        if ac[best_lag] > 0.10:
            confirmed.append(best_lag)

    if not confirmed:
        confirmed = [top_cands[0]]

    confirmed = sorted(set(confirmed))
    return confirmed[0] if len(confirmed) == 1 else confirmed


# ---------------------------------------------------------------------------
# Single-channel fitting
# ---------------------------------------------------------------------------


def _fit_stl_1d(
    X: np.ndarray,
    period: int,
    robust: bool,
) -> tuple[dict[str, np.ndarray], dict, dict]:
    """OLS-equivalent STL fit to a 1-D array.

    Returns (components, coefficients, fit_metadata).
    trend + seasonal + residual == X exactly (Cleveland 1990 §3).
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = STL(X, period=period, robust=robust).fit()

    components = {
        "trend": np.asarray(result.trend, dtype=np.float64),
        "seasonal": np.asarray(result.seasonal, dtype=np.float64),
        "residual": np.asarray(result.resid, dtype=np.float64),
    }
    rmse = float(np.sqrt(np.mean(components["residual"] ** 2)))
    meta = {
        "rmse": rmse,
        "rank": 3,
        "n_params": period + 2,
        "convergence": True,
        "version": "1.0",
        "period": period,
        "robust": robust,
    }
    coefficients = {"period": period, "robust": robust}
    return components, coefficients, meta


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


@register_fitter("STL")
def fit_stl(
    X: np.ndarray,
    period: int | None = None,
    robust: bool = True,
    **kwargs,
) -> DecompositionBlob:
    """Fit STL (Cleveland et al. 1990) to a single-period cycle segment.

    Decomposes x(t) = trend(t) + seasonal(t) + residual(t) via iterative
    LOESS.  Component sum reproduces X within floating-point rounding
    (Cleveland 1990, §3: residual defined as X − trend − seasonal).

    Args:
        X: Segment values, shape (n,) or (n, d) for multivariate input.
        period: Dominant seasonal period (integer ≥ 2).  Auto-detected via
                FFT + ACF if None; if detection returns multiple periods the
                strongest is used (call fit_mstl for multi-period segments).
        robust: Use robust LOESS weights (Cleveland 1990 §3.5).  Default True.

    Returns:
        DecompositionBlob with components ``'trend'``, ``'seasonal'``,
        ``'residual'``.  blob.reassemble() reproduces X within float tolerance.
    """
    X_arr = np.asarray(X, dtype=np.float64)
    multivariate = X_arr.ndim == 2

    if multivariate:
        n, d = X_arr.shape
    else:
        X_arr = X_arr.ravel()
        n = len(X_arr)

    # Period resolution
    if period is not None:
        _period = max(2, int(period))
    else:
        detected = detect_dominant_period(X_arr)
        _period = max(2, int(detected[0] if isinstance(detected, list) else detected))

    # Underdetermined guard: STL requires n > period
    if n <= _period:
        level = float(np.mean(X_arr)) if not multivariate else 0.0
        fitted = np.full(n if not multivariate else (n, d), level, dtype=np.float64)
        residual = X_arr - fitted if not multivariate else X_arr.copy()
        comps = {"trend": fitted, "seasonal": np.zeros_like(X_arr), "residual": residual if not multivariate else X_arr}
        return DecompositionBlob(
            method="STL",
            components=comps,
            coefficients={"period": _period, "robust": robust},
            residual=comps["residual"],
            fit_metadata={
                "rmse": float(np.sqrt(np.mean(comps["residual"] ** 2))),
                "rank": 1,
                "n_params": 1,
                "convergence": True,
                "version": "1.0",
                "period": _period,
                "robust": robust,
                "underdetermined": True,
            },
        )

    if not multivariate:
        comps, coeffs, meta = _fit_stl_1d(X_arr, _period, robust)
        return DecompositionBlob(
            method="STL",
            components=comps,
            coefficients=coeffs,
            residual=comps["residual"],
            fit_metadata=meta,
        )

    # Multivariate: fit per channel, stack arrays to (n, d)
    results = [_fit_stl_1d(X_arr[:, j], _period, robust) for j in range(d)]
    all_keys = list(results[0][0].keys())
    stacked_components = {
        k: np.column_stack([results[j][0][k] for j in range(d)])
        for k in all_keys
    }
    mean_rmse = float(np.mean([results[j][2]["rmse"] for j in range(d)]))
    return DecompositionBlob(
        method="STL",
        components=stacked_components,
        coefficients=results[0][1],
        residual=stacked_components["residual"],
        fit_metadata={
            "rmse": mean_rmse,
            "rank": 3,
            "n_params": _period + 2,
            "convergence": True,
            "version": "1.0",
            "period": _period,
            "robust": robust,
            "n_channels": d,
        },
    )
