"""BFAST (Breaks for Additive Seasonal Trend) fitter — Verbesselt et al. (2010).

Decomposes a remote-sensing-style time series into

    x(t) = T(t) + S(t) + R(t)

where ``T`` is a piecewise-linear trend with structural breakpoints, ``S`` is
a periodic seasonal component fitted by harmonic regression, and ``R`` is the
residual.  Breakpoint epochs and trend-magnitude jumps are stored as editable
coefficients so that OP-022 (Step ops) can read and modify them directly.

Two variants are exposed:

* ``variant='classical'`` — iterative trend/seasonal alternation per
  Verbesselt 2010 §2 with an OLS F-test scan + Bai–Perron-style binary
  segmentation for breakpoints.
* ``variant='lite'`` — single-pass approximation per Masiliūnas et al.
  (2021): one harmonic, at most one breakpoint, no iteration.  Faster and
  appropriate for short series or near-real-time monitoring.

The output component dictionary uses the same ``{'trend', 'seasonal',
'residual'}`` keys as :func:`fit_stl`, so every Tier-2 cycle/trend op is
already compatible (SEG-014 interop).

References
----------
Verbesselt, J., Hyndman, R., Newnham, G., & Culvenor, D. (2010).
    Detecting trend and seasonal changes in satellite image time series.
    *Remote Sensing of Environment* 114(1):106–115.
    DOI 10.1016/j.rse.2009.08.014.
    → §2: iterative T/S decomposition with structural breakpoints.

Verbesselt, J., Zeileis, A., & Herold, M. (2012).
    Near real-time disturbance detection using satellite image time series.
    *Remote Sensing of Environment* 123:98–108.
    → OLS-MOSUM monitoring extension.

Masiliūnas, D., Tsendbazar, N.-E., Herold, M., & Verbesselt, J. (2021).
    BFAST Lite: a lightweight break detection method for time series
    analysis. *Remote Sensing* 13(16):3308.
    → Single-pass lite variant.

Bai, J., & Perron, P. (2003).
    Computation and analysis of multiple structural change models.
    *J. Applied Econometrics* 18(1):1–22.
    → Binary-segmentation breakpoint estimator + F-test.

Chu, C. S. J., Hornik, K., & Kuan, C.-M. (1995).
    MOSUM tests for parameter constancy.  *Biometrika* 82(3):603–617.
    → OLS-MOSUM critical-value framework.
"""
from __future__ import annotations

import logging
from typing import Literal

import numpy as np
from scipy import stats

from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Seasonal component — harmonic regression (Verbesselt 2010 §2.1)
# ---------------------------------------------------------------------------


def fit_seasonal_dummies(
    X: np.ndarray,
    period: int,
    n_harmonics: int | None = None,
) -> np.ndarray:
    """Fit a seasonal component via harmonic regression.

    Models S(t) = Σₖ [αₖ cos(2π·k·t/T) + βₖ sin(2π·k·t/T)] for k = 1..K with
    K = ``n_harmonics`` (defaults to ``min(3, period // 2)``).  The harmonic
    basis is dense per (Verbesselt 2010 §2.1) where the seasonal component is
    constructed as a Fourier series of order K — a smoother and more stable
    alternative to literal indicator-dummy regression on short series.

    Args:
        X:           Detrended segment values, shape (n,).
        period:      Integer seasonal period (samples), ≥ 2.
        n_harmonics: Number of harmonics K.  Defaults to ``min(3, period//2)``.

    Returns:
        Seasonal estimate ``S(t)``, shape (n,).
    """
    arr = np.asarray(X, dtype=np.float64).ravel()
    n = len(arr)
    period_int = max(2, int(period))
    if n_harmonics is None:
        n_harmonics = min(3, period_int // 2)
    n_harmonics = max(1, int(n_harmonics))
    if n < 2 * n_harmonics + 1:
        return np.zeros(n, dtype=np.float64)

    t = np.arange(n, dtype=np.float64)
    cols: list[np.ndarray] = []
    for k in range(1, n_harmonics + 1):
        omega = 2.0 * np.pi * float(k) / float(period_int)
        cols.append(np.cos(omega * t))
        cols.append(np.sin(omega * t))
    A = np.column_stack(cols)
    coeffs, *_ = np.linalg.lstsq(A, arr, rcond=None)
    return A @ coeffs


# ---------------------------------------------------------------------------
# Piecewise linear trend with breakpoints (Verbesselt 2010 §2.2; Bai-Perron 2003)
# ---------------------------------------------------------------------------


def _linear_fit_rss(t: np.ndarray, x: np.ndarray) -> float:
    """Residual sum of squares of an OLS linear fit.

    Uses the closed-form OLS estimator; returns 0.0 when the segment is
    too short to fit (length < 2).
    """
    n = len(x)
    if n < 2:
        return 0.0
    t_mean = t.mean()
    x_mean = x.mean()
    dt = t - t_mean
    denom = float((dt * dt).sum())
    if denom <= 0.0:
        return float(((x - x_mean) ** 2).sum())
    slope = float((dt * (x - x_mean)).sum()) / denom
    intercept = x_mean - slope * t_mean
    resid = x - (slope * t + intercept)
    return float((resid ** 2).sum())


def _best_single_break(
    x: np.ndarray,
    t: np.ndarray,
    h_min: int,
    f_alpha: float = 0.05,
) -> int | None:
    """Find the single best breakpoint in [h_min, n − h_min] by minimum split RSS.

    A Chow-style F-test compares H₀ (single linear fit) against H₁ (two
    linear fits split at the optimal k).  The breakpoint is accepted only
    when F > F_{1−α}(2, n−4), the (1−α)-quantile of the F distribution
    under H₀ (Bai & Perron 2003; Chu, Hornik & Kuan 1995).

    Returns the index k inside ``x`` where the break occurs, or ``None``
    when no significant breakpoint exists.
    """
    n = len(x)
    if n < 2 * h_min or n < 5:
        return None

    # Reject segments that are essentially flat — the F-test denominator
    # collapses to floating-point noise and any sub-pixel ripple would
    # otherwise read as a "significant" break.
    x_var = float(np.var(x))
    if x_var < 1e-12:
        return None

    rss_full = _linear_fit_rss(t, x)
    # A pure linear segment leaves rss_full ≈ 0 (modulo float error); there is
    # no signal to break.  Use a scale-aware floor so noisy data still passes.
    sig_floor = 1e-9 * max(1.0, x_var * n)
    if rss_full <= sig_floor:
        return None

    best_k: int | None = None
    best_rss = np.inf
    for k in range(h_min, n - h_min + 1):
        rss_split = _linear_fit_rss(t[:k], x[:k]) + _linear_fit_rss(t[k:], x[k:])
        if rss_split < best_rss:
            best_rss = rss_split
            best_k = k

    if best_k is None:
        return None

    df_resid = n - 4
    if df_resid <= 0:
        return None

    # Degenerate case: piecewise fit explains essentially all variance, so
    # the F-statistic blows up.  Treat the break as significant — at this
    # point ``rss_full`` is already known to be above the significance floor.
    if best_rss <= 1e-9 * rss_full:
        return best_k

    f_stat = ((rss_full - best_rss) / 2.0) / (best_rss / df_resid)
    f_crit = float(stats.f.ppf(1.0 - f_alpha, 2, df_resid))
    if f_stat <= f_crit:
        return None
    return best_k


def _detect_breakpoints(
    x: np.ndarray,
    t: np.ndarray,
    h: float,
    f_alpha: float = 0.05,
    max_breaks: int | None = None,
) -> list[int]:
    """Recursive binary segmentation with F-test (Bai & Perron 2003).

    Each call locates at most one significant breakpoint inside the current
    sub-segment, then recurses on the two halves until no further break
    survives the F-test or the sub-segment shrinks below ``2·h·N``.

    Args:
        x:          Series values, shape (n,).
        t:          Time index, shape (n,).
        h:          Minimum segment size as a fraction of ``len(x)``.
                    ``h_min = max(2, round(h·n))``; the same ``h_min`` is
                    propagated into recursive calls so that the *global*
                    minimum gap between breakpoints is at least ``h·n``.
        f_alpha:    Significance level for the F-test (default 0.05).
        max_breaks: Optional cap on the number of breakpoints returned;
                    ``None`` = no cap.

    Returns:
        Sorted list of breakpoint indices in ``x`` (each index is the first
        sample of the second sub-segment).
    """
    n = len(x)
    h_min = max(2, int(round(h * n)))
    breaks: list[int] = []

    def recurse(start: int, end: int) -> None:
        if max_breaks is not None and len(breaks) >= max_breaks:
            return
        seg_n = end - start
        if seg_n < 2 * h_min:
            return
        k = _best_single_break(x[start:end], t[start:end], h_min, f_alpha=f_alpha)
        if k is None:
            return
        global_k = start + k
        breaks.append(global_k)
        recurse(start, global_k)
        recurse(global_k, end)

    recurse(0, n)
    return sorted(breaks)


def fit_trend_with_bp(
    X: np.ndarray,
    h: float = 0.15,
    f_alpha: float = 0.05,
    max_breaks: int | None = None,
    t: np.ndarray | None = None,
) -> tuple[np.ndarray, list[int]]:
    """Fit a piecewise-linear trend with structural breakpoints.

    Detects breakpoints via :func:`_detect_breakpoints` and fits independent
    OLS lines on each inter-breakpoint segment.  The minimum segment size is
    ``h·N`` per (Verbesselt 2010 §2): a hard floor on the bandwidth of any
    detected change, used by the OLS-MOSUM theory of Chu, Hornik & Kuan
    (1995) to bound the type-I error of the F-test.

    Args:
        X:          Deseasoned series, shape (n,).
        h:          Minimum segment size as a fraction of ``n``; default 0.15.
        f_alpha:    F-test significance level; default 0.05.
        max_breaks: Optional cap on the breakpoint count.
        t:          Time index; defaults to ``np.arange(n)``.

    Returns:
        ``(trend, breakpoints)`` where ``trend`` has shape (n,) and
        ``breakpoints`` is a sorted list of integer epoch indices.
    """
    arr = np.asarray(X, dtype=np.float64).ravel()
    n = len(arr)
    if t is None:
        t_arr = np.arange(n, dtype=np.float64)
    else:
        t_arr = np.asarray(t, dtype=np.float64).ravel()
    if len(t_arr) != n:
        raise ValueError(f"t length {len(t_arr)} does not match X length {n}.")

    breakpoints = _detect_breakpoints(arr, t_arr, h, f_alpha=f_alpha, max_breaks=max_breaks)

    bounds = [0] + breakpoints + [n]
    trend = np.zeros(n, dtype=np.float64)
    for i in range(len(bounds) - 1):
        lo, hi = bounds[i], bounds[i + 1]
        seg_n = hi - lo
        if seg_n < 1:
            continue
        if seg_n == 1:
            trend[lo:hi] = arr[lo:hi]
            continue
        ts = t_arr[lo:hi]
        xs = arr[lo:hi]
        t_mean = ts.mean()
        x_mean = xs.mean()
        dt = ts - t_mean
        denom = float((dt * dt).sum())
        if denom <= 0.0:
            trend[lo:hi] = x_mean
            continue
        slope = float((dt * (xs - x_mean)).sum()) / denom
        intercept = x_mean - slope * t_mean
        trend[lo:hi] = slope * ts + intercept

    return trend, breakpoints


# ---------------------------------------------------------------------------
# Iterative BFAST loop (Verbesselt 2010 §2.3)
# ---------------------------------------------------------------------------


def _break_magnitudes(trend: np.ndarray, breakpoints: list[int]) -> list[float]:
    """Magnitude of each breakpoint = trend jump T(bp) − T(bp−1).

    A piecewise-linear trend may jump in *level* and/or change *slope* at a
    breakpoint; the magnitude here is the level jump at the break index, which
    is what OP-022 step-edit ops modify directly.
    """
    n = len(trend)
    return [
        float(trend[bp] - trend[bp - 1])
        for bp in breakpoints
        if 0 < bp < n
    ]


@register_fitter("BFAST")
def fit_bfast(
    X: np.ndarray,
    period: int = 12,
    h: float = 0.15,
    max_iter: int = 10,
    variant: Literal["classical", "lite"] = "classical",
    n_harmonics: int | None = None,
    f_alpha: float = 0.05,
    t: np.ndarray | None = None,
    **_kwargs,
) -> DecompositionBlob:
    """Fit BFAST decomposition for a remote-sensing-style segment.

    Iteratively alternates seasonal harmonic regression and trend +
    breakpoint estimation until both stabilise (Verbesselt 2010 §2.3).  The
    minimum gap between adjacent breakpoints is ``h · len(X)`` samples; the
    OLS F-test guards each candidate at significance ``f_alpha``.

    Args:
        X:           Segment values, shape (n,).
        period:      Seasonal period in samples; clamped to ``max(2, period)``.
        h:           Minimum segment size as a fraction of n; default 0.15
                     (Verbesselt 2010 default).
        max_iter:    Iteration cap for the alternation loop; default 10.
                     A warning is logged if convergence is not reached.
        variant:     ``'classical'`` (default) or ``'lite'`` (Masiliūnas 2021,
                     single pass, single harmonic, ≤1 breakpoint).
        n_harmonics: Number of harmonics in the seasonal regression.  Defaults
                     to ``min(3, period // 2)`` for classical and ``1`` for lite.
        f_alpha:     F-test significance level; default 0.05.
        t:           Time index; defaults to ``np.arange(n)``.

    Returns:
        :class:`DecompositionBlob` with ``method='BFAST'`` and components
        ``{'trend', 'seasonal', 'residual'}`` (STL-compatible naming, SEG-014).
        ``coefficients`` carry editable ``break_epochs`` and ``break_magnitudes``
        for OP-022.

    Raises:
        ValueError: If ``X`` is multivariate, ``h`` ∉ (0, 0.5], or
                    ``variant`` is not one of the documented options.
    """
    arr = np.asarray(X, dtype=np.float64)
    if arr.ndim > 1 and (arr.ndim != 2 or arr.shape[1] != 1):
        raise ValueError(
            f"fit_bfast expects 1-D input; got shape {arr.shape}. "
            "Multivariate BFAST is not implemented."
        )
    arr = arr.ravel()
    n = len(arr)

    if not (0.0 < float(h) <= 0.5):
        raise ValueError(f"h must be in (0, 0.5]; got {h!r}.")
    if variant not in ("classical", "lite"):
        raise ValueError(
            f"Unknown variant {variant!r}; expected 'classical' or 'lite'."
        )

    period_int = max(2, int(period))
    if t is None:
        t_arr = np.arange(n, dtype=np.float64)
    else:
        t_arr = np.asarray(t, dtype=np.float64).ravel()
        if len(t_arr) != n:
            raise ValueError(f"t length {len(t_arr)} does not match X length {n}.")

    if variant == "lite":
        eff_n_harmonics = 1 if n_harmonics is None else max(1, int(n_harmonics))
        eff_max_iter = 1
        eff_max_breaks: int | None = 1
    else:
        eff_n_harmonics = (
            min(3, period_int // 2) if n_harmonics is None else max(1, int(n_harmonics))
        )
        eff_max_iter = max(1, int(max_iter))
        eff_max_breaks = None

    Tt = np.zeros(n, dtype=np.float64)
    St = np.zeros(n, dtype=np.float64)
    breakpoints: list[int] = []
    converged = False
    iterations = 0

    for iteration in range(eff_max_iter):
        iterations = iteration + 1
        St_new = fit_seasonal_dummies(arr - Tt, period_int, n_harmonics=eff_n_harmonics)
        Tt_new, breakpoints_new = fit_trend_with_bp(
            arr - St_new,
            h=float(h),
            f_alpha=float(f_alpha),
            max_breaks=eff_max_breaks,
            t=t_arr,
        )
        if iteration > 0 and np.allclose(Tt, Tt_new, atol=1e-6) and np.allclose(
            St, St_new, atol=1e-6
        ):
            Tt, St, breakpoints = Tt_new, St_new, breakpoints_new
            converged = True
            break
        Tt, St, breakpoints = Tt_new, St_new, breakpoints_new

    if not converged and eff_max_iter > 1:
        logger.warning(
            "BFAST did not converge in %d iterations; returning best-so-far.",
            eff_max_iter,
        )

    residual = arr - Tt - St
    magnitudes = _break_magnitudes(Tt, breakpoints)
    rmse = float(np.sqrt(np.mean(residual ** 2))) if n > 0 else 0.0

    return DecompositionBlob(
        method="BFAST",
        components={
            "trend": Tt,
            "seasonal": St,
            "residual": residual,
        },
        coefficients={
            "break_epochs": [int(bp) for bp in breakpoints],
            "break_magnitudes": magnitudes,
            "period": period_int,
            "h": float(h),
            "variant": variant,
            "n_harmonics": eff_n_harmonics,
            "f_alpha": float(f_alpha),
        },
        residual=residual,
        fit_metadata={
            "rmse": rmse,
            "rank": 3,
            "n_params": 2 * eff_n_harmonics + 2 * (len(breakpoints) + 1),
            "convergence": converged,
            "version": "1.0",
            "n_breakpoints": len(breakpoints),
            "iterations": iterations,
            "variant": variant,
        },
    )
