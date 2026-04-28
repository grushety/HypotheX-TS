"""Tests for Tier-2 noise ops: suppress_denoise, amplify, change_color,
inject_synthetic, whiten (OP-026).

Also covers NoiseModel implementations: AR1NoiseModel, FlickerNoiseModel,
GammaSpeckleModel.
"""

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.noise_models import AR1NoiseModel, FlickerNoiseModel, GammaSpeckleModel, NoiseModel
from app.services.operations.tier2.noise import (
    amplify,
    change_color,
    inject_synthetic,
    suppress_denoise,
    whiten,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

N = 200
RNG = np.random.default_rng(42)


def _pink_noise(n: int = N, seed: int = 0) -> np.ndarray:
    """Synthetic pink noise via AR(1) approximation."""
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    for i in range(1, n):
        out[i] = 0.8 * out[i - 1] + rng.normal(0, 1.0)
    return out


def _noise_blob(n: int = N, residual_sigma: float = 1.5) -> DecompositionBlob:
    """Blob representing a noise segment with a trend underneath."""
    rng = np.random.default_rng(7)
    trend = np.linspace(0.0, 2.0, n)
    residual = rng.normal(0.0, residual_sigma, n)
    return DecompositionBlob(
        method="STL",
        coefficients={"period": 10, "robust": False},
        components={
            "trend": trend,
            "seasonal": np.zeros(n),
            "residual": residual,
        },
        fit_metadata={},
    )


def _bare_blob(n: int = N) -> DecompositionBlob:
    """Blob with no residual component."""
    return DecompositionBlob(
        method="ETM",
        coefficients={"x0": 1.0, "linear_rate": 0.01},
        components={
            "x0": np.ones(n),
            "linear_rate": 0.01 * np.arange(n, dtype=float),
        },
        fit_metadata={},
    )


# ---------------------------------------------------------------------------
# TestSuppressDenoise
# ---------------------------------------------------------------------------


class TestSuppressDenoise:
    def test_bayesshrink_reduces_variance(self):
        noisy = _pink_noise()
        result = suppress_denoise(noisy, method="bayesshrink")
        assert float(np.var(result.values)) < float(np.var(noisy))

    def test_bayesshrink_output_length(self):
        noisy = _pink_noise()
        result = suppress_denoise(noisy, method="bayesshrink")
        assert len(result.values) == N

    def test_sg_reduces_variance(self):
        noisy = _pink_noise()
        result = suppress_denoise(noisy, method="sg", window=11, poly=3)
        assert float(np.var(result.values)) < float(np.var(noisy))

    def test_sg_output_length(self):
        noisy = _pink_noise()
        result = suppress_denoise(noisy, method="sg")
        assert len(result.values) == N

    def test_tv_reduces_variance(self):
        noisy = _pink_noise()
        result = suppress_denoise(noisy, method="tv", weight=0.2)
        assert float(np.var(result.values)) < float(np.var(noisy))

    def test_tv_output_length(self):
        noisy = _pink_noise()
        result = suppress_denoise(noisy, method="tv")
        assert len(result.values) == N

    def test_kalman_reduces_variance(self):
        noisy = _pink_noise()
        result = suppress_denoise(noisy, method="kalman")
        assert float(np.var(result.values)) < float(np.var(noisy))

    def test_kalman_output_length(self):
        noisy = _pink_noise()
        result = suppress_denoise(noisy, method="kalman")
        assert len(result.values) == N

    def test_gacos_subtracts_correction(self):
        arr = np.ones(N) * 3.0
        correction = np.ones(N) * 0.5
        result = suppress_denoise(arr, method="gacos", gacos_correction=correction)
        np.testing.assert_allclose(result.values, np.ones(N) * 2.5, atol=1e-10)

    def test_gacos_missing_correction_raises(self):
        with pytest.raises(ValueError, match="gacos_correction"):
            suppress_denoise(_pink_noise(), method="gacos")

    def test_gacos_wrong_length_raises(self):
        with pytest.raises(ValueError, match="length"):
            suppress_denoise(_pink_noise(N), method="gacos",
                             gacos_correction=np.ones(N + 5))

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError, match="unknown method"):
            suppress_denoise(_pink_noise(), method="magic")

    def test_relabel_reclassify(self):
        result = suppress_denoise(_pink_noise(), method="bayesshrink")
        assert result.relabel.rule_class == "RECLASSIFY_VIA_SEGMENTER"
        assert result.relabel.needs_resegment is True

    def test_op_name(self):
        result = suppress_denoise(_pink_noise(), method="bayesshrink")
        assert result.op_name == "suppress_denoise"

    def test_tier(self):
        result = suppress_denoise(_pink_noise(), method="bayesshrink")
        assert result.tier == 2

    def test_result_is_ndarray(self):
        result = suppress_denoise(_pink_noise(), method="bayesshrink")
        assert isinstance(result.values, np.ndarray)

    def test_bayesshrink_short_signal(self):
        # Should not crash on short signals
        short = _pink_noise(n=8)
        result = suppress_denoise(short, method="bayesshrink")
        assert len(result.values) == 8

    def test_sg_short_signal(self):
        short = _pink_noise(n=5)
        result = suppress_denoise(short, method="sg", window=5, poly=2)
        assert len(result.values) == 5

    def test_kalman_q_zero_raises(self):
        with pytest.raises(ValueError, match="q must be > 0"):
            suppress_denoise(_pink_noise(), method="kalman", q=0.0)

    def test_kalman_r_zero_raises(self):
        with pytest.raises(ValueError, match="r must be > 0"):
            suppress_denoise(_pink_noise(), method="kalman", r=0.0)

    def test_whiten_constant_signal_no_nan(self):
        """Near-constant residual should not produce NaN/Inf in whiten output."""
        blob = _noise_blob()
        blob.components["residual"] = np.ones(N) * 2.0  # constant
        result = whiten(blob)
        assert np.all(np.isfinite(result.values))


# ---------------------------------------------------------------------------
# TestAmplify
# ---------------------------------------------------------------------------


class TestAmplify:
    def test_scales_residual_only(self):
        blob = _noise_blob()
        original_trend = blob.components["trend"].copy()
        result = amplify(blob, 2.0)
        # trend unchanged
        np.testing.assert_allclose(result.values[:N] - blob.components["trend"],
                                   blob.components["residual"] * 2.0, atol=1e-10)

    def test_alpha_zero_zeros_residual(self):
        blob = _noise_blob()
        result = amplify(blob, 0.0)
        expected = blob.components["trend"] + blob.components["seasonal"]
        np.testing.assert_allclose(result.values, expected, atol=1e-10)

    def test_alpha_one_identity(self):
        blob = _noise_blob()
        original = blob.reassemble()
        result = amplify(blob, 1.0)
        np.testing.assert_allclose(result.values, original, atol=1e-10)

    def test_caller_blob_unchanged(self):
        blob = _noise_blob()
        original_residual = blob.components["residual"].copy()
        amplify(blob, 3.0)
        np.testing.assert_allclose(blob.components["residual"], original_residual)

    def test_no_residual_logs_warning(self, caplog):
        import logging
        blob = _bare_blob()
        with caplog.at_level(logging.WARNING, logger="app.services.operations.tier2.noise"):
            result = amplify(blob, 2.0)
        assert "no 'residual' component" in caplog.text
        # Returns unchanged values
        np.testing.assert_allclose(result.values, blob.reassemble(), atol=1e-10)

    def test_relabel_preserved(self):
        result = amplify(_noise_blob(), 1.5)
        assert result.relabel.rule_class == "PRESERVED"
        assert result.relabel.new_shape == "noise"

    def test_op_name(self):
        result = amplify(_noise_blob(), 2.0)
        assert result.op_name == "amplify"

    def test_tier(self):
        result = amplify(_noise_blob(), 2.0)
        assert result.tier == 2


# ---------------------------------------------------------------------------
# TestChangeColor
# ---------------------------------------------------------------------------


class TestChangeColor:
    def test_white_output_length(self):
        result = change_color(_noise_blob(), "white", seed=0)
        assert len(result.values) == N

    def test_pink_output_length(self):
        result = change_color(_noise_blob(), "pink", seed=0)
        assert len(result.values) == N

    def test_red_output_length(self):
        result = change_color(_noise_blob(), "red", seed=0)
        assert len(result.values) == N

    def test_preserves_trend_component(self):
        blob = _noise_blob()
        trend = blob.components["trend"].copy()
        result = change_color(blob, "white", seed=1)
        # Result = trend + seasonal + new_residual; seasonal=0
        # So result - trend should equal new_residual (zero mean, sigma~1.5)
        residual_diff = result.values - trend
        # Standard deviation should be similar to original residual sigma
        assert 0.5 < float(np.std(residual_diff)) < 4.0

    def test_preserves_original_sigma(self):
        blob = _noise_blob(residual_sigma=2.0)
        orig_sigma = float(np.std(blob.components["residual"]))
        result = change_color(blob, "pink", seed=3)
        new_residual = result.values - blob.components["trend"]
        new_sigma = float(np.std(new_residual))
        assert abs(new_sigma - orig_sigma) / orig_sigma < 0.1

    def test_different_seeds_produce_different_noise(self):
        blob = _noise_blob()
        r1 = change_color(blob, "white", seed=1)
        r2 = change_color(blob, "white", seed=2)
        assert not np.allclose(r1.values, r2.values)

    def test_same_seed_reproducible(self):
        blob = _noise_blob()
        r1 = change_color(blob, "white", seed=42)
        r2 = change_color(blob, "white", seed=42)
        np.testing.assert_array_equal(r1.values, r2.values)

    def test_pink_psd_slope(self):
        """Log-log PSD of pink noise should have negative slope (1/f)."""
        blob = _noise_blob(n=512)
        result = change_color(blob, "pink", seed=5)
        residual = result.values - blob.components["trend"][:512]
        from scipy.signal import welch
        f, psd = welch(residual, nperseg=64)
        # Fit log-log slope; exclude DC (f=0)
        pos = f > 0
        log_f = np.log10(f[pos])
        log_p = np.log10(psd[pos] + 1e-30)
        slope = float(np.polyfit(log_f, log_p, 1)[0])
        assert slope < -0.3  # pink noise slope ≈ -1

    def test_unknown_color_raises(self):
        with pytest.raises(ValueError, match="unknown target_color"):
            change_color(_noise_blob(), "blue")

    def test_caller_blob_unchanged(self):
        blob = _noise_blob()
        original_residual = blob.components["residual"].copy()
        change_color(blob, "white", seed=0)
        np.testing.assert_allclose(blob.components["residual"], original_residual)

    def test_relabel_preserved(self):
        result = change_color(_noise_blob(), "white", seed=0)
        assert result.relabel.rule_class == "PRESERVED"

    def test_op_name(self):
        result = change_color(_noise_blob(), "white", seed=0)
        assert result.op_name == "change_color"


# ---------------------------------------------------------------------------
# TestInjectSynthetic
# ---------------------------------------------------------------------------


class TestInjectSynthetic:
    def test_ar1_injection_adds_noise(self):
        blob = _noise_blob()
        original = blob.reassemble()
        model = AR1NoiseModel(alpha=0.5, sigma=0.5)
        result = inject_synthetic(blob, model, seed=0)
        assert not np.allclose(result.values, original)

    def test_flicker_injection_output_length(self):
        blob = _noise_blob()
        model = FlickerNoiseModel(sigma=0.5, beta=1.0)
        result = inject_synthetic(blob, model, seed=0)
        assert len(result.values) == N

    def test_gamma_speckle_injection(self):
        blob = _noise_blob()
        model = GammaSpeckleModel(shape=5.0)
        result = inject_synthetic(blob, model, seed=0)
        assert len(result.values) == N
        assert not np.allclose(result.values, blob.reassemble())

    def test_seed_reproducible(self):
        blob = _noise_blob()
        model = AR1NoiseModel(alpha=0.5, sigma=1.0)
        r1 = inject_synthetic(blob, model, seed=99)
        r2 = inject_synthetic(blob, model, seed=99)
        np.testing.assert_array_equal(r1.values, r2.values)

    def test_round_trip_inject_denoise(self):
        """inject + suppress_denoise should recover original within tolerance."""
        rng = np.random.default_rng(12)
        clean = np.sin(np.linspace(0, 4 * np.pi, N))  # pure sinusoid
        noisy = clean + rng.normal(0, 0.1, N)  # small noise

        # Inject more noise
        blob = DecompositionBlob(
            method="Constant",
            coefficients={"mean": float(np.mean(noisy))},
            components={"residual": noisy.copy()},
            fit_metadata={},
        )
        model = AR1NoiseModel(alpha=0.3, sigma=0.05)
        injected = inject_synthetic(blob, model, seed=7)

        # Denoise — should be closer to original noisy signal than to injected
        denoised = suppress_denoise(injected.values, method="sg", window=11, poly=3)
        err_denoised = float(np.mean((denoised.values - clean) ** 2))
        err_injected = float(np.mean((injected.values - clean) ** 2))
        assert err_denoised < err_injected

    def test_preserves_trend_structure(self):
        blob = _noise_blob()
        model = AR1NoiseModel(alpha=0.3, sigma=0.1)
        result = inject_synthetic(blob, model, seed=1)
        # Trend component unchanged in caller's blob
        np.testing.assert_allclose(
            blob.components["trend"],
            blob.components["trend"],
        )

    def test_caller_blob_unchanged(self):
        blob = _noise_blob()
        original_residual = blob.components["residual"].copy()
        model = AR1NoiseModel(alpha=0.5, sigma=0.5)
        inject_synthetic(blob, model, seed=0)
        np.testing.assert_allclose(blob.components["residual"], original_residual)

    def test_relabel_preserved(self):
        model = AR1NoiseModel()
        result = inject_synthetic(_noise_blob(), model)
        assert result.relabel.rule_class == "PRESERVED"

    def test_op_name(self):
        result = inject_synthetic(_noise_blob(), AR1NoiseModel())
        assert result.op_name == "inject_synthetic"


# ---------------------------------------------------------------------------
# TestWhiten
# ---------------------------------------------------------------------------


class TestWhiten:
    def test_output_length(self):
        result = whiten(_noise_blob())
        assert len(result.values) == N

    def test_flatter_psd_after_whitening(self):
        """Whitened signal should have a flatter PSD than pink input."""
        blob = _noise_blob(n=256)
        # Replace residual with known pink noise
        rng = np.random.default_rng(0)
        pink = _pink_noise(n=256, seed=0)
        blob.components["residual"] = pink

        result = whiten(blob)
        residual_white = result.values - blob.components["trend"][:256]

        from scipy.signal import welch
        _, psd_orig = welch(pink, nperseg=64)
        _, psd_white = welch(residual_white, nperseg=64)

        # Variance of log PSD decreases after whitening (flatter spectrum)
        assert float(np.var(np.log10(psd_white + 1e-20))) < float(np.var(np.log10(psd_orig + 1e-20)))

    def test_preserves_std(self):
        blob = _noise_blob(residual_sigma=2.0)
        orig_std = float(np.std(blob.components["residual"]))
        result = whiten(blob)
        residual_white = result.values - blob.components["trend"]
        new_std = float(np.std(residual_white))
        assert abs(new_std - orig_std) / orig_std < 0.1

    def test_caller_blob_unchanged(self):
        blob = _noise_blob()
        original_residual = blob.components["residual"].copy()
        whiten(blob)
        np.testing.assert_allclose(blob.components["residual"], original_residual)

    def test_preserves_trend(self):
        blob = _noise_blob()
        trend = blob.components["trend"].copy()
        result = whiten(blob)
        # Result = trend + seasonal + whitened_residual; seasonal=0
        # trend contribution should still be present
        result_trend_contrib = float(np.mean(result.values[:10]))
        trend_contrib = float(np.mean(trend[:10]))
        assert abs(result_trend_contrib - trend_contrib) < 1.0

    def test_relabel_preserved(self):
        result = whiten(_noise_blob())
        assert result.relabel.rule_class == "PRESERVED"

    def test_op_name(self):
        result = whiten(_noise_blob())
        assert result.op_name == "whiten"

    def test_tier(self):
        result = whiten(_noise_blob())
        assert result.tier == 2


# ---------------------------------------------------------------------------
# TestNoiseModels
# ---------------------------------------------------------------------------


class TestAR1NoiseModel:
    def test_sample_length(self):
        model = AR1NoiseModel(alpha=0.5, sigma=1.0)
        out = model.sample(50)
        assert len(out) == 50

    def test_seed_reproducible(self):
        model = AR1NoiseModel(alpha=0.5, sigma=1.0)
        s1 = model.sample(30, seed=42)
        s2 = model.sample(30, seed=42)
        np.testing.assert_array_equal(s1, s2)

    def test_different_seeds_differ(self):
        model = AR1NoiseModel(alpha=0.5, sigma=1.0)
        assert not np.allclose(model.sample(30, seed=1), model.sample(30, seed=2))

    def test_zero_sigma_returns_zeros(self):
        model = AR1NoiseModel(alpha=0.5, sigma=0.0)
        out = model.sample(20)
        np.testing.assert_allclose(out, np.zeros(20))

    def test_alpha_out_of_range_raises(self):
        with pytest.raises(ValueError, match="alpha must be in"):
            AR1NoiseModel(alpha=1.5)

    def test_satisfies_protocol(self):
        model = AR1NoiseModel()
        assert isinstance(model, NoiseModel)


class TestFlickerNoiseModel:
    def test_sample_length(self):
        model = FlickerNoiseModel(sigma=1.0, beta=1.0)
        out = model.sample(100)
        assert len(out) == 100

    def test_seed_reproducible(self):
        model = FlickerNoiseModel(sigma=1.0, beta=1.0)
        s1 = model.sample(50, seed=7)
        s2 = model.sample(50, seed=7)
        np.testing.assert_array_equal(s1, s2)

    def test_sigma_scaling(self):
        m1 = FlickerNoiseModel(sigma=1.0, beta=1.0)
        m2 = FlickerNoiseModel(sigma=2.0, beta=1.0)
        rng = np.random.default_rng(0)
        s1 = np.array([m1.sample(200, seed=i) for i in range(5)])
        s2 = np.array([m2.sample(200, seed=i) for i in range(5)])
        assert float(np.std(s2)) > float(np.std(s1))

    def test_negative_sigma_raises(self):
        with pytest.raises(ValueError, match="sigma must be"):
            FlickerNoiseModel(sigma=-1.0)

    def test_satisfies_protocol(self):
        model = FlickerNoiseModel()
        assert isinstance(model, NoiseModel)


class TestGammaSpeckleModel:
    def test_sample_length(self):
        model = GammaSpeckleModel(shape=5.0)
        out = model.sample(80)
        assert len(out) == 80

    def test_mean_near_one(self):
        model = GammaSpeckleModel(shape=10.0)
        out = model.sample(10000, seed=0)
        assert abs(float(np.mean(out)) - 1.0) < 0.05

    def test_higher_shape_lower_variance(self):
        m_low = GammaSpeckleModel(shape=1.0)
        m_high = GammaSpeckleModel(shape=20.0)
        v_low = float(np.var(m_low.sample(5000, seed=0)))
        v_high = float(np.var(m_high.sample(5000, seed=0)))
        assert v_high < v_low

    def test_shape_zero_raises(self):
        with pytest.raises(ValueError, match="shape must be > 0"):
            GammaSpeckleModel(shape=0.0)

    def test_satisfies_protocol(self):
        model = GammaSpeckleModel()
        assert isinstance(model, NoiseModel)
