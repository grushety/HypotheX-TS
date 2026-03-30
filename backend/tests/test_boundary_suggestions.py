from app.schemas.suggestions import SuggestionProposal
from app.services.suggestions import BoundarySuggestionService, SuggestionServiceError
from app.services.suggestion.boundary_proposal import BoundaryProposerConfig, propose_boundaries


def test_propose_boundaries_detects_clear_regime_changes():
    series = ([0.0] * 20) + ([4.0] * 20) + ([-3.0] * 20)

    proposal = propose_boundaries(
        series,
        BoundaryProposerConfig(
            window_size=6,
            min_segment_length=5,
            score_threshold=0.25,
            max_boundaries=4,
        ),
    )

    assert [candidate.boundaryIndex for candidate in proposal.candidateBoundaries] == [20, 40]
    assert proposal.provisionalSegments[0].startIndex == 0
    assert proposal.provisionalSegments[0].endIndex == 19
    assert proposal.provisionalSegments[1].startIndex == 20
    assert proposal.provisionalSegments[1].endIndex == 39
    assert proposal.provisionalSegments[2].startIndex == 40
    assert proposal.provisionalSegments[2].endIndex == 59


def test_boundary_suggestion_service_serializes_stable_payload():
    service = BoundarySuggestionService(
        proposer_config={
            "window_size": 5,
            "min_segment_length": 4,
            "score_threshold": 0.25,
            "max_boundaries": 3,
        }
    )

    proposal = service.propose(
        series_id="series-clear-001",
        values=([1.0] * 12) + ([5.0] * 12) + ([1.5] * 12),
        suggestion_id="suggestion-clear-001",
    )

    assert isinstance(proposal, SuggestionProposal)
    payload = proposal.to_dict()

    assert payload["schemaVersion"] == "1.0.0"
    assert payload["suggestionId"] == "suggestion-clear-001"
    assert payload["seriesId"] == "series-clear-001"
    assert payload["modelVersion"] == "suggestion-model-v1"
    assert payload["boundaryProposer"]["name"] == "conservative-change-point-v1"
    assert payload["candidateBoundaries"][0]["boundaryIndex"] == 12
    assert payload["provisionalSegments"][0]["provenance"] == "model"
    assert payload["provisionalSegments"][-1]["endIndex"] == 35


def test_boundary_suggestion_service_rejects_missing_series_id():
    service = BoundarySuggestionService()

    try:
        service.propose(series_id="", values=[0.0, 1.0, 2.0, 3.0])
    except SuggestionServiceError as exc:
        assert "series_id" in str(exc)
    else:
        raise AssertionError("Expected SuggestionServiceError for an empty series_id.")
