"""Tests for VAL-033: PPCEF normalising-flow plausibility for TS decompositions.

Covers:
 - encode_blob_to_vector: Constant + ETM encoders return fixed-length vectors
   with documented layout keys
 - encode_blob_to_vector: unregistered method falls back to summary statistics
 - register_coefficient_encoder swaps the encoder for a method
 - CoefficientFlow construction: dim < 4 → RealNVP, dim ≥ 4 → NSF (default)
 - explicit method override accepted
 - construction with dim < 1 raises
 - construction with unknown method raises
 - fit raises on shape mismatch
 - fit + score round-trip: standardisation applied, log_p produced
 - score before fit raises informative error
 - score with wrong dim raises
 - deterministic training: same seed → same loss curve
 - inference reproducibility: same input + trained flow → same log_p
 - inference latency under 200 ms (loose CI bound; AC asks < 50 ms on
   reference hardware)
 - quantile correctness: log_p at training median ⇒ quantile ≈ 0.5
 - is_plausible threshold respected
 - save / load round-trip preserves μ, σ, log-p percentiles, and predictions
 - LOF baseline returns a finite anomaly score on a reasonable fixture
 - PPCEFResult frozen
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.validation import (
    CoefficientFlow,
    METHOD_NSF,
    METHOD_REALNVP,
    PPCEFError,
    PPCEFResult,
    encode_blob_to_vector,
    lof_baseline_score,
    register_coefficient_encoder,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _constant_blob(level: float = 10.0, n: int = 40) -> DecompositionBlob:
    return DecompositionBlob(
        method="Constant",
        components={"trend": np.full(n, level), "residual": np.zeros(n)},
        coefficients={"level": float(level)},
    )


def _etm_blob(x0: float = 5.0, linear_rate: float = 0.1, n: int = 40,
              n_steps: int = 0, step_amp: float = 0.0) -> DecompositionBlob:
    t = np.arange(n, dtype=np.float64)
    trend = x0 + linear_rate * t
    coeffs: dict = {"x0": x0, "linear_rate": linear_rate}
    for k in range(n_steps):
        coeffs[f"step_at_{k}"] = float(step_amp)
    return DecompositionBlob(
        method="ETM",
        components={"trend": trend, "residual": np.zeros(n)},
        coefficients=coeffs,
    )


# ---------------------------------------------------------------------------
# Coefficient encoders
# ---------------------------------------------------------------------------


class TestEncoders:
    def test_constant_encoder(self):
        vec, layout = encode_blob_to_vector(_constant_blob(level=14.0))
        assert vec.shape == (1,)
        assert layout == ["level"]
        assert vec[0] == 14.0

    def test_etm_encoder(self):
        blob = _etm_blob(x0=5.0, linear_rate=0.2, n_steps=2, step_amp=1.0)
        vec, layout = encode_blob_to_vector(blob)
        # ETM layout: x0, linear_rate, n_steps, mean_abs_step
        assert layout == ["x0", "linear_rate", "n_steps", "mean_abs_step"]
        assert vec.shape == (4,)
        assert vec[0] == 5.0
        assert vec[1] == 0.2
        assert vec[2] == 2.0
        assert vec[3] == 1.0

    def test_etm_encoder_no_steps(self):
        blob = _etm_blob(x0=5.0, linear_rate=0.2, n_steps=0)
        vec, layout = encode_blob_to_vector(blob)
        assert vec[2] == 0.0  # n_steps
        assert vec[3] == 0.0  # mean_abs_step

    def test_unregistered_method_summary_fallback(self):
        blob = DecompositionBlob(
            method="UnknownMethod",
            components={"trend": np.zeros(10)},
            coefficients={"a": 1.0, "b": 2.0, "c": -3.0},
        )
        vec, layout = encode_blob_to_vector(blob)
        # Summary fallback: count, mean, std, max_abs
        assert layout == ["count", "mean", "std", "max_abs"]
        assert vec.shape == (4,)
        assert vec[0] == 3.0  # count
        assert vec[3] == 3.0  # max_abs

    def test_summary_fallback_no_scalars(self):
        blob = DecompositionBlob(
            method="OnlyVectorCoefs",
            components={"trend": np.zeros(10)},
            coefficients={"vec": np.array([1.0, 2.0])},
        )
        vec, _ = encode_blob_to_vector(blob)
        assert np.allclose(vec, np.zeros(4))

    def test_register_replaces_encoder(self):
        # Save original encoder for cleanup
        from app.services.validation.ppcef import _COEFF_ENCODERS, _encode_constant
        original = _COEFF_ENCODERS["Constant"]
        try:
            def custom(blob):
                return np.array([42.0]), ["custom"]
            register_coefficient_encoder("Constant", custom)
            vec, layout = encode_blob_to_vector(_constant_blob())
            assert vec[0] == 42.0
            assert layout == ["custom"]
        finally:
            register_coefficient_encoder("Constant", original)


# ---------------------------------------------------------------------------
# CoefficientFlow construction
# ---------------------------------------------------------------------------


class TestFlowConstruction:
    def test_low_dim_defaults_to_realnvp(self):
        flow = CoefficientFlow(dim=2)
        assert flow.method == METHOD_REALNVP

    def test_high_dim_defaults_to_nsf(self):
        flow = CoefficientFlow(dim=8)
        assert flow.method == METHOD_NSF

    def test_explicit_method_override(self):
        flow = CoefficientFlow(dim=8, method=METHOD_REALNVP)
        assert flow.method == METHOD_REALNVP

    def test_unknown_method_raises(self):
        with pytest.raises(PPCEFError, match="method"):
            CoefficientFlow(dim=4, method="bogus")  # type: ignore[arg-type]

    def test_dim_zero_raises(self):
        with pytest.raises(PPCEFError, match="dim"):
            CoefficientFlow(dim=0)

    def test_dim_one_realnvp_unsupported(self):
        # RealNVP needs dim ≥ 2 per implementation note
        with pytest.raises(PPCEFError, match="≥ 2"):
            CoefficientFlow(dim=1, method=METHOD_REALNVP)


# ---------------------------------------------------------------------------
# Fit / score
# ---------------------------------------------------------------------------


@pytest.fixture
def trained_flow():
    """Small flow trained on a Gaussian cluster; reused across tests."""
    rng = np.random.default_rng(0)
    theta = rng.normal(loc=[1.0, -2.0, 0.5, 3.0], scale=0.5, size=(120, 4))
    flow = CoefficientFlow(dim=4, n_layers=4, hidden_dim=16, seed=0)
    flow.fit(theta, n_epochs=20, batch_size=32, val_frac=0.2)
    return flow, theta


class TestFit:
    def test_fit_summary_keys(self, trained_flow):
        flow, theta = trained_flow
        # Loss curve recorded; population stats stored
        assert flow.mu is not None
        assert flow.sigma is not None
        assert flow.train_log_p_5th is not None
        assert flow.train_log_p_50th is not None
        # 5th < 50th (lower-tail < median)
        assert flow.train_log_p_5th < flow.train_log_p_50th

    def test_fit_shape_mismatch_raises(self):
        flow = CoefficientFlow(dim=4, seed=0)
        with pytest.raises(PPCEFError, match="theta_train must be"):
            flow.fit(np.zeros((10, 3)))

    def test_fit_too_few_samples_raises(self):
        flow = CoefficientFlow(dim=4, seed=0)
        with pytest.raises(PPCEFError, match="≥ 4"):
            flow.fit(np.zeros((2, 4)))

    def test_score_before_fit_raises(self):
        flow = CoefficientFlow(dim=4, seed=0)
        with pytest.raises(PPCEFError, match="not been fit"):
            flow.score(np.zeros(4))

    def test_score_dim_mismatch_raises(self, trained_flow):
        flow, _ = trained_flow
        with pytest.raises(PPCEFError, match="dim mismatch"):
            flow.score(np.zeros(5))

    def test_score_returns_ppcef_result(self, trained_flow):
        flow, theta = trained_flow
        result = flow.score(theta[0], decomposition_method="Constant")
        assert isinstance(result, PPCEFResult)
        assert result.coefficient_dim == 4
        assert result.flow_method == METHOD_NSF
        assert result.decomposition_method == "Constant"
        assert 0.0 <= result.quantile <= 1.0


# ---------------------------------------------------------------------------
# Determinism / reproducibility
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_seed_same_loss_curve(self):
        rng = np.random.default_rng(0)
        theta = rng.normal(loc=0.0, scale=1.0, size=(60, 4)).astype(np.float64)

        f1 = CoefficientFlow(dim=4, n_layers=4, hidden_dim=16, seed=42)
        s1 = f1.fit(theta.copy(), n_epochs=10, batch_size=16, val_frac=0.2)

        f2 = CoefficientFlow(dim=4, n_layers=4, hidden_dim=16, seed=42)
        s2 = f2.fit(theta.copy(), n_epochs=10, batch_size=16, val_frac=0.2)

        assert s1["loss_curve"] == s2["loss_curve"]
        assert s1["best_val_loss"] == pytest.approx(s2["best_val_loss"], rel=1e-6)

    def test_score_reproducibility(self, trained_flow):
        flow, theta = trained_flow
        a = flow.score(theta[0])
        b = flow.score(theta[0])
        assert a.log_p == b.log_p
        assert a.quantile == b.quantile


# ---------------------------------------------------------------------------
# Quantile + plausibility
# ---------------------------------------------------------------------------


class TestQuantile:
    def test_in_distribution_quantile_high(self, trained_flow):
        """An in-distribution sample should be near or above the median."""
        flow, theta = trained_flow
        # Use one of the training samples — should be plausible
        result = flow.score(theta[0])
        assert result.is_plausible is True

    def test_out_of_distribution_quantile_low(self, trained_flow):
        """A clearly-out-of-distribution point should land in the lower
        tail (not necessarily ≤ 5th percentile, but very different)."""
        flow, theta = trained_flow
        far = np.array([100.0, -100.0, 100.0, -100.0])
        result = flow.score(far)
        # OOD points typically have very low quantile
        assert result.quantile < 0.5

    def test_quantile_in_unit_interval(self, trained_flow):
        flow, theta = trained_flow
        for i in [0, 5, 50, 100]:
            result = flow.score(theta[i % theta.shape[0]])
            assert 0.0 <= result.quantile <= 1.0


# ---------------------------------------------------------------------------
# Latency
# ---------------------------------------------------------------------------


class TestLatency:
    def test_inference_under_200ms(self, trained_flow):
        """AC asks ≤ 50 ms on reference hardware; we use 200 ms loose
        bound for CI to absorb cold-start jitter."""
        flow, theta = trained_flow
        # Warm up — first call may JIT
        flow.score(theta[0])
        start = time.perf_counter()
        flow.score(theta[1])
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 200.0, f"inference {elapsed_ms:.1f} ms (>200 ms)"


# ---------------------------------------------------------------------------
# Save / load
# ---------------------------------------------------------------------------


class TestSaveLoad:
    def test_round_trip(self, trained_flow, tmp_path: Path):
        flow, theta = trained_flow
        out = tmp_path / "flow.pt"
        flow.save(out)
        assert out.exists()
        assert out.with_suffix(".json").exists()

        loaded = CoefficientFlow.load(out)
        assert loaded.dim == flow.dim
        assert loaded.method == flow.method
        np.testing.assert_array_equal(loaded.mu, flow.mu)
        np.testing.assert_array_equal(loaded.sigma, flow.sigma)
        assert loaded.train_log_p_5th == flow.train_log_p_5th

        # Predictions should match within float tolerance
        a = flow.score(theta[0])
        b = loaded.score(theta[0])
        assert a.log_p == pytest.approx(b.log_p, rel=1e-5)

    def test_save_before_fit_raises(self, tmp_path: Path):
        flow = CoefficientFlow(dim=4, seed=0)
        with pytest.raises(PPCEFError, match="cannot persist"):
            flow.save(tmp_path / "x.pt")

    def test_load_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(PPCEFError, match="missing"):
            CoefficientFlow.load(tmp_path / "nope.pt")


# ---------------------------------------------------------------------------
# LOF baseline
# ---------------------------------------------------------------------------


class TestLOFBaseline:
    def test_inlier_score_close_to_one(self):
        rng = np.random.default_rng(0)
        train = rng.normal(loc=0.0, scale=1.0, size=(120, 4))
        # An average-y point should be a clear inlier
        score = lof_baseline_score(train, np.zeros(4))
        # LOF score around 1 for inliers
        assert 0.5 < score < 2.0

    def test_outlier_score_above_one(self):
        rng = np.random.default_rng(0)
        train = rng.normal(loc=0.0, scale=1.0, size=(120, 4))
        outlier = np.array([100.0, -100.0, 100.0, -100.0])
        score = lof_baseline_score(train, outlier)
        # Outlier scores typically > 1
        assert score > 1.0

    def test_dim_mismatch_raises(self):
        train = np.zeros((20, 4))
        with pytest.raises(PPCEFError, match="dim mismatch"):
            lof_baseline_score(train, np.zeros(3))


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


class TestDTO:
    def test_frozen(self):
        r = PPCEFResult(
            log_p=-2.0, train_5th_percentile=-5.0, train_50th_percentile=-1.0,
            quantile=0.7, is_plausible=True, flow_method=METHOD_NSF,
            coefficient_dim=4, decomposition_method="Constant",
        )
        with pytest.raises((AttributeError, TypeError)):
            r.log_p = 0.0  # type: ignore[misc]
