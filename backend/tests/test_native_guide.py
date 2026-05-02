"""Tests for VAL-004: Native-Guide proximity & sparsity.

Covers:
 - proximity = 0 on identity edit (all metrics)
 - sparsity = 1 on identity edit; sparsity decreases as more steps move
 - large dense edit triggers `too_dense`
 - tiny sparse edit does NOT trigger `too_dense` (high sparsity)
 - tight metric → DTW respects equal-length and length-mismatch differently
 - percentile_rank monotonicity and edge cases
 - calibration determinism (same data → same thresholds; sorted distances)
 - thresholds JSON round-trip + bad path errors
 - thresholds metric mismatch raises in validator
 - OP-050 wiring: native_guide attached when pre_segment + thresholds supplied
 - OP-050: run_native_guide=True without thresholds → result with too_dense=False
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.events import AuditLog, EventBus
from app.services.operations.cf_coordinator import synthesize_counterfactual
from app.services.operations.tier2.plateau import raise_lower
from app.services.validation import (
    METRIC_DTW,
    METRIC_EUCLIDEAN,
    METRIC_L1,
    NativeGuideError,
    NativeGuideResult,
    NativeGuideThresholds,
    compute_nun_distances,
    load_thresholds,
    native_guide_proximity,
    native_guide_sparsity,
    native_guide_validate,
    percentile_rank,
    save_thresholds,
    thresholds_from_distances,
)


# ---------------------------------------------------------------------------
# Pure proximity
# ---------------------------------------------------------------------------


class TestProximity:
    @pytest.mark.parametrize("metric", [METRIC_DTW, METRIC_EUCLIDEAN, METRIC_L1])
    def test_zero_on_identity(self, metric):
        x = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
        assert native_guide_proximity(x, x.copy(), metric=metric) == 0.0

    def test_l1_value(self):
        a = np.array([0.0, 0.0, 0.0])
        b = np.array([1.0, 2.0, 3.0])
        assert native_guide_proximity(a, b, metric=METRIC_L1) == pytest.approx(6.0)

    def test_euclidean_value(self):
        a = np.array([0.0, 0.0])
        b = np.array([3.0, 4.0])
        assert native_guide_proximity(a, b, metric=METRIC_EUCLIDEAN) == pytest.approx(5.0)

    def test_unknown_metric_rejected(self):
        with pytest.raises(ValueError, match="metric"):
            native_guide_proximity(np.array([1.0]), np.array([1.0]), metric="bogus")

    def test_band_out_of_range_rejected(self):
        with pytest.raises(ValueError, match="dtw_band"):
            native_guide_proximity(np.array([1.0]), np.array([1.0]),
                                   metric=METRIC_DTW, dtw_band=0.0)

    def test_length_mismatch_euclidean_rejected(self):
        with pytest.raises(ValueError, match="equal-length"):
            native_guide_proximity(np.array([1.0, 2.0]), np.array([1.0]),
                                   metric=METRIC_EUCLIDEAN)


# ---------------------------------------------------------------------------
# Pure sparsity
# ---------------------------------------------------------------------------


class TestSparsity:
    def test_sparsity_one_on_identity(self):
        x = np.array([1.0, 2.0, 3.0])
        assert native_guide_sparsity(x, x.copy()) == 1.0

    def test_sparsity_decreases_as_more_change(self):
        x = np.zeros(10)
        # Change first 1 step
        b1 = x.copy()
        b1[0] = 1.0
        # Change first 5 steps
        b5 = x.copy()
        b5[:5] = 1.0
        # Change all
        b10 = np.ones(10)
        assert native_guide_sparsity(x, b1) == 0.9
        assert native_guide_sparsity(x, b5) == 0.5
        assert native_guide_sparsity(x, b10) == 0.0

    def test_eps_threshold_respected(self):
        x = np.array([1.0, 2.0])
        b = np.array([1.0 + 1e-8, 2.0])  # both within default 1e-6
        assert native_guide_sparsity(x, b) == 1.0
        # tighten eps below the perturbation
        assert native_guide_sparsity(x, b, eps_per_dim=1e-10) == 0.5

    def test_negative_eps_rejected(self):
        with pytest.raises(ValueError, match="eps_per_dim"):
            native_guide_sparsity(np.array([1.0]), np.array([1.0]), eps_per_dim=-1)

    def test_length_mismatch_rejected(self):
        with pytest.raises(ValueError, match="equal-length"):
            native_guide_sparsity(np.array([1.0, 2.0]), np.array([1.0]))


# ---------------------------------------------------------------------------
# Percentile rank
# ---------------------------------------------------------------------------


class TestPercentileRank:
    def test_below_min_returns_zero(self):
        assert percentile_rank(0.0, [1.0, 2.0, 3.0]) == 0.0

    def test_above_max_returns_one(self):
        assert percentile_rank(99.0, [1.0, 2.0, 3.0]) == 1.0

    def test_tie_counts_as_le(self):
        # value equals the largest entry → all entries are ≤ value
        assert percentile_rank(3.0, [1.0, 2.0, 3.0]) == 1.0
        # value equals the second entry → 2/3
        assert percentile_rank(2.0, [1.0, 2.0, 3.0]) == pytest.approx(2 / 3)

    def test_empty_distribution_rejected(self):
        with pytest.raises(ValueError):
            percentile_rank(1.0, [])


# ---------------------------------------------------------------------------
# Validate (combined)
# ---------------------------------------------------------------------------


def _thresholds(distances: list[float], q90: float = 1.0,
                metric: str = METRIC_DTW) -> NativeGuideThresholds:
    return NativeGuideThresholds(
        nun_distances=tuple(sorted(distances)),
        q90_nun=q90,
        metric=metric,
        dataset_name="test",
    )


class TestValidate:
    def test_no_thresholds_yields_no_flag(self):
        x = np.zeros(10)
        x_prime = np.zeros(10)
        x_prime[0] = 5.0
        result = native_guide_validate(x, x_prime, metric=METRIC_L1)
        assert result.proximity == 5.0
        assert result.sparsity == 0.9
        assert result.proximity_pct is None
        assert result.too_dense is False

    def test_dense_large_edit_triggers_too_dense(self):
        x = np.zeros(10)
        x_prime = np.full(10, 5.0)  # all changed → sparsity 0
        thr = _thresholds([1.0, 2.0, 3.0, 4.0, 5.0], q90=4.5, metric=METRIC_L1)
        result = native_guide_validate(x, x_prime, thr, metric=METRIC_L1)
        # L1 = 50, q90 = 4.5 → over; sparsity = 0 < 0.7 → too_dense
        assert result.proximity == 50.0
        assert result.sparsity == 0.0
        assert result.too_dense is True
        assert result.proximity_pct == 1.0

    def test_sparse_edit_below_q90_not_too_dense(self):
        x = np.zeros(10)
        x_prime = x.copy()
        x_prime[0] = 0.5  # one tiny change → sparsity 0.9, prox 0.5
        thr = _thresholds([1.0, 2.0, 3.0], q90=2.5, metric=METRIC_L1)
        result = native_guide_validate(x, x_prime, thr, metric=METRIC_L1)
        assert result.too_dense is False
        # sparsity 0.9 ≥ 0.7 → too_dense False even if prox > q90 (it's not here)

    def test_dense_but_below_q90_not_too_dense(self):
        x = np.zeros(10)
        x_prime = np.full(10, 0.1)  # all changed by tiny amount → L1 = 1.0
        thr = _thresholds([5.0, 6.0, 7.0], q90=6.5, metric=METRIC_L1)
        result = native_guide_validate(x, x_prime, thr, metric=METRIC_L1)
        # sparsity 0 < 0.7 BUT prox 1.0 < q90=6.5 → not too_dense
        assert result.sparsity == 0.0
        assert result.proximity == pytest.approx(1.0)
        assert result.too_dense is False

    def test_metric_mismatch_raises(self):
        x = np.zeros(5)
        thr = _thresholds([1.0], metric=METRIC_DTW)
        with pytest.raises(NativeGuideError, match="metric mismatch"):
            native_guide_validate(x, x, thr, metric=METRIC_L1)


# ---------------------------------------------------------------------------
# Threshold construction + cache
# ---------------------------------------------------------------------------


class TestThresholdConstruction:
    def test_thresholds_must_be_sorted(self):
        with pytest.raises(ValueError, match="sorted"):
            NativeGuideThresholds(
                nun_distances=(3.0, 1.0, 2.0),
                q90_nun=2.7,
                metric=METRIC_DTW,
            )

    def test_unknown_metric_rejected(self):
        with pytest.raises(ValueError, match="metric"):
            NativeGuideThresholds(
                nun_distances=(1.0,), q90_nun=1.0, metric="bogus",
            )

    def test_empty_distances_rejected(self):
        with pytest.raises(ValueError, match="at least one"):
            NativeGuideThresholds(nun_distances=(), q90_nun=0.0, metric=METRIC_DTW)

    def test_thresholds_from_distances_sorts(self):
        thr = thresholds_from_distances(
            [3.0, 1.0, 2.0, 5.0, 4.0],
            metric=METRIC_DTW, dataset_name="x",
        )
        assert thr.nun_distances == (1.0, 2.0, 3.0, 4.0, 5.0)
        assert thr.q90_nun == pytest.approx(np.quantile([1, 2, 3, 4, 5], 0.9))


class TestThresholdCache:
    def test_round_trip(self, tmp_path: Path):
        thr = thresholds_from_distances(
            [1.0, 2.0, 3.0],
            metric=METRIC_DTW, dataset_name="ECG200",
        )
        path = save_thresholds(thr, cache_dir=tmp_path)
        assert path.exists() and path.suffix == ".json"

        loaded = load_thresholds("ECG200", cache_dir=tmp_path)
        assert loaded.nun_distances == thr.nun_distances
        assert loaded.q90_nun == thr.q90_nun
        assert loaded.metric == METRIC_DTW

    def test_save_without_dataset_name_rejected(self):
        thr = NativeGuideThresholds(
            nun_distances=(1.0,), q90_nun=1.0, metric=METRIC_DTW,
        )
        with pytest.raises(NativeGuideError, match="dataset_name"):
            save_thresholds(thr)

    def test_load_missing_raises(self, tmp_path: Path):
        with pytest.raises(NativeGuideError, match="not found"):
            load_thresholds("Nope", cache_dir=tmp_path)

    def test_path_traversal_in_dataset_name_blocked(self, tmp_path: Path):
        # Pure-symbol dataset name → no chars survive sanitisation → error
        thr = NativeGuideThresholds(
            nun_distances=(1.0,), q90_nun=1.0, metric=METRIC_DTW,
            dataset_name="../!!!",
        )
        with pytest.raises(NativeGuideError, match="empty cache filename"):
            save_thresholds(thr, cache_dir=tmp_path)


# ---------------------------------------------------------------------------
# Calibration (compute_nun_distances)
# ---------------------------------------------------------------------------


class TestCalibration:
    def test_two_class_simple(self):
        # Class A: rows of 0s; Class B: rows of 1s. NUN distance for any A
        # row to any B row is sqrt(T) under Euclidean — all pairs identical.
        T = 4
        series = np.array([
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0],
            [1.0, 1.0, 1.0, 1.0],
            [1.0, 1.0, 1.0, 1.0],
        ])
        labels = np.array(["a", "a", "b", "b"])
        distances = compute_nun_distances(series, labels, metric=METRIC_EUCLIDEAN)
        expected = float(np.sqrt(T))
        assert distances == (expected, expected, expected, expected)

    def test_single_class_raises(self):
        with pytest.raises(NativeGuideError, match="unlike-neighbour"):
            compute_nun_distances(
                np.zeros((3, 4)), np.array(["a", "a", "a"]),
                metric=METRIC_EUCLIDEAN,
            )

    def test_deterministic(self):
        rng = np.random.default_rng(42)
        T = 8
        series = np.vstack([
            rng.normal(0, 0.1, (5, T)),
            rng.normal(3, 0.1, (5, T)),
        ])
        labels = np.array(["a"] * 5 + ["b"] * 5)
        d1 = compute_nun_distances(series, labels, metric=METRIC_EUCLIDEAN)
        d2 = compute_nun_distances(series, labels, metric=METRIC_EUCLIDEAN)
        assert d1 == d2
        # And the result is sorted non-decreasing
        assert list(d1) == sorted(d1)

    def test_label_length_mismatch_rejected(self):
        with pytest.raises(ValueError, match="length"):
            compute_nun_distances(
                np.zeros((3, 4)), np.array(["a", "b"]),
                metric=METRIC_EUCLIDEAN,
            )


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
    def test_native_guide_attached_when_thresholds_supplied(self):
        n = 40
        blob = _plateau_blob(n=n, level=10.0)
        x = blob.reassemble()
        thr = thresholds_from_distances(
            [1.0, 2.0, 3.0, 4.0, 5.0],
            metric=METRIC_DTW, dataset_name="t",
        )
        result = synthesize_counterfactual(
            segment_id="s",
            segment_label="plateau",
            blob=blob,
            op_tier2=raise_lower,
            op_params={"delta": 5.0},  # X_edit = 15 everywhere
            event_bus=EventBus(),
            audit_log=AuditLog(),
            pre_segment=x,
            native_guide_thresholds=thr,
            native_guide_metric=METRIC_DTW,
        )
        assert result.validation is not None
        assert result.validation.native_guide is not None
        ng: NativeGuideResult = result.validation.native_guide
        # Plateau→plateau edit changes every step → sparsity 0
        assert ng.sparsity == 0.0
        # DTW between flat-10 and flat-15 series of length 40 ≥ q90=4.5 → too_dense
        assert ng.proximity > thr.q90_nun
        assert ng.too_dense is True

    def test_run_native_guide_without_thresholds_yields_metrics_no_flag(self):
        n = 40
        blob = _plateau_blob(n=n, level=10.0)
        x = blob.reassemble()
        result = synthesize_counterfactual(
            segment_id="s",
            segment_label="plateau",
            blob=blob,
            op_tier2=raise_lower,
            op_params={"delta": 1.0},
            event_bus=EventBus(),
            audit_log=AuditLog(),
            pre_segment=x,
            run_native_guide=True,
        )
        assert result.validation is not None
        assert result.validation.native_guide is not None
        ng = result.validation.native_guide
        assert ng.proximity_pct is None
        assert ng.too_dense is False

    def test_native_guide_without_pre_segment_raises(self):
        n = 40
        blob = _plateau_blob(n=n)
        with pytest.raises(ValueError, match="pre_segment"):
            synthesize_counterfactual(
                segment_id="s",
                segment_label="plateau",
                blob=blob,
                op_tier2=raise_lower,
                op_params={"delta": 1.0},
                event_bus=EventBus(),
                audit_log=AuditLog(),
                run_native_guide=True,
            )

    def test_native_guide_absent_when_not_requested(self):
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
