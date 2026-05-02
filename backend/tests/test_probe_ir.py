"""Tests for VAL-002: PROBE invalidation rate.

Covers:
 - linearised vs Monte-Carlo agree within 0.05 on a synthetic logistic model
 - σ sensitivity (larger σ → larger IR; monotonic)
 - linearised closed form matches Pawelczyk 2023 Eq. 5 (one-sided)
 - non-differentiable model: linearised raises; MC works
 - input validation (sigma ≤ 0; n_samples ≤ 0; bad method)
 - zero-gradient model returns IR=0
 - default σ-per-op map and helper
 - OP-050 wiring: probe_model attaches result to CFResult.validation.probe_ir
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.events import AuditLog, EventBus
from app.services.operations.cf_coordinator import synthesize_counterfactual
from app.services.operations.tier2.plateau import raise_lower
from app.services.validation import (
    DEFAULT_SIGMA,
    METHOD_LINEARISED,
    METHOD_MONTE_CARLO,
    TIER2_DEFAULT_SIGMA,
    ProbeIRResult,
    ProbeMethodError,
    default_sigma_for_op,
    probe_invalidation_rate,
)


# ---------------------------------------------------------------------------
# Synthetic models
# ---------------------------------------------------------------------------


@dataclass
class LinearLogisticModel:
    """f(x) = w·x + b; M(x) = 1{σ(f(x)) > 0.5} ⇔ 1{f(x) > 0}.

    Used as the linearised reference: ``score`` is the *logit*, ``threshold``
    is 0, and ``gradient`` of the logit w.r.t. x is exactly ``w``. So the
    linearised PROBE bound is exact for this model — Monte Carlo should
    converge to the same value as N → ∞.
    """

    w: np.ndarray
    b: float = 0.0
    threshold: float = 0.0

    def score(self, x: np.ndarray) -> float:
        return float(np.dot(self.w, np.asarray(x, dtype=np.float64).reshape(-1)) + self.b)

    def predict(self, x: np.ndarray) -> int:
        return int(self.score(x) > self.threshold)

    def gradient(self, x: np.ndarray) -> np.ndarray:  # noqa: ARG002
        return np.asarray(self.w, dtype=np.float64).reshape(-1)


class StepThreshold:
    """Non-differentiable indicator model — for MC-only path."""

    threshold = 0.0

    def score(self, x: np.ndarray) -> float:
        return float(np.sum(np.asarray(x, dtype=np.float64).reshape(-1)))

    def predict(self, x: np.ndarray) -> int:
        return int(self.score(x) > self.threshold)


def _phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ---------------------------------------------------------------------------
# Linearised closed form (Pawelczyk 2023 Eq. 5)
# ---------------------------------------------------------------------------


class TestLinearisedClosedForm:
    def test_matches_eq5_one_sided(self):
        """For linear logit and ε ~ N(0, σ²I): IR = 1 − Φ(margin / (σ ‖w‖))."""
        w = np.array([1.0, -2.0, 0.5])
        x = np.array([2.0, 1.0, 0.0])  # f0 = 2 - 2 + 0 = 0 → margin = 0
        sigma = 0.5
        result = probe_invalidation_rate(LinearLogisticModel(w=w), x, sigma=sigma)
        # margin = 0 → IR should be exactly 1 − Φ(0) = 0.5
        assert result.invalidation_rate == pytest.approx(0.5, abs=1e-12)

    def test_off_boundary_low_ir(self):
        w = np.array([1.0])
        x = np.array([5.0])  # f0 = 5, margin = 5
        sigma = 0.1  # std_f = 0.1 * 1 = 0.1; margin/std_f = 50 → IR ≈ 0
        result = probe_invalidation_rate(LinearLogisticModel(w=w), x, sigma=sigma)
        expected = 1 - _phi(5.0 / 0.1)
        assert result.invalidation_rate == pytest.approx(expected, abs=1e-12)
        assert result.invalidation_rate < 1e-10

    def test_known_value(self):
        """margin / std_f = 1 → IR = 1 − Φ(1) ≈ 0.1587."""
        w = np.array([1.0])
        x = np.array([1.0])
        sigma = 1.0  # std_f = 1; margin = 1
        result = probe_invalidation_rate(LinearLogisticModel(w=w), x, sigma=sigma)
        expected = 1 - _phi(1.0)
        assert result.invalidation_rate == pytest.approx(expected, abs=1e-12)
        assert result.invalidation_rate == pytest.approx(0.158655, abs=1e-5)

    def test_diagnostics_populated(self):
        w = np.array([3.0, 4.0])
        x = np.array([1.0, 0.0])  # f0 = 3, margin = 3, ‖w‖ = 5, std_f = 0.5
        result = probe_invalidation_rate(LinearLogisticModel(w=w), x, sigma=0.1)
        assert result.method == "linearised"
        assert result.margin == pytest.approx(3.0)
        assert result.grad_norm == pytest.approx(5.0)
        assert result.n_samples is None

    def test_zero_gradient_returns_zero(self):
        w = np.zeros(3)
        x = np.array([1.0, 1.0, 1.0])
        result = probe_invalidation_rate(LinearLogisticModel(w=w, b=10.0), x, sigma=1.0)
        assert result.invalidation_rate == 0.0
        assert result.grad_norm == 0.0


# ---------------------------------------------------------------------------
# Linearised vs Monte-Carlo agreement
# ---------------------------------------------------------------------------


class TestLinearisedVsMonteCarlo:
    def test_agree_within_0_05_margin_one(self):
        w = np.array([1.0, 1.0, 1.0])
        # Pick x so margin/std_f ≈ 1 (intermediate IR; MC variance is highest there)
        x = np.array([1.0 / 3, 1.0 / 3, 1.0 / 3])
        sigma = 1.0 / math.sqrt(3.0)  # ‖w‖ = √3, std_f = 1
        model = LinearLogisticModel(w=w)
        rng = np.random.default_rng(42)

        lin = probe_invalidation_rate(model, x, sigma=sigma, method=METHOD_LINEARISED)
        mc = probe_invalidation_rate(model, x, sigma=sigma, method=METHOD_MONTE_CARLO,
                                     n_samples=2000, rng=rng)
        assert abs(lin.invalidation_rate - mc.invalidation_rate) < 0.05

    def test_agree_far_from_boundary(self):
        w = np.array([1.0])
        x = np.array([3.0])
        sigma = 1.0  # margin/std_f = 3 → IR ≈ 0.00135
        model = LinearLogisticModel(w=w)
        rng = np.random.default_rng(7)

        lin = probe_invalidation_rate(model, x, sigma=sigma, method=METHOD_LINEARISED)
        mc = probe_invalidation_rate(model, x, sigma=sigma, method=METHOD_MONTE_CARLO,
                                     n_samples=5000, rng=rng)
        # Both should be small; agreement easy
        assert abs(lin.invalidation_rate - mc.invalidation_rate) < 0.05


# ---------------------------------------------------------------------------
# σ sensitivity
# ---------------------------------------------------------------------------


class TestSigmaSensitivity:
    def test_ir_monotonic_in_sigma(self):
        w = np.array([1.0, -1.0])
        x = np.array([1.5, 0.0])  # margin = 1.5, ‖w‖ = √2
        model = LinearLogisticModel(w=w)
        sigmas = [0.05, 0.1, 0.5, 1.0, 2.0]
        irs = [probe_invalidation_rate(model, x, sigma=s).invalidation_rate
               for s in sigmas]
        # Strictly non-decreasing, in fact strictly increasing here
        for a, b in zip(irs, irs[1:]):
            assert b > a

    def test_ir_approaches_half_as_sigma_diverges(self):
        w = np.array([1.0])
        x = np.array([0.5])
        model = LinearLogisticModel(w=w)
        ir_huge_sigma = probe_invalidation_rate(model, x, sigma=1e6).invalidation_rate
        # margin / std_f → 0 ⇒ IR → 0.5
        assert abs(ir_huge_sigma - 0.5) < 1e-3


# ---------------------------------------------------------------------------
# Method selection / fallback
# ---------------------------------------------------------------------------


class TestMethodSelection:
    def test_non_differentiable_linearised_raises(self):
        with pytest.raises(ProbeMethodError, match="model.gradient"):
            probe_invalidation_rate(StepThreshold(), np.array([1.0]), sigma=0.1,
                                    method=METHOD_LINEARISED)

    def test_non_differentiable_monte_carlo_works(self):
        rng = np.random.default_rng(0)
        result = probe_invalidation_rate(StepThreshold(), np.array([1.0]), sigma=0.5,
                                         method=METHOD_MONTE_CARLO, n_samples=300, rng=rng)
        assert 0.0 <= result.invalidation_rate <= 1.0
        assert result.method == "monte_carlo"
        assert result.n_samples == 300
        assert result.margin is None
        assert result.grad_norm is None

    def test_unknown_method_raises(self):
        with pytest.raises(ProbeMethodError, match="method must be one of"):
            probe_invalidation_rate(LinearLogisticModel(w=np.ones(1)),
                                    np.array([1.0]), method="bogus")  # type: ignore[arg-type]

    def test_gradient_shape_mismatch_raises(self):
        """Silent flatten of a wrong-length gradient would produce a meaningless IR."""

        @dataclass
        class WrongShapeGradModel:
            w: np.ndarray
            threshold: float = 0.0

            def score(self, x: np.ndarray) -> float:
                return float(np.dot(self.w[: len(x)], np.asarray(x).reshape(-1)))

            def predict(self, x: np.ndarray) -> int:
                return int(self.score(x) > self.threshold)

            def gradient(self, x: np.ndarray) -> np.ndarray:  # noqa: ARG002
                return self.w  # length 5, while x has length 3

        model = WrongShapeGradModel(w=np.ones(5))
        with pytest.raises(ProbeMethodError, match="expected"):
            probe_invalidation_rate(model, np.array([1.0, 0.0, 0.0]), sigma=0.1)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_negative_sigma_rejected(self):
        with pytest.raises(ValueError, match="sigma"):
            probe_invalidation_rate(LinearLogisticModel(w=np.ones(1)),
                                    np.array([1.0]), sigma=-0.1)

    def test_zero_sigma_rejected(self):
        with pytest.raises(ValueError, match="sigma"):
            probe_invalidation_rate(LinearLogisticModel(w=np.ones(1)),
                                    np.array([1.0]), sigma=0.0)

    def test_zero_n_samples_rejected(self):
        with pytest.raises(ValueError, match="n_samples"):
            probe_invalidation_rate(LinearLogisticModel(w=np.ones(1)),
                                    np.array([1.0]), method=METHOD_MONTE_CARLO,
                                    n_samples=0)

    def test_invalid_ir_in_dto_rejected(self):
        with pytest.raises(ValueError, match="invalidation_rate"):
            ProbeIRResult(invalidation_rate=1.5, sigma=0.1, method=METHOD_LINEARISED)

    def test_invalid_method_in_dto_rejected(self):
        with pytest.raises(ProbeMethodError, match="method must be one of"):
            ProbeIRResult(invalidation_rate=0.1, sigma=0.1, method="bogus")


# ---------------------------------------------------------------------------
# Default σ map
# ---------------------------------------------------------------------------


class TestDefaultSigmaMap:
    def test_known_op_returns_mapped_value(self):
        for op, sigma in TIER2_DEFAULT_SIGMA.items():
            assert default_sigma_for_op(op) == sigma

    def test_unknown_op_falls_back(self):
        assert default_sigma_for_op("not_a_real_op") == DEFAULT_SIGMA


# ---------------------------------------------------------------------------
# OP-050 integration
# ---------------------------------------------------------------------------


def _plateau_blob(n: int = 40, level: float = 10.0) -> DecompositionBlob:
    return DecompositionBlob(
        method="Constant",
        components={"trend": np.full(n, level), "residual": np.zeros(n)},
        coefficients={"level": level},
    )


class _SeriesLogit:
    """Linear logit on the segment values: f(x) = mean(x) − τ."""

    threshold = 12.0

    def score(self, x: np.ndarray) -> float:
        return float(np.mean(np.asarray(x, dtype=np.float64).reshape(-1)))

    def predict(self, x: np.ndarray) -> int:
        return int(self.score(x) > self.threshold)

    def gradient(self, x: np.ndarray) -> np.ndarray:
        flat = np.asarray(x, dtype=np.float64).reshape(-1)
        return np.full_like(flat, 1.0 / flat.shape[0])


class TestOP050Wiring:
    def test_probe_ir_attached_to_validation(self):
        blob = _plateau_blob(n=40, level=11.0)
        result = synthesize_counterfactual(
            segment_id="s",
            segment_label="plateau",
            blob=blob,
            op_tier2=raise_lower,
            op_params={"delta": 1.0},  # → mean(X_edit) = 12, exactly on threshold
            event_bus=EventBus(),
            audit_log=AuditLog(),
            probe_model=_SeriesLogit(),
            probe_sigma=0.5,
        )
        assert result.validation is not None
        assert result.validation.conformal is None
        assert result.validation.probe_ir is not None
        # margin = 0 → IR exactly 0.5 under the linear logit
        assert result.validation.probe_ir.invalidation_rate == pytest.approx(0.5, abs=1e-9)
        assert result.validation.probe_ir.method == "linearised"

    def test_probe_default_sigma_falls_back_to_op_map(self):
        blob = _plateau_blob(n=40, level=11.0)
        result = synthesize_counterfactual(
            segment_id="s",
            segment_label="plateau",
            blob=blob,
            op_tier2=raise_lower,
            op_params={"delta": 1.0},
            event_bus=EventBus(),
            audit_log=AuditLog(),
            probe_model=_SeriesLogit(),
        )
        assert result.validation is not None
        assert result.validation.probe_ir is not None
        # ``raise_lower`` default σ = 0.05 per TIER2_DEFAULT_SIGMA
        assert result.validation.probe_ir.sigma == pytest.approx(
            TIER2_DEFAULT_SIGMA["raise_lower"]
        )

    def test_no_probe_when_model_absent(self):
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
