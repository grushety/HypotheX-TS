"""align_warp — Tier-3 user-invocable temporal alignment (OP-031).

Aligns one or more segments to a reference segment via DTW, soft-DTW, or
ShapeDBA-style soft-DTW barycenter averaging.  The result replaces each
segment's *values* with a length-preserving warp onto the reference's
time axis — alignment is a value-space rewrite, not a decomposition
edit.

Compatibility (per *Implementation Plan* §6.3 and the OP-031 ticket):

    cycle / spike / transient → ✓ (no warning)
    plateau / trend           → ✓ with ``approx`` warning in audit
    noise                     → :class:`IncompatibleOp` (refused)

Methods
-------
``dtw``       Sakoe-Chiba constrained DTW (Sakoe & Chiba 1978).  The path
              is collapsed onto the reference axis by averaging the segment
              values that map to each reference index.
``soft_dtw``  Differentiable soft-DTW alignment (Cuturi & Blondel 2017).
              The full soft-alignment matrix is row-normalised and used as
              soft warp weights, producing a smoother, gradient-friendly
              warp.
``shapedba``  Soft-DTW barycenter (Petitjean 2011 / Holder 2023).  Returns
              the shape-preserving barycenter of ``[reference, segment]``,
              initialised to the reference so the output length matches.

References
----------
- Sakoe & Chiba (1978) "Dynamic programming algorithm optimization for
  spoken word recognition" — *IEEE ASSP* 26(1):43–49.
- Cuturi & Blondel (2017) "Soft-DTW: a differentiable loss function for
  time-series" — *ICML 2017*. arXiv 1703.01541.
- Petitjean, Ketterlin, Gançarski (2011) "A global averaging method for
  Dynamic Time Warping, with applications to clustering" — *Pattern
  Recognition* 44(3):678–693.
- Holder, Middlehurst, Bagnall (2023) "ShapeDBA" — *IDA 2023*.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

import numpy as np
import tslearn.barycenters as _bary
import tslearn.metrics as _metrics

from app.services.events import (
    AuditLog,
    EventBus,
    default_audit_log,
    default_event_bus,
)


# ---------------------------------------------------------------------------
# Shape vocabulary contract — mirrors SEG-008 ``_SHAPE_LABELS``
# ---------------------------------------------------------------------------


COMPATIBLE_SHAPES: frozenset[str] = frozenset({"cycle", "spike", "transient"})
APPROX_SHAPES: frozenset[str] = frozenset({"plateau", "trend"})
INCOMPATIBLE_SHAPES: frozenset[str] = frozenset({"noise"})

AlignMethod = Literal["dtw", "soft_dtw", "shapedba"]
ALIGN_METHODS: tuple[AlignMethod, ...] = ("dtw", "soft_dtw", "shapedba")


class IncompatibleOp(ValueError):
    """Raised when an operation is invoked on a segment whose shape label
    is not compatible with the operation's semantics.

    Used by :func:`align_warp` to refuse ``noise`` segments — a temporal
    warp on white-noise has no meaningful interpretation.
    """


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AlignableSegment:
    """Segment carrying its raw values for alignment.

    Tier-3 alignment ops consume and return :class:`AlignableSegment`
    rather than :class:`DecomposedSegment` because the unit of edit at
    this op is the time-axis warp of the segment values — no
    decomposition blob is required.

    Attributes:
        segment_id: Stable identifier across edits.
        label:      Shape primitive label (e.g. ``'cycle'``).
        values:     Segment values, shape ``(n,)``, dtype ``float64``.
    """

    segment_id: str
    label: str
    values: np.ndarray

    @property
    def length(self) -> int:
        return int(np.asarray(self.values).shape[0])

    def with_values(self, new_values: np.ndarray) -> "AlignableSegment":
        return replace(self, values=np.asarray(new_values, dtype=np.float64).ravel())


@dataclass(frozen=True)
class AlignWarpAudit:
    """Tier-3 audit entry emitted by :func:`align_warp`.

    Recorded on :data:`app.services.events.default_audit_log` and
    published as an ``'align_warp'`` event on
    :data:`app.services.events.default_event_bus`.

    Attributes:
        op_name:        Always ``'align_warp'``.
        tier:           Always ``3``.
        segment_ids:    Tuple of aligned segment ids (excludes the
                        reference segment).
        reference_id:   Identifier of the reference segment.
        method:         One of :data:`ALIGN_METHODS`.
        warping_band:   Sakoe-Chiba band as a fraction in ``(0, 1]``.
        approx_segment_ids:  Segments where the warp is approximate
                             (plateau / trend); empty tuple if none.
        extra:          Free-form metadata (e.g. soft-DTW gamma, costs).
    """

    op_name: str
    tier: int
    segment_ids: tuple[str, ...]
    reference_id: str
    method: AlignMethod
    warping_band: float
    approx_segment_ids: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


DEFAULT_WARPING_BAND: float = 0.1
DEFAULT_SOFT_DTW_GAMMA: float = 0.1


def align_warp(
    segments: list[AlignableSegment],
    reference_seg: AlignableSegment,
    method: AlignMethod = "dtw",
    warping_band: float = DEFAULT_WARPING_BAND,
    *,
    soft_dtw_gamma: float = DEFAULT_SOFT_DTW_GAMMA,
    event_bus: EventBus | None = None,
    audit_log: AuditLog | None = None,
) -> tuple[list[AlignableSegment], AlignWarpAudit]:
    """Warp each segment onto the reference's time axis.

    Args:
        segments:        Segments to align.  May be empty.
        reference_seg:   The segment whose time axis defines the target.
                         Its label is checked against the same compatibility
                         table as any other segment.
        method:          One of :data:`ALIGN_METHODS`; default ``'dtw'``.
        warping_band:    Sakoe-Chiba band as a fraction of segment length,
                         in ``(0, 1]``.  Default ``0.1`` (10 %).
        soft_dtw_gamma:  Smoothness parameter for ``soft_dtw`` and
                         ``shapedba``.  Smaller → closer to hard DTW.
        event_bus:       Override for the event bus (default: package default).
        audit_log:       Override for the audit log (default: package default).

    Returns:
        ``(aligned_segments, audit)`` — a *new* list of
        :class:`AlignableSegment` (length-equal to the reference) and the
        emitted :class:`AlignWarpAudit`.

    Raises:
        IncompatibleOp: A segment (including the reference) carries the
                        ``noise`` label.
        ValueError:     Unknown ``method`` or invalid ``warping_band``.
    """
    if method not in ALIGN_METHODS:
        raise ValueError(
            f"align_warp: unknown method {method!r}; "
            f"expected one of {ALIGN_METHODS}."
        )
    if not (0 < warping_band <= 1.0):
        raise ValueError(
            f"align_warp: warping_band must lie in (0, 1]; got {warping_band!r}."
        )

    ref_values = np.asarray(reference_seg.values, dtype=np.float64).ravel()
    if ref_values.size == 0:
        raise ValueError("align_warp: reference segment has zero length.")

    _check_compatibility(reference_seg)

    bus = event_bus if event_bus is not None else default_event_bus
    log = audit_log if audit_log is not None else default_audit_log

    aligned: list[AlignableSegment] = []
    approx_ids: list[str] = []
    costs: dict[str, float] = {}

    for seg in segments:
        is_approx = _check_compatibility(seg)
        if is_approx:
            approx_ids.append(seg.segment_id)

        seg_values = np.asarray(seg.values, dtype=np.float64).ravel()
        if seg_values.size == 0:
            aligned.append(seg.with_values(np.zeros_like(ref_values)))
            costs[seg.segment_id] = float("nan")
            continue

        if method == "dtw":
            warped, cost = _warp_dtw(seg_values, ref_values, warping_band)
        elif method == "soft_dtw":
            warped, cost = _warp_soft_dtw(seg_values, ref_values, soft_dtw_gamma)
        else:  # 'shapedba'
            warped, cost = _warp_shapedba(seg_values, ref_values, soft_dtw_gamma)

        aligned.append(seg.with_values(warped))
        costs[seg.segment_id] = float(cost)

    audit = AlignWarpAudit(
        op_name="align_warp",
        tier=3,
        segment_ids=tuple(seg.segment_id for seg in segments),
        reference_id=reference_seg.segment_id,
        method=method,
        warping_band=float(warping_band),
        approx_segment_ids=tuple(approx_ids),
        extra={
            "costs": costs,
            "soft_dtw_gamma": float(soft_dtw_gamma) if method != "dtw" else None,
        },
    )
    log.append(audit)
    bus.publish("align_warp", audit)

    return aligned, audit


# ---------------------------------------------------------------------------
# Per-method warp helpers
# ---------------------------------------------------------------------------


def _warp_dtw(
    seg_values: np.ndarray,
    ref_values: np.ndarray,
    warping_band: float,
) -> tuple[np.ndarray, float]:
    """Hard DTW warp constrained by Sakoe-Chiba radius.

    The radius is computed against the *segment* length, matching the
    OP-031 pseudocode.  ``radius=0`` collapses to point-wise alignment
    (still valid when the two series have the same length); we raise it
    to a minimum of 1 so the band always permits non-trivial paths.
    """
    radius = max(1, int(round(warping_band * len(seg_values))))
    path, cost = _metrics.dtw_path(
        ref_values,
        seg_values,
        sakoe_chiba_radius=radius,
    )
    warped = _collapse_path_to_reference(seg_values, path, len(ref_values))
    return warped, cost


def _warp_soft_dtw(
    seg_values: np.ndarray,
    ref_values: np.ndarray,
    gamma: float,
) -> tuple[np.ndarray, float]:
    """Soft-DTW warp using the full alignment matrix as soft weights.

    `tslearn.metrics.soft_dtw_alignment` returns ``(E, sd)`` where
    ``E[i, j]`` is the soft-alignment mass between reference index ``i``
    and segment index ``j``.  Row-normalising gives the soft warp.

    A fully-degenerate row (``E[i, :].sum() == 0``) is replaced with the
    raw segment value at the closest fractional index — this only
    happens for pathological inputs (e.g. constant-zero series) and
    keeps the output length equal to the reference.
    """
    alignment, sd_dist = _metrics.soft_dtw_alignment(
        ref_values,
        seg_values,
        gamma=gamma,
    )
    row_sums = alignment.sum(axis=1, keepdims=True)
    safe_sums = np.where(row_sums > 0, row_sums, 1.0)
    weights = alignment / safe_sums
    warped = weights @ seg_values

    # Guard the degenerate-row case: fall back to nearest-neighbour resampling.
    degenerate = (row_sums.ravel() <= 0)
    if degenerate.any():
        n_ref = len(ref_values)
        n_seg = len(seg_values)
        idx = np.minimum(
            np.floor(np.arange(n_ref) * n_seg / max(n_ref, 1)).astype(int),
            n_seg - 1,
        )
        warped = np.where(degenerate, seg_values[idx], warped)

    return warped, float(sd_dist)


def _warp_shapedba(
    seg_values: np.ndarray,
    ref_values: np.ndarray,
    gamma: float,
) -> tuple[np.ndarray, float]:
    """Soft-DTW barycenter of ``[reference, segment]``.

    Initialised at the reference so the barycenter length matches the
    reference exactly.  ``tslearn.barycenters.softdtw_barycenter``
    expects a list of 2-D arrays; we reshape to ``(n, 1)`` and reduce
    back to 1-D on output.

    The "cost" reported in the audit is the soft-DTW distance from the
    barycenter to the reference — a coarse proxy for "how far did this
    segment pull the average from the reference".
    """
    init = ref_values.reshape(-1, 1)
    bc_2d = _bary.softdtw_barycenter(
        [ref_values.reshape(-1, 1), seg_values.reshape(-1, 1)],
        gamma=gamma,
        init=init,
    )
    warped = np.asarray(bc_2d, dtype=np.float64).ravel()
    _, sd_dist = _metrics.soft_dtw_alignment(ref_values, warped, gamma=gamma)
    return warped, float(sd_dist)


def _collapse_path_to_reference(
    seg_values: np.ndarray,
    path: list[tuple[int, int]],
    target_length: int,
) -> np.ndarray:
    """Average segment values per reference index along a DTW path.

    The ``path`` is a list of ``(i_ref, j_seg)`` pairs; for each
    reference index ``i`` we collect every segment value ``seg[j]``
    that maps to it and take the arithmetic mean.  Reference indices
    missing from the path (impossible for a proper DTW path but
    defended for safety) get the segment's first value.
    """
    out = np.zeros(target_length, dtype=np.float64)
    counts = np.zeros(target_length, dtype=np.int64)
    for i_ref, j_seg in path:
        out[i_ref] += seg_values[j_seg]
        counts[i_ref] += 1
    missing = counts == 0
    if missing.any():
        out[missing] = seg_values[0]
        counts[missing] = 1
    return out / counts


# ---------------------------------------------------------------------------
# Compatibility check
# ---------------------------------------------------------------------------


def _check_compatibility(seg: AlignableSegment) -> bool:
    """Validate a segment's shape label against the compatibility table.

    Returns ``True`` if the warp will be approximate (plateau / trend),
    ``False`` if fully compatible (cycle / spike / transient).  Raises
    :class:`IncompatibleOp` for ``noise``.
    """
    label = seg.label
    if label in INCOMPATIBLE_SHAPES:
        raise IncompatibleOp(
            f"align_warp not applicable to {label!r} segments "
            f"(id={seg.segment_id!r}). Refusing to warp white noise — "
            "the result has no meaningful temporal interpretation."
        )
    if label in APPROX_SHAPES:
        return True
    if label in COMPATIBLE_SHAPES:
        return False
    # Unknown labels are treated as approx so the operation still runs but
    # the audit captures the uncertainty.
    return True
