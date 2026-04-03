"""Tests for the data-loading helpers in scripts/train_tcn_encoder.py (SEG-003).

Covers:
  - extract_training_segments returns valid feature matrices for univariate datasets
  - extract_training_segments skips multivariate datasets (n_channels != 1)
  - extract_training_segments skips segments shorter than min_length
  - build_support_feature_matrices returns one matrix per semantic class
  - build_support_feature_matrices returns consistent label ordering
  - resample_feat produces the correct output shape
  - assign_pseudo_labels returns one integer per input segment
  - assign_pseudo_labels returns values in [0, n_classes)
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pytest

# ------------------------------------------------------------------
# Path setup — train_tcn_encoder.py lives in scripts/, which is not
# a package, so we add the project root to sys.path first, then
# import the helpers directly.
# ------------------------------------------------------------------
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_PROJECT_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "backend"))
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

torch = pytest.importorskip("torch")

from train_tcn_encoder import (  # noqa: E402
    assign_pseudo_labels,
    build_support_feature_matrices,
    compute_prototypes,
    extract_training_segments,
    resample_feat,
)
from app.services.datasets import DatasetRegistry  # noqa: E402
from app.services.suggestion.segment_encoder import SegmentEncoderConfig  # noqa: E402
from app.services.suggestion.tcn_encoder import TcnEncoderConfig, _build_tcn_model  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def encoder_config() -> SegmentEncoderConfig:
    return SegmentEncoderConfig()


@pytest.fixture(scope="module")
def tcn_config() -> TcnEncoderConfig:
    return TcnEncoderConfig()


@pytest.fixture(scope="module")
def registry() -> DatasetRegistry:
    return DatasetRegistry()


@pytest.fixture(scope="module")
def support_data(encoder_config: SegmentEncoderConfig):
    return build_support_feature_matrices(encoder_config)


@pytest.fixture(scope="module")
def tcn_model(tcn_config: TcnEncoderConfig):
    model = _build_tcn_model(tcn_config)
    model.eval()
    return model


# ---------------------------------------------------------------------------
# build_support_feature_matrices
# ---------------------------------------------------------------------------


class TestBuildSupportFeatureMatrices:
    def test_returns_six_entries(self, support_data):
        x_feats, labels = support_data
        assert len(x_feats) == 6
        assert len(labels) == 6

    def test_label_names_are_expected_semantic_classes(self, support_data):
        _, labels = support_data
        expected = {"trend", "plateau", "spike", "event", "transition", "periodic"}
        assert set(labels) == expected

    def test_each_feature_matrix_has_five_channels(self, support_data):
        x_feats, _ = support_data
        for x_feat in x_feats:
            assert x_feat.shape[0] == 5, f"Expected 5 channels, got {x_feat.shape[0]}"

    def test_all_feature_matrices_are_finite(self, support_data):
        x_feats, _ = support_data
        for x_feat in x_feats:
            assert np.all(np.isfinite(x_feat)), "Feature matrix contains non-finite values"

    def test_label_order_is_stable(self, encoder_config):
        _, labels_a = build_support_feature_matrices(encoder_config)
        _, labels_b = build_support_feature_matrices(encoder_config)
        assert labels_a == labels_b


# ---------------------------------------------------------------------------
# extract_training_segments
# ---------------------------------------------------------------------------


class TestExtractTrainingSegments:
    def test_returns_list_of_arrays(self, registry, encoder_config):
        segments = extract_training_segments(registry, encoder_config)
        assert isinstance(segments, list)
        assert len(segments) > 0

    def test_all_segments_have_five_channels(self, registry, encoder_config):
        segments = extract_training_segments(registry, encoder_config)
        for s in segments:
            assert s.shape[0] == 5, f"Expected 5 channels, got {s.shape[0]}"

    def test_all_segments_meet_min_length(self, registry, encoder_config):
        min_len = 8
        segments = extract_training_segments(registry, encoder_config, min_length=min_len)
        for s in segments:
            assert s.shape[1] >= min_len, f"Segment length {s.shape[1]} < min {min_len}"

    def test_segments_are_finite(self, registry, encoder_config):
        segments = extract_training_segments(registry, encoder_config)
        for s in segments[:20]:  # spot-check first 20 for speed
            assert np.all(np.isfinite(s)), "Segment feature matrix has non-finite values"

    def test_skips_multivariate_datasets(self, encoder_config, monkeypatch):
        """If all datasets are multivariate (n_channels != 1), result is empty."""
        class _FakeSummary:
            n_channels = 6
            name = "FakeMulti"

        class _FakeRegistry:
            def list_datasets(self):
                return [_FakeSummary()]

        result = extract_training_segments(_FakeRegistry(), encoder_config)
        assert result == []

    def test_larger_min_length_reduces_segment_count(self, registry, encoder_config):
        small = extract_training_segments(registry, encoder_config, min_length=4)
        large = extract_training_segments(registry, encoder_config, min_length=32)
        assert len(large) <= len(small)


# ---------------------------------------------------------------------------
# resample_feat
# ---------------------------------------------------------------------------


class TestResampleFeat:
    def test_output_shape(self, tcn_config):
        x_feat = np.random.default_rng(0).standard_normal((5, 40)).astype(np.float32)
        tensor = resample_feat(x_feat, tcn_config.resample_length)
        assert tuple(tensor.shape) == (1, 5, tcn_config.resample_length)

    def test_output_is_float32(self, tcn_config):
        x_feat = np.ones((5, 20), dtype=np.float64)
        tensor = resample_feat(x_feat, tcn_config.resample_length)
        assert tensor.dtype == torch.float32

    def test_no_copy_needed_for_float32_input(self, tcn_config):
        """Should not raise even for very short inputs."""
        x_feat = np.ones((5, 2), dtype=np.float32)
        tensor = resample_feat(x_feat, tcn_config.resample_length)
        assert tensor.shape[-1] == tcn_config.resample_length


# ---------------------------------------------------------------------------
# assign_pseudo_labels
# ---------------------------------------------------------------------------


class TestAssignPseudoLabels:
    def test_returns_one_label_per_segment(self, tcn_model, support_data, tcn_config):
        x_feats, _ = support_data
        prototypes = compute_prototypes(tcn_model, x_feats, tcn_config.resample_length)
        query_feats = [np.random.default_rng(i).standard_normal((5, 20)).astype(np.float32) for i in range(10)]
        labels = assign_pseudo_labels(tcn_model, query_feats, prototypes, tcn_config.resample_length)
        assert len(labels) == 10

    def test_all_labels_in_valid_range(self, tcn_model, support_data, tcn_config):
        x_feats, _ = support_data
        n_classes = len(x_feats)
        prototypes = compute_prototypes(tcn_model, x_feats, tcn_config.resample_length)
        query_feats = [np.random.default_rng(i).standard_normal((5, 20)).astype(np.float32) for i in range(20)]
        labels = assign_pseudo_labels(tcn_model, query_feats, prototypes, tcn_config.resample_length)
        for label in labels:
            assert 0 <= label < n_classes

    def test_support_templates_label_themselves_as_own_class(self, tcn_model, support_data, tcn_config):
        """After freezing: each support template should map to its own index via
        prototype nearest-neighbour (trivially true since prototypes == template embeds)."""
        x_feats, _ = support_data
        prototypes = compute_prototypes(tcn_model, x_feats, tcn_config.resample_length)
        labels = assign_pseudo_labels(tcn_model, x_feats, prototypes, tcn_config.resample_length)
        assert labels == list(range(len(x_feats)))
