"""Tests for Tier-1 time atoms: time_shift, reverse_time, resample (OP-011)."""

import math

import numpy as np
import pytest

from app.services.operations.tier1.time import TimeOpResult, resample, reverse_time, time_shift


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ramp(n: int = 50) -> np.ndarray:
    return np.linspace(0.0, 1.0, n)


def _sine(n: int = 64, freq: float = 0.1) -> np.ndarray:
    t = np.arange(n, dtype=float)
    return np.sin(2 * math.pi * freq * t)


# ---------------------------------------------------------------------------
# time_shift — basic behaviour
# ---------------------------------------------------------------------------


def test_time_shift_zero_returns_copy():
    arr = _ramp()
    result = time_shift(arr, delta_t=0)
    assert np.allclose(result.values, arr)
    assert result.values is not arr


def test_time_shift_preserves_length_positive():
    arr = _ramp(40)
    result = time_shift(arr, delta_t=5)
    assert len(result.values) == len(arr)


def test_time_shift_preserves_length_negative():
    arr = _ramp(40)
    result = time_shift(arr, delta_t=-7)
    assert len(result.values) == len(arr)


def test_time_shift_rolls_values():
    arr = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0])
    result = time_shift(arr, delta_t=2, taper_width=1)
    assert np.isclose(result.values[2], arr[0], atol=1e-10)
    assert np.isclose(result.values[3], arr[1], atol=1e-10)


def test_time_shift_taper_smooths_wrap_positive():
    arr = _ramp(30)
    result = time_shift(arr, delta_t=5, taper_width=5)
    rolled = np.roll(arr, 5)
    assert not np.allclose(result.values[:5], rolled[:5])


def test_time_shift_taper_smooths_wrap_negative():
    arr = _ramp(30)
    result = time_shift(arr, delta_t=-5, taper_width=5)
    rolled = np.roll(arr, -5)
    assert not np.allclose(result.values[-5:], rolled[-5:])


def test_time_shift_taper_width_configurable():
    arr = _ramp(40)
    result_w3 = time_shift(arr, delta_t=4, taper_width=3)
    result_w8 = time_shift(arr, delta_t=4, taper_width=8)
    assert not np.allclose(result_w3.values, result_w8.values)


def test_time_shift_invalid_taper_zero_raises():
    with pytest.raises(ValueError, match="taper_width"):
        time_shift(_ramp(20), delta_t=3, taper_width=0)


def test_time_shift_invalid_taper_too_large_raises():
    arr = _ramp(10)
    with pytest.raises(ValueError, match="taper_width"):
        time_shift(arr, delta_t=2, taper_width=10)


def test_time_shift_relabel_preserved():
    result = time_shift(_ramp(20), delta_t=3, pre_shape="cycle")
    assert result.relabel.rule_class == "PRESERVED"
    assert result.relabel.new_shape == "cycle"


def test_time_shift_op_name_and_tier():
    result = time_shift(_ramp(20), delta_t=1)
    assert result.op_name == "time_shift"
    assert result.tier == 1


# ---------------------------------------------------------------------------
# reverse_time — involution
# ---------------------------------------------------------------------------


def test_reverse_time_reverses_array():
    arr = _ramp(10)
    result = reverse_time(arr)
    assert np.allclose(result.values, arr[::-1])


def test_reverse_time_involutive():
    arr = _ramp(30)
    once = reverse_time(arr)
    twice = reverse_time(once.values)
    assert np.allclose(twice.values, arr)


def test_reverse_time_preserves_length():
    arr = _ramp(25)
    result = reverse_time(arr)
    assert len(result.values) == len(arr)


def test_reverse_time_returns_copy():
    arr = _ramp(10)
    result = reverse_time(arr)
    assert result.values is not arr


def test_reverse_time_relabel_preserved():
    result = reverse_time(_ramp(10), pre_shape="trend")
    assert result.relabel.rule_class == "PRESERVED"
    assert result.relabel.new_shape == "trend"


def test_reverse_time_op_name_and_tier():
    result = reverse_time(_ramp(10))
    assert result.op_name == "reverse_time"
    assert result.tier == 1


# ---------------------------------------------------------------------------
# resample — linear method
# ---------------------------------------------------------------------------


def test_resample_linear_identity_ratio():
    arr = _ramp(20)
    result = resample(arr, new_dt=1.0, old_dt=1.0, method="linear")
    assert np.allclose(result.values, arr)


def test_resample_linear_downsample_halves_length():
    arr = _ramp(40)
    result = resample(arr, new_dt=2.0, old_dt=1.0, method="linear")
    assert len(result.values) == 20


def test_resample_linear_upsample_doubles_length():
    arr = _ramp(20)
    result = resample(arr, new_dt=0.5, old_dt=1.0, method="linear")
    assert len(result.values) == 40


def test_resample_linear_monotone_in_monotone_out():
    arr = _ramp(30)
    result = resample(arr, new_dt=0.5, method="linear")
    assert np.all(np.diff(result.values) >= -1e-12)


# ---------------------------------------------------------------------------
# resample — sg method
# ---------------------------------------------------------------------------


def test_resample_sg_downsample():
    arr = _sine(n=64, freq=0.05)
    result = resample(arr, new_dt=2.0, old_dt=1.0, method="sg")
    assert len(result.values) == 32


def test_resample_sg_upsample():
    arr = _sine(n=32, freq=0.05)
    result = resample(arr, new_dt=0.5, old_dt=1.0, method="sg")
    assert len(result.values) == 64


def test_resample_sg_short_signal():
    arr = np.array([1.0, 2.0, 3.0])
    result = resample(arr, new_dt=0.5, method="sg")
    assert len(result.values) == 6


# ---------------------------------------------------------------------------
# resample — antialiased method
# ---------------------------------------------------------------------------


def test_resample_antialiased_downsample_length():
    arr = _ramp(40)
    result = resample(arr, new_dt=2.0, old_dt=1.0, method="antialiased")
    assert len(result.values) == 20


def test_resample_antialiased_upsample_length():
    arr = _ramp(20)
    result = resample(arr, new_dt=0.5, old_dt=1.0, method="antialiased")
    assert len(result.values) == 40


def test_resample_antialiased_removes_above_nyquist():
    """Signals above the Nyquist of the decimated output are suppressed.

    sin(2π·0.4·t) at dt=1.0 decimated by 2 (new_dt=2.0):
    - Nyquist of decimated signal = 0.25 Hz
    - Signal at 0.4 Hz is above Nyquist
    - FIR LPF applied before decimation must suppress it
    - Output energy should be << original energy
    """
    n = 256
    t = np.arange(n, dtype=float)
    X = np.sin(2 * math.pi * 0.4 * t)

    antialiased_result = resample(X, new_dt=2.0, old_dt=1.0, method="antialiased")
    linear_result = resample(X, new_dt=2.0, old_dt=1.0, method="linear")

    energy_antialiased = float(np.mean(antialiased_result.values ** 2))
    energy_linear = float(np.mean(linear_result.values ** 2))
    energy_original = float(np.mean(X ** 2))

    # Linear (no LPF) preserves the aliased signal → energy comparable to original
    assert energy_linear > 0.2 * energy_original, (
        f"Expected linear path to preserve aliased energy; got {energy_linear:.4f}"
    )
    # Antialiased LPF suppresses the above-Nyquist component significantly
    assert energy_antialiased < 0.1 * energy_linear, (
        f"Expected antialiased path to suppress above-Nyquist energy; "
        f"got {energy_antialiased:.4f} vs linear {energy_linear:.4f}"
    )


def test_resample_antialiased_preserves_low_freq():
    """Low-frequency signal below Nyquist should survive antialiased decimation."""
    n = 256
    t = np.arange(n, dtype=float)
    X = np.sin(2 * math.pi * 0.05 * t)

    result = resample(X, new_dt=2.0, old_dt=1.0, method="antialiased")
    energy_in = float(np.mean(X ** 2))
    energy_out = float(np.mean(result.values ** 2))

    assert energy_out > 0.3 * energy_in


# ---------------------------------------------------------------------------
# resample — error handling
# ---------------------------------------------------------------------------


def test_resample_negative_new_dt_raises():
    with pytest.raises(ValueError, match="new_dt"):
        resample(_ramp(20), new_dt=-1.0)


def test_resample_zero_new_dt_raises():
    with pytest.raises(ValueError, match="new_dt"):
        resample(_ramp(20), new_dt=0.0)


def test_resample_negative_old_dt_raises():
    with pytest.raises(ValueError, match="old_dt"):
        resample(_ramp(20), new_dt=1.0, old_dt=-1.0)


def test_resample_unknown_method_raises():
    with pytest.raises(ValueError, match="unknown method"):
        resample(_ramp(20), new_dt=2.0, method="cubic")


# ---------------------------------------------------------------------------
# resample — relabel and metadata
# ---------------------------------------------------------------------------


def test_resample_relabel_preserved():
    result = resample(_ramp(20), new_dt=2.0, method="linear", pre_shape="plateau")
    assert result.relabel.rule_class == "PRESERVED"
    assert result.relabel.new_shape == "plateau"


def test_resample_op_name_and_tier():
    result = resample(_ramp(20), new_dt=1.0)
    assert result.op_name == "resample"
    assert result.tier == 1


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_all_ops_return_time_op_result():
    arr = _ramp(30)
    assert isinstance(time_shift(arr, 2), TimeOpResult)
    assert isinstance(reverse_time(arr), TimeOpResult)
    assert isinstance(resample(arr, 1.0), TimeOpResult)
