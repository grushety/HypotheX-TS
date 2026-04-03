"""Tests for uncertainty scoring module and route (SEG-004).

Covers:
  - Entropy of 0 for a certain (deterministic) prediction
  - Entropy of 1 for a uniform distribution
  - boundary_uncertainty length equals series length
  - segment_uncertainty length equals number of segments
  - Gaussian smoothing preserves array length and clips to [0, 1]
  - score_uncertainty raises on length mismatch
  - compute_boundary_scores returns array of correct length
  - Route GET /api/benchmarks/suggestion/uncertainty returns correct shape
"""

import math

import numpy as np
import pytest

from app.services.suggestion.boundary_proposal import (
    BoundaryProposerConfig,
    ProvisionalSegment,
    compute_boundary_scores,
)
from app.services.suggestion.uncertainty import (
    UncertaintyResult,
    _gaussian_kernel,
    _normalized_entropy,
    _smooth_boundary_scores,
    score_uncertainty,
)
from app.services.suggestions import BoundarySuggestionService


# ---------------------------------------------------------------------------
# _normalized_entropy
# ---------------------------------------------------------------------------


class TestNormalizedEntropy:
    def test_certain_prediction_returns_zero(self):
        probs = {"trend": 1.0, "plateau": 0.0, "spike": 0.0}
        assert _normalized_entropy(probs) == 0.0

    def test_uniform_distribution_returns_one(self):
        n = 6
        probs = {str(i): 1.0 / n for i in range(n)}
        result = _normalized_entropy(probs)
        assert math.isclose(result, 1.0, rel_tol=1e-6)

    def test_empty_dict_returns_zero(self):
        assert _normalized_entropy({}) == 0.0

    def test_single_label_returns_zero(self):
        assert _normalized_entropy({"trend": 1.0}) == 0.0

    def test_two_label_half_half_returns_one(self):
        probs = {"a": 0.5, "b": 0.5}
        result = _normalized_entropy(probs)
        assert math.isclose(result, 1.0, rel_tol=1e-6)

    def test_value_between_zero_and_one_for_skewed_distribution(self):
        probs = {"trend": 0.7, "plateau": 0.2, "spike": 0.1}
        result = _normalized_entropy(probs)
        assert 0.0 < result < 1.0

    def test_result_capped_at_one(self):
        # Slightly over-summing probs should not exceed 1.0 after capping.
        probs = {str(i): 1.0 / 6.0 for i in range(6)}
        result = _normalized_entropy(probs)
        assert result <= 1.0


# ---------------------------------------------------------------------------
# _gaussian_kernel
# ---------------------------------------------------------------------------


class TestGaussianKernel:
    def test_sums_to_one(self):
        kernel = _gaussian_kernel(sigma=2.0)
        assert math.isclose(float(np.sum(kernel)), 1.0, rel_tol=1e-9)

    def test_odd_length(self):
        kernel = _gaussian_kernel(sigma=2.0)
        assert len(kernel) % 2 == 1

    def test_symmetric(self):
        kernel = _gaussian_kernel(sigma=2.0)
        np.testing.assert_allclose(kernel, kernel[::-1], rtol=1e-9)

    def test_minimum_radius(self):
        # Very small sigma → radius clamped to 1 → length at least 3.
        kernel = _gaussian_kernel(sigma=0.01)
        assert len(kernel) >= 3


# ---------------------------------------------------------------------------
# _smooth_boundary_scores
# ---------------------------------------------------------------------------


class TestSmoothBoundaryScores:
    def test_output_length_equals_input_length(self):
        scores = np.zeros(50, dtype=np.float64)
        smoothed = _smooth_boundary_scores(scores)
        assert len(smoothed) == 50

    def test_all_values_in_unit_interval(self):
        rng = np.random.default_rng(0)
        scores = rng.uniform(0.0, 1.0, 80)
        smoothed = _smooth_boundary_scores(scores)
        assert float(np.min(smoothed)) >= 0.0
        assert float(np.max(smoothed)) <= 1.0

    def test_zero_input_gives_near_zero_output(self):
        scores = np.zeros(40, dtype=np.float64)
        smoothed = _smooth_boundary_scores(scores)
        assert float(np.max(np.abs(smoothed))) < 1e-12

    def test_spike_spreads_to_neighbours(self):
        scores = np.zeros(30, dtype=np.float64)
        scores[15] = 1.0
        smoothed = _smooth_boundary_scores(scores, sigma=2.0)
        # The spike should spread to adjacent positions.
        assert smoothed[13] > 0.0
        assert smoothed[17] > 0.0
        # And should be near-zero far away.
        assert smoothed[0] < 0.01
        assert smoothed[29] < 0.01

    def test_peak_is_at_original_spike_position(self):
        scores = np.zeros(30, dtype=np.float64)
        scores[10] = 1.0
        smoothed = _smooth_boundary_scores(scores, sigma=2.0)
        assert int(np.argmax(smoothed)) == 10


# ---------------------------------------------------------------------------
# score_uncertainty
# ---------------------------------------------------------------------------


def _make_segment(start: int, end: int, label_scores: dict | None = None) -> ProvisionalSegment:
    return ProvisionalSegment(
        segmentId=f"seg-{start}",
        startIndex=start,
        endIndex=end,
        label=max(label_scores, key=label_scores.get) if label_scores else None,
        labelScores=label_scores,
    )


class TestScoreUncertainty:
    def test_boundary_uncertainty_length_equals_series_length(self):
        values = list(range(50))
        scores = np.zeros(50)
        segments = [_make_segment(0, 24), _make_segment(25, 49)]
        result = score_uncertainty(values, segments, scores)
        assert len(result.boundary_uncertainty) == 50

    def test_segment_uncertainty_length_equals_segment_count(self):
        values = list(range(30))
        scores = np.zeros(30)
        segments = [_make_segment(0, 9), _make_segment(10, 19), _make_segment(20, 29)]
        result = score_uncertainty(values, segments, scores)
        assert len(result.segment_uncertainty) == 3

    def test_result_is_uncertainty_result_instance(self):
        values = [1.0] * 20
        scores = np.zeros(20)
        segments = [_make_segment(0, 19)]
        result = score_uncertainty(values, segments, scores)
        assert isinstance(result, UncertaintyResult)

    def test_certain_segment_has_zero_uncertainty(self):
        values = [1.0] * 20
        scores = np.zeros(20)
        certain_scores = {"trend": 1.0, "plateau": 0.0, "spike": 0.0}
        segments = [_make_segment(0, 19, certain_scores)]
        result = score_uncertainty(values, segments, scores)
        assert result.segment_uncertainty[0] == 0.0

    def test_uniform_segment_has_max_uncertainty(self):
        values = [1.0] * 20
        scores = np.zeros(20)
        n = 6
        uniform = {str(i): 1.0 / n for i in range(n)}
        segments = [_make_segment(0, 19, uniform)]
        result = score_uncertainty(values, segments, scores)
        assert math.isclose(result.segment_uncertainty[0], 1.0, rel_tol=1e-6)

    def test_segment_without_label_scores_gets_zero_uncertainty(self):
        values = [1.0] * 20
        scores = np.zeros(20)
        segments = [_make_segment(0, 19, None)]  # no labelScores
        result = score_uncertainty(values, segments, scores)
        assert result.segment_uncertainty[0] == 0.0

    def test_raises_on_length_mismatch(self):
        values = list(range(20))
        wrong_scores = np.zeros(30)  # 30 ≠ 20
        with pytest.raises(Exception):
            score_uncertainty(values, [], wrong_scores)

    def test_all_boundary_values_in_unit_interval(self):
        rng = np.random.default_rng(42)
        values = rng.standard_normal(60).tolist()
        scores = rng.uniform(0.0, 1.0, 60)
        segments = [_make_segment(0, 29), _make_segment(30, 59)]
        result = score_uncertainty(values, segments, scores)
        for v in result.boundary_uncertainty:
            assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# compute_boundary_scores
# ---------------------------------------------------------------------------


class TestComputeBoundaryScores:
    def test_returns_array_of_series_length(self):
        values = list(range(50))
        scores = compute_boundary_scores(values)
        assert len(scores) == 50

    def test_returns_array_for_flat_signal(self):
        values = [1.0] * 30
        scores = compute_boundary_scores(values)
        assert len(scores) == 30
        assert np.all(scores == 0.0)

    def test_scores_in_unit_interval(self):
        rng = np.random.default_rng(7)
        values = rng.standard_normal(80).tolist()
        scores = compute_boundary_scores(values)
        assert float(np.min(scores)) >= 0.0
        assert float(np.max(scores)) <= 1.0

    def test_accepts_custom_config(self):
        values = list(range(40))
        config = BoundaryProposerConfig(window_size=4)
        scores = compute_boundary_scores(values, config)
        assert len(scores) == 40


# ---------------------------------------------------------------------------
# BoundarySuggestionService.propose include_uncertainty
# ---------------------------------------------------------------------------


class TestProposeWithUncertainty:
    def test_uncertainty_fields_absent_by_default(self):
        svc = BoundarySuggestionService()
        values = [float(i) for i in range(30)]
        proposal = svc.propose(series_id="test", values=values)
        assert proposal.boundary_uncertainty is None
        assert proposal.segment_uncertainty is None

    def test_uncertainty_fields_present_when_requested(self):
        svc = BoundarySuggestionService()
        values = [float(i) for i in range(30)]
        proposal = svc.propose(series_id="test", values=values, include_uncertainty=True)
        assert proposal.boundary_uncertainty is not None
        assert proposal.segment_uncertainty is not None
        assert len(proposal.boundary_uncertainty) == 30
        assert len(proposal.segment_uncertainty) == len(proposal.provisionalSegments)

    def test_to_dict_includes_uncertainty_keys_when_present(self):
        svc = BoundarySuggestionService()
        values = [float(i) for i in range(30)]
        proposal = svc.propose(series_id="test", values=values, include_uncertainty=True)
        d = proposal.to_dict()
        assert "boundaryUncertainty" in d
        assert "segmentUncertainty" in d

    def test_to_dict_omits_uncertainty_keys_when_absent(self):
        svc = BoundarySuggestionService()
        values = [float(i) for i in range(30)]
        proposal = svc.propose(series_id="test", values=values)
        d = proposal.to_dict()
        assert "boundaryUncertainty" not in d
        assert "segmentUncertainty" not in d


# ---------------------------------------------------------------------------
# Route: GET /api/benchmarks/suggestion/uncertainty
# ---------------------------------------------------------------------------


class TestUncertaintyRoute:
    def test_returns_200_with_correct_keys(self, client):
        resp = client.get(
            "/api/benchmarks/suggestion/uncertainty?dataset=ECG200&split=test&sample_index=0"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "boundary_uncertainty" in data
        assert "segment_uncertainty" in data

    def test_boundary_uncertainty_length_matches_series(self, client):
        resp = client.get(
            "/api/benchmarks/suggestion/uncertainty?dataset=ECG200&split=test&sample_index=0"
        )
        data = resp.get_json()
        # ECG200 series length is 96
        assert len(data["boundary_uncertainty"]) == 96

    def test_segment_uncertainty_is_list_of_floats(self, client):
        resp = client.get(
            "/api/benchmarks/suggestion/uncertainty?dataset=ECG200&split=test&sample_index=0"
        )
        data = resp.get_json()
        seg_u = data["segment_uncertainty"]
        assert isinstance(seg_u, list)
        assert all(isinstance(v, float) for v in seg_u)

    def test_missing_params_returns_400(self, client):
        resp = client.get("/api/benchmarks/suggestion/uncertainty?dataset=ECG200")
        assert resp.status_code == 400

    def test_unknown_dataset_returns_404(self, client):
        resp = client.get(
            "/api/benchmarks/suggestion/uncertainty?dataset=UNKNOWN&split=test&sample_index=0"
        )
        assert resp.status_code == 404
