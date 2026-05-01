"""Eckhardt baseflow fitter — Eckhardt (2005) two-parameter recursive filter.

Splits a streamflow series Q(t) into a slow baseflow component b(t) and a
fast quickflow component q(t) such that Q = b + q exactly by construction.
The fitter is dispatched by SEG-019 when ``domain_hint='hydrology'``; the
output blob carries ``baseflow`` and ``quickflow`` as named components plus
the calibrated parameters ``BFImax`` and ``a`` as editable coefficients, so
OP-020 ``raise_lower`` on a baseflow segment becomes a hydrology-meaningful
``BFImax ← BFImax · α`` edit (SEG-021 baseflow / stormflow / recession_limb /
rising_limb labels).

References
----------
Eckhardt, K. (2005).
    How to construct recursive digital filters for baseflow separation.
    *Hydrological Processes* 19(2):507–515.
    DOI 10.1002/hyp.5675.
    → Eq. 6: two-parameter recursive filter; Table 1: regime-specific defaults.

Lyne, V., & Hollick, M. (1979).
    Stochastic time-variable rainfall-runoff modelling.
    *Institution of Engineers Australia National Conference Publication* 79/10.
    → Single-parameter precursor used here as the BFImax pre-estimator.

Tallaksen, L. M. (1995).
    A review of baseflow recession analysis.
    *J. Hydrology* 165:349–370.
    → Master recession curve framework for the recession-constant fit.
"""
from __future__ import annotations

import logging

import numpy as np

from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Calibration helpers — recession constant + long-term BFI
# ---------------------------------------------------------------------------


# Eckhardt (2005) Table 1 regime defaults; expressed for daily-step data and
# used as the fallback when calibration data is missing or non-physical.
DEFAULT_A: float = 0.98
DEFAULT_BFI_MAX: float = 0.80
A_LOWER_BOUND: float = 0.50
A_UPPER_BOUND: float = 0.999
BFI_MAX_LOWER_BOUND: float = 0.05
BFI_MAX_UPPER_BOUND: float = 0.95


def _normalize_segments(
    recession_segments: object,
    n: int,
) -> list[tuple[int, int]]:
    """Coerce ``recession_segments`` into a list of validated (start, end) pairs.

    Accepts either a list/tuple of ``(start, end)`` pairs or a 2-D array-like
    of shape ``(k, 2)``.  Out-of-range or empty intervals are dropped.
    """
    if recession_segments is None:
        return []
    pairs: list[tuple[int, int]] = []
    for seg in recession_segments:
        try:
            start, end = int(seg[0]), int(seg[1])
        except (TypeError, ValueError, IndexError):
            continue
        start = max(0, start)
        end = min(n, end)
        if end - start >= 2:
            pairs.append((start, end))
    return pairs


def estimate_recession_constant(
    Q: np.ndarray,
    recession_segments: object,
    fallback: float = DEFAULT_A,
) -> float:
    """Estimate the recession constant ``a`` from log-slope of recession segments.

    For each (start, end) recession segment, accumulates ``ln(Q[t+1]/Q[t])``
    over consecutive strictly-positive samples and returns
    ``a = exp(mean(log_ratios))`` clipped to ``[A_LOWER_BOUND, A_UPPER_BOUND]``.
    Falls back to ``fallback`` when no usable ratio is available.

    Reference: Tallaksen (1995) §3 — log-linear recession fit.
    """
    arr = np.asarray(Q, dtype=np.float64).ravel()
    n = len(arr)
    pairs = _normalize_segments(recession_segments, n)
    log_ratios: list[float] = []
    for start, end in pairs:
        seg = arr[start:end]
        for i in range(len(seg) - 1):
            qa, qb = float(seg[i]), float(seg[i + 1])
            if qa > 0.0 and qb > 0.0:
                log_ratios.append(float(np.log(qb / qa)))
    if not log_ratios:
        return float(np.clip(fallback, A_LOWER_BOUND, A_UPPER_BOUND))
    a = float(np.exp(float(np.mean(log_ratios))))
    return float(np.clip(a, A_LOWER_BOUND, A_UPPER_BOUND))


def _lyne_hollick_baseflow(Q: np.ndarray, a: float) -> np.ndarray:
    """Single forward pass of the Lyne & Hollick (1979) one-parameter filter.

    Used internally by :func:`estimate_long_term_bfi` to bootstrap a BFImax
    estimate before the Eckhardt two-parameter filter is run.

    The recursion is

        q(t)  = a · q(t−1) + (1 + a) / 2 · (Q(t) − Q(t−1))
        q(t) ← clip(q(t), 0, Q(t))
        b(t)  = Q(t) − q(t)

    with ``q(0) = 0`` so that ``b(0) = Q(0)``.
    """
    arr = np.asarray(Q, dtype=np.float64).ravel()
    n = len(arr)
    q = np.zeros(n, dtype=np.float64)
    b = np.zeros(n, dtype=np.float64)
    if n == 0:
        return b
    b[0] = arr[0]
    for t in range(1, n):
        raw_q = a * q[t - 1] + 0.5 * (1.0 + a) * (arr[t] - arr[t - 1])
        q[t] = max(0.0, min(raw_q, float(arr[t])))
        b[t] = float(arr[t]) - q[t]
    return b


def estimate_long_term_bfi(
    Q: np.ndarray,
    a: float = DEFAULT_A,
    fallback: float = DEFAULT_BFI_MAX,
    window_years: int | None = None,  # documentation-only; window mode is not implemented
) -> float:
    """Estimate ``BFImax`` as the long-term baseflow index via Lyne–Hollick.

    Runs a single forward pass of :func:`_lyne_hollick_baseflow` and returns
    ``sum(b) / sum(Q)``, clipped to a physically-plausible range.  Falls back
    to ``fallback`` when ``Q`` is empty or its total is non-positive.

    The ``window_years`` argument mirrors the ticket pseudocode signature
    (``estimate_long_term_bfi(Q, window_years=5)``); a windowed estimator is
    not implemented here because daily timestamps are not always available
    on the segment-level Q passed to the filter.
    """
    arr = np.asarray(Q, dtype=np.float64).ravel()
    if arr.size == 0:
        return float(np.clip(fallback, BFI_MAX_LOWER_BOUND, BFI_MAX_UPPER_BOUND))
    total = float(np.sum(arr))
    if total <= 0.0:
        return float(np.clip(fallback, BFI_MAX_LOWER_BOUND, BFI_MAX_UPPER_BOUND))
    b_lh = _lyne_hollick_baseflow(arr, float(a))
    bfi = float(np.sum(b_lh) / total)
    if window_years is not None:
        logger.debug(
            "estimate_long_term_bfi: window_years=%s requested but global BFI is used.",
            window_years,
        )
    return float(np.clip(bfi, BFI_MAX_LOWER_BOUND, BFI_MAX_UPPER_BOUND))


def calibrate_eckhardt(
    Q: np.ndarray,
    recession_segments: object,
) -> tuple[float, float]:
    """Calibrate ``(a, BFImax)`` from streamflow + user-flagged recession segments.

    Two-step procedure (Eckhardt 2005 §3; Tallaksen 1995):

    1. Estimate ``a`` from the master recession curve via
       :func:`estimate_recession_constant`.
    2. Plug that ``a`` into a Lyne–Hollick pre-filter and use the resulting
       long-term BFI as ``BFImax``.

    Args:
        Q:                  Streamflow series, shape (n,).  Must be non-negative.
        recession_segments: Iterable of ``(start, end)`` index pairs marking
                            falling-limb (recession) periods.

    Returns:
        ``(a, BFImax)`` — both clipped to the documented physical bounds.

    Raises:
        ValueError: If ``Q`` contains negative values.
    """
    arr = np.asarray(Q, dtype=np.float64).ravel()
    if (arr < 0.0).any():
        raise ValueError(
            f"calibrate_eckhardt: Q must be non-negative; "
            f"got min={float(arr.min())}."
        )
    a = estimate_recession_constant(arr, recession_segments)
    bfi_max = estimate_long_term_bfi(arr, a=a)
    return a, bfi_max


# ---------------------------------------------------------------------------
# Eckhardt recursive filter — Eckhardt (2005) Eq. 6
# ---------------------------------------------------------------------------


@register_fitter("Eckhardt")
def eckhardt_baseflow(
    Q: np.ndarray,
    bfi_max: float = DEFAULT_BFI_MAX,
    a: float = DEFAULT_A,
    **_kwargs,
) -> DecompositionBlob:
    """Apply the Eckhardt (2005) two-parameter recursive baseflow filter.

    Implements the recursion of Eckhardt 2005 Eq. 6 verbatim::

        b(t) = ((1 − BFImax) · a · b(t−1) + (1 − a) · BFImax · Q(t))
               / (1 − a · BFImax)

    subject to the physical constraint ``b(t) ≤ Q(t)`` (Eckhardt §2).
    The initial condition is ``b(0) = Q(0) · BFImax`` and the quickflow is
    ``q(t) = Q(t) − b(t)``, so ``Q ≡ b + q`` exactly by construction
    (``residual`` is the zero array).

    Args:
        Q:        Streamflow series, shape (n,).  Must be non-negative.
        bfi_max:  Long-term baseflow index ``BFImax``.  Catchment-specific;
                  Eckhardt 2005 Table 1 lists 0.80 (perennial / porous), 0.50
                  (ephemeral / porous), 0.25 (perennial / hard-rock) as
                  regime-specific defaults.  Must lie in (0, 1).
        a:        Recession constant.  Daily-step default 0.98 per Eckhardt
                  Table 1.  Must lie in (0, 1).

    Returns:
        :class:`DecompositionBlob` with ``method='Eckhardt'``, components
        ``{'baseflow', 'quickflow', 'residual'}`` (residual all-zeros) and
        coefficients ``{'BFImax', 'a'}`` for OP-020 ``raise_lower``.

    Raises:
        ValueError: If ``Q`` is multivariate, contains negative values, or if
                    ``a`` / ``bfi_max`` is outside the open interval (0, 1).
    """
    arr = np.asarray(Q, dtype=np.float64)
    if arr.ndim > 1 and (arr.ndim != 2 or arr.shape[1] != 1):
        raise ValueError(
            f"eckhardt_baseflow expects 1-D streamflow input; got shape {arr.shape}. "
            "Multi-channel Eckhardt is not implemented."
        )
    arr = arr.ravel()
    if (arr < 0.0).any():
        raise ValueError(
            f"eckhardt_baseflow: Q must be non-negative; "
            f"got min={float(arr.min())}."
        )
    if not (0.0 < float(a) < 1.0):
        raise ValueError(
            f"eckhardt_baseflow: recession constant a must be in (0, 1); got {a!r}."
        )
    if not (0.0 < float(bfi_max) < 1.0):
        raise ValueError(
            f"eckhardt_baseflow: BFImax must be in (0, 1); got {bfi_max!r}."
        )

    n = len(arr)
    b = np.zeros(n, dtype=np.float64)
    if n > 0:
        b[0] = float(arr[0]) * float(bfi_max)
        denom = 1.0 - float(a) * float(bfi_max)
        for t in range(1, n):
            raw = (
                (1.0 - float(bfi_max)) * float(a) * b[t - 1]
                + (1.0 - float(a)) * float(bfi_max) * float(arr[t])
            ) / denom
            b[t] = min(raw, float(arr[t]))

    quickflow = arr - b
    residual = np.zeros_like(arr)
    total_q = float(np.sum(arr))
    bfi = float(np.sum(b) / total_q) if total_q > 0.0 else 0.0

    return DecompositionBlob(
        method="Eckhardt",
        components={
            "baseflow": b,
            "quickflow": quickflow,
            "residual": residual,
        },
        coefficients={
            "BFImax": float(bfi_max),
            "a": float(a),
        },
        residual=residual,
        fit_metadata={
            "rmse": 0.0,  # Q ≡ b + q by construction
            "rank": 2,
            "n_params": 2,
            "convergence": True,
            "version": "1.0",
            "bfi": bfi,
        },
    )
