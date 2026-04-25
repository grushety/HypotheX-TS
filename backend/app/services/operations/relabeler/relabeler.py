"""Relabeler interface and default implementation (OP-040 foundation).

Every Tier-0/1/2/3 operation that changes segment shape calls the relabeler to
determine the post-edit shape label.  The full rule table is implemented in
OP-040; this module provides the ``RelabelResult`` dataclass and the default
``default_relabeler`` used by OP-003 merge via the RECLASSIFY_VIA_SEGMENTER
path.

Design follows HypotheX-TS Operation Vocabulary Research §6.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class RelabelResult:
    """Result returned by every relabeler call.

    Attributes:
        new_shape:       Post-edit shape label.
        confidence:      Classifier confidence in [0, 1].
        needs_resegment: True when the RECLASSIFY_VIA_SEGMENTER path was taken.
        rule_class:      'PRESERVED' | 'DETERMINISTIC' | 'RECLASSIFY_VIA_SEGMENTER'
    """

    new_shape: str
    confidence: float
    needs_resegment: bool
    rule_class: str


# Type alias for the relabeler callable passed to tier-0 ops.
RelabelerFn = Callable[..., RelabelResult]


def default_relabeler(
    *,
    old_shape: str,
    operation: str,
    op_params: dict[str, Any] | None = None,
    edited_series: Any,
    classifier: Any = None,
) -> RelabelResult:
    """Default relabeler: RECLASSIFY_VIA_SEGMENTER using the SEG-008 classifier.

    Used by merge (and other ops whose rule-table entry is RECLASSIFY_VIA_SEGMENTER)
    until the full OP-040 rule table is wired in.

    Args:
        old_shape:     Shape label of the segment before the edit.
        operation:     Operation name (e.g. 'merge', 'split').
        op_params:     Operation-specific parameters (e.g. {'neighbour_label': ...}).
        edited_series: Time-series values for the edited segment.
        classifier:    SEG-008 classifier instance; a fresh one is created if None.

    Returns:
        RelabelResult with rule_class='RECLASSIFY_VIA_SEGMENTER'.
    """
    from app.services.suggestion.rule_classifier import RuleBasedShapeClassifier

    clf = classifier if classifier is not None else RuleBasedShapeClassifier()
    shape_label = clf.classify_shape(edited_series)
    return RelabelResult(
        new_shape=shape_label.label,
        confidence=float(shape_label.confidence),
        needs_resegment=True,
        rule_class="RECLASSIFY_VIA_SEGMENTER",
    )
