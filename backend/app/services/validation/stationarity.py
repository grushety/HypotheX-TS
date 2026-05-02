"""ADF + KPSS joint stationarity tests, plus one-break ZA (VAL-006).

Detects whether an edit introduced spurious non-stationarity (drift, level
shift) on top of a previously stationary signal — or vice versa. Running
ADF and KPSS jointly avoids the well-known asymmetric failure mode of
either test alone:

    ADF:  H0: unit root present       (reject ⇒ stationary)
    KPSS: H0: trend-stationary        (reject ⇒ non-stationary)

A signal is judged stationary only when ADF rejects *and* KPSS does not.
Zivot-Andrews is added on the raw post signal to detect a single
structural break that the unit-root tests can miss.

Sources (binding for ``algorithm-auditor``):

  - Dickey & Fuller, *JASA* 74:427 (1979/1981) — ADF test.
  - Kwiatkowski, Phillips, Schmidt, Shin, "Testing the null hypothesis of
    stationarity against the alternative of a unit root,"
    *J. Econometrics* 54:159 (1992),
    DOI:10.1016/0304-4076(92)90104-Y — KPSS test.
  - Phillips & Perron, *Biometrika* 75:335 (1988) — PP test (alternative).
  - Zivot & Andrews, *J. Business & Economic Statistics* 10:251 (1992) —
    one-break unit-root test.

All three tests are delegated to ``statsmodels.tsa.stattools``; we never
reimplement them. ``whiten_residual`` (cube-root-rule lag, capped at 10)
is exposed as a helper but **off by default** in
``joint_stationarity_check`` — see the deviation note below.

Pseudocode-vs-AC deviation (load-bearing):
The ticket pseudocode detrends *and* pre-whitens both signals before
running ADF and KPSS. Each step is academically defensible in isolation
but together they directly conflict with the ticket's own test case
("synthetic random walk → ADF rejects no, KPSS rejects yes"):

  * Detrending a random walk over a finite sample biases ADF toward
    rejecting the unit-root null (Phillips 1988; the spurious-trend
    problem).
  * Whitening a random walk via AR(1) produces white noise — both tests
    then call it stationary, which is correct for "non-AR-explained
    structure" but wrong for "is the raw signal stationary?".

The user-facing question ("did my edit introduce drift?") is bound by
the AC's test specification, so this implementation:

  1. Feeds the raw signals straight to ADF and KPSS (which handle their
     own deterministic regressors via ``regression='c'``).
  2. Exposes ``detrend=True`` and ``whiten=True`` as opt-in toggles for
     callers who explicitly want the pseudocode's behaviour.

The ``whiten_residual`` helper is retained so the AC's "exposed helper"
requirement is satisfied either way.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Literal

import numpy as np


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class StationarityError(RuntimeError):
    """Raised when the stationarity check cannot run (e.g. degenerate input)."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


VERDICT_INTRODUCED = "edit_introduced_nonstationarity"
VERDICT_REDUCED = "edit_reduced_nonstationarity"
VERDICT_STATIONARY_PRESERVED = "stationary_preserved"
VERDICT_NONSTATIONARY_PRESERVED = "nonstationary_preserved"
VERDICT_UNDETERMINED = "undetermined"

_ALLOWED_VERDICTS = frozenset({
    VERDICT_INTRODUCED,
    VERDICT_REDUCED,
    VERDICT_STATIONARY_PRESERVED,
    VERDICT_NONSTATIONARY_PRESERVED,
    VERDICT_UNDETERMINED,
})

DEFAULT_ALPHA = 0.05
DEFAULT_AR_ORDER_CAP = 10
DEFAULT_BREAK_TOLERANCE = 0.2  # ±20 % of edit-window length, per AC


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StationarityResult:
    """Outcome of the joint ADF + KPSS + ZA stationarity check.

    Attributes:
        adf_pre_p / adf_post_p:   ADF p-values; small ⇒ reject unit root
                                  (i.e. stationary).
        kpss_pre_p / kpss_post_p: KPSS p-values; small ⇒ reject stationarity.
        za_post_p:                Zivot-Andrews p-value on the raw post
                                  signal; ``None`` if ZA was skipped or failed.
        za_post_break:            Sample index of the most-likely structural
                                  break in the post signal; ``None`` when
                                  ``za_post_p ≥ alpha`` (no significant break).
        za_break_consistent:      ``None`` when no break or no edit window
                                  was supplied; ``True`` when the break sits
                                  within ``edit_window`` extended by
                                  ``break_tolerance × len(window)`` on each
                                  side; ``False`` otherwise.
        verdict:                  One of the five ``VERDICT_*`` constants.
        alpha:                    Significance threshold used for the
                                  pre/post stationarity classification and
                                  the ZA break-significance test.
        ar_order:                 AR lag order used in whitening (0 if the
                                  whitening step was skipped or failed).
    """

    adf_pre_p: float
    adf_post_p: float
    kpss_pre_p: float
    kpss_post_p: float
    za_post_p: float | None
    za_post_break: int | None
    za_break_consistent: bool | None
    verdict: str
    alpha: float
    ar_order: int

    def __post_init__(self) -> None:
        if self.verdict not in _ALLOWED_VERDICTS:
            raise ValueError(
                f"verdict must be one of {sorted(_ALLOWED_VERDICTS)}; got {self.verdict!r}"
            )


# ---------------------------------------------------------------------------
# Whitening
# ---------------------------------------------------------------------------


def _auto_ar_order(n: int) -> int:
    return max(1, min(int(np.cbrt(n)), DEFAULT_AR_ORDER_CAP))


def whiten_residual(
    r: np.ndarray,
    *,
    ar_order: int | Literal["auto"] = "auto",
) -> tuple[np.ndarray, int]:
    """Pre-whiten ``r`` via an AR fit; return ``(residual_after_AR, lag_used)``.

    Falls back to the input array unchanged (``lag = 0``) when the data are
    too short, constant, or when ``AutoReg`` raises. The fall-back is loud
    only via a warning — callers continue with ADF / KPSS on the un-whitened
    series, which is fine for short / constant signals where there is
    nothing to whiten anyway.
    """
    arr = np.asarray(r, dtype=np.float64).reshape(-1)
    n = arr.shape[0]
    lag = _auto_ar_order(n) if ar_order == "auto" else int(ar_order)
    # Need at least 2(lag + 1) samples for AutoReg to fit without numerical
    # collapse — a single lag-shifted residual gives a degenerate covariance.
    if lag < 1 or n <= 2 * (lag + 1):
        return arr.copy(), 0
    if np.allclose(arr.std(), 0.0):
        return arr.copy(), 0
    try:
        from statsmodels.tsa.ar_model import AutoReg  # noqa: PLC0415
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # statsmodels emits ConvergenceWarning on weak signals
            fit = AutoReg(arr, lags=lag, old_names=False).fit()
        return np.asarray(fit.resid, dtype=np.float64), lag
    except Exception as exc:  # noqa: BLE001
        warnings.warn(
            f"whiten_residual: AR({lag}) fit failed ({exc}); falling back to un-whitened residual.",
            RuntimeWarning,
            stacklevel=2,
        )
        return arr.copy(), 0


# ---------------------------------------------------------------------------
# Detrending
# ---------------------------------------------------------------------------


def _detrend(x: np.ndarray) -> np.ndarray:
    """Remove an OLS linear trend from x; returns the residual."""
    arr = np.asarray(x, dtype=np.float64).reshape(-1)
    n = arr.shape[0]
    if n < 2:
        return arr - arr.mean() if n > 0 else arr.copy()
    t = np.arange(n, dtype=np.float64)
    slope, intercept = np.polyfit(t, arr, 1)
    return arr - (slope * t + intercept)


# ---------------------------------------------------------------------------
# Test wrappers
# ---------------------------------------------------------------------------


def _adf_p(values: np.ndarray) -> float:
    if values.size < 4 or np.allclose(values.std(), 0.0):
        return float("nan")
    try:
        from statsmodels.tsa.stattools import adfuller  # noqa: PLC0415
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = adfuller(values, autolag="AIC")
        return float(result[1])
    except Exception:  # noqa: BLE001
        return float("nan")


def _kpss_p(values: np.ndarray) -> float:
    if values.size < 4 or np.allclose(values.std(), 0.0):
        return float("nan")
    try:
        from statsmodels.tsa.stattools import kpss  # noqa: PLC0415
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # InterpolationWarning when p<0.01 / >0.1
            result = kpss(values, regression="c", nlags="auto")
        return float(result[1])
    except Exception:  # noqa: BLE001
        return float("nan")


def _zivot_andrews(values: np.ndarray) -> tuple[float | None, int | None]:
    """Run Zivot-Andrews on the raw signal; return ``(p_value, break_index)``.

    Returns ``(None, None)`` when ZA cannot run (signal too short, all-equal,
    or ``zivot_andrews`` raises).
    """
    if values.size < 12 or np.allclose(values.std(), 0.0):
        return None, None
    try:
        from statsmodels.tsa.stattools import zivot_andrews  # noqa: PLC0415
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = zivot_andrews(values, trim=0.15)
        # statsmodels returns (stat, pvalue, crit, baselags, bpidx)
        p = float(result[1])
        bp = int(result[4])
        return p, bp
    except Exception:  # noqa: BLE001
        return None, None


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------


def _is_stationary(adf_p: float, kpss_p: float, alpha: float) -> bool | None:
    """Return ``True`` (stationary), ``False`` (non-stationary), or ``None``
    when either p-value is NaN (test couldn't run)."""
    if np.isnan(adf_p) or np.isnan(kpss_p):
        return None
    return bool(adf_p < alpha and kpss_p >= alpha)


def _classify(
    adf_pre: float, adf_post: float,
    kpss_pre: float, kpss_post: float,
    *, alpha: float,
) -> str:
    pre = _is_stationary(adf_pre, kpss_pre, alpha)
    post = _is_stationary(adf_post, kpss_post, alpha)
    if pre is None or post is None:
        return VERDICT_UNDETERMINED
    if pre and not post:
        return VERDICT_INTRODUCED
    if not pre and post:
        return VERDICT_REDUCED
    if pre and post:
        return VERDICT_STATIONARY_PRESERVED
    return VERDICT_NONSTATIONARY_PRESERVED


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def joint_stationarity_check(
    x_pre: np.ndarray,
    x_post: np.ndarray,
    *,
    alpha: float = DEFAULT_ALPHA,
    detrend: bool = False,
    whiten: bool = False,
    ar_order: int | Literal["auto"] = "auto",
    edit_window: tuple[int, int] | None = None,
    break_tolerance: float = DEFAULT_BREAK_TOLERANCE,
) -> StationarityResult:
    """Run the joint stationarity battery on ``(x_pre, x_post)``.

    Pipeline (per side):
      1. (Optional, ``detrend=True``) OLS-detrend the signal — strips
         slope+intercept. Off by default because finite-sample detrending
         biases ADF toward rejecting on a random walk (Phillips 1988).
      2. (Optional, ``whiten=True``) Whiten the (possibly detrended)
         series via AR(``ar_order``); auto-select with the cube-root rule
         (capped at 10) when ``ar_order='auto'``. Off by default because
         whitening a random walk produces white noise and both tests then
         call it stationary.
      3. Run ADF (``H0`` unit root) and KPSS (``H0`` trend-stationary) on
         the resulting series; collect p-values.

    Then run Zivot-Andrews on the raw post signal to detect a single
    structural break. If ``edit_window=(start, end)`` is supplied and ZA
    detects a significant break (``p < alpha``), the break sample index is
    compared to the window: ``za_break_consistent`` is ``True`` iff the
    break sits within ``[start − tol·L, end + tol·L]`` where
    ``L = end − start`` and ``tol = break_tolerance``.

    Args:
        x_pre / x_post:    Pre- and post-edit signals (1-D arrays).
        alpha:             p-value threshold for the verdict and the ZA break.
        ar_order:          AR lag order for whitening; ``'auto'`` triggers
                           the cube-root rule capped at 10.
        edit_window:       Optional ``(start, end)`` (sample indices) for
                           the break-consistency check.
        break_tolerance:   Fractional slack on the edit window for the
                           consistency check; default 0.2 per AC.

    Returns:
        ``StationarityResult`` with raw p-values, the ZA break (when
        significant), the consistency flag, and a verdict.

    Raises:
        ``StationarityError`` only when the inputs are unusable (zero-length
        / shape-mismatch). Test-level failures fall back to ``NaN`` p-values
        and ``verdict='undetermined'``.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1); got {alpha}")
    if not 0.0 <= break_tolerance:
        raise ValueError(f"break_tolerance must be ≥ 0; got {break_tolerance}")

    pre = np.asarray(x_pre, dtype=np.float64).reshape(-1)
    post = np.asarray(x_post, dtype=np.float64).reshape(-1)
    if pre.size == 0 or post.size == 0:
        raise StationarityError("joint_stationarity_check: x_pre and x_post must be non-empty")

    pre_p = _detrend(pre) if detrend else pre.copy()
    post_p = _detrend(post) if detrend else post.copy()
    if whiten:
        pre_processed, lag_pre = whiten_residual(pre_p, ar_order=ar_order)
        post_processed, lag_post = whiten_residual(post_p, ar_order=ar_order)
    else:
        pre_processed, lag_pre = pre_p, 0
        post_processed, lag_post = post_p, 0

    adf_pre = _adf_p(pre_processed)
    adf_post = _adf_p(post_processed)
    kpss_pre = _kpss_p(pre_processed)
    kpss_post = _kpss_p(post_processed)

    za_p, za_break = _zivot_andrews(post)
    if za_p is None or za_p >= alpha:
        za_break = None  # not significant → don't surface
    consistent = _break_consistent(za_break, edit_window, break_tolerance, post.size)

    verdict = _classify(adf_pre, adf_post, kpss_pre, kpss_post, alpha=alpha)

    return StationarityResult(
        adf_pre_p=adf_pre,
        adf_post_p=adf_post,
        kpss_pre_p=kpss_pre,
        kpss_post_p=kpss_post,
        za_post_p=za_p,
        za_post_break=za_break,
        za_break_consistent=consistent,
        verdict=verdict,
        alpha=float(alpha),
        ar_order=int(max(lag_pre, lag_post)),
    )


def _break_consistent(
    break_idx: int | None,
    edit_window: tuple[int, int] | None,
    tolerance: float,
    n: int,
) -> bool | None:
    if break_idx is None or edit_window is None:
        return None
    start, end = int(edit_window[0]), int(edit_window[1])
    if not 0 <= start < end <= n:
        raise ValueError(
            f"edit_window must satisfy 0 ≤ start < end ≤ n; got {edit_window} for n={n}"
        )
    span = end - start
    slack = tolerance * span
    return float(start - slack) <= float(break_idx) <= float(end + slack)
