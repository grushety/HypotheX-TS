"""Tests for build_feature_matrix and the new SegmentEncoderConfig fields (SEG-001).

Covers:
  - Feature matrix shape for 1-D and multi-channel inputs
  - Missingness mask flag set correctly for NaN / inf values
  - Local z-score has near-zero mean on a clean (NaN-free) signal
  - include_missingness_mask=False omits the mask channel
  - smoothing_window and zscore_window are forwarded correctly
"""

import math

import numpy as np
import pytest

from app.services.suggestion.segment_encoder import (
    SegmentEncoderConfig,
    build_feature_matrix,
    encode_segment,
)


# ---------------------------------------------------------------------------
# Feature-matrix shape
# ---------------------------------------------------------------------------


class TestBuildFeatureMatrixShape:
    def test_single_channel_default_config_has_five_channels(self):
        # 1-D input, include_missingness_mask=True (default) → d' = 1*5 = 5
        values = list(range(20))
        matrix = build_feature_matrix(values)
        assert matrix.shape == (5, 20)

    def test_single_channel_no_mask_has_four_channels(self):
        values = list(range(20))
        config = SegmentEncoderConfig(include_missingness_mask=False)
        matrix = build_feature_matrix(values, config)
        assert matrix.shape == (4, 20)

    def test_multi_channel_default_config_scales_channels(self):
        # 2-channel input, 30 time steps → d' = 2*5 = 10
        rng = np.random.default_rng(0)
        values = rng.standard_normal((2, 30))
        matrix = build_feature_matrix(values)
        assert matrix.shape == (10, 30)

    def test_multi_channel_no_mask_has_four_groups(self):
        rng = np.random.default_rng(1)
        values = rng.standard_normal((3, 25))
        config = SegmentEncoderConfig(include_missingness_mask=False)
        matrix = build_feature_matrix(values, config)
        assert matrix.shape == (12, 25)  # 3 channels * 4 feature types

    def test_output_length_equals_input_length(self):
        for length in [5, 16, 100]:
            matrix = build_feature_matrix(list(range(length)))
            assert matrix.shape[1] == length


# ---------------------------------------------------------------------------
# Missingness mask
# ---------------------------------------------------------------------------


class TestMissingnessFlag:
    def test_nan_sets_mask_to_one(self):
        values = [1.0, 2.0, float("nan"), 4.0, 5.0]
        config = SegmentEncoderConfig()
        matrix = build_feature_matrix(values, config)
        # mask is the last channel group (index 4 for 1-channel input)
        mask_channel = matrix[4, :]
        assert mask_channel[2] == 1.0, "NaN position should be flagged"
        assert mask_channel[0] == 0.0
        assert mask_channel[1] == 0.0
        assert mask_channel[3] == 0.0
        assert mask_channel[4] == 0.0

    def test_inf_sets_mask_to_one(self):
        values = [0.0, float("inf"), 2.0, -float("inf"), 4.0]
        config = SegmentEncoderConfig()
        matrix = build_feature_matrix(values, config)
        mask_channel = matrix[4, :]
        assert mask_channel[1] == 1.0, "+inf should be flagged"
        assert mask_channel[3] == 1.0, "-inf should be flagged"
        assert mask_channel[0] == 0.0
        assert mask_channel[2] == 0.0
        assert mask_channel[4] == 0.0

    def test_clean_signal_mask_is_all_zeros(self):
        values = [float(i) for i in range(20)]
        matrix = build_feature_matrix(values)
        mask_channel = matrix[4, :]
        assert np.all(mask_channel == 0.0)

    def test_nan_raw_channel_replaced_with_zero(self):
        values = [1.0, float("nan"), 3.0]
        matrix = build_feature_matrix(values)
        raw_channel = matrix[0, :]
        # NaN at index 1 should have been replaced with 0.0
        assert raw_channel[1] == 0.0
        assert math.isfinite(raw_channel[1])

    def test_include_missingness_mask_false_omits_mask_channel(self):
        values = [1.0, float("nan"), 3.0, 4.0, 5.0]
        config_with = SegmentEncoderConfig(include_missingness_mask=True)
        config_without = SegmentEncoderConfig(include_missingness_mask=False)
        matrix_with = build_feature_matrix(values, config_with)
        matrix_without = build_feature_matrix(values, config_without)
        assert matrix_with.shape[0] == matrix_without.shape[0] + 1


# ---------------------------------------------------------------------------
# Local z-score — near-zero mean on clean signal
# ---------------------------------------------------------------------------


class TestLocalZscoreProperties:
    def test_zscore_channel_has_near_zero_mean_on_clean_signal(self):
        # For a clean signal the local z-score is normalised to zero-mean per
        # window; the time-average should be very small in magnitude.
        rng = np.random.default_rng(42)
        values = rng.standard_normal(50).tolist()
        config = SegmentEncoderConfig(zscore_window=10)
        matrix = build_feature_matrix(values, config)
        zscore_channel = matrix[3, :]  # 4th channel for 1-channel input
        assert abs(float(np.mean(zscore_channel))) < 0.5

    def test_zscore_channel_is_near_zero_for_constant_signal(self):
        # For a constant signal, local mean == value, local std == 0, so the
        # safe-std fallback kicks in and zscore = (x - x) / 1.0 ≈ 0 (up to
        # floating-point rounding in the cumsum variance computation).
        values = [3.7] * 20
        matrix = build_feature_matrix(values)
        zscore_channel = matrix[3, :]
        assert float(np.max(np.abs(zscore_channel))) < 1e-6

    def test_zscore_channel_is_finite_for_clean_signal(self):
        values = [math.sin(i * 0.3) for i in range(30)]
        matrix = build_feature_matrix(values)
        zscore_channel = matrix[3, :]
        assert np.all(np.isfinite(zscore_channel))


# ---------------------------------------------------------------------------
# New SegmentEncoderConfig fields
# ---------------------------------------------------------------------------


class TestSegmentEncoderConfigNewFields:
    def test_default_smoothing_window(self):
        config = SegmentEncoderConfig()
        assert config.smoothing_window == 5

    def test_default_zscore_window(self):
        config = SegmentEncoderConfig()
        assert config.zscore_window == 10

    def test_default_include_missingness_mask(self):
        config = SegmentEncoderConfig()
        assert config.include_missingness_mask is True

    def test_new_fields_do_not_break_existing_fields(self):
        config = SegmentEncoderConfig(resample_length=8, include_differences=False)
        assert config.resample_length == 8
        assert config.include_differences is False
        assert config.smoothing_window == 5


# ---------------------------------------------------------------------------
# encode_segment still calls build_feature_matrix (NaN handling)
# ---------------------------------------------------------------------------


class TestEncodeSegmentUsesFeatureMatrix:
    def test_encode_segment_handles_nan_via_feature_matrix(self):
        # A signal with one NaN should not raise; the feature matrix replaces
        # NaN with 0 in the raw channel before the embedding pipeline runs.
        values = [0.0, 1.0, float("nan"), 3.0, 4.0, 5.0, 6.0, 7.0]
        config = SegmentEncoderConfig(resample_length=4)
        embedding = encode_segment(values, config)
        assert len(embedding.values) > 0
        assert all(math.isfinite(v) for v in embedding.values)
        assert math.isclose(
            sum(v * v for v in embedding.values), 1.0, rel_tol=1e-6
        )

    def test_encode_segment_embedding_size_unchanged_by_new_config_defaults(self):
        # Adding new fields with defaults must not change the embedding size.
        values = [float(i) / 10 for i in range(20)]
        old_style = SegmentEncoderConfig(resample_length=8)
        embedding = encode_segment(values, old_style)
        # Size = resample_length + resample_length + 4 = 8 + 8 + 4 = 20
        assert len(embedding.values) == 20
