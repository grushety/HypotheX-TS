from app.services.suggestion.boundary_proposal import ProvisionalSegment
from app.services.suggestion.prototype_classifier import (
    LabeledSupportSegment,
    PrototypeChunkClassifier,
    PrototypeMemoryConfig,
)
from app.services.suggestions import DurationSmoothingConfig, smooth_provisional_segments


def test_prototype_memory_rejects_low_confidence_updates():
    classifier = PrototypeChunkClassifier()
    memory_bank = classifier.build_memory_bank(
        [LabeledSupportSegment(label="trend", values=[value / 23 for value in range(24)])],
        memory_config=PrototypeMemoryConfig(
            min_update_confidence=0.9,
            max_buffer_per_label=4,
            max_prototype_drift=1.0,
        ),
    )

    next_memory_bank, update = classifier.update_memory_bank(
        memory_bank,
        label="trend",
        values=[1.0] * 24,
        confidence=0.5,
    )

    assert update.applied is False
    assert update.reason == "confidence_below_threshold"
    assert next_memory_bank == memory_bank
    assert update.buffer_size == 1


def test_prototype_memory_rejects_large_drift_updates():
    classifier = PrototypeChunkClassifier()
    memory_bank = classifier.build_memory_bank(
        [LabeledSupportSegment(label="trend", values=[value / 23 for value in range(24)])],
        memory_config=PrototypeMemoryConfig(
            min_update_confidence=0.6,
            max_buffer_per_label=4,
            max_prototype_drift=0.1,
        ),
    )

    next_memory_bank, update = classifier.update_memory_bank(
        memory_bank,
        label="trend",
        values=[0.0] * 12 + [8.0] * 12,
        confidence=0.95,
    )

    assert update.applied is False
    assert update.reason == "drift_threshold_exceeded"
    assert update.drift is not None
    assert next_memory_bank == memory_bank


def test_prototype_memory_caps_buffer_size():
    classifier = PrototypeChunkClassifier()
    memory_bank = classifier.build_memory_bank(
        [LabeledSupportSegment(label="plateau", values=[0.25] * 24)],
        memory_config=PrototypeMemoryConfig(
            min_update_confidence=0.5,
            max_buffer_per_label=2,
            max_prototype_drift=1.0,
        ),
    )

    memory_bank, first_update = classifier.update_memory_bank(
        memory_bank,
        label="plateau",
        values=[0.3] * 24,
        confidence=0.9,
    )
    memory_bank, second_update = classifier.update_memory_bank(
        memory_bank,
        label="plateau",
        values=[0.35] * 24,
        confidence=0.9,
    )

    assert first_update.applied is True
    assert second_update.applied is True
    assert len(memory_bank.embeddings_by_label["plateau"]) == 2


def test_duration_smoother_merges_too_short_event_into_more_compatible_neighbor():
    result = smooth_provisional_segments(
        [
            ProvisionalSegment(
                segmentId="segment-001",
                startIndex=0,
                endIndex=5,
                label="plateau",
                confidence=0.9,
                labelScores={"plateau": 0.8, "event": 0.1, "trend": 0.1},
            ),
            ProvisionalSegment(
                segmentId="segment-002",
                startIndex=6,
                endIndex=7,
                label="event",
                confidence=0.55,
                labelScores={"plateau": 0.75, "event": 0.15, "trend": 0.1},
            ),
            ProvisionalSegment(
                segmentId="segment-003",
                startIndex=8,
                endIndex=13,
                label="trend",
                confidence=0.85,
                labelScores={"plateau": 0.1, "event": 0.1, "trend": 0.8},
            ),
        ],
        config=DurationSmoothingConfig(
            default_min_length=2,
            per_label_min_lengths={"event": 3},
        ),
    )

    assert result.merged_segment_ids == ("segment-002",)
    assert len(result.segments) == 2
    assert result.segments[0].label == "plateau"
    assert result.segments[0].startIndex == 0
    assert result.segments[0].endIndex == 7
    assert result.segments[1].label == "trend"
