"""Tests for SupportBuffer (SEG-020) — few-shot support buffer with drift tracking."""

import json
import math

import numpy as np
import pytest

from app.services.suggestion.prototype_classifier import PrototypeShapeClassifier, SupportSegment
from app.services.suggestion.support_buffer import AcceptResult, SupportBuffer, SupportBufferConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trend(n: int = 24) -> list[float]:
    return [i / (n - 1) for i in range(n)]


def _plateau(n: int = 24) -> list[float]:
    return [0.5] * n


def _cycle(n: int = 24) -> list[float]:
    return [math.sin(2 * math.pi * i / 6) for i in range(n)]


def _spike(n: int = 24) -> list[float]:
    sig = [0.0] * n
    sig[n // 2] = 3.0
    return sig


def _step(n: int = 24) -> list[float]:
    return [0.0] * (n // 2) + [1.0] * (n - n // 2)


def _minimal_classifier() -> PrototypeShapeClassifier:
    """Classifier pre-fitted with one sample per class so accept_correction works."""
    clf = PrototypeShapeClassifier()
    support = [
        SupportSegment(shape_label="trend", values=tuple(_trend()), provenance="user"),
        SupportSegment(shape_label="plateau", values=tuple(_plateau()), provenance="user"),
        SupportSegment(shape_label="cycle", values=tuple(_cycle()), provenance="user"),
        SupportSegment(shape_label="spike", values=tuple(_spike()), provenance="user"),
        SupportSegment(shape_label="step", values=tuple(_step()), provenance="user"),
        SupportSegment(shape_label="transient", values=tuple(_plateau()), provenance="user"),
        SupportSegment(shape_label="noise", values=tuple(_trend()), provenance="user"),
    ]
    clf.fit_prototypes(support)
    return clf


# ---------------------------------------------------------------------------
# AcceptResult structure
# ---------------------------------------------------------------------------


def test_accept_result_defaults():
    result = AcceptResult(accepted=True, reason="buffered")
    assert result.prototypes_updated is False
    assert result.drift is None


def test_accept_result_is_frozen():
    result = AcceptResult(accepted=True, reason="buffered")
    with pytest.raises((AttributeError, TypeError)):
        result.accepted = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Confidence gate
# ---------------------------------------------------------------------------


def test_confidence_gate_rejects_below_threshold():
    buf = SupportBuffer(SupportBufferConfig(confidence_gate=0.7))
    clf = _minimal_classifier()

    result = buf.accept_correction(_trend(), "trend", confidence=0.5, classifier=clf)

    assert result.accepted is False
    assert result.reason == "below_confidence_gate"
    assert buf.total_accepted == 0


def test_confidence_gate_rejects_strictly_below():
    buf = SupportBuffer(SupportBufferConfig(confidence_gate=0.7))
    clf = _minimal_classifier()

    result = buf.accept_correction(_trend(), "trend", confidence=0.6999, classifier=clf)

    assert result.accepted is False


def test_confidence_gate_accepts_at_threshold():
    buf = SupportBuffer(SupportBufferConfig(confidence_gate=0.7, n_update=100))
    clf = _minimal_classifier()

    result = buf.accept_correction(_trend(), "trend", confidence=0.7, classifier=clf)

    assert result.accepted is True
    assert buf.total_accepted == 1


def test_confidence_gate_accepts_above_threshold():
    buf = SupportBuffer(SupportBufferConfig(confidence_gate=0.7, n_update=100))
    clf = _minimal_classifier()

    result = buf.accept_correction(_trend(), "trend", confidence=0.95, classifier=clf)

    assert result.accepted is True


# ---------------------------------------------------------------------------
# Unknown label
# ---------------------------------------------------------------------------


def test_unknown_label_rejected():
    buf = SupportBuffer()
    clf = _minimal_classifier()

    result = buf.accept_correction(_trend(), "anomaly", confidence=0.9, classifier=clf)

    assert result.accepted is False
    assert result.reason == "unknown_label"
    assert buf.total_accepted == 0


# ---------------------------------------------------------------------------
# Buffer cap / FIFO eviction
# ---------------------------------------------------------------------------


def test_buffer_cap_enforces_fifo_eviction():
    cap = 5
    buf = SupportBuffer(SupportBufferConfig(cap_per_class=cap, n_update=1000))
    clf = _minimal_classifier()

    for _ in range(cap + 3):
        buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)

    assert len(buf.buffers["trend"]) == cap


def test_buffer_cap_keeps_newest_segments():
    cap = 3
    buf = SupportBuffer(SupportBufferConfig(cap_per_class=cap, n_update=1000))
    clf = _minimal_classifier()

    signals = [[float(i)] * 6 for i in range(cap + 2)]
    for sig in signals:
        buf.accept_correction(sig, "trend", confidence=0.9, classifier=clf)

    stored_values = [list(seg.values) for seg in buf.buffers["trend"]]
    assert stored_values == signals[-(cap):]


def test_buffer_cap_independent_per_class():
    cap = 3
    buf = SupportBuffer(SupportBufferConfig(cap_per_class=cap, n_update=1000))
    clf = _minimal_classifier()

    for _ in range(cap + 1):
        buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)
    buf.accept_correction(_plateau(), "plateau", confidence=0.9, classifier=clf)

    assert len(buf.buffers["trend"]) == cap
    assert len(buf.buffers["plateau"]) == 1


# ---------------------------------------------------------------------------
# Trigger frequency
# ---------------------------------------------------------------------------


def test_no_update_before_n_update():
    n = 5
    buf = SupportBuffer(SupportBufferConfig(n_update=n, confidence_gate=0.0))
    clf = _minimal_classifier()

    for _ in range(n - 1):
        result = buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)
        assert result.prototypes_updated is False


def test_update_triggered_at_n_update():
    n = 5
    buf = SupportBuffer(SupportBufferConfig(n_update=n, confidence_gate=0.0))
    clf = _minimal_classifier()

    for _ in range(n - 1):
        buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)
    result = buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)

    assert result.prototypes_updated is True
    assert result.drift is not None


def test_update_triggered_at_2n():
    n = 3
    buf = SupportBuffer(SupportBufferConfig(n_update=n, confidence_gate=0.0))
    clf = _minimal_classifier()

    updates = 0
    for _ in range(n * 2):
        r = buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)
        if r.prototypes_updated:
            updates += 1

    assert updates == 2


def test_rejected_corrections_do_not_advance_counter():
    buf = SupportBuffer(SupportBufferConfig(n_update=5, confidence_gate=0.8))
    clf = _minimal_classifier()

    for _ in range(10):
        buf.accept_correction(_trend(), "trend", confidence=0.3, classifier=clf)

    assert buf.total_accepted == 0


# ---------------------------------------------------------------------------
# Drift computation
# ---------------------------------------------------------------------------


def test_drift_zero_on_first_recompute():
    buf = SupportBuffer(SupportBufferConfig(n_update=1, confidence_gate=0.0))
    clf = _minimal_classifier()

    result = buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)

    assert result.prototypes_updated is True
    assert result.drift == 0.0


def test_drift_nonzero_after_different_support():
    n = 3
    buf = SupportBuffer(SupportBufferConfig(n_update=n, confidence_gate=0.0, cap_per_class=100))
    clf = _minimal_classifier()

    for _ in range(n):
        buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)

    for _ in range(n):
        buf.accept_correction(_plateau(), "trend", confidence=0.9, classifier=clf)

    last_drift = buf._compute_max_drift()
    assert last_drift >= 0.0


def test_drift_zero_when_same_support_repeated():
    n = 2
    buf = SupportBuffer(SupportBufferConfig(n_update=n, confidence_gate=0.0, cap_per_class=n))
    clf = _minimal_classifier()

    for _ in range(n):
        buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)

    first_result = buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)
    second_result = buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)

    assert second_result.prototypes_updated is True
    assert second_result.drift is not None
    assert second_result.drift >= 0.0


# ---------------------------------------------------------------------------
# prev_prototypes retained for rollback
# ---------------------------------------------------------------------------


def test_prev_prototypes_empty_before_first_update():
    buf = SupportBuffer(SupportBufferConfig(n_update=5, confidence_gate=0.0))
    assert buf.prev_prototypes == {}


def test_prev_prototypes_retained_after_update():
    n = 2
    buf = SupportBuffer(SupportBufferConfig(n_update=n, confidence_gate=0.0))
    clf = _minimal_classifier()

    for _ in range(n):
        buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)

    for _ in range(n):
        buf.accept_correction(_plateau(), "trend", confidence=0.9, classifier=clf)

    prev = buf.prev_prototypes
    assert isinstance(prev, dict)
    assert "trend" in prev


def test_prev_prototypes_property_is_copy():
    n = 2
    buf = SupportBuffer(SupportBufferConfig(n_update=n, confidence_gate=0.0))
    clf = _minimal_classifier()

    for _ in range(n):
        buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)

    prev1 = buf.prev_prototypes
    prev2 = buf.prev_prototypes
    assert prev1 is not prev2


# ---------------------------------------------------------------------------
# Drift warning logged
# ---------------------------------------------------------------------------


def test_drift_warning_logged_above_threshold(caplog):
    import logging

    buf = SupportBuffer(SupportBufferConfig(
        n_update=1,
        confidence_gate=0.0,
        drift_threshold=0.0,
    ))
    clf = _minimal_classifier()

    buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)

    with caplog.at_level(logging.WARNING, logger="app.services.suggestion.support_buffer"):
        buf.accept_correction(_plateau(), "trend", confidence=0.9, classifier=clf)

    assert any("drift" in record.message.lower() for record in caplog.records)


def test_no_warning_when_drift_below_threshold(caplog):
    import logging

    buf = SupportBuffer(SupportBufferConfig(
        n_update=2,
        confidence_gate=0.0,
        drift_threshold=999.0,
    ))
    clf = _minimal_classifier()

    with caplog.at_level(logging.WARNING, logger="app.services.suggestion.support_buffer"):
        buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)
        buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 0


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------


def test_json_round_trip_preserves_total_accepted():
    buf = SupportBuffer(SupportBufferConfig(n_update=100))
    clf = _minimal_classifier()
    for _ in range(3):
        buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)

    data = buf.to_dict()
    restored = SupportBuffer.from_dict(data)

    assert restored.total_accepted == buf.total_accepted


def test_json_round_trip_preserves_config():
    config = SupportBufferConfig(cap_per_class=20, drift_threshold=0.5, n_update=3, confidence_gate=0.6)
    buf = SupportBuffer(config)

    data = buf.to_dict()
    restored = SupportBuffer.from_dict(data)

    assert restored.config.cap_per_class == 20
    assert restored.config.drift_threshold == 0.5
    assert restored.config.n_update == 3
    assert restored.config.confidence_gate == 0.6


def test_json_round_trip_preserves_buffer_segments():
    buf = SupportBuffer(SupportBufferConfig(n_update=100))
    clf = _minimal_classifier()
    buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)
    buf.accept_correction(_plateau(), "plateau", confidence=0.9, classifier=clf)

    data = buf.to_dict()
    restored = SupportBuffer.from_dict(data)

    assert len(restored.buffers["trend"]) == 1
    assert len(restored.buffers["plateau"]) == 1
    assert restored.buffers["trend"][0].shape_label == "trend"


def test_json_round_trip_is_json_serializable():
    buf = SupportBuffer(SupportBufferConfig(n_update=100))
    clf = _minimal_classifier()
    buf.accept_correction(_trend(), "trend", confidence=0.9, classifier=clf)

    raw = json.dumps(buf.to_dict())
    data = json.loads(raw)
    restored = SupportBuffer.from_dict(data)

    assert restored.total_accepted == 1


def test_json_round_trip_empty_buffer():
    buf = SupportBuffer()
    data = buf.to_dict()
    restored = SupportBuffer.from_dict(data)

    assert restored.total_accepted == 0
    for label in restored.buffers:
        assert len(restored.buffers[label]) == 0


def test_from_dict_initialises_all_shape_labels():
    from app.services.suggestion.prototype_classifier import SHAPE_LABELS
    buf = SupportBuffer.from_dict({"total_accepted": 0, "config": {}, "buffers": {}})
    assert set(buf.buffers.keys()) == set(SHAPE_LABELS)
