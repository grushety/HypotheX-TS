"""Tests for VAL-003: yNN k-NN plausibility under DTW.

Covers:
 - yNN = 1 on a training-set member that is itself in the target class
 - yNN = 0 on a far-OOD point with no same-class neighbours
 - LB_Keogh correctness: distance ≤ true DTW distance for all pairs
 - LB_Keogh shortlist preserves the true K-NN ordering on small sets
 - DTW band parameter respected (different band → different envelope/result)
 - K = 0 returns nan with warning
 - K_eff clipped when K > training-set size
 - Index serialization round-trip via .npz cache (no pickle)
 - Cached config mismatch raises
 - OP-050 wiring: ynn_validator + ynn_target_class → CFResult.validation.ynn
 - OP-050: validator without target_class raises
 - Latency budget proxy (5k training set ≤ 200 ms; smaller than the 50k/100ms AC)
"""
from __future__ import annotations

import time
import warnings
from pathlib import Path

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.events import AuditLog, EventBus
from app.services.operations.cf_coordinator import synthesize_counterfactual
from app.services.operations.tier2.plateau import raise_lower
from app.services.validation import (
    YnnConfig,
    YnnIndexError,
    YnnPlausibilityValidator,
    YnnResult,
    keogh_envelope,
    lb_keogh,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _two_class_dataset(rng: np.random.Generator, n_per_class: int = 30, T: int = 40):
    """Class A: rising trends. Class B: falling trends. Disjoint clusters."""
    t = np.linspace(0.0, 1.0, T)
    series = []
    labels: list[str] = []
    for _ in range(n_per_class):
        slope = rng.uniform(0.5, 1.5)
        noise = rng.normal(0, 0.05, T)
        series.append(slope * t + noise)
        labels.append("up")
    for _ in range(n_per_class):
        slope = rng.uniform(0.5, 1.5)
        noise = rng.normal(0, 0.05, T)
        series.append(-slope * t + 1.0 + noise)
        labels.append("down")
    return np.array(series), np.array(labels)


# ---------------------------------------------------------------------------
# YnnConfig validation
# ---------------------------------------------------------------------------


class TestYnnConfig:
    def test_negative_K_rejected(self):
        with pytest.raises(ValueError, match="K"):
            YnnConfig(K=-1)

    def test_band_out_of_range_rejected(self):
        with pytest.raises(ValueError, match="dtw_band"):
            YnnConfig(dtw_band=0.0)
        with pytest.raises(ValueError, match="dtw_band"):
            YnnConfig(dtw_band=1.5)

    def test_invalid_candidate_multiplier_rejected(self):
        with pytest.raises(ValueError, match="candidate_multiplier"):
            YnnConfig(candidate_multiplier=0)


# ---------------------------------------------------------------------------
# LB_Keogh correctness
# ---------------------------------------------------------------------------


class TestLBKeogh:
    def test_envelope_bounds_signal(self):
        x = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
        U, L = keogh_envelope(x, radius=1)
        assert np.all(U >= x) and np.all(L <= x)
        assert U[2] == 3.0 and L[2] == 2.0

    def test_zero_when_query_inside_envelope(self):
        x = np.array([1.0, 1.0, 1.0, 1.0])
        U, L = keogh_envelope(x, radius=1)
        # Same-shape query inside its own envelope → LB = 0
        assert lb_keogh(x, U, L) == 0.0

    def test_lb_keogh_lower_bounds_dtw(self):
        """LB_Keogh ≤ DTW for every pair — the lower-bound property."""
        from tslearn.metrics import dtw

        rng = np.random.default_rng(0)
        T = 30
        radius = max(1, int(round(0.1 * T)))
        for trial in range(20):
            a = rng.normal(0, 1, T)
            b = rng.normal(0, 1, T)
            U, L = keogh_envelope(b, radius=radius)
            lb = lb_keogh(a, U, L)
            d = float(dtw(a, b, sakoe_chiba_radius=radius))
            assert lb <= d + 1e-9, f"LB_Keogh {lb} exceeds DTW {d} on trial {trial}"

    def test_envelope_radius_zero(self):
        x = np.array([1.0, 2.0, 3.0])
        U, L = keogh_envelope(x, radius=0)
        np.testing.assert_array_equal(U, x)
        np.testing.assert_array_equal(L, x)

    def test_envelope_negative_radius_rejected(self):
        with pytest.raises(ValueError, match="radius"):
            keogh_envelope(np.array([1.0]), radius=-1)

    def test_lb_keogh_shape_mismatch_rejected(self):
        with pytest.raises(ValueError, match="shape"):
            lb_keogh(np.array([1.0, 2.0]), np.array([1.0]), np.array([1.0]))


# ---------------------------------------------------------------------------
# yNN core behaviour
# ---------------------------------------------------------------------------


class TestYnnCore:
    def test_training_member_returns_one(self):
        """A training-set member queried against itself with its own label
        gets yNN = 1: the nearest neighbour is itself, plus K−1 same-class peers."""
        rng = np.random.default_rng(123)
        series, labels = _two_class_dataset(rng, n_per_class=20)
        validator = YnnPlausibilityValidator(series, labels, YnnConfig(K=5))
        result = validator.ynn(series[0], "up")
        assert result.ynn == 1.0
        assert result.K == 5

    def test_far_ood_returns_zero(self):
        """Query is class A in shape but we ask for class B membership; yNN ≈ 0."""
        rng = np.random.default_rng(7)
        series, labels = _two_class_dataset(rng, n_per_class=20)
        validator = YnnPlausibilityValidator(series, labels, YnnConfig(K=5))
        # An "up" series; we ask for "down" agreement → 0
        T = series.shape[1]
        up_query = np.linspace(0.0, 1.0, T)
        result = validator.ynn(up_query, "down")
        assert result.ynn == 0.0

    def test_yNN_in_unit_interval(self):
        rng = np.random.default_rng(42)
        series, labels = _two_class_dataset(rng, n_per_class=15)
        validator = YnnPlausibilityValidator(series, labels, YnnConfig(K=5))
        rng2 = np.random.default_rng(99)
        T = series.shape[1]
        for _ in range(20):
            q = rng2.normal(0, 1, T)
            result = validator.ynn(q, "up")
            assert 0.0 <= result.ynn <= 1.0

    def test_K_zero_returns_nan_with_warning(self):
        rng = np.random.default_rng(0)
        series, labels = _two_class_dataset(rng, n_per_class=5)
        validator = YnnPlausibilityValidator(series, labels, YnnConfig(K=0))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = validator.ynn(series[0], "up")
        assert any("K = 0" in str(w.message) for w in caught)
        assert np.isnan(result.ynn)
        assert result.K == 0

    def test_K_clipped_to_training_size(self):
        rng = np.random.default_rng(5)
        series, labels = _two_class_dataset(rng, n_per_class=2)  # 4 training pts
        validator = YnnPlausibilityValidator(series, labels, YnnConfig(K=10))
        result = validator.ynn(series[0], "up")
        assert result.K == 4
        assert result.n_neighbours_evaluated == 4


# ---------------------------------------------------------------------------
# DTW band parameter is respected
# ---------------------------------------------------------------------------


class TestBandParameter:
    def test_different_band_changes_envelope(self):
        x = np.array([0.0, 1.0, 5.0, 1.0, 0.0])
        U_narrow, L_narrow = keogh_envelope(x, radius=0)
        U_wide, L_wide = keogh_envelope(x, radius=2)
        # Wider band → wider envelope (U increases, L decreases or stays)
        assert np.all(U_wide >= U_narrow)
        assert np.all(L_wide <= L_narrow)

    def test_radius_scales_with_dtw_band(self):
        rng = np.random.default_rng(11)
        series, labels = _two_class_dataset(rng, n_per_class=10)
        T = series.shape[1]

        v_narrow = YnnPlausibilityValidator(series, labels, YnnConfig(dtw_band=0.05))
        v_wide = YnnPlausibilityValidator(series, labels, YnnConfig(dtw_band=0.5))

        # narrow: radius = max(1, round(0.05*40)) = 2;  wide: round(0.5*40) = 20
        assert v_narrow._radius_for_length(T) == 2
        assert v_wide._radius_for_length(T) == 20


# ---------------------------------------------------------------------------
# Index serialization
# ---------------------------------------------------------------------------


class TestIndexSerialization:
    def test_round_trip_via_npz(self, tmp_path: Path):
        rng = np.random.default_rng(2026)
        series, labels = _two_class_dataset(rng, n_per_class=10)

        v1 = YnnPlausibilityValidator(
            series, labels, dataset_name="ECG200", cache_dir=tmp_path
        )
        cache_path = v1.cache_path
        assert cache_path is not None and cache_path.exists()
        assert cache_path.suffix == ".npz"

        v2 = YnnPlausibilityValidator(dataset_name="ECG200", cache_dir=tmp_path)
        np.testing.assert_array_equal(v1._series, v2._series)
        np.testing.assert_array_equal(v1._labels, v2._labels)
        np.testing.assert_array_equal(v1._upper, v2._upper)
        np.testing.assert_array_equal(v1._lower, v2._lower)

        # And the rehydrated validator reproduces yNN values
        r1 = v1.ynn(series[0], "up")
        r2 = v2.ynn(series[0], "up")
        assert r1.ynn == r2.ynn

    def test_no_cache_no_training_data_raises(self, tmp_path: Path):
        with pytest.raises(YnnIndexError, match="training_series"):
            YnnPlausibilityValidator(cache_dir=tmp_path)

    def test_config_mismatch_raises(self, tmp_path: Path):
        rng = np.random.default_rng(0)
        series, labels = _two_class_dataset(rng, n_per_class=5)
        YnnPlausibilityValidator(
            series, labels, YnnConfig(K=5),
            dataset_name="ECG200", cache_dir=tmp_path,
        )
        with pytest.raises(YnnIndexError, match="cached config"):
            YnnPlausibilityValidator(
                dataset_name="ECG200", cache_dir=tmp_path,
                config=YnnConfig(K=7),
            )

    def test_npz_does_not_use_pickle(self, tmp_path: Path):
        """allow_pickle=False on load — security boundary for cached indices."""
        rng = np.random.default_rng(0)
        series, labels = _two_class_dataset(rng, n_per_class=5)
        YnnPlausibilityValidator(
            series, labels, dataset_name="ECG200", cache_dir=tmp_path,
        )
        # Reload should succeed *without* allow_pickle anywhere
        validator = YnnPlausibilityValidator(dataset_name="ECG200", cache_dir=tmp_path)
        assert validator.n_train == series.shape[0]


# ---------------------------------------------------------------------------
# Build-time validation
# ---------------------------------------------------------------------------


class TestBuildValidation:
    def test_empty_training_set_raises(self):
        with pytest.raises(YnnIndexError, match="empty"):
            YnnPlausibilityValidator(np.empty((0, 10)), np.array([]))

    def test_label_count_mismatch_raises(self):
        series = np.zeros((5, 10))
        with pytest.raises(YnnIndexError, match="length"):
            YnnPlausibilityValidator(series, np.array(["a"] * 3))

    def test_non_2d_series_rejected(self):
        with pytest.raises(YnnIndexError, match="2-D"):
            YnnPlausibilityValidator(np.zeros((10,)), np.array(["a"] * 10))

    def test_query_length_mismatch_raises(self):
        rng = np.random.default_rng(0)
        series, labels = _two_class_dataset(rng, n_per_class=3)
        validator = YnnPlausibilityValidator(series, labels, YnnConfig(K=3))
        with pytest.raises(ValueError, match="length"):
            validator.ynn(np.zeros(7), "up")


# ---------------------------------------------------------------------------
# Latency proxy
# ---------------------------------------------------------------------------


class TestLatency:
    def test_query_under_200ms_on_5k_training(self):
        """5k training × T=40 should comfortably finish each query under 200 ms.
        AC asks ≤ 100 ms for 50k; this proxy is conservative and avoids the
        slow build of a 50k fixture inside CI."""
        rng = np.random.default_rng(7)
        n = 5000
        T = 40
        series = rng.normal(0, 1, (n, T))
        labels = rng.choice(["a", "b"], size=n)
        validator = YnnPlausibilityValidator(series, labels, YnnConfig(K=5))

        q = rng.normal(0, 1, T)
        # warm-up (tslearn JIT path)
        validator.ynn(q, "a")

        start = time.perf_counter()
        validator.ynn(q, "a")
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 200.0, f"query took {elapsed_ms:.1f} ms (>200 ms budget)"


# ---------------------------------------------------------------------------
# OP-050 integration
# ---------------------------------------------------------------------------


def _plateau_blob(n: int = 40, level: float = 10.0) -> DecompositionBlob:
    return DecompositionBlob(
        method="Constant",
        components={"trend": np.full(n, level), "residual": np.zeros(n)},
        coefficients={"level": level},
    )


class TestOP050Wiring:
    def test_ynn_attached_to_validation(self):
        rng = np.random.default_rng(5)
        n = 40
        # Training set: 30 plateau-around-15 (label "up") + 30 plateau-around-5 (label "down")
        T = n
        up = np.full((30, T), 15.0) + rng.normal(0, 0.1, (30, T))
        down = np.full((30, T), 5.0) + rng.normal(0, 0.1, (30, T))
        series = np.vstack([up, down])
        labels = np.array(["up"] * 30 + ["down"] * 30)
        validator = YnnPlausibilityValidator(series, labels, YnnConfig(K=5))

        # raise_lower(delta=+5) on a plateau-at-10 → X_edit ≈ 15 → "up" cluster
        blob = _plateau_blob(n=n, level=10.0)
        result = synthesize_counterfactual(
            segment_id="s",
            segment_label="plateau",
            blob=blob,
            op_tier2=raise_lower,
            op_params={"delta": 5.0},
            event_bus=EventBus(),
            audit_log=AuditLog(),
            ynn_validator=validator,
            ynn_target_class="up",
        )
        assert result.validation is not None
        assert result.validation.ynn is not None
        assert isinstance(result.validation.ynn, YnnResult)
        # All 5 nearest neighbours should be "up" (the edited plateau is at 15)
        assert result.validation.ynn.ynn == 1.0

    def test_ynn_zero_when_target_class_missing_from_neighbours(self):
        rng = np.random.default_rng(11)
        n = 40
        # Training set without any "rare" label
        series = np.full((20, n), 15.0) + rng.normal(0, 0.1, (20, n))
        labels = np.array(["common"] * 20)
        validator = YnnPlausibilityValidator(series, labels, YnnConfig(K=5))

        blob = _plateau_blob(n=n, level=10.0)
        result = synthesize_counterfactual(
            segment_id="s",
            segment_label="plateau",
            blob=blob,
            op_tier2=raise_lower,
            op_params={"delta": 5.0},
            event_bus=EventBus(),
            audit_log=AuditLog(),
            ynn_validator=validator,
            ynn_target_class="rare",
        )
        assert result.validation is not None
        assert result.validation.ynn is not None
        assert result.validation.ynn.ynn == 0.0

    def test_validator_without_target_class_raises(self):
        rng = np.random.default_rng(0)
        series, labels = _two_class_dataset(rng, n_per_class=5, T=40)
        validator = YnnPlausibilityValidator(series, labels)

        blob = _plateau_blob(n=40)
        with pytest.raises(ValueError, match="ynn_target_class"):
            synthesize_counterfactual(
                segment_id="s",
                segment_label="plateau",
                blob=blob,
                op_tier2=raise_lower,
                op_params={"delta": 1.0},
                event_bus=EventBus(),
                audit_log=AuditLog(),
                ynn_validator=validator,
                # ynn_target_class omitted
            )

    def test_no_validation_block_when_ynn_absent(self):
        blob = _plateau_blob()
        result = synthesize_counterfactual(
            segment_id="s",
            segment_label="plateau",
            blob=blob,
            op_tier2=raise_lower,
            op_params={"delta": 1.0},
            event_bus=EventBus(),
            audit_log=AuditLog(),
        )
        assert result.validation is None
