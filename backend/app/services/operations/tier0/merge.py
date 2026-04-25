"""merge — Tier-0 structural operation (OP-003).

Combines segments[k] and segments[k+1] into one segment.  The merged
segment's shape label is determined by the OP-040 relabeler
(RECLASSIFY_VIA_SEGMENTER path for merge), never by simple majority.

Transaction semantics: no mutation if validation fails.
Design follows HypotheX-TS Formal Definitions §5.0.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from app.core.domain_config import DomainConfig, load_domain_config
from app.services.operations.relabeler.relabeler import (
    RelabelResult,
    RelabelerFn,
    default_relabeler,
)
from app.services.operations.tier0.edit_boundary import InvalidEdit, Segment


def merge(
    segments: list[Segment],
    k: int,
    X: Any,
    *,
    relabeler: RelabelerFn | None = None,
    domain_config: DomainConfig | None = None,
) -> list[Segment]:
    """Merge segments[k] and segments[k+1] into one segment.

    The merged segment spans [left.start_index, right.end_index].  Its shape
    label is determined by the relabeler (OP-040), not by simple majority.
    Scope from the left (earlier) segment wins.  Provenance is set to 'user'.

    A merged segment that would violate L_min is allowed and logged as a
    warning — this can only occur if the source segments already violated it.

    Args:
        segments:      Contiguous segment list in time order.
        k:             Index of the left segment to merge.
        X:             Full time-series array; used to extract merged series
                       for the relabeler.
        relabeler:     Callable matching RelabelerFn; defaults to
                       ``default_relabeler`` (RECLASSIFY_VIA_SEGMENTER path).
        domain_config: Domain config; loaded from cache if None.

    Returns:
        New list where segments[k] and segments[k+1] are replaced by the
        merged segment.

    Raises:
        InvalidEdit: If k is out of range or no right neighbour exists at k+1.
    """
    _relabeler = relabeler if relabeler is not None else default_relabeler
    config = domain_config or load_domain_config()

    if k < 0 or k >= len(segments):
        raise InvalidEdit(
            f"Segment index {k} is out of range for a list of {len(segments)} segment(s)."
        )
    if k >= len(segments) - 1:
        raise InvalidEdit(
            f"Cannot merge segment at index {k}: no right neighbour exists."
        )

    left = segments[k]
    right = segments[k + 1]

    series = np.asarray(X)
    merged_series = series[left.start_index : right.end_index + 1]

    relabel_result: RelabelResult = _relabeler(
        old_shape=left.label,
        operation="merge",
        op_params={"neighbour_label": right.label},
        edited_series=merged_series,
    )

    merged_id = f"{left.segment_id}+{right.segment_id}"
    merged = Segment(
        segment_id=merged_id,
        start_index=left.start_index,
        end_index=right.end_index,
        label=relabel_result.new_shape,
        provenance="user",
        confidence=relabel_result.confidence,
        scope=left.scope,
        decomposition_dirty=True,
    )

    candidate = list(segments)
    candidate[k : k + 2] = [merged]
    return candidate
