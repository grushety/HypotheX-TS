"""Tests for OP-041: post-op label chip emission and event bus.

Covers:
 - LabelChip has all 10 required fields
 - chip emitted for Tier-1, Tier-2, and Tier-0 split/merge ops
 - chip NOT emitted for edit_boundary (returns None, bus not called)
 - chip IS emitted for other Tier-0 ops (split, merge)
 - subscriber receives chip in FIFO order
 - chip appended to audit log in FIFO order
 - custom event_bus / audit_log injection
 - default_event_bus / default_audit_log used when None supplied
 - unsubscribe stops delivery (and is idempotent)
 - chip_id is UUID-format string and unique per chip
 - confidence and rule_class forwarded from RelabelResult
"""

import uuid

import pytest

from app.services.events import AuditLog, EventBus, default_audit_log, default_event_bus
from app.services.operations.relabeler.label_chip import LabelChip, emit_label_chip
from app.services.operations.relabeler.relabeler import RelabelResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _relabel(rule_class="PRESERVED", new_shape="trend", confidence=1.0):
    return RelabelResult(
        new_shape=new_shape,
        confidence=confidence,
        needs_resegment=(rule_class == "RECLASSIFY_VIA_SEGMENTER"),
        rule_class=rule_class,
    )


def _emit(
    op_name="scale",
    tier=1,
    old_shape="trend",
    relabel_result=None,
    event_bus=None,
    audit_log=None,
    segment_id="seg-1",
    op_id=None,
):
    return emit_label_chip(
        segment_id=segment_id,
        op_id=op_id or str(uuid.uuid4()),
        op_name=op_name,
        tier=tier,
        old_shape=old_shape,
        relabel_result=relabel_result or _relabel(),
        event_bus=event_bus,
        audit_log=audit_log,
    )


def _bus_and_log():
    """Return a fresh (EventBus, AuditLog, received_list) triple."""
    bus = EventBus()
    log = AuditLog()
    received = []
    bus.subscribe("label_chip", received.append)
    return bus, log, received


# ---------------------------------------------------------------------------
# LabelChip dataclass contract
# ---------------------------------------------------------------------------


class TestLabelChipContract:
    def test_all_ten_fields_present(self):
        chip = LabelChip(
            segment_id="seg-1",
            op_id="op-1",
            op_name="scale",
            tier=1,
            old_shape="trend",
            new_shape="trend",
            confidence=1.0,
            rule_class="PRESERVED",
        )
        assert hasattr(chip, "chip_id")
        assert hasattr(chip, "segment_id")
        assert hasattr(chip, "op_id")
        assert hasattr(chip, "op_name")
        assert hasattr(chip, "tier")
        assert hasattr(chip, "old_shape")
        assert hasattr(chip, "new_shape")
        assert hasattr(chip, "confidence")
        assert hasattr(chip, "rule_class")
        assert hasattr(chip, "timestamp")

    def test_is_frozen(self):
        chip = LabelChip(
            segment_id="seg-1",
            op_id="op-1",
            op_name="scale",
            tier=1,
            old_shape="trend",
            new_shape="trend",
            confidence=1.0,
            rule_class="PRESERVED",
        )
        with pytest.raises((AttributeError, TypeError)):
            chip.new_shape = "noise"  # type: ignore[misc]

    def test_chip_id_is_uuid_format(self):
        chip = LabelChip(
            segment_id="s",
            op_id="o",
            op_name="flatten",
            tier=2,
            old_shape="trend",
            new_shape="plateau",
            confidence=1.0,
            rule_class="DETERMINISTIC",
        )
        uuid.UUID(chip.chip_id)  # raises ValueError if not a valid UUID

    def test_chip_id_unique_per_instance(self):
        def make():
            return LabelChip(
                segment_id="s",
                op_id="o",
                op_name="flatten",
                tier=2,
                old_shape="trend",
                new_shape="plateau",
                confidence=1.0,
                rule_class="DETERMINISTIC",
            )
        assert make().chip_id != make().chip_id

    def test_timestamp_is_nonempty_string(self):
        chip = LabelChip(
            segment_id="s",
            op_id="o",
            op_name="scale",
            tier=1,
            old_shape="cycle",
            new_shape="cycle",
            confidence=1.0,
            rule_class="PRESERVED",
        )
        assert isinstance(chip.timestamp, str)
        assert chip.timestamp  # non-empty


# ---------------------------------------------------------------------------
# emit_label_chip — suppression for edit_boundary
# ---------------------------------------------------------------------------


class TestEditBoundarySuppression:
    def test_edit_boundary_tier0_returns_none(self):
        bus, log, received = _bus_and_log()
        result = _emit(op_name="edit_boundary", tier=0, event_bus=bus, audit_log=log)
        assert result is None
        assert received == []
        assert log.records == []

    def test_split_tier0_emits(self):
        bus, log, received = _bus_and_log()
        chip = _emit(op_name="split", tier=0, event_bus=bus, audit_log=log,
                     relabel_result=_relabel("RECLASSIFY_VIA_SEGMENTER", "trend", 0.8))
        assert chip is not None
        assert len(received) == 1
        assert len(log) == 1

    def test_merge_tier0_emits(self):
        bus, log, received = _bus_and_log()
        chip = _emit(op_name="merge", tier=0, event_bus=bus, audit_log=log,
                     relabel_result=_relabel("RECLASSIFY_VIA_SEGMENTER", "plateau", 0.6))
        assert chip is not None
        assert len(received) == 1

    def test_other_tier0_op_emits(self):
        bus, log, received = _bus_and_log()
        chip = _emit(op_name="suppress", tier=0, event_bus=bus, audit_log=log)
        assert chip is not None


# ---------------------------------------------------------------------------
# emit_label_chip — chip fields are correctly populated
# ---------------------------------------------------------------------------


class TestChipFieldPopulation:
    def test_fields_match_inputs(self):
        bus, log, received = _bus_and_log()
        seg_id = "seg-abc"
        op_id = str(uuid.uuid4())
        relabel = _relabel("DETERMINISTIC", "plateau", 1.0)

        chip = emit_label_chip(
            segment_id=seg_id,
            op_id=op_id,
            op_name="flatten",
            tier=2,
            old_shape="trend",
            relabel_result=relabel,
            event_bus=bus,
            audit_log=log,
        )
        assert chip is not None
        assert chip.segment_id == seg_id
        assert chip.op_id == op_id
        assert chip.op_name == "flatten"
        assert chip.tier == 2
        assert chip.old_shape == "trend"
        assert chip.new_shape == "plateau"
        assert chip.confidence == pytest.approx(1.0)
        assert chip.rule_class == "DETERMINISTIC"
        assert chip.chip_id
        assert chip.timestamp

    def test_confidence_forwarded(self):
        bus, log, _ = _bus_and_log()
        chip = _emit(
            relabel_result=_relabel("RECLASSIFY_VIA_SEGMENTER", "noise", 0.73),
            event_bus=bus, audit_log=log,
        )
        assert chip.confidence == pytest.approx(0.73)

    def test_rule_class_preserved(self):
        bus, log, _ = _bus_and_log()
        chip = _emit(relabel_result=_relabel("PRESERVED", "cycle"), event_bus=bus, audit_log=log)
        assert chip.rule_class == "PRESERVED"

    def test_rule_class_deterministic(self):
        bus, log, _ = _bus_and_log()
        chip = _emit(relabel_result=_relabel("DETERMINISTIC", "plateau"), event_bus=bus, audit_log=log)
        assert chip.rule_class == "DETERMINISTIC"

    def test_rule_class_reclassify(self):
        bus, log, _ = _bus_and_log()
        chip = _emit(
            relabel_result=_relabel("RECLASSIFY_VIA_SEGMENTER", "trend", 0.9),
            event_bus=bus, audit_log=log,
        )
        assert chip.rule_class == "RECLASSIFY_VIA_SEGMENTER"

    def test_tier1_op(self):
        bus, log, _ = _bus_and_log()
        chip = _emit(op_name="scale", tier=1, old_shape="step", event_bus=bus, audit_log=log)
        assert chip is not None
        assert chip.tier == 1
        assert chip.op_name == "scale"

    def test_tier2_op(self):
        bus, log, _ = _bus_and_log()
        chip = _emit(op_name="raise_lower", tier=2, old_shape="plateau", event_bus=bus, audit_log=log)
        assert chip is not None
        assert chip.tier == 2


# ---------------------------------------------------------------------------
# EventBus — subscriber delivery and FIFO order
# ---------------------------------------------------------------------------


class TestEventBus:
    def test_subscriber_receives_chip(self):
        bus, log, received = _bus_and_log()
        chip = _emit(event_bus=bus, audit_log=log)
        assert received == [chip]

    def test_fifo_order(self):
        bus, log, received = _bus_and_log()
        chips = [_emit(op_name=f"op{i}", event_bus=bus, audit_log=log) for i in range(5)]
        assert received == chips

    def test_multiple_subscribers_all_receive(self):
        bus = EventBus()
        log_a, log_b = [], []
        bus.subscribe("label_chip", log_a.append)
        bus.subscribe("label_chip", log_b.append)
        chip = _emit(event_bus=bus, audit_log=AuditLog())
        assert chip in log_a
        assert chip in log_b

    def test_multiple_subscribers_fifo_within_subscriber(self):
        bus, log, received = _bus_and_log()
        c1 = _emit(op_name="scale", event_bus=bus, audit_log=log)
        c2 = _emit(op_name="offset", event_bus=bus, audit_log=log)
        c3 = _emit(op_name="flatten", event_bus=bus, audit_log=log)
        assert received == [c1, c2, c3]

    def test_unsubscribe_stops_delivery(self):
        bus = EventBus()
        received = []
        handler = received.append
        bus.subscribe("label_chip", handler)
        _emit(event_bus=bus, audit_log=AuditLog())
        bus.unsubscribe("label_chip", handler)
        _emit(event_bus=bus, audit_log=AuditLog())
        assert len(received) == 1

    def test_unsubscribe_idempotent(self):
        bus = EventBus()
        received = []
        bus.subscribe("label_chip", received.append)
        bus.unsubscribe("label_chip", received.append)
        bus.unsubscribe("label_chip", received.append)  # second call must not raise

    def test_unsubscribe_never_subscribed_is_noop(self):
        bus = EventBus()
        bus.unsubscribe("label_chip", lambda x: None)  # must not raise

    def test_clear_removes_all_subscribers(self):
        bus = EventBus()
        received = []
        bus.subscribe("label_chip", received.append)
        bus.clear("label_chip")
        _emit(event_bus=bus, audit_log=AuditLog())
        assert received == []

    def test_clear_all_removes_all_event_types(self):
        bus = EventBus()
        log_a, log_b = [], []
        bus.subscribe("label_chip", log_a.append)
        bus.subscribe("other_event", log_b.append)
        bus.clear()
        bus.publish("label_chip", "x")
        bus.publish("other_event", "y")
        assert log_a == []
        assert log_b == []

    def test_no_subscribers_is_no_op(self):
        bus = EventBus()
        chip = _emit(event_bus=bus, audit_log=AuditLog())
        assert chip is not None

    def test_publish_passes_payload_unmodified(self):
        bus, log, received = _bus_and_log()
        chip = _emit(event_bus=bus, audit_log=log)
        assert received[0] is chip


# ---------------------------------------------------------------------------
# AuditLog — ordered persistence
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_chip_appended_to_audit_log(self):
        bus, log, _ = _bus_and_log()
        chip = _emit(event_bus=bus, audit_log=log)
        assert log.records == [chip]

    def test_edit_boundary_not_in_audit_log(self):
        bus, log, _ = _bus_and_log()
        _emit(op_name="edit_boundary", tier=0, event_bus=bus, audit_log=log)
        assert log.records == []

    def test_audit_log_fifo_order(self):
        log = AuditLog()
        bus = EventBus()
        chips = [_emit(op_name=f"op{i}", event_bus=bus, audit_log=log) for i in range(4)]
        assert log.records == chips

    def test_audit_log_records_returns_copy(self):
        log = AuditLog()
        bus = EventBus()
        _emit(event_bus=bus, audit_log=log)
        r = log.records
        r.append("extra")
        assert len(log.records) == 1  # internal list not mutated

    def test_audit_log_len(self):
        log = AuditLog()
        bus = EventBus()
        assert len(log) == 0
        _emit(event_bus=bus, audit_log=log)
        assert len(log) == 1

    def test_audit_log_clear(self):
        log = AuditLog()
        bus = EventBus()
        _emit(event_bus=bus, audit_log=log)
        log.clear()
        assert log.records == []


# ---------------------------------------------------------------------------
# Default bus / audit log injection
# ---------------------------------------------------------------------------


class TestDefaultInjection:
    def setup_method(self):
        default_event_bus.clear("label_chip")
        default_audit_log.clear()

    def teardown_method(self):
        default_event_bus.clear("label_chip")
        default_audit_log.clear()

    def test_default_bus_used_when_none(self):
        received = []
        default_event_bus.subscribe("label_chip", received.append)
        chip = _emit(event_bus=None, audit_log=AuditLog())
        assert received == [chip]

    def test_default_audit_log_used_when_none(self):
        chip = _emit(event_bus=EventBus(), audit_log=None)
        assert default_audit_log.records == [chip]

    def test_custom_bus_does_not_publish_to_default(self):
        default_received = []
        default_event_bus.subscribe("label_chip", default_received.append)
        custom_bus = EventBus()
        custom_received = []
        custom_bus.subscribe("label_chip", custom_received.append)

        chip = _emit(event_bus=custom_bus, audit_log=AuditLog())
        assert custom_received == [chip]
        assert default_received == []

    def test_custom_audit_log_does_not_append_to_default(self):
        custom_log = AuditLog()
        _emit(event_bus=EventBus(), audit_log=custom_log)
        assert len(custom_log) == 1
        assert len(default_audit_log) == 0
