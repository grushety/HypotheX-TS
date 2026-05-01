"""aggregate — Tier-3 read-only summary metrics over selected segments (OP-033).

Computes named summary statistics (peak, trough, duration, area, amplitude,
period, τ, BFI, SOS/EOS, M₀) over one or more :class:`DecomposedSegment`
instances.  This is the *observational* counterpart to perturbation
operations — it answers "what is this region's summary metric?" without
modifying the series, the segments, or any decomposition blob.

The metric table is extensible: domain packs can append more metrics via
the :func:`register_metric` decorator (e.g. hydrology adds
``recession_coefficient``, phenology adds ``peak_value``).

Read-only contract
------------------
:func:`aggregate` is forbidden from mutating its inputs.  The caller's
``DecomposedSegment`` instances are frozen by construction (OP-030); the
underlying series ``X`` and any decomposition blob are *only read*, never
written.  The :func:`test_aggregate_is_read_only` test pins this
behaviour by checking byte-equality of every input before and after.

When the requested metric does not apply to a segment (e.g. ``'period'``
on a ``plateau`` segment without a fitted decomposition), the per-segment
result is ``None``; :func:`aggregate` does not silently fit a new blob.

References
----------
Eckhardt, K. (2005).  Hydrological Processes 19(2):507–515.  → BFI.
Jönsson, P. & Eklundh, L. (2004).  Computers & Geosciences 30:833–845.
    → TIMESAT SOS / EOS amplitude-threshold definitions; Table 1
    default 20 % threshold.
Aki, K. & Richards, P. (2002).  Quantitative Seismology, 2nd ed., Ch. 3.
    → Scalar seismic moment ``M₀ = μ · A · s``.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

import numpy as np

from .decompose import DecomposedSegment

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


MetricFn = Callable[[DecomposedSegment, np.ndarray, dict[str, Any]], Any]
METRIC_REGISTRY: dict[str, MetricFn] = {}


def register_metric(name: str) -> Callable[[MetricFn], MetricFn]:
    """Decorator that registers a metric callable in :data:`METRIC_REGISTRY`.

    Domain packs (SEG-021..023) can extend the table at import time::

        @register_metric("recession_coefficient")
        def metric_recession_coefficient(seg, X_seg, aux):
            ...
    """

    def decorator(fn: MetricFn) -> MetricFn:
        if name in METRIC_REGISTRY and METRIC_REGISTRY[name] is not fn:
            logger.warning(
                "register_metric: re-registering %r — previous callable replaced.",
                name,
            )
        METRIC_REGISTRY[name] = fn
        return fn

    return decorator


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def aggregate(
    X: np.ndarray,
    segments: list[DecomposedSegment],
    metric: str,
    aux: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute ``metric`` over each segment and return a result dict.

    Args:
        X:        Underlying time series, shape ``(n,)``.
        segments: Iterable of :class:`DecomposedSegment` to aggregate over.
        metric:   Key into :data:`METRIC_REGISTRY`.
        aux:      Optional metric-specific auxiliary data
                  (e.g. ``{'dt': 0.5, 'shear_modulus': 3e10}``).

    Returns:
        ``dict[segment_id, metric_value]``.  ``metric_value`` is ``None``
        when the metric is not applicable to a given segment.

    Raises:
        ValueError: ``metric`` is not registered, or a segment's bounds
                    fall outside ``X``.
    """
    if metric not in METRIC_REGISTRY:
        known = sorted(METRIC_REGISTRY)
        raise ValueError(
            f"aggregate: unknown metric {metric!r}. Registered metrics: {known}."
        )

    arr = np.asarray(X, dtype=np.float64).ravel()
    n = len(arr)
    metric_fn = METRIC_REGISTRY[metric]
    eff_aux: dict[str, Any] = aux or {}

    results: dict[str, Any] = {}
    for seg in segments:
        _validate_bounds(seg, n)
        X_seg = arr[seg.start_index : seg.end_index + 1]
        try:
            results[seg.segment_id] = metric_fn(seg, X_seg, eff_aux)
        except Exception as exc:  # noqa: BLE001 — never crash the table
            logger.warning(
                "aggregate: metric %r failed on segment %r: %s",
                metric, seg.segment_id, exc,
            )
            results[seg.segment_id] = None

    return results


def _validate_bounds(seg: DecomposedSegment, n: int) -> None:
    if seg.start_index < 0:
        raise ValueError(
            f"aggregate: segment {seg.segment_id!r} has start_index "
            f"{seg.start_index} < 0."
        )
    if seg.end_index >= n:
        raise ValueError(
            f"aggregate: segment {seg.segment_id!r} has end_index "
            f"{seg.end_index} ≥ series length {n}."
        )
    if seg.end_index < seg.start_index:
        raise ValueError(
            f"aggregate: segment {seg.segment_id!r} has end_index "
            f"{seg.end_index} < start_index {seg.start_index}."
        )


# ---------------------------------------------------------------------------
# Built-in metrics
# ---------------------------------------------------------------------------


@register_metric("peak")
def metric_peak(seg: DecomposedSegment, X_seg: np.ndarray, aux: dict[str, Any]) -> float | None:
    """Maximum value over the segment."""
    if X_seg.size == 0:
        return None
    return float(np.max(X_seg))


@register_metric("trough")
def metric_trough(seg: DecomposedSegment, X_seg: np.ndarray, aux: dict[str, Any]) -> float | None:
    """Minimum value over the segment."""
    if X_seg.size == 0:
        return None
    return float(np.min(X_seg))


@register_metric("duration")
def metric_duration(seg: DecomposedSegment, X_seg: np.ndarray, aux: dict[str, Any]) -> float:
    """Segment length × ``aux['dt']`` (default ``dt=1``).

    Uses ``seg.length = end − start + 1`` so an inclusive single-sample
    segment has duration ``dt``.
    """
    dt = float(aux.get("dt", 1.0))
    return float(seg.length) * dt


@register_metric("area")
def metric_area(seg: DecomposedSegment, X_seg: np.ndarray, aux: dict[str, Any]) -> float | None:
    """Trapezoidal integral of the segment values with spacing ``aux['dt']``."""
    if X_seg.size < 2:
        return None
    dt = float(aux.get("dt", 1.0))
    return float(np.trapezoid(X_seg, dx=dt))


@register_metric("amplitude")
def metric_amplitude(seg: DecomposedSegment, X_seg: np.ndarray, aux: dict[str, Any]) -> float | None:
    """Peak-to-trough range: ``max(X_seg) − min(X_seg)``."""
    if X_seg.size == 0:
        return None
    return float(np.max(X_seg) - np.min(X_seg))


@register_metric("period")
def metric_period(seg: DecomposedSegment, X_seg: np.ndarray, aux: dict[str, Any]) -> float | None:
    """Dominant period from the decomposition blob's ``coefficients['period']``.

    Returns ``None`` when the segment has no fitted decomposition or
    when the blob does not carry a ``'period'`` coefficient (e.g.
    plateau / trend / step methods).
    """
    blob = seg.decomposition
    if blob is None:
        return None
    val = blob.coefficients.get("period")
    return float(val) if val is not None else None


@register_metric("tau")
def metric_tau(seg: DecomposedSegment, X_seg: np.ndarray, aux: dict[str, Any]) -> float | None:
    """First transient-feature time constant ``τ`` (GrAtSiD blobs only).

    Reads ``seg.decomposition.coefficients['features'][0]['tau']``;
    returns ``None`` when the blob is missing, the method is not
    GrAtSiD, or the feature list is empty.
    """
    blob = seg.decomposition
    if blob is None or blob.method != "GrAtSiD":
        return None
    feats = blob.coefficients.get("features") or []
    if not feats:
        return None
    first = feats[0]
    if isinstance(first, dict) and "tau" in first:
        return float(first["tau"])
    return None


@register_metric("bfi")
def metric_bfi(seg: DecomposedSegment, X_seg: np.ndarray, aux: dict[str, Any]) -> float | None:
    """Baseflow Index (Eckhardt 2005): ``Σ baseflow / Σ Q``.

    Reads ``seg.decomposition.components['baseflow']``; returns
    ``None`` when the blob lacks a ``'baseflow'`` component or when the
    total flow is non-positive.
    """
    blob = seg.decomposition
    if blob is None:
        return None
    bflow = blob.components.get("baseflow")
    if bflow is None:
        return None
    total_q = float(np.sum(X_seg))
    if total_q <= 0.0:
        return None
    return float(np.sum(bflow) / total_q)


@register_metric("sos_eos")
def metric_sos_eos(
    seg: DecomposedSegment, X_seg: np.ndarray, aux: dict[str, Any],
) -> dict[str, Any] | None:
    """TIMESAT-style start-of-season / end-of-season indices (Jönsson 2004).

    Returns ``{'sos': int, 'eos': int, 'threshold_value': float}`` —
    ``sos`` is the first sample at or above ``threshold_percent`` of the
    segment's amplitude range, ``eos`` is the last such sample.

    ``aux['threshold_percent']`` defaults to 20 (Jönsson Table 1 SOS).
    Returns ``None`` for segments shorter than 2 samples or when the
    segment's amplitude is exactly zero.
    """
    if X_seg.size < 2:
        return None
    threshold_percent = float(aux.get("threshold_percent", 20.0))
    arr_min = float(np.min(X_seg))
    arr_max = float(np.max(X_seg))
    amplitude = arr_max - arr_min
    if amplitude <= 0.0:
        return None
    threshold_value = arr_min + (threshold_percent / 100.0) * amplitude
    above = X_seg >= threshold_value
    if not above.any():
        return None
    sos = int(np.argmax(above))
    eos = int(len(X_seg) - 1 - np.argmax(above[::-1]))
    return {"sos": sos, "eos": eos, "threshold_value": float(threshold_value)}


@register_metric("m0")
def metric_m0(seg: DecomposedSegment, X_seg: np.ndarray, aux: dict[str, Any]) -> float | None:
    """Scalar seismic moment ``M₀ = μ · A · s`` (Aki & Richards 2002 Ch. 3).

    Requires ``aux`` to carry ``shear_modulus`` (μ, Pa), ``fault_area``
    (A, m²), and ``slip_from_segment`` (s, m).  Returns ``None`` when
    any of the three is missing — this is a "user must supply rock
    properties" metric, not derivable from the segment alone.
    """
    required = ("shear_modulus", "fault_area", "slip_from_segment")
    if not all(k in aux for k in required):
        return None
    return float(aux["shear_modulus"] * aux["fault_area"] * aux["slip_from_segment"])
