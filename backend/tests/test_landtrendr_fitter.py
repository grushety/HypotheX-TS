"""Tests for the LandTrendr decomposition fitter — SEG-017.

References
----------
Kennedy, R., Yang, Z., & Cohen, W. (2010) RSE 114(12):2897–2910.
Kennedy, R. et al. (2018) Remote Sensing 10(5):691.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import FITTER_REGISTRY, _ensure_fitters_loaded
from app.services.decomposition.fitters.landtrendr import (
    find_candidate_vertices,
    fit_landtrendr,
    fit_piecewise_linear,
)


RNG = np.random.default_rng(42)


# ---------------------------------------------------------------------------
# Synthetic NDVI fixtures
# ---------------------------------------------------------------------------


def _three_vertex_trajectory(
    n: int = 240,
    bp1: int | None = None,
    bp2: int | None = None,
    y0: float = 0.7,
    y1: float = 0.3,
    y2: float = 0.6,
    noise_sd: float = 0.0,
) -> np.ndarray:
    """Three internal vertices at indices 0, bp1, bp2, n-1.

    Disturbance segment [0, bp1] declines from y0 → y1; recovery segment
    [bp1, bp2] climbs to y2; final segment [bp2, n-1] holds y2.
    Defaults scale to ``n``: ``bp1=n//2-20``, ``bp2=n*3//4``.
    """
    if bp1 is None:
        bp1 = max(2, n // 2 - 20)
    if bp2 is None:
        bp2 = max(bp1 + 2, n * 3 // 4)
    if not (0 < bp1 < bp2 < n - 1):
        raise ValueError(
            f"_three_vertex_trajectory: need 0 < bp1 < bp2 < n-1; "
            f"got n={n}, bp1={bp1}, bp2={bp2}."
        )
    Y = np.empty(n, dtype=np.float64)
    Y[: bp1 + 1] = np.linspace(y0, y1, bp1 + 1)
    Y[bp1 : bp2 + 1] = np.linspace(y1, y2, bp2 - bp1 + 1)
    Y[bp2:] = y2
    if noise_sd > 0.0:
        Y = Y + RNG.normal(scale=noise_sd, size=n)
    return Y


def _straight_line(n: int = 100, slope: float = 0.01, intercept: float = 0.5) -> np.ndarray:
    return intercept + slope * np.arange(n, dtype=np.float64)


# ---------------------------------------------------------------------------
# Registry / dispatcher integration
# ---------------------------------------------------------------------------


def test_landtrendr_registered():
    _ensure_fitters_loaded()
    assert "LandTrendr" in FITTER_REGISTRY
    assert FITTER_REGISTRY["LandTrendr"] is fit_landtrendr


def test_landtrendr_returns_decomposition_blob():
    X = _three_vertex_trajectory()
    blob = fit_landtrendr(X)
    assert isinstance(blob, DecompositionBlob)
    assert blob.method == "LandTrendr"


# ---------------------------------------------------------------------------
# Components (trend + residual) and shapes
# ---------------------------------------------------------------------------


def test_landtrendr_components_present():
    X = _three_vertex_trajectory()
    blob = fit_landtrendr(X)
    assert "trend" in blob.components
    assert "residual" in blob.components


def test_landtrendr_components_have_correct_shape():
    n = 240
    X = _three_vertex_trajectory(n=n)
    blob = fit_landtrendr(X)
    for name, arr in blob.components.items():
        assert arr.shape == (n,), f"{name} has shape {arr.shape}"


# ---------------------------------------------------------------------------
# Acceptance fixture: 3 true vertices at t={0, 100, 200} → recovers within ±1
# ---------------------------------------------------------------------------


def test_landtrendr_recovers_three_true_vertices_within_one_timestep():
    """Synthetic trajectory with vertices at indices {0, 100, 200} —
    LandTrendr must recover both internal vertices within ±1 sample."""
    X = _three_vertex_trajectory(n=240, bp1=100, bp2=200, y0=0.7, y1=0.3, y2=0.6)
    blob = fit_landtrendr(X, max_vertices=4, penalty_per_vertex=0.001)
    vx = [int(round(v[0])) for v in blob.coefficients["vertices"]]
    assert any(abs(v - 100) <= 1 for v in vx), f"missing vertex near 100, got {vx}"
    assert any(abs(v - 200) <= 1 for v in vx), f"missing vertex near 200, got {vx}"


def test_landtrendr_includes_endpoints_as_vertices():
    n = 240
    X = _three_vertex_trajectory(n=n)
    blob = fit_landtrendr(X)
    vx = [v[0] for v in blob.coefficients["vertices"]]
    assert vx[0] == pytest.approx(0.0)
    assert vx[-1] == pytest.approx(float(n - 1))


# ---------------------------------------------------------------------------
# Vertex-count budget (max_vertices respected)
# ---------------------------------------------------------------------------


def test_landtrendr_max_vertices_respected():
    X = _three_vertex_trajectory(noise_sd=0.05)
    for k_max in (2, 3, 4, 5, 6):
        blob = fit_landtrendr(X, max_vertices=k_max, penalty_per_vertex=0.0)
        assert blob.fit_metadata["n_vertices"] <= k_max


def test_landtrendr_invalid_max_vertices_raises():
    X = _three_vertex_trajectory()
    with pytest.raises(ValueError, match="max_vertices"):
        fit_landtrendr(X, max_vertices=1)


# ---------------------------------------------------------------------------
# 2-vertex straight-line fit
# ---------------------------------------------------------------------------


def test_landtrendr_two_vertex_fit_recovers_straight_line():
    X = _straight_line(n=100, slope=0.01, intercept=0.5)
    blob = fit_landtrendr(X, max_vertices=2)
    assert blob.fit_metadata["n_vertices"] == 2
    np.testing.assert_allclose(blob.components["trend"], X, atol=1e-9)


def test_landtrendr_two_vertex_slopes_have_one_entry():
    X = _straight_line(n=50)
    blob = fit_landtrendr(X, max_vertices=2)
    assert len(blob.coefficients["slopes"]) == 1
    assert len(blob.coefficients["intercepts"]) == 1


# ---------------------------------------------------------------------------
# 6-vertex fit
# ---------------------------------------------------------------------------


def test_landtrendr_six_vertex_fit_for_bumpy_trajectory():
    """Construct a trajectory with 5 internal vertices; verify the fitter can
    use up to 6 vertices when penalty is small."""
    n = 300
    Y = np.empty(n, dtype=np.float64)
    knots_x = [0, 50, 100, 150, 200, 250, 299]
    knots_y = [0.5, 0.8, 0.4, 0.7, 0.3, 0.6, 0.5]
    for i in range(len(knots_x) - 1):
        a, b = knots_x[i], knots_x[i + 1]
        Y[a : b + 1] = np.linspace(knots_y[i], knots_y[i + 1], b - a + 1)
    blob = fit_landtrendr(Y, max_vertices=7, penalty_per_vertex=0.0)
    assert blob.fit_metadata["n_vertices"] >= 5


# ---------------------------------------------------------------------------
# Penalty effect on chosen vertex count
# ---------------------------------------------------------------------------


def test_landtrendr_higher_penalty_picks_fewer_vertices():
    X = _three_vertex_trajectory(noise_sd=0.05)
    low = fit_landtrendr(X, max_vertices=6, penalty_per_vertex=0.0)
    high = fit_landtrendr(X, max_vertices=6, penalty_per_vertex=10.0)
    assert high.fit_metadata["n_vertices"] <= low.fit_metadata["n_vertices"]


def test_landtrendr_huge_penalty_collapses_to_two_vertices():
    X = _three_vertex_trajectory(noise_sd=0.05)
    blob = fit_landtrendr(X, max_vertices=6, penalty_per_vertex=1e6)
    assert blob.fit_metadata["n_vertices"] == 2


# ---------------------------------------------------------------------------
# Recovery flagging (Kennedy 2010 §3.2)
# ---------------------------------------------------------------------------


def test_landtrendr_recovery_flag_set_after_disturbance():
    """y0=0.7 → y1=0.3 (drop of 0.4 > threshold 0.25), then climbs to 0.6."""
    X = _three_vertex_trajectory(n=240, bp1=100, bp2=200, y0=0.7, y1=0.3, y2=0.6)
    blob = fit_landtrendr(X, max_vertices=4, recovery_threshold=0.25, penalty_per_vertex=0.001)
    recovery = blob.coefficients["recovery"]
    assert any(recovery), f"expected at least one recovery flag; got {recovery}"


def test_landtrendr_no_recovery_flag_when_drop_below_threshold():
    """Drop of only 0.1 (y0=0.7 → y1=0.6) must not trigger recovery flag."""
    X = _three_vertex_trajectory(n=240, bp1=100, bp2=200, y0=0.7, y1=0.6, y2=0.65)
    blob = fit_landtrendr(X, max_vertices=4, recovery_threshold=0.25, penalty_per_vertex=0.001)
    assert not any(blob.coefficients["recovery"])


def test_landtrendr_recovery_threshold_recorded():
    X = _three_vertex_trajectory()
    blob = fit_landtrendr(X, recovery_threshold=0.30)
    assert blob.coefficients["recovery_threshold"] == pytest.approx(0.30)


def test_landtrendr_recovery_flag_count_matches_slopes():
    X = _three_vertex_trajectory()
    blob = fit_landtrendr(X)
    assert len(blob.coefficients["recovery"]) == len(blob.coefficients["slopes"])


# ---------------------------------------------------------------------------
# Reassembly within vertex-bounded RMS
# ---------------------------------------------------------------------------


def test_landtrendr_trend_plus_residual_equals_input():
    X = _three_vertex_trajectory(noise_sd=0.05)
    blob = fit_landtrendr(X)
    np.testing.assert_allclose(
        blob.components["trend"] + blob.components["residual"], X, atol=1e-12
    )


def test_landtrendr_rmse_recorded_in_metadata():
    X = _three_vertex_trajectory(noise_sd=0.05)
    blob = fit_landtrendr(X)
    expected = float(np.sqrt(np.mean(blob.components["residual"] ** 2)))
    assert blob.fit_metadata["rmse"] == pytest.approx(expected)


def test_landtrendr_clean_signal_low_rmse():
    """Noise-free 3-vertex signal — fitter should drive RMSE near zero."""
    X = _three_vertex_trajectory(noise_sd=0.0)
    blob = fit_landtrendr(X, max_vertices=4, penalty_per_vertex=0.001)
    assert blob.fit_metadata["rmse"] < 0.01


# ---------------------------------------------------------------------------
# OP-021 backward-compat (legacy schema)
# ---------------------------------------------------------------------------


def test_landtrendr_emits_legacy_op021_schema():
    X = _three_vertex_trajectory(noise_sd=0.05)
    blob = fit_landtrendr(X, max_vertices=4, penalty_per_vertex=0.001)
    for k in ("slope_1", "slope_2", "intercept_1", "intercept_2", "breakpoint"):
        assert k in blob.coefficients, f"missing legacy key {k}"


def test_landtrendr_legacy_keys_match_first_and_last_segment():
    X = _three_vertex_trajectory(noise_sd=0.0)
    blob = fit_landtrendr(X, max_vertices=4, penalty_per_vertex=0.001)
    slopes = blob.coefficients["slopes"]
    intercepts = blob.coefficients["intercepts"]
    assert blob.coefficients["slope_1"] == pytest.approx(slopes[0])
    assert blob.coefficients["intercept_1"] == pytest.approx(intercepts[0])
    assert blob.coefficients["slope_2"] == pytest.approx(slopes[-1])
    assert blob.coefficients["intercept_2"] == pytest.approx(intercepts[-1])


def test_landtrendr_breakpoint_is_first_internal_vertex():
    X = _three_vertex_trajectory(noise_sd=0.0)
    blob = fit_landtrendr(X, max_vertices=4, penalty_per_vertex=0.001)
    vx = [int(round(v[0])) for v in blob.coefficients["vertices"]]
    if len(vx) >= 3:
        assert blob.coefficients["breakpoint"] == vx[1]
    else:
        assert blob.coefficients["breakpoint"] is None


def test_landtrendr_breakpoint_none_for_two_vertex_fit():
    X = _straight_line(n=50)
    blob = fit_landtrendr(X, max_vertices=2)
    assert blob.coefficients["breakpoint"] is None


# ---------------------------------------------------------------------------
# Coefficients (new schema)
# ---------------------------------------------------------------------------


def test_landtrendr_coefficient_lengths_consistent():
    X = _three_vertex_trajectory()
    blob = fit_landtrendr(X)
    n_v = blob.fit_metadata["n_vertices"]
    assert len(blob.coefficients["vertices"]) == n_v
    assert len(blob.coefficients["slopes"]) == n_v - 1
    assert len(blob.coefficients["intercepts"]) == n_v - 1
    assert len(blob.coefficients["recovery"]) == n_v - 1


def test_landtrendr_vertices_are_python_floats():
    X = _three_vertex_trajectory()
    blob = fit_landtrendr(X)
    for vx, vy in blob.coefficients["vertices"]:
        assert isinstance(vx, float)
        assert isinstance(vy, float)


def test_landtrendr_slopes_intercepts_are_python_floats():
    X = _three_vertex_trajectory()
    blob = fit_landtrendr(X)
    for s in blob.coefficients["slopes"]:
        assert isinstance(s, float)
    for i in blob.coefficients["intercepts"]:
        assert isinstance(i, float)


def test_landtrendr_penalty_recorded():
    X = _three_vertex_trajectory()
    blob = fit_landtrendr(X, penalty_per_vertex=0.05)
    assert blob.coefficients["penalty_per_vertex"] == pytest.approx(0.05)


def test_landtrendr_max_vertices_recorded():
    X = _three_vertex_trajectory()
    blob = fit_landtrendr(X, max_vertices=4)
    assert blob.coefficients["max_vertices"] == 4


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_landtrendr_rejects_multivariate_input():
    X = np.zeros((100, 3))
    with pytest.raises(ValueError, match="1-D"):
        fit_landtrendr(X)


def test_landtrendr_accepts_2d_single_column():
    X = _three_vertex_trajectory().reshape(-1, 1)
    blob = fit_landtrendr(X)
    assert blob.method == "LandTrendr"


def test_landtrendr_t_length_mismatch_raises():
    X = _three_vertex_trajectory(n=100)
    with pytest.raises(ValueError, match="length"):
        fit_landtrendr(X, t=np.arange(50, dtype=np.float64))


def test_landtrendr_empty_input_returns_empty_blob():
    blob = fit_landtrendr(np.array([], dtype=np.float64))
    assert blob.method == "LandTrendr"
    assert blob.components["trend"].size == 0
    assert blob.fit_metadata["n_vertices"] == 0


def test_landtrendr_single_point_input():
    blob = fit_landtrendr(np.array([0.5]))
    assert blob.fit_metadata["n_vertices"] == 1
    np.testing.assert_array_equal(blob.components["trend"], np.array([0.5]))


# ---------------------------------------------------------------------------
# Custom time index
# ---------------------------------------------------------------------------


def test_landtrendr_with_custom_time_index_recovers_vertices_in_t_units():
    """When t = 2·index (skip every other sample), vertex X positions must be
    expressed in the user's t units, not in sample indices."""
    X = _three_vertex_trajectory(n=120, bp1=50, bp2=100, y0=0.7, y1=0.3, y2=0.6)
    t = 2.0 * np.arange(120, dtype=np.float64)
    blob = fit_landtrendr(X, t=t, max_vertices=4, penalty_per_vertex=0.001)
    vx = [v[0] for v in blob.coefficients["vertices"]]
    assert any(abs(v - 100.0) <= 2.0 for v in vx), f"expected vertex near t=100, got {vx}"


# ---------------------------------------------------------------------------
# Helpers — direct unit tests
# ---------------------------------------------------------------------------


def test_find_candidate_vertices_starts_with_endpoints():
    X = _three_vertex_trajectory(n=100)
    cand = find_candidate_vertices(X, max_candidates=2)
    assert cand == [0.0, 99.0]


def test_find_candidate_vertices_grows_to_cap():
    """With noise present, candidate generation must grow up to the cap.
    (A noise-free 3-vertex trajectory hits zero residual at 4 candidates and
    stops early, which is also correct.)"""
    X = _three_vertex_trajectory(n=240, bp1=100, bp2=180, noise_sd=0.05)
    cand = find_candidate_vertices(X, max_candidates=8)
    assert len(cand) == 8
    assert cand == sorted(cand)


def test_find_candidate_vertices_picks_largest_residual_first():
    """For a clean 3-vertex piecewise signal, the first-added candidate is the
    sample with the largest residual against the endpoint-only fit."""
    X = _three_vertex_trajectory(n=200, bp1=100, bp2=150, y0=0.7, y1=0.0, y2=0.7)
    cand = find_candidate_vertices(X, max_candidates=3)
    assert any(abs(v - 100) <= 5 for v in cand[1:-1])


def test_fit_piecewise_linear_two_vertex_recovers_straight_line():
    X = _straight_line(n=50, slope=0.02, intercept=0.1)
    t = np.arange(50, dtype=np.float64)
    pairs, trend = fit_piecewise_linear(X, t, vertices=[0.0, 49.0])
    np.testing.assert_allclose(trend, X, atol=1e-9)
    assert len(pairs) == 2


def test_fit_piecewise_linear_rejects_one_vertex():
    X = _straight_line(n=10)
    t = np.arange(10, dtype=np.float64)
    with pytest.raises(ValueError, match="at least 2 vertices"):
        fit_piecewise_linear(X, t, vertices=[0.0])


# ---------------------------------------------------------------------------
# Metadata required keys
# ---------------------------------------------------------------------------


def test_landtrendr_fit_metadata_has_required_keys():
    X = _three_vertex_trajectory()
    blob = fit_landtrendr(X)
    for k in ("rmse", "rank", "n_params", "convergence", "version", "n_vertices", "sse"):
        assert k in blob.fit_metadata, f"missing fit_metadata key: {k}"
    assert isinstance(blob.fit_metadata["convergence"], bool)


def test_landtrendr_sse_matches_residual_squared_sum():
    X = _three_vertex_trajectory(noise_sd=0.05)
    blob = fit_landtrendr(X)
    expected = float(np.sum(blob.components["residual"] ** 2))
    assert blob.fit_metadata["sse"] == pytest.approx(expected)
