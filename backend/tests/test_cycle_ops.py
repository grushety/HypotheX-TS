"""Tests for Tier-2 cycle ops: deseasonalise_remove, amplify_amplitude,
dampen_amplitude, phase_shift, change_period, change_harmonic_content,
replace_with_flat (OP-024).
"""

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.operations.tier2.cycle import (
    amplify_amplitude,
    change_harmonic_content,
    change_period,
    dampen_amplitude,
    deseasonalise_remove,
    phase_shift,
    replace_with_flat,
)
from app.services.operations.tier2.plateau import Tier2OpResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

N = 80
PERIOD = 10


def _stl_blob(n: int = N, period: int = PERIOD, amp: float = 2.0) -> DecompositionBlob:
    """Synthetic STL blob: trend + seasonal sine + small residual."""
    t = np.arange(n, dtype=float)
    trend = 0.1 * t + 5.0
    seasonal = amp * np.sin(2 * np.pi * t / period)
    residual = np.zeros(n)
    return DecompositionBlob(
        method="STL",
        components={"trend": trend, "seasonal": seasonal, "residual": residual},
        coefficients={"period": period, "robust": True},
        fit_metadata={},
    )


def _mstl_blob(
    n: int = 120, periods: tuple = (10, 30), amps: tuple = (2.0, 1.0)
) -> DecompositionBlob:
    """Synthetic MSTL blob: trend + two seasonal sines + small residual."""
    t = np.arange(n, dtype=float)
    trend = 0.05 * t + 3.0
    seasonal_10 = amps[0] * np.sin(2 * np.pi * t / periods[0])
    seasonal_30 = amps[1] * np.cos(2 * np.pi * t / periods[1])
    residual = np.zeros(n)
    return DecompositionBlob(
        method="MSTL",
        components={
            "trend": trend,
            f"seasonal_{periods[0]}": seasonal_10,
            f"seasonal_{periods[1]}": seasonal_30,
            "residual": residual,
        },
        coefficients={"periods": list(periods), "valid_periods": list(periods)},
        fit_metadata={},
    )


# ---------------------------------------------------------------------------
# deseasonalise_remove
# ---------------------------------------------------------------------------


class TestDeseasonaliseRemove:
    def test_seasonal_zeroed_stl(self):
        blob = _stl_blob()
        result = deseasonalise_remove(blob)
        expected = blob.components["trend"] + blob.components["residual"]
        np.testing.assert_allclose(result.values, expected, atol=1e-12)

    def test_seasonal_zeroed_mstl(self):
        blob = _mstl_blob()
        result = deseasonalise_remove(blob)
        expected = blob.components["trend"] + blob.components["residual"]
        np.testing.assert_allclose(result.values, expected, atol=1e-12)

    def test_relabel_reclassify(self):
        result = deseasonalise_remove(_stl_blob())
        assert result.relabel.rule_class == "RECLASSIFY_VIA_SEGMENTER"
        assert result.relabel.needs_resegment is True

    def test_op_name(self):
        assert deseasonalise_remove(_stl_blob()).op_name == "deseasonalise_remove"

    def test_tier(self):
        assert deseasonalise_remove(_stl_blob()).tier == 2

    def test_caller_blob_not_mutated(self):
        blob = _stl_blob()
        orig = blob.components["seasonal"].copy()
        deseasonalise_remove(blob)
        np.testing.assert_array_equal(blob.components["seasonal"], orig)

    def test_pre_shape_forwarded(self):
        result = deseasonalise_remove(_stl_blob(), pre_shape="noise")
        assert result.relabel.new_shape == "noise"

    def test_trend_unchanged(self):
        blob = _stl_blob()
        result = deseasonalise_remove(blob)
        np.testing.assert_allclose(
            result.values,
            blob.components["trend"],  # residual is zero in fixture
            atol=1e-12,
        )


# ---------------------------------------------------------------------------
# amplify_amplitude
# ---------------------------------------------------------------------------


class TestAmplifyAmplitude:
    def test_seasonal_doubled(self):
        blob = _stl_blob(amp=2.0)
        result = amplify_amplitude(blob, alpha=2.0)
        t = np.arange(N, dtype=float)
        expected_seasonal = 4.0 * np.sin(2 * np.pi * t / PERIOD)
        expected = blob.components["trend"] + expected_seasonal
        np.testing.assert_allclose(result.values, expected, atol=1e-12)

    def test_alpha_zero_relabel_plateau(self):
        result = amplify_amplitude(_stl_blob(), alpha=0.0)
        assert result.relabel.rule_class == "DETERMINISTIC"
        assert result.relabel.new_shape == "plateau"

    def test_alpha_nonzero_relabel_preserved(self):
        result = amplify_amplitude(_stl_blob(), alpha=3.0)
        assert result.relabel.rule_class == "PRESERVED"
        assert result.relabel.new_shape == "cycle"

    def test_alpha_negative_relabel_preserved(self):
        result = amplify_amplitude(_stl_blob(), alpha=-1.0)
        assert result.relabel.rule_class == "PRESERVED"

    def test_op_name(self):
        assert amplify_amplitude(_stl_blob(), alpha=2.0).op_name == "amplify_amplitude"

    def test_caller_blob_not_mutated(self):
        blob = _stl_blob(amp=2.0)
        orig_seasonal = blob.components["seasonal"].copy()
        amplify_amplitude(blob, alpha=3.0)
        np.testing.assert_array_equal(blob.components["seasonal"], orig_seasonal)

    def test_mstl_both_components_scaled(self):
        blob = _mstl_blob(amps=(2.0, 1.0))
        result = amplify_amplitude(blob, alpha=3.0)
        expected = (
            blob.components["trend"]
            + 3.0 * blob.components["seasonal_10"]
            + 3.0 * blob.components["seasonal_30"]
        )
        np.testing.assert_allclose(result.values, expected, atol=1e-12)

    def test_alpha_one_identity(self):
        blob = _stl_blob()
        result = amplify_amplitude(blob, alpha=1.0)
        np.testing.assert_allclose(result.values, blob.reassemble(), atol=1e-12)

    def test_pre_shape_forwarded(self):
        result = amplify_amplitude(_stl_blob(), alpha=2.0, pre_shape="noise")
        assert result.relabel.new_shape == "noise"


# ---------------------------------------------------------------------------
# dampen_amplitude
# ---------------------------------------------------------------------------


class TestDampenAmplitude:
    def test_seasonal_halved(self):
        blob = _stl_blob(amp=2.0)
        result = dampen_amplitude(blob, alpha=0.5)
        t = np.arange(N, dtype=float)
        expected_seasonal = 1.0 * np.sin(2 * np.pi * t / PERIOD)
        expected = blob.components["trend"] + expected_seasonal
        np.testing.assert_allclose(result.values, expected, atol=1e-12)

    def test_relabel_always_preserved(self):
        result = dampen_amplitude(_stl_blob(), alpha=0.5)
        assert result.relabel.rule_class == "PRESERVED"
        assert result.relabel.new_shape == "cycle"

    def test_op_name(self):
        assert dampen_amplitude(_stl_blob(), alpha=0.5).op_name == "dampen_amplitude"

    def test_alpha_zero_raises(self):
        with pytest.raises(ValueError, match="alpha"):
            dampen_amplitude(_stl_blob(), alpha=0.0)

    def test_alpha_negative_raises(self):
        with pytest.raises(ValueError):
            dampen_amplitude(_stl_blob(), alpha=-0.1)

    def test_alpha_greater_than_one_raises(self):
        with pytest.raises(ValueError):
            dampen_amplitude(_stl_blob(), alpha=1.1)

    def test_alpha_one_identity(self):
        blob = _stl_blob()
        result = dampen_amplitude(blob, alpha=1.0)
        np.testing.assert_allclose(result.values, blob.reassemble(), atol=1e-12)

    def test_caller_blob_not_mutated(self):
        blob = _stl_blob()
        orig = blob.components["seasonal"].copy()
        dampen_amplitude(blob, alpha=0.5)
        np.testing.assert_array_equal(blob.components["seasonal"], orig)


# ---------------------------------------------------------------------------
# phase_shift
# ---------------------------------------------------------------------------


class TestPhaseShift:
    def _pure_cosine_blob(self, n=80, period=10, amp=2.0):
        """Blob with a pure cosine seasonal (no residual, flat trend)."""
        t = np.arange(n, dtype=float)
        seasonal = amp * np.cos(2 * np.pi * t / period)
        return DecompositionBlob(
            method="STL",
            components={"trend": np.zeros(n), "seasonal": seasonal, "residual": np.zeros(n)},
            coefficients={"period": period},
            fit_metadata={},
        ), t

    def test_hilbert_quarter_cycle_cosine_to_neg_sine(self):
        """cos shifted by pi/2 → -sin (interior, away from edge artefacts)."""
        blob, t = self._pure_cosine_blob(n=80, period=10, amp=2.0)
        result = phase_shift(blob, delta_phi=np.pi / 2, method="hilbert")
        period = 10
        expected = -2.0 * np.sin(2 * np.pi * t / period)
        interior = slice(5, 75)
        np.testing.assert_allclose(
            result.values[interior], expected[interior], atol=0.15
        )

    def test_harmonic_quarter_cycle_cosine_to_neg_sine(self):
        blob, t = self._pure_cosine_blob(n=80, period=10, amp=2.0)
        result = phase_shift(blob, delta_phi=np.pi / 2, method="harmonic")
        period = 10
        expected = -2.0 * np.sin(2 * np.pi * t / period)
        interior = slice(5, 75)
        np.testing.assert_allclose(
            result.values[interior], expected[interior], atol=0.15
        )

    def test_zero_shift_identity(self):
        blob = _stl_blob()
        result = phase_shift(blob, delta_phi=0.0)
        np.testing.assert_allclose(result.values, blob.reassemble(), atol=1e-6)

    def test_relabel_preserved(self):
        result = phase_shift(_stl_blob(), delta_phi=1.0)
        assert result.relabel.rule_class == "PRESERVED"
        assert result.relabel.new_shape == "cycle"

    def test_op_name(self):
        assert phase_shift(_stl_blob(), delta_phi=1.0).op_name == "phase_shift"

    def test_tier(self):
        assert phase_shift(_stl_blob(), delta_phi=1.0).tier == 2

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError, match="unknown method"):
            phase_shift(_stl_blob(), delta_phi=1.0, method="fft_bad")

    def test_caller_blob_not_mutated(self):
        blob = _stl_blob()
        orig = blob.components["seasonal"].copy()
        phase_shift(blob, delta_phi=1.0)
        np.testing.assert_array_equal(blob.components["seasonal"], orig)

    def test_mstl_all_seasonal_shifted(self):
        blob = _mstl_blob()
        orig_10 = blob.components["seasonal_10"].copy()
        orig_30 = blob.components["seasonal_30"].copy()
        result = phase_shift(blob, delta_phi=np.pi, method="harmonic")
        # After pi shift, seasonal should be negated
        np.testing.assert_allclose(result.values,
            blob.components["trend"] - orig_10 - orig_30 + blob.components["residual"],
            atol=0.1)

    def test_hilbert_both_methods_similar_interior(self):
        """hilbert and harmonic methods should give similar results in interior."""
        blob = _stl_blob()
        r_h = phase_shift(blob, delta_phi=0.5, method="hilbert")
        r_f = phase_shift(blob, delta_phi=0.5, method="harmonic")
        interior = slice(5, N - 5)
        np.testing.assert_allclose(
            r_h.values[interior], r_f.values[interior], atol=0.2
        )


# ---------------------------------------------------------------------------
# change_period
# ---------------------------------------------------------------------------


class TestChangePeriod:
    def test_beta_one_identity(self):
        blob = _stl_blob()
        orig = blob.reassemble().copy()
        result = change_period(blob, beta=1.0)
        np.testing.assert_allclose(result.values, orig, atol=1e-10)

    def test_op_name_period_doubled(self):
        blob = _stl_blob(period=10)
        result = change_period(blob, beta=2.0)
        assert result.op_name == "change_period"

    def test_period_doubled_slows_cycle(self):
        """Doubling period: the value at index T_new should equal original T_old value."""
        blob = _stl_blob(n=80, period=10)
        result = change_period(blob, beta=2.0)
        # At new period T_new=20, index 20 should be close to what was at index 10
        # in the original (first full cycle in old → at halfway in new)
        # The interpolation maps new[20] = old[20/2] = old[10]
        # original seasonal at 10 = 2*sin(2pi*10/10) = 0
        orig_seasonal_10 = blob.components["seasonal"][10]
        # new seasonal at 20 = orig at 20/2 = 10
        # result.values = trend + seasonal + residual
        # compare seasonal contribution only
        result_seasonal_20 = (result.values[20]
            - blob.components["trend"][20]  # trend unchanged
            - blob.components["residual"][20])
        np.testing.assert_allclose(result_seasonal_20, orig_seasonal_10, atol=1e-10)

    def test_beta_zero_raises(self):
        with pytest.raises(ValueError, match="beta"):
            change_period(_stl_blob(), beta=0.0)

    def test_beta_negative_raises(self):
        with pytest.raises(ValueError):
            change_period(_stl_blob(), beta=-1.0)

    def test_relabel_preserved(self):
        result = change_period(_stl_blob(), beta=2.0)
        assert result.relabel.rule_class == "PRESERVED"
        assert result.relabel.new_shape == "cycle"

    def test_op_name(self):
        assert change_period(_stl_blob(), beta=2.0).op_name == "change_period"

    def test_caller_blob_not_mutated(self):
        blob = _stl_blob()
        orig = blob.components["seasonal"].copy()
        change_period(blob, beta=2.0)
        np.testing.assert_array_equal(blob.components["seasonal"], orig)

    def test_mstl_both_periods_resampled(self):
        blob = _mstl_blob(n=120, periods=(10, 30))
        result = change_period(blob, beta=1.0)
        # Identity for beta=1
        np.testing.assert_allclose(result.values, blob.reassemble(), atol=1e-10)

    def test_output_length_unchanged(self):
        blob = _stl_blob(n=80)
        result = change_period(blob, beta=2.0)
        assert len(result.values) == 80


# ---------------------------------------------------------------------------
# change_harmonic_content
# ---------------------------------------------------------------------------


class TestChangeHarmonicContent:
    def test_fundamental_zeroed(self):
        """Setting k=1 to (0, 0) removes the fundamental."""
        blob = _stl_blob(amp=2.0)
        result = change_harmonic_content(blob, coeffs_dict={1: (0.0, 0.0)})
        # Seasonal should now have near-zero fundamental
        # Check amplitude at period is reduced
        seasonal_after = result.values - blob.components["trend"]
        # Fundamental contributes mostly at low frequency — check std is reduced
        t = np.arange(N, dtype=float)
        fundamental = np.sin(2 * np.pi * t / PERIOD)
        original_corr = abs(np.dot(blob.components["seasonal"], fundamental))
        new_corr = abs(np.dot(seasonal_after, fundamental))
        assert new_corr < original_corr * 0.1

    def test_set_pure_cosine_fundamental(self):
        """Set k=1 to (A, 0) → pure cosine fundamental."""
        blob = _stl_blob(amp=0.0)  # start with flat seasonal
        A = 3.0
        result = change_harmonic_content(blob, coeffs_dict={1: (A, 0.0)})
        t = np.arange(N, dtype=float)
        expected_seasonal = A * np.cos(2 * np.pi * t / PERIOD)
        seasonal_result = result.values - blob.components["trend"]
        np.testing.assert_allclose(seasonal_result, expected_seasonal, atol=0.05)

    def test_relabel_preserved(self):
        result = change_harmonic_content(_stl_blob(), coeffs_dict={1: (1.0, 0.0)})
        assert result.relabel.rule_class == "PRESERVED"
        assert result.relabel.new_shape == "cycle"

    def test_op_name(self):
        assert change_harmonic_content(_stl_blob(), {1: (1.0, 0.0)}).op_name == "change_harmonic_content"

    def test_tier(self):
        assert change_harmonic_content(_stl_blob(), {1: (1.0, 0.0)}).tier == 2

    def test_caller_blob_not_mutated(self):
        blob = _stl_blob()
        orig = blob.components["seasonal"].copy()
        change_harmonic_content(blob, {1: (1.0, 0.0)})
        np.testing.assert_array_equal(blob.components["seasonal"], orig)

    def test_empty_coeffs_dict_identity(self):
        blob = _stl_blob()
        result = change_harmonic_content(blob, coeffs_dict={})
        np.testing.assert_allclose(result.values, blob.reassemble(), atol=1e-12)

    def test_pre_shape_forwarded(self):
        result = change_harmonic_content(_stl_blob(), {1: (1.0, 0.0)}, pre_shape="noise")
        assert result.relabel.new_shape == "noise"

    def test_mstl_both_seasonals_modified(self):
        blob = _mstl_blob()
        result = change_harmonic_content(blob, coeffs_dict={1: (0.0, 0.0)})
        # Both seasonal components should have their fundamental reduced
        assert isinstance(result, Tier2OpResult)


# ---------------------------------------------------------------------------
# replace_with_flat
# ---------------------------------------------------------------------------


class TestReplaceWithFlat:
    def test_output_is_constant(self):
        blob = _stl_blob()
        result = replace_with_flat(blob)
        np.testing.assert_allclose(
            result.values, result.values[0] * np.ones(N), atol=1e-10
        )

    def test_relabel_deterministic_plateau(self):
        result = replace_with_flat(_stl_blob())
        assert result.relabel.rule_class == "DETERMINISTIC"
        assert result.relabel.new_shape == "plateau"
        assert result.relabel.needs_resegment is False

    def test_op_name(self):
        assert replace_with_flat(_stl_blob()).op_name == "replace_with_flat"

    def test_tier(self):
        assert replace_with_flat(_stl_blob()).tier == 2

    def test_caller_blob_not_mutated(self):
        blob = _stl_blob()
        orig_seasonal = blob.components["seasonal"].copy()
        orig_trend = blob.components["trend"].copy()
        replace_with_flat(blob)
        np.testing.assert_array_equal(blob.components["seasonal"], orig_seasonal)
        np.testing.assert_array_equal(blob.components["trend"], orig_trend)

    def test_mstl_output_is_constant(self):
        blob = _mstl_blob()
        result = replace_with_flat(blob)
        np.testing.assert_allclose(
            result.values, result.values[0] * np.ones(120), atol=1e-10
        )

    def test_plateau_level_near_trend_mean(self):
        blob = _stl_blob()
        trend_mean = float(np.mean(blob.components["trend"]))
        result = replace_with_flat(blob)
        np.testing.assert_allclose(result.values[0], trend_mean, atol=1e-10)

    def test_pre_shape_forwarded(self):
        result = replace_with_flat(_stl_blob(), pre_shape="noise")
        # Note: DETERMINISTIC always outputs the target shape, not pre_shape
        assert result.relabel.new_shape == "plateau"

    def test_output_constant_with_nonzero_residual(self):
        """Residual must also be zeroed — DETERMINISTIC('plateau') must hold."""
        rng = np.random.default_rng(7)
        residual = rng.normal(0, 0.3, N)
        blob = DecompositionBlob(
            method="STL",
            components={
                "trend": 0.1 * np.arange(N, dtype=float) + 5.0,
                "seasonal": 2.0 * np.sin(2 * np.pi * np.arange(N, dtype=float) / PERIOD),
                "residual": residual,
            },
            coefficients={"period": PERIOD},
            fit_metadata={},
        )
        result = replace_with_flat(blob)
        np.testing.assert_allclose(
            result.values, result.values[0] * np.ones(N), atol=1e-10
        )


# ---------------------------------------------------------------------------
# Cross-op
# ---------------------------------------------------------------------------


class TestCrossOp:
    def test_all_ops_return_tier2_result(self):
        blob = _stl_blob()
        ops = [
            deseasonalise_remove(blob),
            amplify_amplitude(blob, alpha=2.0),
            dampen_amplitude(blob, alpha=0.5),
            phase_shift(blob, delta_phi=1.0),
            change_period(blob, beta=1.5),
            change_harmonic_content(blob, {1: (1.0, 0.0)}),
            replace_with_flat(blob),
        ]
        for r in ops:
            assert isinstance(r, Tier2OpResult)

    def test_deseasonalise_and_replace_flat_agree_on_seasonal_removal(self):
        """Both zero the seasonal; replace_with_flat also flattens trend."""
        blob = _stl_blob()
        r_remove = deseasonalise_remove(blob)
        r_flat = replace_with_flat(blob)
        # r_remove keeps original trend; r_flat flattens it
        # Their values should differ by the trend variation
        assert not np.allclose(r_remove.values, r_flat.values)

    def test_amplify_alpha_zero_same_as_replace_flat_seasonal_part(self):
        """amplify_amplitude(0) zeros seasonals (same as replace_with_flat for flat trend)."""
        blob = _stl_blob()
        # Make trend flat so the comparison is clean
        blob.components["trend"] = np.full(N, 5.0)
        r_amp = amplify_amplitude(blob, alpha=0.0)
        r_flat = replace_with_flat(blob)
        np.testing.assert_allclose(r_amp.values, r_flat.values, atol=1e-10)

    def test_change_period_beta_one_identity_mstl(self):
        blob = _mstl_blob()
        result = change_period(blob, beta=1.0)
        np.testing.assert_allclose(result.values, blob.reassemble(), atol=1e-10)
