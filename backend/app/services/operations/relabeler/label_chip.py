"""Post-op label chip emission (OP-041).

Every Tier-1/2/3 operation (and Tier-0 structural ops other than edit_boundary)
calls emit_label_chip() once after the operation completes.  The chip is
published on the default_event_bus (topic: 'label_chip') so that UI-013 can
render the predicted-label chip, and is appended to default_audit_log so that
UI-015 can flush it to the SQLite AuditEvent table.

LabelChip fields (10 total):
    chip_id     — UUID4, unique per emission
    segment_id  — segment that was edited
    op_id       — caller-supplied operation instance ID (UUID4 typically)
    op_name     — canonical op name, e.g. 'scale', 'flatten'
    tier        — 0 / 1 / 2 / 3
    old_shape   — shape label before the op
    new_shape   — shape label after (from RelabelResult)
    confidence  — classifier confidence in [0, 1]
    rule_class  — 'PRESERVED' | 'DETERMINISTIC' | 'RECLASSIFY_VIA_SEGMENTER'
    timestamp   — UTC ISO-8601 string at emission time

Reference: HypotheX-TS OP-041 ticket (event plumbing; no algorithm paper).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.services.events import AuditLog, EventBus

from app.services.events import default_audit_log as _default_audit_log
from app.services.events import default_event_bus as _default_bus
from app.services.operations.relabeler.relabeler import RelabelResult


@dataclass(frozen=True)
class LabelChip:
    """Immutable record of a single post-op relabeling event.

    All 10 fields are populated by emit_label_chip(); callers should not
    construct LabelChip directly in production code.
    """

    segment_id: str
    op_id: str
    op_name: str
    tier: int
    old_shape: str
    new_shape: str
    confidence: float
    rule_class: Literal["PRESERVED", "DETERMINISTIC", "RECLASSIFY_VIA_SEGMENTER"]
    chip_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def emit_label_chip(
    *,
    segment_id: str,
    op_id: str,
    op_name: str,
    tier: int,
    old_shape: str,
    relabel_result: RelabelResult,
    event_bus: EventBus | None = None,
    audit_log: AuditLog | None = None,
) -> LabelChip | None:
    """Create, publish, and log a LabelChip for a completed operation.

    Pure boundary edits (tier=0, op_name='edit_boundary') do NOT emit a chip
    because they leave the shape unchanged.  All other ops — including split and
    merge which are Tier-0 but may change shape — DO emit a chip.

    The chip is published on the event bus (topic: 'label_chip') and appended
    to the audit log.  Both are injected; defaults are the module-level
    default_event_bus and default_audit_log.

    Reference: HypotheX-TS OP-041 ticket.

    Args:
        segment_id:     ID of the edited segment.
        op_id:          Caller-supplied unique ID for this operation instance.
        op_name:        Canonical operation name (e.g. 'scale', 'flatten').
        tier:           Operation tier (0–3).
        old_shape:      Shape label before the op.
        relabel_result: Output of relabel(); provides new_shape, confidence,
                        rule_class.
        event_bus:      Bus to publish on; uses default_event_bus when None.
        audit_log:      Audit log to append to; uses default_audit_log when None.

    Returns:
        The emitted LabelChip, or None if the op is a pure boundary edit.
    """
    if tier == 0 and op_name == "edit_boundary":
        return None

    chip = LabelChip(
        segment_id=segment_id,
        op_id=op_id,
        op_name=op_name,
        tier=tier,
        old_shape=old_shape,
        new_shape=relabel_result.new_shape,
        confidence=relabel_result.confidence,
        rule_class=relabel_result.rule_class,
    )

    bus = event_bus if event_bus is not None else _default_bus
    bus.publish("label_chip", chip)

    log = audit_log if audit_log is not None else _default_audit_log
    log.append(chip)

    return chip
