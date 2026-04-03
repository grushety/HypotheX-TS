"""Tests for the adapt_model endpoint and BoundarySuggestionService.adapt() (SEG-005).

Covers:
  - Successful prototype update (applied=True)
  - Confidence below threshold → not applied, no drift_report entry
  - Unknown label → raises / 400
  - Empty support_segments → raises / 400
  - Missing session initialises from default templates
  - model_version_id increments with each adapt call
  - Route: 200 correct shape, 400 missing fields, 400 empty segments
"""

import json

import pytest

from app.services.suggestion.prototype_classifier import PrototypeMemoryConfig
from app.services.suggestions import AdaptResult, BoundarySuggestionService, SuggestionServiceError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TREND_VALUES = [float(i) / 23 for i in range(24)]   # length-24 linearly rising
_PLATEAU_VALUES = [0.25] * 24


def _make_service() -> BoundarySuggestionService:
    return BoundarySuggestionService()


# ---------------------------------------------------------------------------
# BoundarySuggestionService.adapt() — unit tests
# ---------------------------------------------------------------------------


class TestAdaptServiceSuccessfulUpdate:
    def test_returns_adapt_result(self):
        svc = _make_service()
        result = svc.adapt(
            session_id="s1",
            support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}],
        )
        assert isinstance(result, AdaptResult)

    def test_model_version_id_format(self):
        svc = _make_service()
        result = svc.adapt(
            session_id="s1",
            support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}],
        )
        assert result.model_version_id.startswith("suggestion-model-v1+adapt-")

    def test_applied_label_in_prototypes_updated(self):
        svc = _make_service()
        result = svc.adapt(
            session_id="s1",
            support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}],
        )
        assert "trend" in result.prototypes_updated

    def test_drift_report_contains_applied_label(self):
        svc = _make_service()
        result = svc.adapt(
            session_id="s1",
            support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}],
        )
        assert "trend" in result.drift_report
        assert isinstance(result.drift_report["trend"], float)

    def test_default_confidence_is_one(self):
        """Omitting confidence should default to 1.0 (update applied)."""
        svc = _make_service()
        result = svc.adapt(
            session_id="s2",
            support_segments=[{"label": "plateau", "values": _PLATEAU_VALUES}],
        )
        assert "plateau" in result.prototypes_updated

    def test_multiple_segments_in_one_call(self):
        svc = _make_service()
        result = svc.adapt(
            session_id="s3",
            support_segments=[
                {"label": "trend", "values": _TREND_VALUES, "confidence": 1.0},
                {"label": "plateau", "values": _PLATEAU_VALUES, "confidence": 1.0},
            ],
        )
        assert "trend" in result.prototypes_updated
        assert "plateau" in result.prototypes_updated


class TestAdaptServiceVersionCounter:
    def test_update_count_increments_across_calls(self):
        svc = _make_service()
        r1 = svc.adapt(
            session_id="s1",
            support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}],
        )
        r2 = svc.adapt(
            session_id="s1",
            support_segments=[{"label": "plateau", "values": _PLATEAU_VALUES, "confidence": 1.0}],
        )
        n1 = int(r1.model_version_id.split("adapt-")[1])
        n2 = int(r2.model_version_id.split("adapt-")[1])
        assert n2 > n1

    def test_different_sessions_have_independent_counters(self):
        svc = _make_service()
        svc.adapt(session_id="a", support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}])
        svc.adapt(session_id="a", support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}])
        r = svc.adapt(session_id="b", support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}])
        n = int(r.model_version_id.split("adapt-")[1])
        assert n == 1  # session "b" has had only one call


class TestAdaptServiceRejections:
    def test_confidence_below_threshold_not_applied(self):
        """Confidence 0.0 < default min_update_confidence 0.75 → rejected."""
        svc = _make_service()
        result = svc.adapt(
            session_id="s1",
            support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 0.0}],
        )
        assert "trend" not in result.prototypes_updated
        assert "trend" not in result.drift_report

    def test_empty_support_segments_raises(self):
        svc = _make_service()
        with pytest.raises(SuggestionServiceError, match="at least one"):
            svc.adapt(session_id="s1", support_segments=[])

    def test_unknown_label_raises(self):
        svc = _make_service()
        with pytest.raises(SuggestionServiceError):
            svc.adapt(
                session_id="s1",
                support_segments=[{"label": "NOT_A_LABEL", "values": _TREND_VALUES, "confidence": 1.0}],
            )

    def test_missing_label_key_raises(self):
        svc = _make_service()
        with pytest.raises(SuggestionServiceError):
            svc.adapt(
                session_id="s1",
                support_segments=[{"values": _TREND_VALUES, "confidence": 1.0}],
            )

    def test_missing_values_key_raises(self):
        svc = _make_service()
        with pytest.raises(SuggestionServiceError):
            svc.adapt(
                session_id="s1",
                support_segments=[{"label": "trend", "confidence": 1.0}],
            )


class TestAdaptServiceSessionInit:
    def test_new_session_initialises_from_defaults(self):
        """First call for an unseen session_id should not raise."""
        svc = _make_service()
        result = svc.adapt(
            session_id="brand-new-session",
            support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}],
        )
        assert isinstance(result, AdaptResult)

    def test_session_state_persists_across_calls(self):
        """Second call uses updated bank from first call (counter increments)."""
        svc = _make_service()
        svc.adapt(session_id="persist", support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}])
        r2 = svc.adapt(session_id="persist", support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}])
        n2 = int(r2.model_version_id.split("adapt-")[1])
        assert n2 == 2  # second call in this session

    def test_different_sessions_are_isolated(self):
        """Updates to one session do not affect another."""
        svc = _make_service()
        svc.adapt(session_id="x", support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}])
        svc.adapt(session_id="x", support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}])
        r_y = svc.adapt(session_id="y", support_segments=[{"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}])
        n_y = int(r_y.model_version_id.split("adapt-")[1])
        assert n_y == 1


# ---------------------------------------------------------------------------
# Route: POST /api/benchmarks/suggestion/adapt
# ---------------------------------------------------------------------------


class TestAdaptRoute:
    def test_valid_request_returns_200(self, client):
        resp = client.post(
            "/api/benchmarks/suggestion/adapt",
            json={
                "session_id": "route-test-1",
                "support_segments": [
                    {"label": "trend", "values": _TREND_VALUES, "confidence": 1.0}
                ],
            },
        )
        assert resp.status_code == 200

    def test_response_has_correct_keys(self, client):
        resp = client.post(
            "/api/benchmarks/suggestion/adapt",
            json={
                "session_id": "route-test-2",
                "support_segments": [{"label": "trend", "values": _TREND_VALUES}],
            },
        )
        data = resp.get_json()
        assert "model_version_id" in data
        assert "prototypes_updated" in data
        assert "drift_report" in data

    def test_model_version_id_format(self, client):
        resp = client.post(
            "/api/benchmarks/suggestion/adapt",
            json={
                "session_id": "route-test-3",
                "support_segments": [{"label": "trend", "values": _TREND_VALUES}],
            },
        )
        data = resp.get_json()
        assert data["model_version_id"].startswith("suggestion-model-v1+adapt-")

    def test_prototypes_updated_is_list(self, client):
        resp = client.post(
            "/api/benchmarks/suggestion/adapt",
            json={
                "session_id": "route-test-4",
                "support_segments": [{"label": "plateau", "values": _PLATEAU_VALUES}],
            },
        )
        data = resp.get_json()
        assert isinstance(data["prototypes_updated"], list)

    def test_drift_report_is_dict(self, client):
        resp = client.post(
            "/api/benchmarks/suggestion/adapt",
            json={
                "session_id": "route-test-5",
                "support_segments": [{"label": "trend", "values": _TREND_VALUES}],
            },
        )
        data = resp.get_json()
        assert isinstance(data["drift_report"], dict)

    def test_empty_support_segments_returns_400(self, client):
        resp = client.post(
            "/api/benchmarks/suggestion/adapt",
            json={"session_id": "s", "support_segments": []},
        )
        assert resp.status_code == 400

    def test_missing_session_id_returns_400(self, client):
        resp = client.post(
            "/api/benchmarks/suggestion/adapt",
            json={"support_segments": [{"label": "trend", "values": _TREND_VALUES}]},
        )
        assert resp.status_code == 400

    def test_missing_support_segments_returns_400(self, client):
        resp = client.post(
            "/api/benchmarks/suggestion/adapt",
            json={"session_id": "s"},
        )
        assert resp.status_code == 400

    def test_no_body_returns_400(self, client):
        resp = client.post(
            "/api/benchmarks/suggestion/adapt",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400

    def test_unknown_label_returns_400(self, client):
        resp = client.post(
            "/api/benchmarks/suggestion/adapt",
            json={
                "session_id": "s",
                "support_segments": [{"label": "INVALID_LABEL", "values": _TREND_VALUES}],
            },
        )
        assert resp.status_code == 400

    def test_low_confidence_segment_not_in_prototypes_updated(self, client):
        resp = client.post(
            "/api/benchmarks/suggestion/adapt",
            json={
                "session_id": "low-conf",
                "support_segments": [{"label": "trend", "values": _TREND_VALUES, "confidence": 0.0}],
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "trend" not in data["prototypes_updated"]
