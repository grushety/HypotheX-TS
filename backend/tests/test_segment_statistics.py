import numpy as np
import pytest

from app.domain.stats import (
    SegmentStatisticsError,
    compute_context_contrast,
    compute_peak_score,
    compute_periodicity_score,
    compute_residual_to_line,
    compute_segment_statistics,
    compute_sign_consistency,
    compute_slope,
    compute_variance,
)


def test_compute_segment_statistics_returns_expected_bundle_for_trend_segment():
    series = np.asarray([0.0, 0.4, 0.8, 1.2, 1.6, 2.0], dtype=np.float64)

    stats = compute_segment_statistics(
        series,
        1,
        4,
        smoothing_window=1,
        context_window=1,
        peak_window=1,
        min_segment_length=2,
    )

    assert stats.seriesLength == 6
    assert stats.startIndex == 1
    assert stats.endIndex == 4
    assert stats.segmentLength == 4
    assert stats.channelCount == 1
    assert stats.mean == pytest.approx((1.0,))
    assert stats.variance == pytest.approx(0.2)
    assert stats.slope == pytest.approx(0.4)
    assert stats.signConsistency == pytest.approx(1.0)
    assert stats.residualToLine == pytest.approx(0.0)
    assert stats.contextContrast > 0
    assert stats.peakScore >= 0
    assert stats.periodicityScore >= 0
    assert stats.to_dict()["schemaVersion"] == "1.0.0"


def test_compute_peak_score_detects_spike_like_segment():
    segment = np.asarray([0.0, 0.1, 3.0, 0.1, 0.0], dtype=np.float64)

    score = compute_peak_score(segment, window_size=1)

    assert score > 2.0


def test_multivariate_statistics_average_across_channels():
    segment = np.asarray(
        [
            [0.0, 1.0],
            [1.0, 2.0],
            [2.0, 3.0],
            [3.0, 4.0],
        ],
        dtype=np.float64,
    )

    assert compute_variance(segment) == pytest.approx(2.5)
    assert compute_slope(segment) == pytest.approx(1.0)
    assert compute_sign_consistency(segment) == pytest.approx(1.0)
    assert compute_residual_to_line(segment) == pytest.approx(0.0)


def test_context_contrast_uses_neighboring_windows_when_available():
    series = np.asarray([0.0, 0.0, 1.0, 1.0, 3.0, 3.0], dtype=np.float64)

    contrast = compute_context_contrast(series, 2, 3, context_window=2)

    assert contrast == pytest.approx(0.5)


def test_periodicity_score_detects_repeating_segment():
    segment = np.asarray([0.0, 1.0, 0.0, -1.0, 0.0, 1.0, 0.0, -1.0], dtype=np.float64)

    score = compute_periodicity_score(segment)

    assert score > 0.7


def test_segment_statistics_fail_explicitly_on_invalid_interval():
    series = np.asarray([0.0, 1.0, 2.0], dtype=np.float64)

    with pytest.raises(SegmentStatisticsError, match="greater than end_index"):
        compute_segment_statistics(series, 2, 1, min_segment_length=2)


def test_segment_statistics_fail_on_too_short_segments():
    series = np.asarray([1.0], dtype=np.float64)

    with pytest.raises(SegmentStatisticsError, match="too short"):
        compute_slope(series)
