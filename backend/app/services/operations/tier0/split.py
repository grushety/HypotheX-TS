"""split — Tier-0 structural operation (OP-002).

Splits segment k at t_star into two contiguous halves.  Both halves
inherit the parent's label, scope, and confidence; provenance is set to
'user'.  Decomposition blobs are invalidated (dirty) on both halves.

Transaction semantics: no mutation if validation fails.
Design follows HypotheX-TS Formal Definitions §5.0.
"""
from __future__ import annotations

from app.core.domain_config import DomainConfig, load_domain_config
from app.services.operations.tier0.edit_boundary import (
    InvalidEdit,
    Segment,
    _l_min_for,
)


def split(
    segments: list[Segment],
    k: int,
    t_star: int,
    *,
    domain_config: DomainConfig | None = None,
) -> list[Segment]:
    """Split segment k at t_star into two contiguous halves.

    Args:
        segments:      Contiguous segment list in time order.
        k:             Index of the target segment.
        t_star:        Split point; left half ends at t_star, right starts at t_star+1.
        domain_config: Domain config for L_min lookup; loaded from cache if None.

    Returns:
        New list where segments[k] is replaced by [left, right].

    Raises:
        InvalidEdit: If t_star is not strictly inside the segment, or if
                     either half would be shorter than L_min.  No segment
                     is mutated on failure.
    """
    config = domain_config or load_domain_config()
    s = segments[k]

    if not (s.start_index < t_star < s.end_index):
        raise InvalidEdit(
            f"Split point {t_star} is not strictly inside segment "
            f"'{s.segment_id}' [{s.start_index}, {s.end_index}]."
        )

    left_id = f"{s.segment_id}-a"
    right_id = f"{s.segment_id}-b"
    left_length = t_star - s.start_index + 1
    right_length = s.end_index - t_star

    l_min = _l_min_for(s.label, config)
    if left_length < l_min:
        raise InvalidEdit(
            f"Left half '{left_id}' length {left_length} < L_min {l_min}"
            f" for label '{s.label}'."
        )
    if right_length < l_min:
        raise InvalidEdit(
            f"Right half '{right_id}' length {right_length} < L_min {l_min}"
            f" for label '{s.label}'."
        )

    left = Segment(
        segment_id=left_id,
        start_index=s.start_index,
        end_index=t_star,
        label=s.label,
        provenance="user",
        confidence=s.confidence,
        scope=s.scope,
        decomposition_dirty=True,
    )
    right = Segment(
        segment_id=right_id,
        start_index=t_star + 1,
        end_index=s.end_index,
        label=s.label,
        provenance="user",
        confidence=s.confidence,
        scope=s.scope,
        decomposition_dirty=True,
    )

    candidate = list(segments)
    candidate[k : k + 1] = [left, right]
    return candidate
