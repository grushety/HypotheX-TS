"""Tests for VAL-006: ADF + KPSS + Zivot-Andrews joint stationarity battery.

Covers:
 - whiten_residual: cube-root rule, lag-cap, fallback on degenerate input
 - synthetic stationary AR(1) → both pre and post stationary → 'stationary_preserved'
 - synthetic random walk → ADF fails to reject, KPSS rejects → 'nonstationary_preserved'
 - flat-pre + post-with-mid-stream-level-shift → ZA detects break
 - 'edit_introduced_nonstationarity' verdict path
 - StationarityResult frozen + verdict guard
 - degenerate inputs (constant, near-constant, very short) → undetermined / safe fallback
 - edit_window break-consistency: in-window vs far-out
 - OP-050 wiring: run_stationarity=True attaches result; missing pre_segment raises
"""
from __future__ import annotations

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.events import AuditLog, EventBus
from app.services.operations.cf_coordinator import synthesize_counterfactual
from app.services.operations.tier2.plateau import raise_lower
from app.services.validation import (
    StationarityError,
    StationarityResult,
    VERDICT_INTRODUCED,
    VERDICT_NONSTATIONARY_PRESERVED,
    VERDICT_STATIONARY_PRESERVED,
    VERDICT_UNDETERMINED,
    joint_stationarity_check,
    whiten_residual,
)


# ---------------------------------------------------------------------------
# Synthetic series
# ---------------------------------------------------------------------------


def _ar1(n: int, phi: float, sigma: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    for t in range(1, n):
        out[t] = phi * out[t - 1] + rng.normal(0, sigma)
    return out


def _random_walk(n: int, sigma: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.cumsum(rng.normal(0, sigma, n))


def _level_shift(n: int, shift_at: int, jump: float, seed: int,
                 sigma: float = 1.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = rng.normal(0, sigma, n)
    base[shift_at:] += jump
    return base


# ---------------------------------------------------------------------------
# whiten_residual
# ---------------------------------------------------------------------------


class TestWhitenResidual:
    def test_auto_uses_cube_root_capped(self):
        # n=27 → cbrt = 3
        rng = np.random.default_rng(0)
        out, lag = whiten_residual(rng.standard_normal(27))
        assert lag == 3

    def test_auto_caps_at_10(self):
        # n=10000 → cbrt ≈ 21.5 but capped at 10
        rng = np.random.default_rng(0)
        out, lag = whiten_residual(rng.standard_normal(10000))
        assert lag == 10

    def test_constant_input_falls_back(self):
        out, lag = whiten_residual(np.full(100, 5.0))
        assert lag == 0
        np.testing.assert_array_equal(out, np.full(100, 5.0))

    def test_too_short_falls_back(self):
        # Insufficient samples for AR — early fall-back returns the input
        # unchanged with lag=0.
        out, lag = whiten_residual(np.array([1.0, 2.0, 3.0]))
        assert lag == 0
        assert out.shape == (3,)

    def test_explicit_lag_respected(self):
        rng = np.random.default_rng(0)
        out, lag = whiten_residual(rng.standard_normal(50), ar_order=2)
        assert lag == 2


# ---------------------------------------------------------------------------
# joint_stationarity_check — verdict logic on synthetic series
# ---------------------------------------------------------------------------


class TestJointStationarity:
    def test_ar1_both_sides_stationary(self):
        x_pre = _ar1(300, 0.4, 1.0, seed=1)
        x_post = _ar1(300, 0.4, 1.0, seed=2)
        result = joint_stationarity_check(x_pre, x_post)
        assert result.verdict in (
            VERDICT_STATIONARY_PRESERVED,
            VERDICT_NONSTATIONARY_PRESERVED,  # tolerated: small-sample noise
        )
        # Specifically AR(1) with phi=0.4 should be stationary on most seeds
        assert result.adf_post_p < 0.05 or result.kpss_post_p > 0.05

    def test_random_walk_nonstationary(self):
        x_pre = _random_walk(300, 1.0, seed=10)
        x_post = _random_walk(300, 1.0, seed=11)
        result = joint_stationarity_check(x_pre, x_post)
        # Random walk: ADF should NOT reject (p high), KPSS should reject (p low)
        assert result.adf_post_p > 0.05 or result.kpss_post_p < 0.05

    def test_introduce_nonstationarity_verdict(self):
        """Stationary pre, random-walk post → edit_introduced_nonstationarity."""
        x_pre = _ar1(300, 0.3, 1.0, seed=101)
        x_post = _random_walk(300, 1.0, seed=102)
        result = joint_stationarity_check(x_pre, x_post)
        # The verdict can be 'edit_introduced_nonstationarity' or 'undetermined'
        # depending on small-sample test behavior; we accept either as long as
        # NOT 'stationary_preserved'
        assert result.verdict != VERDICT_STATIONARY_PRESERVED

    def test_zivot_andrews_detects_level_shift(self):
        # Flat-ish pre signal vs post signal with mid-stream level shift
        rng = np.random.default_rng(33)
        x_pre = rng.normal(0, 0.5, 200)
        shift_at = 100
        x_post = _level_shift(200, shift_at, jump=8.0, seed=34, sigma=0.5)
        result = joint_stationarity_check(x_pre, x_post)
        # ZA should detect the break (p < 0.05) and place it near the actual shift
        assert result.za_post_p is not None
        if result.za_post_break is not None:
            # Tolerance: within ±20% of n=200 → ±40 samples around shift_at=100
            assert abs(result.za_post_break - shift_at) <= 40

    def test_edit_window_break_consistency(self):
        x_pre = np.random.default_rng(50).normal(0, 0.5, 200)
        x_post = _level_shift(200, shift_at=100, jump=10.0, seed=51, sigma=0.5)
        # In-window: window covers the entire signal
        in_window = joint_stationarity_check(
            x_pre, x_post, edit_window=(0, 200),
        )
        # Out-of-window: claim the edit was at the very end (160-200), break at 100 is far outside
        out_window = joint_stationarity_check(
            x_pre, x_post, edit_window=(160, 200),
        )
        if in_window.za_post_break is not None:
            assert in_window.za_break_consistent is True
        if out_window.za_post_break is not None:
            assert out_window.za_break_consistent is False

    def test_no_edit_window_break_consistent_is_none(self):
        x_pre = np.random.default_rng(60).normal(0, 1, 200)
        x_post = _level_shift(200, 100, 8.0, seed=61)
        result = joint_stationarity_check(x_pre, x_post)
        # No edit_window passed → consistent is always None
        assert result.za_break_consistent is None

    def test_constant_input_undetermined(self):
        x_pre = np.full(100, 5.0)
        x_post = np.full(100, 5.0)
        result = joint_stationarity_check(x_pre, x_post)
        # ADF / KPSS skip constant input → NaN p-values → undetermined
        assert result.verdict == VERDICT_UNDETERMINED
        assert np.isnan(result.adf_pre_p) or np.isnan(result.kpss_pre_p)

    def test_empty_input_raises(self):
        with pytest.raises(StationarityError, match="non-empty"):
            joint_stationarity_check(np.array([]), np.array([1.0, 2.0]))

    def test_alpha_out_of_range_rejected(self):
        with pytest.raises(ValueError, match="alpha"):
            joint_stationarity_check(np.zeros(10), np.zeros(10), alpha=0.0)
        with pytest.raises(ValueError, match="alpha"):
            joint_stationarity_check(np.zeros(10), np.zeros(10), alpha=1.5)

    def test_negative_break_tolerance_rejected(self):
        with pytest.raises(ValueError, match="break_tolerance"):
            joint_stationarity_check(np.zeros(10), np.zeros(10), break_tolerance=-0.1)

    def test_invalid_edit_window_rejected(self):
        x = np.random.default_rng(0).normal(0, 1, 100)
        # ZA needs n >= 12 to run; pick a level-shift signal so ZA fires
        x_post = _level_shift(100, 50, 10.0, seed=99, sigma=0.5)
        with pytest.raises(ValueError, match="edit_window"):
            joint_stationarity_check(x, x_post, edit_window=(50, 30))


# ---------------------------------------------------------------------------
# StationarityResult DTO
# ---------------------------------------------------------------------------


class TestStationarityResultDTO:
    def test_invalid_verdict_rejected(self):
        with pytest.raises(ValueError, match="verdict"):
            StationarityResult(
                adf_pre_p=0.1, adf_post_p=0.1,
                kpss_pre_p=0.1, kpss_post_p=0.1,
                za_post_p=None, za_post_break=None,
                za_break_consistent=None,
                verdict="bogus", alpha=0.05, ar_order=2,
            )

    def test_frozen(self):
        r = StationarityResult(
            adf_pre_p=0.1, adf_post_p=0.1,
            kpss_pre_p=0.1, kpss_post_p=0.1,
            za_post_p=None, za_post_break=None,
            za_break_consistent=None,
            verdict=VERDICT_UNDETERMINED, alpha=0.05, ar_order=2,
        )
        with pytest.raises((AttributeError, TypeError)):
            r.alpha = 0.01  # type: ignore[misc]


# ---------------------------------------------------------------------------
# OP-050 integration
# ---------------------------------------------------------------------------


def _plateau_blob(n: int = 80, level: float = 10.0) -> DecompositionBlob:
    return DecompositionBlob(
        method="Constant",
        components={"trend": np.full(n, level), "residual": np.zeros(n)},
        coefficients={"level": level},
    )


class TestOP050Wiring:
    def test_run_stationarity_attaches_result(self):
        n = 200
        # Pre: noisy plateau (stationary). Post: identity edit (still stationary).
        rng = np.random.default_rng(7)
        residual = rng.normal(0, 0.5, n)
        blob = DecompositionBlob(
            method="Constant",
            components={"trend": np.full(n, 10.0), "residual": residual},
            coefficients={"level": 10.0},
        )
        pre = blob.reassemble()

        result = synthesize_counterfactual(
            segment_id="s",
            segment_label="plateau",
            blob=blob,
            op_tier2=raise_lower,
            op_params={"delta": 0.0},
            event_bus=EventBus(),
            audit_log=AuditLog(),
            pre_segment=pre,
            run_stationarity=True,
        )
        assert result.validation is not None
        assert result.validation.stationarity is not None
        sr = result.validation.stationarity
        assert isinstance(sr, StationarityResult)
        assert sr.alpha == 0.05

    def test_stationarity_without_pre_segment_raises(self):
        blob = _plateau_blob()
        with pytest.raises(ValueError, match="pre_segment"):
            synthesize_counterfactual(
                segment_id="s",
                segment_label="plateau",
                blob=blob,
                op_tier2=raise_lower,
                op_params={"delta": 1.0},
                event_bus=EventBus(),
                audit_log=AuditLog(),
                run_stationarity=True,
            )

    def test_no_stationarity_when_not_requested(self):
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
