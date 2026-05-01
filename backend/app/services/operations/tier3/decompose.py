"""decompose — Tier-3 user-invocable refit (OP-030).

Exposes the SEG-019 :func:`dispatch_fitter` registry as a single user-facing
Tier-3 operation: "re-fit the underlying model of this region".  Users hit
the *decompose* button in the UI-005 Tier-3 toolbar after correcting a
segment boundary or selecting a different ``domain_hint`` and the
operation runs the appropriate fitter(s) fresh, replacing each segment's
:class:`DecompositionBlob`.

Every refit attaches ``fit_metadata['refit_reason'] = 'user_tier3_decompose'``
so that downstream audits can distinguish a user-triggered refit from an
automatic one (e.g. dirty-on-edit_boundary refits).

Audit emission
--------------
Pure-functional core (mutates only the segment list it returns); a
:class:`DecomposeAudit` record is published on the OP-041 event bus and
appended to the default audit log on every successful invocation.  No
``LabelChip`` is emitted because :func:`decompose` does not change a
segment's *shape label* — only its decomposition.

References
----------
HypotheX-TS — *Implementation Plan* §6.3 (Tier-3 user-invocable ops);
*Formal Definitions* §5.3 (decompose semantics).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import dispatch_fitter
from app.services.events import (
    AuditLog,
    EventBus,
    default_audit_log,
    default_event_bus,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecomposedSegment:
    """Segment carrying its decomposition blob.

    Tier-3 operations consume and return :class:`DecomposedSegment` lists
    rather than the tier-0 :class:`Segment` because the decomposition blob
    is the unit of edit at this tier.

    Attributes:
        segment_id:    Stable identifier across edits.
        start_index:   Inclusive left bound into the underlying series ``X``.
        end_index:     Inclusive right bound into ``X``.
        label:         Shape primitive label (e.g. ``'plateau'``).
        scope:         Optional dict carrying per-segment metadata.
                       ``scope['domain_hint']`` is consulted by
                       :func:`decompose` when the function-level
                       ``domain_hint`` is ``None``.
        decomposition: Optional :class:`DecompositionBlob`.  ``None`` before
                       the first :func:`decompose` call.
    """

    segment_id: str
    start_index: int
    end_index: int
    label: str
    scope: dict[str, Any] | None = None
    decomposition: DecompositionBlob | None = None

    @property
    def length(self) -> int:
        return self.end_index - self.start_index + 1


@dataclass(frozen=True)
class DecomposeAudit:
    """Tier-3 audit entry emitted by :func:`decompose`.

    Recorded on :data:`app.services.events.default_audit_log` and
    published as a ``'decompose'`` event on
    :data:`app.services.events.default_event_bus`.
    """

    op_name: str
    tier: int
    segment_ids: tuple[str, ...]
    methods_used: tuple[str, ...]
    domain_hint: str | None
    refit_reason: str
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


REFIT_REASON: str = "user_tier3_decompose"


def decompose(
    X: np.ndarray,
    segments: list[DecomposedSegment],
    domain_hint: str | None = None,
    *,
    event_bus: EventBus | None = None,
    audit_log: AuditLog | None = None,
) -> list[DecomposedSegment]:
    """Refit decomposition for one or more selected segments.

    For each segment, resolves the effective ``domain_hint`` (function arg
    overrides per-segment ``scope['domain_hint']``), looks up the fitter
    via :func:`dispatch_fitter`, and runs the fitter on the segment's slice
    of ``X``.  Returns a *new* list of segments; the input list is not
    mutated (segments are frozen dataclasses).

    Args:
        X:           Underlying time series, shape ``(n,)``.
        segments:    Iterable of :class:`DecomposedSegment` to refit.
        domain_hint: Optional global override applied to every segment.
                     ``None`` falls back to per-segment scope.
        event_bus:   Override for the event bus (default: package default).
        audit_log:   Override for the audit log (default: package default).

    Returns:
        New list of :class:`DecomposedSegment` with refit decompositions.

    Raises:
        ValueError: A segment lies outside ``X`` bounds, has
                    ``end_index < start_index``, or refers to an unknown
                    shape label.
    """
    arr = np.asarray(X, dtype=np.float64).ravel()
    n = len(arr)

    bus = event_bus if event_bus is not None else default_event_bus
    log = audit_log if audit_log is not None else default_audit_log

    new_segments: list[DecomposedSegment] = []
    methods: list[str] = []

    for seg in segments:
        _validate_bounds(seg, n)
        effective_hint = _effective_domain_hint(seg, domain_hint)

        fitter = dispatch_fitter(seg.label, effective_hint)
        sl = arr[seg.start_index : seg.end_index + 1]
        t = np.arange(seg.start_index, seg.end_index + 1, dtype=np.float64)

        blob = fitter(sl, t=t)
        blob = _annotate_refit(blob, effective_hint)

        new_segments.append(replace(seg, decomposition=blob))
        methods.append(blob.method)

    audit = DecomposeAudit(
        op_name="decompose",
        tier=3,
        segment_ids=tuple(seg.segment_id for seg in segments),
        methods_used=tuple(methods),
        domain_hint=domain_hint,
        refit_reason=REFIT_REASON,
    )
    log.append(audit)
    bus.publish("decompose", audit)

    return new_segments


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_bounds(seg: DecomposedSegment, n: int) -> None:
    """Raise :class:`ValueError` if the segment's indices are outside ``X``."""
    if seg.start_index < 0:
        raise ValueError(
            f"decompose: segment {seg.segment_id!r} has start_index "
            f"{seg.start_index} < 0."
        )
    if seg.end_index >= n:
        raise ValueError(
            f"decompose: segment {seg.segment_id!r} has end_index "
            f"{seg.end_index} ≥ series length {n}."
        )
    if seg.end_index < seg.start_index:
        raise ValueError(
            f"decompose: segment {seg.segment_id!r} has end_index "
            f"{seg.end_index} < start_index {seg.start_index}."
        )


def _effective_domain_hint(
    seg: DecomposedSegment,
    arg_hint: str | None,
) -> str | None:
    """Resolve the effective domain hint for a segment.

    Priority order: function-level ``arg_hint`` > per-segment
    ``scope['domain_hint']`` > ``None`` (generic fitter).
    """
    if arg_hint is not None:
        return arg_hint
    if seg.scope is None:
        return None
    return seg.scope.get("domain_hint")


def _annotate_refit(
    blob: DecompositionBlob,
    domain_hint: str | None,
) -> DecompositionBlob:
    """Stamp ``refit_reason`` and ``domain_hint`` into the blob's
    ``fit_metadata``.

    Returns a deep-copied blob to avoid mutating any cache shared with the
    fitter implementation.
    """
    blob = copy.deepcopy(blob)
    blob.fit_metadata["refit_reason"] = REFIT_REASON
    if domain_hint is not None:
        blob.fit_metadata["domain_hint"] = str(domain_hint)
    return blob
