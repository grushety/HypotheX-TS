import math

from app.services.suggestion.prototype_classifier import (
    LabeledSupportSegment,
    PrototypeChunkClassifier,
)
from app.services.suggestion.segment_encoder import SegmentEncoderConfig, encode_segment
from app.services.suggestions import BoundarySuggestionService


def test_segment_encoder_returns_fixed_size_l2_normalized_embeddings():
    short_embedding = encode_segment(
        [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        SegmentEncoderConfig(resample_length=12),
    )
    long_embedding = encode_segment(
        [value / 20 for value in range(20)],
        SegmentEncoderConfig(resample_length=12),
    )

    assert len(short_embedding.values) == len(long_embedding.values)
    assert math.isclose(sum(value * value for value in short_embedding.values), 1.0, rel_tol=1e-6)
    assert math.isclose(sum(value * value for value in long_embedding.values), 1.0, rel_tol=1e-6)


def test_prototype_classifier_returns_probabilities_for_active_chunk_types():
    classifier = PrototypeChunkClassifier()
    support_segments = [
        LabeledSupportSegment(label="trend", values=[value / 23 for value in range(24)]),
        LabeledSupportSegment(label="plateau", values=[0.3] * 24),
        LabeledSupportSegment(label="spike", values=[0.0] * 11 + [3.0] + [0.0] * 12),
        LabeledSupportSegment(label="event", values=[0.0] * 8 + [1.0] * 8 + [0.0] * 8),
        LabeledSupportSegment(
            label="transition",
            values=[0.0] * 8 + [index / 7 for index in range(8)] + [1.0] * 8,
        ),
        LabeledSupportSegment(
            label="periodic",
            values=[math.sin(index * (2 * math.pi / 6)) for index in range(24)],
        ),
    ]

    prototypes = classifier.build_prototypes(support_segments)
    classification = classifier.classify_segment(
        [0.0] * 8 + [0.95] * 8 + [0.0] * 8,
        prototypes=prototypes,
    )

    assert set(classification.probabilities) == set(classifier.active_labels)
    assert math.isclose(sum(classification.probabilities.values()), 1.0, rel_tol=1e-6)
    assert classification.label == "event"
    assert classification.confidence == classification.probabilities["event"]


def test_boundary_suggestion_service_serializes_classifier_output_into_contract():
    service = BoundarySuggestionService(
        proposer_config={
            "window_size": 5,
            "min_segment_length": 4,
            "score_threshold": 0.25,
            "max_boundaries": 3,
        },
        encoder_config={"resample_length": 12},
        classifier_config={"temperature": 0.15},
    )
    support_segments = [
        LabeledSupportSegment(label="plateau", values=[0.2] * 12),
        LabeledSupportSegment(
            label="periodic",
            values=[math.sin(index * (2 * math.pi / 6)) for index in range(12)],
        ),
    ]

    proposal = service.propose(
        series_id="series-proto-001",
        values=([0.2] * 12)
        + ([math.sin(index * (2 * math.pi / 6)) for index in range(12)])
        + ([0.2] * 12),
        suggestion_id="suggestion-proto-001",
        support_segments=support_segments,
    )
    payload = proposal.to_dict()

    assert payload["provisionalSegments"][0]["label"] == "plateau"
    assert payload["provisionalSegments"][0]["confidence"] > 0.0
    assert "labelScores" in payload["provisionalSegments"][0]
    assert set(payload["provisionalSegments"][0]["labelScores"]) == {
        "trend",
        "plateau",
        "spike",
        "event",
        "transition",
        "periodic",
    }
    for segment_payload in payload["provisionalSegments"]:
        assert segment_payload["label"] in {
            "trend",
            "plateau",
            "spike",
            "event",
            "transition",
            "periodic",
        }
        assert math.isclose(sum(segment_payload["labelScores"].values()), 1.0, rel_tol=1e-6)
