"""Tests for Tier-1 stochastic atoms: suppress and add_uncertainty (OP-013)."""

import math

import numpy as np
import pytest

from app.services.operations.tier1.stochastic import (
    StochasticOpResult,
    add_uncertainty,
    default_suppress_strategy,
    suppress,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _flat(n: int = 30, val: float = 1.0) -> np.ndarray:
    return np.full(n, val, dtype=np.float64)


def _ramp(n: int = 30, start: float = 0.0, stop: float = 1.0) -> np.ndarray:
    return np.linspace(start, stop, n)


# ---------------------------------------------------------------------------
# suppress — result type and relabeling
# ---------------------------------------------------------------------------


def test_suppress_returns_stochastic_result():
    result = suppress(_flat(20), strategy="linear")
    assert isinstance(result, StochasticOpResult)


def test_suppress_result_length_matches_input():
    X = _ramp(25)
    result = suppress(X, ctx_pre=_flat(5, 0.0), ctx_post=_flat(5, 2.0), strategy="linear")
    assert len(result.values) == 25


def test_suppress_relabel_is_reclassify():
    result = suppress(_flat(20), strategy="linear", pre_shape="cycle")
    assert result.relabel.rule_class == "RECLASSIFY_VIA_SEGMENTER"
    assert result.relabel.needs_resegment is True


def test_suppress_op_name():
    result = suppress(_flat(20), strategy="linear")
    assert result.op_name == "suppress"


def test_suppress_tier_is_1():
    result = suppress(_flat(20), strategy="linear")
    assert result.tier == 1


# ---------------------------------------------------------------------------
# suppress — unknown strategy raises
# ---------------------------------------------------------------------------


def test_suppress_unknown_strategy_raises():
    with pytest.raises(ValueError, match="unknown fill strategy"):
        suppress(_flat(20), strategy="fourier")


# ---------------------------------------------------------------------------
# suppress — linear strategy
# ---------------------------------------------------------------------------


def test_suppress_linear_endpoints():
    pre = np.array([0.0, 0.0, 0.0])
    post = np.array([3.0, 3.0, 3.0])
    result = suppress(np.zeros(10), ctx_pre=pre, ctx_post=post, strategy="linear")
    assert math.isclose(result.values[0], 0.0, abs_tol=1e-12)
    assert math.isclose(result.values[-1], 3.0, abs_tol=1e-12)


def test_suppress_linear_is_monotone_between_endpoints():
    pre = np.array([0.0])
    post = np.array([1.0])
    result = suppress(np.zeros(10), ctx_pre=pre, ctx_post=post, strategy="linear")
    diffs = np.diff(result.values)
    assert np.all(diffs >= -1e-12)


def test_suppress_linear_no_context_uses_segment_endpoints():
    X = np.array([5.0, 3.0, 1.0])
    result = suppress(X, strategy="linear")
    assert math.isclose(result.values[0], 5.0, abs_tol=1e-12)
    assert math.isclose(result.values[-1], 1.0, abs_tol=1e-12)


def test_suppress_linear_pre_mean_uses_last_3():
    pre = np.array([10.0, 1.0, 1.0, 1.0])
    result = suppress(np.zeros(5), ctx_pre=pre, strategy="linear")
    assert math.isclose(result.values[0], 1.0, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# suppress — spline strategy
# ---------------------------------------------------------------------------


def test_suppress_spline_length_matches():
    pre = _ramp(5, 0.0, 0.5)
    post = _ramp(5, 1.5, 2.0)
    result = suppress(np.zeros(10), ctx_pre=pre, ctx_post=post, strategy="spline")
    assert len(result.values) == 10


def test_suppress_spline_no_context_returns_mean():
    X = _flat(10, 3.7)
    result = suppress(X, strategy="spline")
    assert np.allclose(result.values, 3.7, atol=1e-10)


def test_suppress_spline_single_anchor_falls_back_to_linear():
    pre = np.array([0.0])
    result = suppress(np.zeros(5), ctx_pre=pre, strategy="spline")
    assert len(result.values) == 5


def test_suppress_spline_smooth_across_gap():
    pre = np.linspace(0.0, 1.0, 10)
    post = np.linspace(2.0, 3.0, 10)
    result = suppress(np.zeros(10), ctx_pre=pre, ctx_post=post, strategy="spline")
    assert result.values[0] > result.values[-1] or result.values[-1] > result.values[0]


# ---------------------------------------------------------------------------
# suppress — stl_trend strategy
# ---------------------------------------------------------------------------


def test_suppress_stl_trend_length_matches():
    n_seg = 20
    period = 7
    full = np.sin(2 * np.pi * np.arange(80) / period) + np.linspace(0, 1, 80)
    pre = full[:30]
    seg = full[30 : 30 + n_seg]
    post = full[50:]
    result = suppress(seg, ctx_pre=pre, ctx_post=post, strategy="stl_trend", aux={"period": period})
    assert len(result.values) == n_seg


def test_suppress_stl_trend_requires_period():
    with pytest.raises(ValueError, match="period"):
        suppress(np.zeros(20), ctx_pre=np.ones(10), ctx_post=np.ones(10), strategy="stl_trend", aux={})


def test_suppress_stl_trend_requires_period_ge_2():
    with pytest.raises(ValueError, match="period"):
        suppress(np.zeros(20), ctx_pre=np.ones(10), ctx_post=np.ones(10), strategy="stl_trend", aux={"period": 1})


def test_suppress_stl_trend_too_short_falls_back_to_linear(caplog):
    import logging
    seg = np.zeros(5)
    pre = np.ones(3)
    post = np.ones(3) * 2.0
    with caplog.at_level(logging.WARNING):
        result = suppress(seg, ctx_pre=pre, ctx_post=post, strategy="stl_trend", aux={"period": 12})
    assert len(result.values) == 5
    assert any("falling back" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# suppress — climatology strategy
# ---------------------------------------------------------------------------


def _doy_clim() -> dict[int, float]:
    return {d: float(d) * 0.1 for d in range(1, 366)}


def test_suppress_climatology_dict_lookup():
    clim = _doy_clim()
    dates = list(range(1, 11))
    X = np.zeros(10)
    result = suppress(X, strategy="climatology", aux={"doy_climatology": clim, "dates_in_segment": dates})
    expected = np.array([clim[d] for d in dates])
    assert np.allclose(result.values, expected, atol=1e-12)


def test_suppress_climatology_array_lookup():
    clim_arr = np.arange(366, dtype=float) * 0.5
    dates = [0, 10, 100, 200, 300]
    X = np.zeros(5)
    result = suppress(X, strategy="climatology", aux={"doy_climatology": clim_arr, "dates_in_segment": dates})
    expected = clim_arr[np.array(dates)]
    assert np.allclose(result.values, expected, atol=1e-12)


def test_suppress_climatology_missing_aux_raises():
    with pytest.raises(ValueError, match="doy_climatology"):
        suppress(np.zeros(5), strategy="climatology", aux={})


def test_suppress_climatology_dates_length_mismatch_raises():
    with pytest.raises(ValueError, match="length"):
        suppress(
            np.zeros(5),
            strategy="climatology",
            aux={"doy_climatology": _doy_clim(), "dates_in_segment": [1, 2, 3]},
        )


def test_suppress_climatology_missing_dict_key_raises():
    clim = {1: 0.1, 2: 0.2}
    with pytest.raises(ValueError, match="DOY key"):
        suppress(
            np.zeros(3),
            strategy="climatology",
            aux={"doy_climatology": clim, "dates_in_segment": [1, 2, 999]},
        )


def test_suppress_climatology_oob_array_index_raises():
    clim_arr = np.zeros(10)
    with pytest.raises(ValueError, match="out of bounds"):
        suppress(
            np.zeros(2),
            strategy="climatology",
            aux={"doy_climatology": clim_arr, "dates_in_segment": [1, 500]},
        )


# ---------------------------------------------------------------------------
# suppress — baseflow strategy (delegates to Eckhardt fitter)
# ---------------------------------------------------------------------------


def test_suppress_baseflow_length_matches():
    pytest.importorskip("app.services.decomposition.fitters.eckhardt", reason="eckhardt fitter not present")
    n_seg = 20
    rng = np.random.default_rng(42)
    seg = rng.uniform(0.5, 1.5, n_seg)
    pre = rng.uniform(0.5, 1.5, 15)
    post = rng.uniform(0.5, 1.5, 15)
    result = suppress(seg, ctx_pre=pre, ctx_post=post, strategy="baseflow")
    assert len(result.values) == n_seg


def test_suppress_baseflow_values_are_finite():
    pytest.importorskip("app.services.decomposition.fitters.eckhardt", reason="eckhardt fitter not present")
    rng = np.random.default_rng(7)
    seg = rng.uniform(0.5, 2.0, 15)
    pre = rng.uniform(0.5, 2.0, 10)
    post = rng.uniform(0.5, 2.0, 10)
    result = suppress(seg, ctx_pre=pre, ctx_post=post, strategy="baseflow")
    assert np.all(np.isfinite(result.values))


# ---------------------------------------------------------------------------
# suppress — domain hint default strategy
# ---------------------------------------------------------------------------


def test_default_strategy_remote_sensing():
    assert default_suppress_strategy("remote_sensing") == "climatology"


def test_default_strategy_hydrology():
    assert default_suppress_strategy("hydrology") == "baseflow"


def test_default_strategy_unknown_is_linear():
    assert default_suppress_strategy("seismo") == "linear"


def test_default_strategy_none_is_linear():
    assert default_suppress_strategy(None) == "linear"


def test_suppress_domain_hint_selects_climatology():
    clim = _doy_clim()
    dates = list(range(1, 11))
    X = np.zeros(10)
    result = suppress(
        X,
        domain_hint="remote_sensing",
        aux={"doy_climatology": clim, "dates_in_segment": dates},
    )
    assert result.op_name == "suppress"
    assert len(result.values) == 10


def test_suppress_explicit_strategy_overrides_domain_hint():
    result = suppress(
        np.zeros(10),
        ctx_pre=np.ones(5),
        ctx_post=np.ones(5) * 2.0,
        strategy="linear",
        domain_hint="hydrology",
    )
    assert len(result.values) == 10


# ---------------------------------------------------------------------------
# add_uncertainty — result type and relabeling
# ---------------------------------------------------------------------------


def test_add_uncertainty_returns_stochastic_result():
    result = add_uncertainty(np.ones(20), sigma=0.1)
    assert isinstance(result, StochasticOpResult)


def test_add_uncertainty_relabel_is_preserved():
    result = add_uncertainty(np.ones(20), sigma=0.1, pre_shape="trend")
    assert result.relabel.rule_class == "PRESERVED"
    assert result.relabel.needs_resegment is False


def test_add_uncertainty_op_name():
    result = add_uncertainty(np.ones(20), sigma=0.1)
    assert result.op_name == "add_uncertainty"


def test_add_uncertainty_tier_is_1():
    result = add_uncertainty(np.ones(20), sigma=0.1)
    assert result.tier == 1


def test_add_uncertainty_output_length_matches_input():
    X = np.zeros(50)
    result = add_uncertainty(X, sigma=1.0)
    assert len(result.values) == 50


# ---------------------------------------------------------------------------
# add_uncertainty — error handling
# ---------------------------------------------------------------------------


def test_add_uncertainty_negative_sigma_raises():
    with pytest.raises(ValueError, match="sigma"):
        add_uncertainty(np.ones(20), sigma=-0.1)


def test_add_uncertainty_unknown_color_raises():
    with pytest.raises(ValueError, match="color"):
        add_uncertainty(np.ones(20), sigma=0.5, color="blue")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# add_uncertainty — white noise
# ---------------------------------------------------------------------------


def test_add_uncertainty_white_sigma_zero_is_identity():
    X = np.linspace(0, 1, 30)
    result = add_uncertainty(X, sigma=0.0, color="white", seed=0)
    assert np.allclose(result.values, X, atol=1e-12)


def test_add_uncertainty_white_mean_close_to_signal():
    n = 2000
    X = np.zeros(n)
    result = add_uncertainty(X, sigma=1.0, color="white", seed=42)
    assert abs(float(np.mean(result.values))) < 0.1


def test_add_uncertainty_white_std_close_to_sigma():
    n = 5000
    X = np.zeros(n)
    result = add_uncertainty(X, sigma=2.0, color="white", seed=7)
    assert abs(float(np.std(result.values)) - 2.0) < 0.15


def test_add_uncertainty_white_seed_reproducible():
    X = np.ones(100)
    r1 = add_uncertainty(X, sigma=1.0, color="white", seed=99)
    r2 = add_uncertainty(X, sigma=1.0, color="white", seed=99)
    assert np.array_equal(r1.values, r2.values)


def test_add_uncertainty_white_different_seeds_differ():
    X = np.ones(100)
    r1 = add_uncertainty(X, sigma=1.0, color="white", seed=1)
    r2 = add_uncertainty(X, sigma=1.0, color="white", seed=2)
    assert not np.array_equal(r1.values, r2.values)


# ---------------------------------------------------------------------------
# add_uncertainty — colored noise (pink / red)
# ---------------------------------------------------------------------------

colorednoise = pytest.importorskip("colorednoise", reason="colorednoise not installed")


def test_add_uncertainty_pink_output_length():
    X = np.zeros(200)
    result = add_uncertainty(X, sigma=1.0, color="pink", seed=0)
    assert len(result.values) == 200


def test_add_uncertainty_red_output_length():
    X = np.zeros(200)
    result = add_uncertainty(X, sigma=1.0, color="red", seed=0)
    assert len(result.values) == 200


def test_add_uncertainty_pink_seed_reproducible():
    X = np.zeros(200)
    r1 = add_uncertainty(X, sigma=1.0, color="pink", seed=5)
    r2 = add_uncertainty(X, sigma=1.0, color="pink", seed=5)
    assert np.array_equal(r1.values, r2.values)


def test_add_uncertainty_red_seed_reproducible():
    X = np.zeros(200)
    r1 = add_uncertainty(X, sigma=1.0, color="red", seed=5)
    r2 = add_uncertainty(X, sigma=1.0, color="red", seed=5)
    assert np.array_equal(r1.values, r2.values)


def test_add_uncertainty_pink_std_close_to_sigma():
    n = 5000
    X = np.zeros(n)
    result = add_uncertainty(X, sigma=2.0, color="pink", seed=123)
    assert abs(float(np.std(result.values)) - 2.0) < 0.2


def test_add_uncertainty_red_std_close_to_sigma():
    n = 5000
    X = np.zeros(n)
    result = add_uncertainty(X, sigma=2.0, color="red", seed=456)
    assert abs(float(np.std(result.values)) - 2.0) < 0.2


def test_add_uncertainty_pink_psd_slope_negative():
    """Pink noise should have a negatively-sloped log-log PSD (slope ~ -1)."""
    n = 4096
    X = np.zeros(n)
    result = add_uncertainty(X, sigma=1.0, color="pink", seed=11)
    noise = result.values
    fft_mag = np.abs(np.fft.rfft(noise))[1:]
    freqs = np.fft.rfftfreq(n)[1:]
    log_f = np.log10(freqs)
    log_p = np.log10(fft_mag**2 + 1e-30)
    slope, _ = np.polyfit(log_f, log_p, 1)
    assert slope < -0.3, f"Expected negative PSD slope for pink noise, got {slope:.3f}"


def test_add_uncertainty_red_psd_slope_steeper_than_pink():
    """Red noise should have a steeper log-log PSD slope than pink noise."""
    n = 4096
    X = np.zeros(n)
    pink = add_uncertainty(X, sigma=1.0, color="pink", seed=22)
    red = add_uncertainty(X, sigma=1.0, color="red", seed=22)

    def _slope(arr: np.ndarray) -> float:
        fft_mag = np.abs(np.fft.rfft(arr))[1:]
        freqs = np.fft.rfftfreq(n)[1:]
        log_f = np.log10(freqs)
        log_p = np.log10(fft_mag**2 + 1e-30)
        s, _ = np.polyfit(log_f, log_p, 1)
        return s

    assert _slope(red.values) < _slope(pink.values)


# ---------------------------------------------------------------------------
# add_uncertainty — sigma=0 for colored noise
# ---------------------------------------------------------------------------


def test_add_uncertainty_pink_sigma_zero_is_identity():
    X = np.linspace(0, 1, 100)
    result = add_uncertainty(X, sigma=0.0, color="pink", seed=0)
    assert np.allclose(result.values, X, atol=1e-12)
