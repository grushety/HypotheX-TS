"""Relabeler interface, rule-table lookup, and default implementation (OP-040).

Every Tier-0/1/2/3 operation that changes segment shape calls relabel() to
determine the post-edit shape label via the canonical RULE_TABLE.

Design follows HypotheX-TS Operation Vocabulary Research §6.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Lazy singleton — built once on first RECLASSIFY call so callers that never
# reach that path pay no construction cost; callers may still inject their own.
_default_classifier: object | None = None


def _get_default_classifier() -> object:
    global _default_classifier
    if _default_classifier is None:
        from app.services.suggestion.rule_classifier import RuleBasedShapeClassifier  # noqa: PLC0415
        _default_classifier = RuleBasedShapeClassifier()
    return _default_classifier


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


# ---------------------------------------------------------------------------
# Primary entry point: relabel()
# ---------------------------------------------------------------------------


def relabel(
    old_shape: str,
    operation: str,
    op_params: dict[str, Any] | None = None,
    edited_series: Any = None,
    classifier: Any = None,
) -> RelabelResult:
    """Determine the post-edit shape label via the canonical RULE_TABLE.

    Lookup order:
      1. (old_shape, operation, param_predicate)
      2. (old_shape, operation, None)          — predicate fallback
      3. ('*',       operation, None)           — wildcard shape

    For RECLASSIFY_VIA_SEGMENTER: invokes the SEG-008 RuleBasedShapeClassifier
    on edited_series (or returns a confidence-0 stub if edited_series is None).

    Reference: HypotheX-TS Operation Vocabulary Research §6.

    Args:
        old_shape:     Shape label of the segment before the edit.
        operation:     Op name exactly as registered in RULE_TABLE (e.g. 'flatten').
        op_params:     Dict of op parameters used for predicate dispatch (e.g.
                       {'alpha': 0.0} triggers the 'alpha=0' predicate).
        edited_series: Post-edit time-series values; required for RECLASSIFY path.
        classifier:    SEG-008 classifier instance; a fresh one is created if None.

    Returns:
        RelabelResult with new_shape, confidence, needs_resegment, rule_class.

    Raises:
        UnknownRelabelRule: No rule found for (old_shape, operation).
    """
    from app.services.operations.relabeler.rule_table import (  # noqa: PLC0415
        RULE_TABLE,
        UnknownRelabelRule,
        _param_predicate,
    )

    predicate = _param_predicate(op_params)
    rule = (
        RULE_TABLE.get((old_shape, operation, predicate))
        or RULE_TABLE.get(("*", operation, predicate))
        or RULE_TABLE.get((old_shape, operation, None))
        or RULE_TABLE.get(("*", operation, None))
    )
    if rule is None:
        raise UnknownRelabelRule(
            f"No relabel rule for ({old_shape!r}, {operation!r}). "
            "Add an entry to RULE_TABLE in rule_table.py."
        )
    rule_class, target = rule

    if rule_class == "PRESERVED":
        return RelabelResult(
            new_shape=old_shape,
            confidence=1.0,
            needs_resegment=False,
            rule_class="PRESERVED",
        )

    if rule_class == "DETERMINISTIC":
        return RelabelResult(
            new_shape=target,
            confidence=1.0,
            needs_resegment=False,
            rule_class="DETERMINISTIC",
        )

    if rule_class == "RECLASSIFY_VIA_SEGMENTER":
        if edited_series is None:
            logger.warning(
                "relabel: RECLASSIFY_VIA_SEGMENTER called without edited_series "
                "for (%r, %r); returning confidence-0 stub.",
                old_shape, operation,
            )
            return RelabelResult(
                new_shape=old_shape,
                confidence=0.0,
                needs_resegment=True,
                rule_class="RECLASSIFY_VIA_SEGMENTER",
            )
        clf = classifier if classifier is not None else _get_default_classifier()
        shape_label = clf.classify_shape(edited_series)
        return RelabelResult(
            new_shape=shape_label.label,
            confidence=float(shape_label.confidence),
            needs_resegment=True,
            rule_class="RECLASSIFY_VIA_SEGMENTER",
        )

    raise UnknownRelabelRule(  # unreachable unless RULE_TABLE is corrupted
        f"Unknown rule_class {rule_class!r} for ({old_shape!r}, {operation!r})."
    )


# ---------------------------------------------------------------------------
# Backward-compatible default_relabeler (kept for merge/split callers)
# ---------------------------------------------------------------------------


def default_relabeler(
    *,
    old_shape: str,
    operation: str,
    op_params: dict[str, Any] | None = None,
    edited_series: Any,
    classifier: Any = None,
) -> RelabelResult:
    """Backward-compatible wrapper: delegates to relabel().

    Previously used directly by merge/split before the full rule table existed.
    New code should call relabel() instead.

    Args:
        old_shape:     Shape label before the edit.
        operation:     Operation name.
        op_params:     Operation parameters for predicate dispatch.
        edited_series: Post-edit time-series values.
        classifier:    SEG-008 classifier instance.

    Returns:
        RelabelResult from the rule table.
    """
    return relabel(
        old_shape=old_shape,
        operation=operation,
        op_params=op_params,
        edited_series=edited_series,
        classifier=classifier,
    )
