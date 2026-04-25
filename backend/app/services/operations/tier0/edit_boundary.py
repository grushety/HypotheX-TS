"""edit_boundary — Tier-0 structural operation (OP-001).

Moves segment k's boundaries by (delta_b, delta_e) while maintaining
contiguity with neighbours and enforcing per-class minimum-duration
constraints.  Transaction semantics: if validation fails, no segment
is mutated.

Callers are responsible for emitting an audit entry after calling this
function (the pure function itself has no I/O).

Design follows HypotheX-TS Formal Definitions §5.0.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from app.core.domain_config import DomainConfig, load_domain_config


class InvalidEdit(ValueError):
    """Raised when edit_boundary would violate a structural constraint."""


@dataclass(frozen=True)
class Segment:
    """Segment used by tier-0 operations."""

    segment_id: str
    start_index: int
    end_index: int
    label: str
    provenance: str = "user"
    confidence: float | None = None
    scope: str | None = None
    decomposition_dirty: bool = False

    @property
    def length(self) -> int:
        return self.end_index - self.start_index + 1


def edit_boundary(
    segments: list[Segment],
    k: int,
    delta_b: int,
    delta_e: int,
    *,
    domain_config: DomainConfig | None = None,
) -> list[Segment]:
    """Move segment k's boundaries by (delta_b, delta_e).

    Propagates changes to adjacent segments to maintain:
      segments[k-1].end_index + 1 == segments[k].start_index
      segments[k].end_index + 1   == segments[k+1].start_index

    Marks up to three affected segments as decomposition_dirty=True so
    callers know which blobs require refit.

    Args:
        segments:      Contiguous segment list in time order.
        k:             Index of the target segment.
        delta_b:       Shift applied to segments[k].start_index.
        delta_e:       Shift applied to segments[k].end_index.
        domain_config: Domain config for L_min lookup; loaded from cache if None.

    Returns:
        New list of segments with updated boundaries and dirty flags set
        on all affected segments.

    Raises:
        InvalidEdit: If any affected segment's resulting length falls below
                     its per-class L_min.  No segment is mutated on failure.
    """
    config = domain_config or load_domain_config()
    seg = segments[k]
    new_b = seg.start_index + delta_b
    new_e = seg.end_index + delta_e

    if new_b < 0:
        raise InvalidEdit(
            f"Segment '{seg.segment_id}' start_index would become {new_b} (< 0)."
        )
    if new_b > new_e:
        raise InvalidEdit(
            f"Segment '{seg.segment_id}' boundaries inverted: start {new_b} > end {new_e}."
        )

    # Build candidate list without touching the originals (transaction semantics).
    candidate: list[Segment] = list(segments)
    candidate[k] = replace(seg, start_index=new_b, end_index=new_e)

    if k > 0:
        candidate[k - 1] = replace(candidate[k - 1], end_index=new_b - 1)
    if k < len(segments) - 1:
        candidate[k + 1] = replace(candidate[k + 1], start_index=new_e + 1)

    # Collect affected indices then validate — raise before touching anything.
    affected: set[int] = {k}
    if k > 0:
        affected.add(k - 1)
    if k < len(segments) - 1:
        affected.add(k + 1)

    for i in affected:
        s = candidate[i]
        l_min = _l_min_for(s.label, config)
        if s.length < l_min:
            raise InvalidEdit(
                f"Segment '{s.segment_id}' length {s.length} < L_min {l_min}"
                f" for label '{s.label}'."
            )

    for i in affected:
        candidate[i] = replace(candidate[i], decomposition_dirty=True)

    return candidate


def _l_min_for(label: str, config: DomainConfig) -> int:
    """Return the per-class minimum segment length from the domain config."""
    limits = config.duration_limits
    if label == "event":
        return limits.get("eventMinLength", limits["minimumSegmentLength"])
    if label == "transition":
        return limits.get("transitionMinLength", limits["minimumSegmentLength"])
    if label == "periodic":
        return limits.get("periodicMinLength", limits["minimumSegmentLength"])
    return limits["minimumSegmentLength"]
