from app.domain.chunk_assignment import assign_chunk_type
from app.domain.chunk_scoring import compute_chunk_scores
from app.domain.stats import SegmentStatistics


def test_compute_chunk_scores_covers_every_active_chunk_type_for_clear_plateau():
    statistics = SegmentStatistics(
        schemaVersion="1.0.0",
        seriesLength=12,
        startIndex=2,
        endIndex=7,
        segmentLength=6,
        channelCount=1,
        mean=(0.25,),
        variance=0.001,
        slope=0.01,
        signConsistency=0.55,
        residualToLine=0.004,
        contextContrast=0.05,
        peakScore=0.4,
        periodicityScore=0.08,
    )

    scores = compute_chunk_scores(statistics)

    assert set(scores.scores) == {
        "trend",
        "plateau",
        "spike",
        "event",
        "transition",
        "periodic",
    }
    assert scores.scores["plateau"] > scores.scores["trend"]
    assert scores.scores["plateau"] > scores.scores["event"]


def test_assign_chunk_type_flags_ambiguous_borderline_trend_plateau_case():
    statistics = SegmentStatistics(
        schemaVersion="1.0.0",
        seriesLength=12,
        startIndex=3,
        endIndex=8,
        segmentLength=6,
        channelCount=1,
        mean=(0.4,),
        variance=0.01,
        slope=0.08,
        signConsistency=0.88,
        residualToLine=0.04,
        contextContrast=0.12,
        peakScore=0.6,
        periodicityScore=0.05,
    )

    assignment = assign_chunk_type(statistics)

    assert assignment.assignedLabel == "plateau"
    assert assignment.runnerUpLabel == "trend"
    assert assignment.isAmbiguous is True
    assert assignment.ambiguityMargin < 0.1


def test_assignment_can_serialize_to_shared_segment_shape():
    statistics = SegmentStatistics(
        schemaVersion="1.0.0",
        seriesLength=10,
        startIndex=1,
        endIndex=6,
        segmentLength=6,
        channelCount=1,
        mean=(0.2,),
        variance=0.002,
        slope=0.0,
        signConsistency=0.5,
        residualToLine=0.002,
        contextContrast=0.06,
        peakScore=0.3,
        periodicityScore=0.04,
    )

    assignment = assign_chunk_type(statistics)
    payload = assignment.to_segment_payload(
        segment_id="segment-plateau-001",
        start_index=1,
        end_index=6,
        provenance="model",
    )

    assert payload == {
        "segmentId": "segment-plateau-001",
        "startIndex": 1,
        "endIndex": 6,
        "label": assignment.assignedLabel,
        "confidence": assignment.confidence,
        "provenance": "model",
    }
    assert payload["label"] in {"trend", "plateau", "spike", "event", "transition", "periodic"}
