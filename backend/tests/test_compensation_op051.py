"""Tests for the OP-051 compensation-mode projection."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from app.services.operations.tier3 import (
    default_compensation_mode_for_domain,
    project,
)


# ---------------------------------------------------------------------------
# Test-only constraint fixtures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SumEqualsTarget:
    """Linear scalar constraint:  sum(X) − target = 0  (Nocedal-Wright Ch. 17)."""

    target: float
    name: str = "sum_equals_target"

    def residual(self, X: np.ndarray) -> float:
        return float(np.sum(X) - self.target)

    def jacobian(self, X: np.ndarray) -> np.ndarray:
        return np.ones((1, len(X)), dtype=np.float64)

    def satisfied(self, X: np.ndarray, *, aux=None) -> bool:
        return abs(self.residual(X)) < 1e-9


@dataclass(frozen=True)
class WaterBalance:
    """4-block linear constraint: P − ET − Q − ΔS = 0  (Eckhardt 2005).

    X is laid out as concatenated ``[P, ET, Q, dS]`` blocks each of length
    ``block_size``; the residual is the per-element sum across the four
    blocks.  Jacobian is constant.
    """

    block_size: int
    name: str = "water_balance"

    def residual(self, X: np.ndarray) -> np.ndarray:
        bs = self.block_size
        P, ET, Q, dS = X[:bs], X[bs : 2 * bs], X[2 * bs : 3 * bs], X[3 * bs : 4 * bs]
        return P - ET - Q - dS

    def jacobian(self, X: np.ndarray) -> np.ndarray:
        bs = self.block_size
        I = np.eye(bs, dtype=np.float64)  # noqa: E741
        return np.hstack([I, -I, -I, -I])

    def satisfied(self, X: np.ndarray, *, aux=None) -> bool:
        return float(np.max(np.abs(self.residual(X)))) < 1e-9


@dataclass(frozen=True)
class TraceZero:
    """Trace of a 3×3 tensor stored as a flat 9-vector = 0  (Aki & Richards Ch. 3)."""

    name: str = "trace_zero"

    def residual(self, X: np.ndarray) -> float:
        return float(X[0] + X[4] + X[8])

    def jacobian(self, X: np.ndarray) -> np.ndarray:
        j = np.zeros((1, 9), dtype=np.float64)
        j[0, [0, 4, 8]] = 1.0
        return j

    def satisfied(self, X: np.ndarray, *, aux=None) -> bool:
        return abs(self.residual(X)) < 1e-9


@dataclass(frozen=True)
class SumOfSquaresEqualsTarget:
    """Nonlinear scalar constraint: ‖X‖² = target.  Tests the iterative path."""

    target: float
    name: str = "sum_of_squares"

    def residual(self, X: np.ndarray) -> float:
        return float(np.sum(X * X) - self.target)

    def jacobian(self, X: np.ndarray) -> np.ndarray:
        return (2.0 * X)[None, :]

    def satisfied(self, X: np.ndarray, *, aux=None) -> bool:
        return abs(self.residual(X)) < 1e-6


# Constraint without ``jacobian`` — exercises the numerical-Jacobian fallback.
class SumEqualsTargetNoJacobian:
    name = "sum_no_jac"

    def __init__(self, target: float) -> None:
        self.target = float(target)

    def residual(self, X: np.ndarray) -> float:
        return float(np.sum(X) - self.target)

    def satisfied(self, X: np.ndarray, *, aux=None) -> bool:
        return abs(self.residual(X)) < 1e-9


# ---------------------------------------------------------------------------
# Mode validation
# ---------------------------------------------------------------------------


def test_unknown_compensation_mode_raises():
    X = np.array([1.0, 2.0, 3.0])
    c = SumEqualsTarget(target=0.0)
    with pytest.raises(ValueError, match="compensation_mode"):
        project(X, c, compensation_mode="quantum")  # type: ignore[arg-type]


def test_local_mode_requires_segment_mask():
    X = np.array([1.0, 2.0, 3.0])
    c = SumEqualsTarget(target=0.0)
    with pytest.raises(ValueError, match="segment_mask"):
        project(X, c, compensation_mode="local")


def test_local_mode_mask_shape_mismatch_raises():
    X = np.array([1.0, 2.0, 3.0])
    c = SumEqualsTarget(target=0.0)
    with pytest.raises(ValueError, match="shape"):
        project(X, c, compensation_mode="local", segment_mask=np.array([True, False]))


# ---------------------------------------------------------------------------
# naive mode
# ---------------------------------------------------------------------------


def test_naive_returns_X_unchanged_byte_for_byte():
    X = np.array([1.0, 2.0, 3.0, 4.0])
    c = SumEqualsTarget(target=0.0)  # residual = 10
    out = project(X, c, compensation_mode="naive")
    np.testing.assert_array_equal(out, X)


def test_naive_returns_a_fresh_array_not_the_input():
    """``project`` must never alias / mutate the input."""
    X = np.array([1.0, 2.0, 3.0])
    c = SumEqualsTarget(target=0.0)
    out = project(X, c, compensation_mode="naive")
    assert out is not X
    out[0] = 999.0  # mutate result; input must stay intact
    assert X[0] == 1.0


def test_naive_does_not_call_jacobian():
    """Naive mode should never touch the constraint's Jacobian."""

    class JacobianTrap:
        name = "trap"

        def residual(self, X):
            return 0.0

        def jacobian(self, X):  # pragma: no cover — intentionally raises
            raise AssertionError("naive mode must not compute Jacobian")

        def satisfied(self, X, *, aux=None):
            return True

    project(np.array([1.0, 2.0]), JacobianTrap(), compensation_mode="naive")


# ---------------------------------------------------------------------------
# coupled mode — linear constraints converge in one Newton step
# ---------------------------------------------------------------------------


def test_coupled_zeros_linear_residual_within_tolerance():
    X = np.array([1.0, 2.0, 3.0, 4.0])  # sum = 10
    c = SumEqualsTarget(target=0.0)
    out = project(X, c, compensation_mode="coupled")
    assert abs(c.residual(out)) <= 1e-6
    # Residual was 10; minimum-norm correction subtracts 10/4 = 2.5 from each
    np.testing.assert_allclose(out, X - 2.5, atol=1e-9)


def test_coupled_water_balance_zeros_per_element_residual():
    rng = np.random.default_rng(42)
    bs = 8
    P = rng.normal(loc=10.0, scale=2.0, size=bs)
    ET = rng.normal(loc=3.0, scale=0.5, size=bs)
    Q = rng.normal(loc=2.0, scale=0.5, size=bs)
    dS = rng.normal(loc=4.0, scale=0.3, size=bs)
    X = np.concatenate([P, ET, Q, dS])
    c = WaterBalance(block_size=bs)
    out = project(X, c, compensation_mode="coupled")
    final = c.residual(out)
    assert float(np.max(np.abs(final))) <= 1e-6


def test_coupled_moment_balance_zeros_trace():
    M = np.array([1.0, 0.5, 0.0,
                  0.5, 2.0, 0.3,
                  0.0, 0.3, 3.0])  # trace = 6
    c = TraceZero()
    out = project(M, c, compensation_mode="coupled")
    assert abs(c.residual(out)) <= 1e-6
    # Off-diagonals untouched by trace-zero projection
    assert out[1] == M[1]
    assert out[2] == M[2]
    assert out[5] == M[5]


def test_coupled_minimum_norm_correction():
    """Closed-form check: Jᵀ(JJᵀ)⁻¹r is the minimum-norm correction."""
    X = np.array([1.0, 2.0, 3.0, 4.0, 5.0])  # sum = 15
    c = SumEqualsTarget(target=0.0)
    out = project(X, c, compensation_mode="coupled")
    # All elements receive identical correction = 15/5 = 3
    np.testing.assert_allclose(out, X - 3.0, atol=1e-9)


def test_coupled_already_satisfied_input_returns_X_unchanged():
    """If the constraint is already satisfied, the projector should
    short-circuit on the first iteration and return the input."""
    X = np.array([1.0, -1.0, 2.0, -2.0])  # sum = 0
    c = SumEqualsTarget(target=0.0)
    out = project(X, c, compensation_mode="coupled")
    np.testing.assert_allclose(out, X, atol=1e-12)


def test_coupled_nonlinear_constraint_converges():
    """‖X‖² = 4 starting from ‖X‖² = 14 — Newton-style iteration converges."""
    X = np.array([1.0, 2.0, 3.0])  # sum-of-squares = 14
    c = SumOfSquaresEqualsTarget(target=4.0)
    out = project(X, c, compensation_mode="coupled", tolerance=1e-6, max_iter=50)
    final = c.residual(out)
    assert abs(final) <= 1e-4  # nonlinear tolerance per docstring


# ---------------------------------------------------------------------------
# local mode — only mask values change
# ---------------------------------------------------------------------------


def test_local_preserves_values_outside_mask_byte_identical():
    X = np.array([1.0, 2.0, 3.0, 4.0, 5.0])  # sum = 15
    c = SumEqualsTarget(target=0.0)
    mask = np.array([False, False, True, True, True])
    out = project(X, c, compensation_mode="local", segment_mask=mask)
    # Indices 0 and 1 must be byte-identical to the input
    assert out[0] == X[0]
    assert out[1] == X[1]
    # Final residual ≤ tolerance
    assert abs(c.residual(out)) <= 1e-6


def test_local_distributes_residual_over_masked_indices_only():
    X = np.array([1.0, 2.0, 3.0, 4.0, 5.0])  # sum = 15
    c = SumEqualsTarget(target=0.0)
    mask = np.array([False, False, True, True, True])
    out = project(X, c, compensation_mode="local", segment_mask=mask)
    # 3 masked indices receive correction = 15/3 = 5 each
    np.testing.assert_allclose(out[2:], X[2:] - 5.0, atol=1e-9)


def test_local_full_mask_is_equivalent_to_coupled_for_linear_constraint():
    X = np.array([1.0, 2.0, 3.0, 4.0])
    c = SumEqualsTarget(target=0.0)
    mask = np.ones(len(X), dtype=bool)
    local_out = project(X, c, compensation_mode="local", segment_mask=mask)
    coupled_out = project(X, c, compensation_mode="coupled")
    np.testing.assert_allclose(local_out, coupled_out, atol=1e-12)


def test_local_all_false_mask_returns_X_unchanged_with_warning(caplog):
    """An all-False mask cannot redistribute the residual; the function
    must log a warning and return X unchanged rather than raising or
    silently returning a corrupted array."""
    X = np.array([1.0, 2.0, 3.0])  # residual = 6
    c = SumEqualsTarget(target=0.0)
    mask = np.zeros(len(X), dtype=bool)
    with caplog.at_level("WARNING"):
        out = project(X, c, compensation_mode="local", segment_mask=mask)
    np.testing.assert_array_equal(out, X)
    assert any("all-False mask" in rec.message for rec in caplog.records)


def test_local_water_balance_redistributes_within_block():
    """Restrict the mask to the ΔS block — residual should be absorbed
    entirely by ΔS, leaving P / ET / Q untouched."""
    bs = 5
    P = np.full(bs, 10.0)
    ET = np.full(bs, 3.0)
    Q = np.full(bs, 2.0)
    dS = np.full(bs, 4.0)  # residual = 10 - 3 - 2 - 4 = 1
    X = np.concatenate([P, ET, Q, dS])
    c = WaterBalance(block_size=bs)
    mask = np.zeros_like(X, dtype=bool)
    mask[3 * bs : 4 * bs] = True  # ΔS only
    out = project(X, c, compensation_mode="local", segment_mask=mask,
                  tolerance=1e-9)
    # P, ET, Q unchanged
    np.testing.assert_array_equal(out[: 3 * bs], X[: 3 * bs])
    # ΔS absorbed the entire residual
    np.testing.assert_allclose(out[3 * bs : 4 * bs], dS + 1.0, atol=1e-9)


# ---------------------------------------------------------------------------
# Numerical-Jacobian fallback (constraint without .jacobian())
# ---------------------------------------------------------------------------


def test_coupled_works_when_constraint_has_no_jacobian_method():
    X = np.array([1.0, 2.0, 3.0])
    c = SumEqualsTargetNoJacobian(target=0.0)  # no jacobian method
    out = project(X, c, compensation_mode="coupled")
    assert abs(c.residual(out)) <= 1e-6
    # Numerical Jacobian gives the same closed-form correction
    np.testing.assert_allclose(out, X - 2.0, atol=1e-5)


def test_local_works_when_constraint_has_no_jacobian_method():
    X = np.array([1.0, 2.0, 3.0, 4.0])
    c = SumEqualsTargetNoJacobian(target=0.0)
    mask = np.array([False, True, True, False])
    out = project(X, c, compensation_mode="local", segment_mask=mask)
    assert out[0] == X[0]
    assert out[3] == X[3]
    assert abs(c.residual(out)) <= 1e-6


# ---------------------------------------------------------------------------
# Convergence / max_iter behaviour for nonlinear constraints
# ---------------------------------------------------------------------------


def test_max_iter_bound_respected_for_nonconvergent_case(caplog):
    """A pathological starting point that keeps Newton overshooting —
    the function logs a warning and returns the best-so-far rather than
    raising or looping forever."""
    # Start at zero so the Jacobian (= 2X) is also zero — the first step
    # is undefined; lstsq returns zero, residual stays at -target.
    X = np.zeros(3)
    c = SumOfSquaresEqualsTarget(target=4.0)  # residual = -4
    with caplog.at_level("WARNING"):
        out = project(X, c, compensation_mode="coupled",
                      tolerance=1e-6, max_iter=3)
    # Output is finite and a fresh array
    assert np.all(np.isfinite(out))
    # A warning was logged about non-convergence
    assert any("did not converge" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Default-mode-per-domain helper
# ---------------------------------------------------------------------------


def test_default_mode_for_hydrology_is_local():
    assert default_compensation_mode_for_domain("hydrology") == "local"


def test_default_mode_for_seismo_geodesy_is_coupled():
    assert default_compensation_mode_for_domain("seismo-geodesy") == "coupled"
    assert default_compensation_mode_for_domain("seismo_geodesy") == "coupled"
    assert default_compensation_mode_for_domain("geodesy") == "coupled"


def test_default_mode_for_remote_sensing_is_local():
    assert default_compensation_mode_for_domain("remote-sensing") == "local"


def test_default_mode_for_unknown_domain_is_naive():
    assert default_compensation_mode_for_domain("unknown_domain") == "naive"


def test_default_mode_for_none_domain_is_naive():
    assert default_compensation_mode_for_domain(None) == "naive"


def test_default_mode_is_case_insensitive():
    assert default_compensation_mode_for_domain("HYDROLOGY") == "local"
    assert default_compensation_mode_for_domain("Seismo-Geodesy") == "coupled"


# ---------------------------------------------------------------------------
# Input non-mutation
# ---------------------------------------------------------------------------


def test_project_does_not_mutate_input_array():
    X = np.array([1.0, 2.0, 3.0, 4.0])
    X_copy = X.copy()
    c = SumEqualsTarget(target=0.0)
    project(X, c, compensation_mode="coupled")
    np.testing.assert_array_equal(X, X_copy)


def test_project_local_does_not_mutate_input_array():
    X = np.array([1.0, 2.0, 3.0, 4.0])
    X_copy = X.copy()
    c = SumEqualsTarget(target=0.0)
    project(X, c, compensation_mode="local",
            segment_mask=np.array([True, True, True, True]))
    np.testing.assert_array_equal(X, X_copy)


# ---------------------------------------------------------------------------
# Integration sanity — naive vs local vs coupled on the same fixture
# ---------------------------------------------------------------------------


def test_three_modes_on_water_balance_fixture_have_expected_relationships():
    """For the same residual, naive leaves it alone, local absorbs it
    inside the mask, and coupled distributes it globally — the ‖r‖
    ordering after projection is naive ≥ {local, coupled} ≈ 0."""
    bs = 4
    P = np.full(bs, 10.0)
    ET = np.full(bs, 3.0)
    Q = np.full(bs, 2.0)
    dS = np.full(bs, 4.0)  # residual per element = 1
    X = np.concatenate([P, ET, Q, dS])
    c = WaterBalance(block_size=bs)
    mask = np.zeros_like(X, dtype=bool)
    mask[3 * bs : 4 * bs] = True

    out_naive = project(X, c, compensation_mode="naive")
    out_local = project(X, c, compensation_mode="local", segment_mask=mask)
    out_coupled = project(X, c, compensation_mode="coupled")

    naive_r = float(np.linalg.norm(c.residual(out_naive)))
    local_r = float(np.linalg.norm(c.residual(out_local)))
    coupled_r = float(np.linalg.norm(c.residual(out_coupled)))

    assert naive_r > local_r and naive_r > coupled_r
    assert local_r <= 1e-6
    assert coupled_r <= 1e-6


# ---------------------------------------------------------------------------
# cf_coordinator integration — Mock-style Constraint without Jacobian still works
# ---------------------------------------------------------------------------


def test_cf_coordinator_style_constraint_works_in_naive_mode():
    """The OP-050 Constraint Protocol exposes only ``name`` / ``residual``
    / ``satisfied`` — no Jacobian.  Naive mode must accept this directly
    (no Jacobian needed) and return X unchanged."""

    class MockConstraint:
        name = "mock"

        def residual(self, X):
            return 0.5

        def satisfied(self, X, *, aux=None):
            return False

    X = np.array([1.0, 2.0, 3.0])
    out = project(X, MockConstraint(), compensation_mode="naive")
    np.testing.assert_array_equal(out, X)
