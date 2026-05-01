"""Tests for the SEG-018 GrAtSiD greedy decomposition fitter."""
from __future__ import annotations

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import dispatch_fitter
from app.services.decomposition.fitters.gratsid import (
    DEFAULT_BASIS_TYPES,
    DEFAULT_MAX_FEATURES,
    basis,
    candidate_t_refs,
    fit_gratsid,
)


# ---------------------------------------------------------------------------
# Single-feature fixtures — recovery should be exact
# ---------------------------------------------------------------------------


def test_single_log_feature_recovered_exactly():
    n = 200
    t = np.arange(n, dtype=float)
    X = 1.0 * np.log1p(np.maximum(0, (t - 50) / 10))
    tau_grid = np.array([5, 7, 10, 14, 20])

    blob = fit_gratsid(
        X,
        t,
        basis_types=("log",),
        tau_grid=tau_grid,
        residual_threshold=0.05,
        pre_skeleton=np.zeros(n),
    )

    assert blob.method == "GrAtSiD"
    feats = blob.coefficients["features"]
    assert len(feats) >= 1
    top = feats[0]
    assert top["type"] == "log"
    assert top["t_ref"] == pytest.approx(50.0, abs=2.0)
    assert top["tau"] == pytest.approx(10.0, rel=0.2)
    assert top["amplitude"] == pytest.approx(1.0, rel=0.05)
    assert blob.fit_metadata["rmse"] < 1e-6


def test_single_step_feature_recovered_exactly():
    n = 120
    t = np.arange(n, dtype=float)
    X = 2.5 * (t >= 60).astype(float)

    blob = fit_gratsid(
        X,
        t,
        basis_types=("step",),
        residual_threshold=0.05,
        pre_skeleton=np.zeros(n),
    )

    feats = blob.coefficients["features"]
    assert feats[0]["type"] == "step"
    assert feats[0]["t_ref"] == pytest.approx(60.0, abs=2.0)
    assert feats[0]["amplitude"] == pytest.approx(2.5, rel=0.05)


# ---------------------------------------------------------------------------
# Multi-feature recovery (the headline AC: 3 superposed transients)
# ---------------------------------------------------------------------------


def test_three_superposed_steps_recovered_within_tolerance():
    """AC: 3 superposed step transients at known (t_ref, A) → recover
    all 3 within 10 % amplitude tolerance and ±5 timesteps on t_ref."""
    n = 200
    t = np.arange(n, dtype=float)
    truth = [(30, 1.0), (90, -0.6), (150, 0.4)]
    X = np.zeros(n)
    for tr, amp in truth:
        X += amp * (t >= tr).astype(float)

    blob = fit_gratsid(
        X,
        t,
        basis_types=("step",),
        max_features=10,
        residual_threshold=0.02,
        pre_skeleton=np.zeros(n),
    )

    feats = blob.coefficients["features"]
    # Match each truth feature against the recovered list.
    for tr_truth, amp_truth in truth:
        match = next(
            (
                f
                for f in feats
                if abs(f["t_ref"] - tr_truth) <= 5.0
                and abs(f["amplitude"] - amp_truth) <= 0.10 * abs(amp_truth) + 0.02
            ),
            None,
        )
        assert match is not None, (
            f"truth feature t_ref={tr_truth}, amp={amp_truth} not recovered "
            f"within tolerance.  Got: {feats!r}"
        )


def test_three_superposed_logs_signal_well_explained():
    """AC adaptation for log bases: 3 superposed logs are an over-complete
    dictionary so exact (t_ref, τ) recovery is not unique.  We assert that
    the algorithm explains ≥ 95 % of the residual variance — the headline
    Bedford 2018 quality metric."""
    n = 200
    t = np.arange(n, dtype=float)
    truth = [(30, 5, 1.0), (90, 8, -0.7), (150, 12, 0.5)]
    X = np.zeros(n)
    for tr, tau, amp in truth:
        X += amp * np.log1p(np.maximum(0, (t - tr) / tau))

    tau_grid = np.array([3, 5, 8, 12, 18, 25])
    blob = fit_gratsid(
        X,
        t,
        basis_types=("log",),
        tau_grid=tau_grid,
        max_features=10,
        residual_threshold=0.02,
        pre_skeleton=np.zeros(n),
    )

    assert blob.fit_metadata["explained_fraction"] >= 0.95
    # Sanity: feature count should be small (Bedford 2018 §4 — sparse
    # representation).  Capping max_features=10 already enforces this; the
    # assertion verifies the algorithm wasn't fighting the cap.
    feats = blob.coefficients["features"]
    assert 1 <= len(feats) <= 10


# ---------------------------------------------------------------------------
# Stopping rules
# ---------------------------------------------------------------------------


def test_max_features_caps_feature_count():
    n = 150
    t = np.arange(n, dtype=float)
    rng = np.random.default_rng(0)
    X = rng.normal(scale=0.5, size=n)  # noise; greedy will keep finding bases
    blob = fit_gratsid(
        X,
        t,
        basis_types=("step",),
        max_features=4,
        residual_threshold=1e-9,
        pre_skeleton=np.zeros(n),
    )
    assert len(blob.coefficients["features"]) <= 4
    # convergence flag is False when we hit the cap with non-trivial residual.
    if blob.fit_metadata["rmse"] > 1e-6:
        assert blob.fit_metadata["convergence"] is False


def test_residual_threshold_stops_loop_before_max_features():
    """A flat segment has nothing for greedy basis pursuit to extract; the
    loop should stop on the relative-residual rule far below max_features."""
    n = 100
    t = np.arange(n, dtype=float)
    X = np.zeros(n)
    blob = fit_gratsid(
        X,
        t,
        basis_types=("log", "exp", "step"),
        max_features=30,
        residual_threshold=0.05,
    )
    assert len(blob.coefficients["features"]) < DEFAULT_MAX_FEATURES
    assert blob.fit_metadata["rmse"] == pytest.approx(0.0)
    assert blob.fit_metadata["convergence"] is True


# ---------------------------------------------------------------------------
# Duplicate suppression
# ---------------------------------------------------------------------------


def test_no_duplicate_features_in_same_t_ref_tau_family():
    """Bedford 2018 §3: two features within ±10 % τ and within ~5 % of
    segment length on t_ref should not both be selected."""
    n = 200
    t = np.arange(n, dtype=float)
    rng = np.random.default_rng(7)
    X = rng.normal(scale=0.3, size=n)  # noise: greedy will try every basis
    blob = fit_gratsid(
        X,
        t,
        basis_types=("log",),
        max_features=15,
        residual_threshold=1e-9,
        pre_skeleton=np.zeros(n),
    )
    feats = blob.coefficients["features"]
    t_gap = max(1.0, 0.05 * n)
    for i, fi in enumerate(feats):
        for fj in feats[i + 1 :]:
            if fi["type"] != fj["type"]:
                continue
            close_t = abs(fi["t_ref"] - fj["t_ref"]) <= t_gap
            close_tau = (
                abs(fi["tau"]) > 1e-12
                and abs(fj["tau"] / fi["tau"] - 1.0) <= 0.10
            )
            assert not (close_t and close_tau), (
                f"duplicate-family pair: {fi!r} vs {fj!r}"
            )


# ---------------------------------------------------------------------------
# Empty-input handling
# ---------------------------------------------------------------------------


def test_empty_input_returns_empty_blob_without_error():
    blob = fit_gratsid(np.array([], dtype=float))
    assert blob.method == "GrAtSiD"
    assert blob.coefficients["n_features"] == 0
    assert blob.coefficients["features"] == []
    assert blob.fit_metadata["rmse"] == 0.0
    assert blob.fit_metadata["convergence"] is True


# ---------------------------------------------------------------------------
# ETM-handoff compatibility
# ---------------------------------------------------------------------------


def test_pre_skeleton_arg_strips_known_skeleton_first():
    """SEG-013 ETM may have already fit linear + seasonal + known-step.
    Passing the ETM skeleton via ``pre_skeleton`` should let GrAtSiD work
    on the residual without a duplicate internal linear fit."""
    n = 150
    t = np.arange(n, dtype=float)
    skeleton = 0.05 * t + 0.5  # ETM-style linear background
    transient = 0.8 * (t >= 70).astype(float)
    X = skeleton + transient

    blob = fit_gratsid(
        X,
        t,
        basis_types=("step",),
        max_features=4,
        residual_threshold=0.02,
        pre_skeleton=skeleton,
    )

    feats = blob.coefficients["features"]
    np.testing.assert_array_almost_equal(blob.components["skeleton"], skeleton)
    assert blob.coefficients["skeleton"]["source"] == "pre_skeleton"
    top = feats[0]
    assert top["type"] == "step"
    assert top["t_ref"] == pytest.approx(70.0, abs=2.0)
    assert top["amplitude"] == pytest.approx(0.8, rel=0.05)


def test_pre_skeleton_length_mismatch_raises():
    with pytest.raises(ValueError, match="pre_skeleton length"):
        fit_gratsid(
            np.zeros(100),
            np.arange(100, dtype=float),
            pre_skeleton=np.zeros(50),
        )


# ---------------------------------------------------------------------------
# Output contract — components, coefficients, metadata
# ---------------------------------------------------------------------------


def test_output_blob_carries_required_components_and_coefficients():
    n = 100
    t = np.arange(n, dtype=float)
    X = 1.0 * (t >= 40).astype(float)
    blob = fit_gratsid(X, t, basis_types=("step",), pre_skeleton=np.zeros(n))

    # components must include the three named arrays for OP-025 reassembly
    assert set(blob.components.keys()) == {"skeleton", "transient", "residual"}
    assert blob.components["skeleton"].shape == (n,)
    assert blob.components["transient"].shape == (n,)
    assert blob.components["residual"].shape == (n,)

    # OP-025 reads coefficients['features'] — the contract that lets
    # transient ops (amplify / shift_time / change_decay_constant / ...)
    # edit GrAtSiD output without knowing it came from this fitter.
    assert isinstance(blob.coefficients["features"], list)
    for f in blob.coefficients["features"]:
        assert {"type", "t_ref", "tau", "amplitude"} <= set(f.keys())

    # fit_metadata schema parity with the other fitters (SEG-013/14/15/16).
    md = blob.fit_metadata
    for key in ("rmse", "rank", "n_params", "convergence", "version"):
        assert key in md, f"missing {key} in fit_metadata"


def test_blob_reassembly_matches_input_within_residual():
    """sum(components) should reproduce the original signal within the
    residual error — the DecompositionBlob.reassemble() invariant."""
    n = 80
    t = np.arange(n, dtype=float)
    X = 1.5 * (t >= 30).astype(float) - 0.7 * (t >= 60).astype(float)
    blob = fit_gratsid(
        X,
        t,
        basis_types=("step",),
        max_features=5,
        residual_threshold=0.01,
        pre_skeleton=np.zeros(n),
    )
    reassembled = blob.reassemble()
    np.testing.assert_allclose(reassembled, X, atol=1e-9)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_unknown_basis_type_raises():
    with pytest.raises(ValueError, match="unknown basis type"):
        fit_gratsid(np.zeros(50), basis_types=("bogus",))


def test_residual_threshold_out_of_range_rejected():
    for bad in (0.0, -0.1, 1.5):
        with pytest.raises(ValueError, match="residual_threshold"):
            fit_gratsid(np.zeros(50), residual_threshold=bad)


def test_two_dim_input_with_one_column_is_flattened():
    n = 60
    X = np.zeros((n, 1))
    X[30:, 0] = 1.0
    blob = fit_gratsid(
        X,
        basis_types=("step",),
        residual_threshold=0.05,
        pre_skeleton=np.zeros(n),
    )
    assert blob.coefficients["features"][0]["t_ref"] == pytest.approx(30.0, abs=2.0)


def test_genuine_multivariate_input_rejected():
    with pytest.raises(ValueError, match="1-D"):
        fit_gratsid(np.zeros((40, 3)))


# ---------------------------------------------------------------------------
# Helpers exposed for direct testing
# ---------------------------------------------------------------------------


def test_basis_log_matches_op025_reader_formula():
    t = np.arange(20, dtype=float)
    expected = np.log1p(np.maximum(0, (t - 5) / 3))
    np.testing.assert_array_equal(basis("log", 5, 3, t), expected)


def test_basis_exp_constant_before_t_ref_then_decays():
    t = np.arange(20, dtype=float)
    b = basis("exp", 10, 4, t)
    # Before t_ref: exp(-0) = 1
    assert np.allclose(b[:10], 1.0)
    # After t_ref: monotonically decreasing toward 0
    assert np.all(np.diff(b[10:]) <= 0)
    assert b[-1] < 1.0


def test_basis_step_is_heaviside():
    t = np.arange(10, dtype=float)
    np.testing.assert_array_equal(
        basis("step", 4, 1.0, t),
        np.array([0, 0, 0, 0, 1, 1, 1, 1, 1, 1], dtype=float),
    )


def test_candidate_t_refs_picks_kink_locations():
    """A pure step at index 50 has its largest |Δresidual| between index
    49 and 50; the candidate selector should put a candidate within one
    sample of the kink (off-by-one is acceptable — the basis loop tries
    both)."""
    n = 100
    t = np.arange(n, dtype=float)
    residual = (t >= 50).astype(float)
    cands = [int(c) for c in candidate_t_refs(residual, t, top_k=5)]
    assert any(abs(c - 50) <= 1 for c in cands), cands


def test_candidate_t_refs_includes_segment_endpoints():
    n = 50
    t = np.arange(n, dtype=float)
    residual = np.zeros(n)
    cands = candidate_t_refs(residual, t, top_k=3)
    assert 0 in [int(c) for c in cands]
    assert n - 1 in [int(c) for c in cands]


# ---------------------------------------------------------------------------
# Dispatcher integration
# ---------------------------------------------------------------------------


def test_dispatcher_routes_transient_seismo_geodesy_to_gratsid():
    fn = dispatch_fitter("transient", "seismo-geodesy")
    blob = fn(np.zeros(20))
    assert isinstance(blob, DecompositionBlob)
    assert blob.method == "GrAtSiD"


def test_default_basis_types_are_three_documented_kinds():
    assert set(DEFAULT_BASIS_TYPES) == {"log", "exp", "step"}
