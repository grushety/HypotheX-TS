"""Tier-1 stochastic atoms: suppress, add_uncertainty (OP-013).

suppress       — replace a segment with an inferred baseline via one of five
                 fill strategies (linear, spline, stl_trend, climatology,
                 baseflow).
add_uncertainty — inject calibrated colored noise (white, pink, red) on top of
                 the segment signal.

Paper references
----------------
Timmer, J. & König, M. (1995) "On generating power law noise",
    Astron. Astrophys. 300:707-710.
    → add_uncertainty colored-noise generator (library: colorednoise).

Cleveland, R. B., Cleveland, W. S., McRae, J. E., & Terpenning, I. (1990).
    STL: A Seasonal-Trend Decomposition Procedure Based on Loess.
    Journal of Official Statistics 6(1):3-73.
    → suppress stl_trend strategy delegates to SEG-014 STL fitter.

Eckhardt, K. (2005) "How to construct recursive digital bandpass filters for
    baseflow separation", Hydrological Processes 19(2):507-515.
    → suppress baseflow strategy delegates to SEG-016 Eckhardt fitter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from app.services.operations.relabeler.relabeler import RelabelResult

logger = logging.getLogger(__name__)

_FILL_STRATEGIES = ("linear", "spline", "stl_trend", "climatology", "baseflow")
_NOISE_COLORS = ("white", "pink", "red")

_DOMAIN_DEFAULT_STRATEGY: dict[str, str] = {
    "remote_sensing": "climatology",
    "hydrology": "baseflow",
}
_DEFAULT_STRATEGY = "linear"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class StochasticOpResult:
    """Result of a Tier-1 stochastic operation.

    Attributes:
        values:   Edited segment values (numpy array).
        op_name:  'suppress' or 'add_uncertainty'.
        relabel:  suppress → RECLASSIFY_VIA_SEGMENTER;
                  add_uncertainty → PRESERVED.
        tier:     Always 1.
    """

    values: np.ndarray
    op_name: str
    relabel: RelabelResult
    tier: int = 1


# ---------------------------------------------------------------------------
# Relabeler helpers
# ---------------------------------------------------------------------------


def _preserved(pre_shape: str) -> RelabelResult:
    return RelabelResult(
        new_shape=pre_shape,
        confidence=1.0,
        needs_resegment=False,
        rule_class="PRESERVED",
    )


def _reclassify(pre_shape: str) -> RelabelResult:
    return RelabelResult(
        new_shape=pre_shape,
        confidence=0.0,
        needs_resegment=True,
        rule_class="RECLASSIFY_VIA_SEGMENTER",
    )


# ---------------------------------------------------------------------------
# suppress
# ---------------------------------------------------------------------------


def suppress(
    X_seg: np.ndarray,
    ctx_pre: np.ndarray | None = None,
    ctx_post: np.ndarray | None = None,
    strategy: str | None = None,
    aux: dict[str, Any] | None = None,
    domain_hint: str | None = None,
    pre_shape: str = "unknown",
) -> StochasticOpResult:
    """Replace segment with an inferred baseline.

    The fill strategy is chosen in priority order:
      1. ``strategy`` argument (explicit)
      2. Domain-hint default: 'climatology' for remote_sensing, 'baseflow' for
         hydrology (see ``_DOMAIN_DEFAULT_STRATEGY``)
      3. 'linear' fallback

    Fill strategies:
      linear       — linearly interpolates between the mean of the last 3
                     samples of ctx_pre and the mean of the first 3 of ctx_post.
      spline       — CubicSpline through ctx_pre ++ ctx_post anchors.
      stl_trend    — STL decomposition of [ctx_pre, X_seg, ctx_post]; returns the
                     trend slice covering X_seg.  Delegates to statsmodels STL
                     (SEG-014).  Requires aux={'period': int}.
      climatology  — index aux['doy_climatology'] by aux['dates_in_segment'].
                     Requires aux with both keys.
      baseflow     — Eckhardt recursive filter on [ctx_pre, X_seg, ctx_post];
                     returns the baseflow slice.  Delegates to SEG-016 fitter.
                     Accepts optional aux keys: alpha, bfi_max.

    Args:
        X_seg:       Segment signal, shape (n,).
        ctx_pre:     Left-context values (may be empty or None).
        ctx_post:    Right-context values (may be empty or None).
        strategy:    One of the five fill strategies; None → domain/fallback.
        aux:         Strategy-specific parameters dict.
        domain_hint: 'hydrology' | 'remote_sensing' | other → default strategy.
        pre_shape:   Shape label before the edit, for relabeling.

    Returns:
        StochasticOpResult with filled values and RECLASSIFY_VIA_SEGMENTER.

    Raises:
        ValueError: Unknown strategy, or required aux keys are missing.
    """
    arr = np.asarray(X_seg, dtype=np.float64)
    pre = np.asarray(ctx_pre if ctx_pre is not None else [], dtype=np.float64)
    post = np.asarray(ctx_post if ctx_post is not None else [], dtype=np.float64)
    aux = aux or {}

    chosen = strategy or _DOMAIN_DEFAULT_STRATEGY.get(domain_hint or "", _DEFAULT_STRATEGY)

    if chosen not in _FILL_STRATEGIES:
        raise ValueError(
            f"suppress: unknown fill strategy '{chosen}'. "
            f"Valid strategies: {_FILL_STRATEGIES}."
        )

    filled = _fill(arr, pre, post, chosen, aux)
    return StochasticOpResult(
        values=filled,
        op_name="suppress",
        relabel=_reclassify(pre_shape),
    )


def _fill(
    arr: np.ndarray,
    pre: np.ndarray,
    post: np.ndarray,
    strategy: str,
    aux: dict[str, Any],
) -> np.ndarray:
    if strategy == "linear":
        return _fill_linear(arr, pre, post)

    if strategy == "spline":
        return _fill_spline(arr, pre, post)

    if strategy == "stl_trend":
        return _fill_stl_trend(arr, pre, post, aux)

    if strategy == "climatology":
        return _fill_climatology(arr, aux)

    if strategy == "baseflow":
        return _fill_baseflow(arr, pre, post, aux)

    raise ValueError(f"suppress: unhandled strategy '{strategy}'.")  # unreachable


def _fill_linear(arr: np.ndarray, pre: np.ndarray, post: np.ndarray) -> np.ndarray:
    n = len(arr)
    v_left = float(np.mean(pre[-3:])) if len(pre) >= 1 else float(arr[0])
    v_right = float(np.mean(post[:3])) if len(post) >= 1 else float(arr[-1])
    return np.linspace(v_left, v_right, n)


def _fill_spline(arr: np.ndarray, pre: np.ndarray, post: np.ndarray) -> np.ndarray:
    from scipy.interpolate import CubicSpline  # noqa: PLC0415

    n = len(arr)
    if len(pre) == 0 and len(post) == 0:
        return np.full(n, float(np.mean(arr)))

    t_known: list[float] = []
    y_known: list[float] = []

    if len(pre) > 0:
        for i, v in enumerate(pre):
            t_known.append(float(i - len(pre)))
            y_known.append(float(v))

    if len(post) > 0:
        for i, v in enumerate(post):
            t_known.append(float(n + i))
            y_known.append(float(v))

    if len(t_known) < 2:
        return _fill_linear(arr, pre, post)

    t_arr = np.array(t_known)
    y_arr = np.array(y_known)
    cs = CubicSpline(t_arr, y_arr)
    return cs(np.arange(n, dtype=float))


def _fill_stl_trend(
    arr: np.ndarray,
    pre: np.ndarray,
    post: np.ndarray,
    aux: dict[str, Any],
) -> np.ndarray:
    """Delegates to SEG-014 statsmodels STL.

    Requires aux['period'] (int).
    """
    from statsmodels.tsa.seasonal import STL  # noqa: PLC0415

    period = int(aux.get("period", 0))
    if period < 2:
        raise ValueError(
            "suppress stl_trend: aux['period'] must be an integer >= 2."
        )

    full = np.concatenate([pre, arr, post])
    if len(full) < 2 * period + 1:
        logger.warning(
            "suppress stl_trend: series too short for period=%d; falling back to linear.",
            period,
        )
        return _fill_linear(arr, pre, post)

    stl_result = STL(full, period=period).fit()
    trend = stl_result.trend
    start = len(pre)
    return trend[start : start + len(arr)].copy()


def _fill_climatology(arr: np.ndarray, aux: dict[str, Any]) -> np.ndarray:
    """Index a day-of-year climatology by the segment dates.

    Requires aux['doy_climatology'] (array or dict mapping DOY → value)
    and aux['dates_in_segment'] (array of DOY integers, length == len(arr)).
    """
    clim = aux.get("doy_climatology")
    dates = aux.get("dates_in_segment")
    if clim is None or dates is None:
        raise ValueError(
            "suppress climatology: aux must contain 'doy_climatology' and "
            "'dates_in_segment'."
        )
    dates_arr = np.asarray(dates, dtype=int)
    if len(dates_arr) != len(arr):
        raise ValueError(
            f"suppress climatology: dates_in_segment length {len(dates_arr)} "
            f"does not match segment length {len(arr)}."
        )
    if isinstance(clim, dict):
        try:
            return np.array([float(clim[d]) for d in dates_arr])
        except KeyError as exc:
            raise ValueError(
                f"suppress climatology: DOY key {exc} not found in doy_climatology dict."
            ) from exc
    clim_arr = np.asarray(clim, dtype=np.float64)
    try:
        return clim_arr[dates_arr].astype(np.float64)
    except IndexError as exc:
        raise ValueError(
            f"suppress climatology: dates_in_segment contains an index out of bounds "
            f"for doy_climatology array of length {len(clim_arr)}."
        ) from exc


def _fill_baseflow(
    arr: np.ndarray,
    pre: np.ndarray,
    post: np.ndarray,
    aux: dict[str, Any],
) -> np.ndarray:
    """Delegates to SEG-016 Eckhardt fitter.

    Optional aux keys: alpha (default 0.925), bfi_max (default 0.80).
    """
    from app.services.decomposition.fitters.eckhardt import fit_eckhardt  # noqa: PLC0415

    full = np.concatenate([pre, arr, post])
    alpha = float(aux.get("alpha", 0.925))
    bfi_max = float(aux.get("bfi_max", 0.80))
    blob = fit_eckhardt(full, alpha=alpha, bfi_max=bfi_max)
    baseflow = blob.components["baseflow"]
    start = len(pre)
    return baseflow[start : start + len(arr)].copy()


# ---------------------------------------------------------------------------
# add_uncertainty
# ---------------------------------------------------------------------------


def add_uncertainty(
    X_seg: np.ndarray,
    sigma: float,
    color: Literal["white", "pink", "red"] = "white",
    seed: int | None = None,
    pre_shape: str = "unknown",
) -> StochasticOpResult:
    """Inject calibrated colored noise onto the segment.

    Noise colors:
      white — Gaussian N(0, σ²) via numpy (i.i.d. across samples).
      pink  — 1/f power spectrum (β=1) via Timmer & König (1995).
      red   — Brownian 1/f² spectrum (β=2) via Timmer & König (1995).

    The generated noise is scaled so that its standard deviation equals σ.
    Pink and red noise are generated by ``colorednoise.powerlaw_psd_gaussian``
    and then normalized.

    Deterministic mode: when ``seed`` is provided, the output is bit-identical
    across independent calls with the same seed.

    Source:
        Timmer, J. & König, M. (1995) "On generating power law noise",
        Astron. Astrophys. 300:707-710.

    Args:
        X_seg:     Segment signal, shape (n,).
        sigma:     Standard deviation of the injected noise.
        color:     'white', 'pink', or 'red'.
        seed:      Optional integer seed for reproducibility.
        pre_shape: Shape label before the edit, for relabeling.

    Returns:
        StochasticOpResult with noisy values and relabel=PRESERVED.

    Raises:
        ValueError: sigma < 0 or unknown color.
    """
    if sigma < 0:
        raise ValueError(f"add_uncertainty: sigma must be >= 0, got {sigma}.")
    if color not in _NOISE_COLORS:
        raise ValueError(
            f"add_uncertainty: unknown color '{color}'. "
            f"Valid colors: {_NOISE_COLORS}."
        )

    arr = np.asarray(X_seg, dtype=np.float64)
    n = len(arr)
    rng = np.random.default_rng(seed)

    if color == "white":
        noise = rng.normal(0.0, sigma, n)
    else:
        try:
            import colorednoise  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "add_uncertainty colored noise requires colorednoise. "
                "Install with: pip install colorednoise"
            ) from exc

        beta = {"pink": 1.0, "red": 2.0}[color]
        raw = colorednoise.powerlaw_psd_gaussian(beta, n, random_state=rng)
        raw_std = float(np.std(raw))
        if raw_std > 1e-12:
            noise = raw * (sigma / raw_std)
        else:
            logger.warning(
                "add_uncertainty %s: generated noise has near-zero std; returning zero noise.",
                color,
            )
            noise = np.zeros(n)

    return StochasticOpResult(
        values=arr + noise,
        op_name="add_uncertainty",
        relabel=_preserved(pre_shape),
    )


# ---------------------------------------------------------------------------
# Default strategy helper
# ---------------------------------------------------------------------------


def default_suppress_strategy(domain_hint: str | None) -> str:
    """Return the default fill strategy for a given domain hint.

    remote_sensing → 'climatology'
    hydrology      → 'baseflow'
    other / None   → 'linear'
    """
    return _DOMAIN_DEFAULT_STRATEGY.get(domain_hint or "", _DEFAULT_STRATEGY)
