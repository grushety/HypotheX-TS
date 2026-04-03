"""Tests for TcnSegmentEncoder and load_tcn_encoder (SEG-002).

Covers:
  - Output shape is (embedding_dim,)
  - L2 norm of output is approximately 1.0
  - load_tcn_encoder returns None when no checkpoint exists (graceful fallback)
  - No gradient computation during inference (torch.no_grad context)
  - TcnEncoderConfig defaults and round-trip serialisation
  - encode() raises ValueError on wrong channel count

All tests skip automatically if torch is not installed.
"""

import math
import pathlib
import tempfile

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from app.services.suggestion.tcn_encoder import (  # noqa: E402
    TcnEncoderConfig,
    TcnSegmentEncoder,
    _build_tcn_model,
    load_tcn_encoder,
    save_tcn_encoder_checkpoint,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_encoder(config: TcnEncoderConfig | None = None) -> TcnSegmentEncoder:
    """Build a randomly-initialised TcnSegmentEncoder (no checkpoint needed)."""
    cfg = config or TcnEncoderConfig()
    model = _build_tcn_model(cfg)
    return TcnSegmentEncoder(model, cfg)


def _random_feat(config: TcnEncoderConfig) -> np.ndarray:
    rng = np.random.default_rng(0)
    return rng.standard_normal((config.in_channels, 40)).astype(np.float32)


# ---------------------------------------------------------------------------
# Output shape and L2 norm
# ---------------------------------------------------------------------------


class TestTcnEncoderOutputContract:
    def test_output_shape_is_embedding_dim(self):
        cfg = TcnEncoderConfig(embedding_dim=64)
        encoder = _make_encoder(cfg)
        x_feat = _random_feat(cfg)
        out = encoder.encode(x_feat)
        assert out.shape == (64,)

    def test_output_is_float64(self):
        cfg = TcnEncoderConfig()
        encoder = _make_encoder(cfg)
        out = encoder.encode(_random_feat(cfg))
        assert out.dtype == np.float64

    def test_l2_norm_approximately_one(self):
        cfg = TcnEncoderConfig()
        encoder = _make_encoder(cfg)
        out = encoder.encode(_random_feat(cfg))
        norm = float(np.linalg.norm(out))
        assert math.isclose(norm, 1.0, rel_tol=1e-5), f"Expected norm ≈ 1.0, got {norm}"

    def test_l2_norm_one_for_various_input_lengths(self):
        cfg = TcnEncoderConfig()
        encoder = _make_encoder(cfg)
        rng = np.random.default_rng(7)
        for T in [5, 16, 50, 200]:
            x = rng.standard_normal((cfg.in_channels, T)).astype(np.float32)
            norm = float(np.linalg.norm(encoder.encode(x)))
            assert math.isclose(norm, 1.0, rel_tol=1e-5), f"T={T}: norm={norm}"

    def test_wrong_channel_count_raises_value_error(self):
        cfg = TcnEncoderConfig(in_channels=5)
        encoder = _make_encoder(cfg)
        bad_input = np.zeros((3, 40), dtype=np.float32)  # 3 ≠ 5
        with pytest.raises(ValueError, match="input channels"):
            encoder.encode(bad_input)


# ---------------------------------------------------------------------------
# No gradient computation during inference
# ---------------------------------------------------------------------------


class TestNoGradientDuringInference:
    def test_model_parameters_require_no_grad(self):
        encoder = _make_encoder()
        for param in encoder._model.parameters():
            assert not param.requires_grad

    def test_model_is_in_eval_mode(self):
        encoder = _make_encoder()
        assert not encoder._model.training

    def test_encode_does_not_accumulate_gradients(self):
        """Running encode many times must not grow memory via gradient tape."""
        cfg = TcnEncoderConfig()
        encoder = _make_encoder(cfg)
        x_feat = _random_feat(cfg)
        for _ in range(10):
            encoder.encode(x_feat)
        # If gradients were accumulating the model's conv weights would have
        # non-None .grad tensors.  All should be None after inference-only use.
        for param in encoder._model.parameters():
            assert param.grad is None


# ---------------------------------------------------------------------------
# Graceful fallback — load_tcn_encoder returns None when no checkpoint
# ---------------------------------------------------------------------------


class TestLoadTcnEncoderFallback:
    def test_returns_none_when_checkpoint_absent(self, tmp_path, monkeypatch):
        import app.services.suggestion.tcn_encoder as mod

        # Point the module-level path to a file that doesn't exist.
        monkeypatch.setattr(mod, "_CHECKPOINT_PATH", tmp_path / "nonexistent.pt")
        # Clear the lru_cache so the patched path is used.
        mod.load_tcn_encoder.cache_clear()
        result = mod.load_tcn_encoder()
        assert result is None
        mod.load_tcn_encoder.cache_clear()  # clean up for other tests

    def test_returns_none_for_corrupt_checkpoint(self, tmp_path, monkeypatch):
        import app.services.suggestion.tcn_encoder as mod

        corrupt = tmp_path / "corrupt.pt"
        corrupt.write_bytes(b"this is not a valid torch checkpoint")
        monkeypatch.setattr(mod, "_CHECKPOINT_PATH", corrupt)
        mod.load_tcn_encoder.cache_clear()
        result = mod.load_tcn_encoder()
        assert result is None
        mod.load_tcn_encoder.cache_clear()


# ---------------------------------------------------------------------------
# Checkpoint round-trip
# ---------------------------------------------------------------------------


class TestCheckpointRoundTrip:
    def test_save_and_load_produce_identical_embeddings(self, tmp_path, monkeypatch):
        import app.services.suggestion.tcn_encoder as mod

        cfg = TcnEncoderConfig(embedding_dim=32, resample_length=16, in_channels=5)
        encoder = _make_encoder(cfg)
        x_feat = _random_feat(cfg)
        expected = encoder.encode(x_feat)

        dest = tmp_path / "encoder.pt"
        save_tcn_encoder_checkpoint(encoder, dest)

        monkeypatch.setattr(mod, "_CHECKPOINT_PATH", dest)
        mod.load_tcn_encoder.cache_clear()
        loaded = mod.load_tcn_encoder()
        assert loaded is not None
        actual = loaded.encode(x_feat)
        np.testing.assert_allclose(actual, expected, rtol=1e-5)
        mod.load_tcn_encoder.cache_clear()


# ---------------------------------------------------------------------------
# TcnEncoderConfig serialisation
# ---------------------------------------------------------------------------


class TestTcnEncoderConfigSerialisation:
    def test_default_values(self):
        cfg = TcnEncoderConfig()
        assert cfg.embedding_dim == 64
        assert cfg.resample_length == 32
        assert cfg.channels == (32, 64, 64)
        assert cfg.kernel_size == 3
        assert cfg.in_channels == 5

    def test_round_trip_to_dict(self):
        cfg = TcnEncoderConfig(embedding_dim=32, resample_length=16, in_channels=3)
        restored = TcnEncoderConfig.from_dict(cfg.to_dict())
        assert restored == cfg
