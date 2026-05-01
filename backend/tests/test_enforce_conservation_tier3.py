"""Tests for the OP-032 enforce_conservation Tier-3 operation."""
from __future__ import annotations

import math

import numpy as np
import pytest

from app.services.events import AuditLog, EventBus
from app.services.operations.tier3 import (
    DEFAULT_TOLERANCE,
    HARD_LAWS,
    LAW_REGISTRY,
    SOFT_LAWS,
    ConservationAudit,
    ConservationResult,
    UnknownLaw,
    enforce_conservation,
    register_law,
)


RNG = np.random.default_rng(42)


def _isolated_bus() -> tuple[EventBus, AuditLog]:
    return EventBus(), AuditLog()


# ---------------------------------------------------------------------------
# Registry / dispatcher
# ---------------------------------------------------------------------------


def test_all_four_laws_registered():
    for law in ("water_balance", "moment_balance", "phase_closure", "nnr_frame"):
        assert law in LAW_REGISTRY, f"missing law {law!r}"


def test_hard_and_soft_law_partition_is_consistent():
    """Every registered law is either hard or soft, not both."""
    for law in LAW_REGISTRY:
        assert law in HARD_LAWS or law in SOFT_LAWS, (
            f"law {law!r} not classified as hard or soft"
        )
        assert not (law in HARD_LAWS and law in SOFT_LAWS), (
            f"law {law!r} classified as both hard and soft"
        )


def test_unknown_law_raises_unknown_law_error():
    bus, log = _isolated_bus()
    with pytest.raises(UnknownLaw):
        enforce_conservation({}, "not_a_real_law", event_bus=bus, audit_log=log)


def test_unknown_compensation_mode_raises_value_error():
    bus, log = _isolated_bus()
    with pytest.raises(ValueError, match="compensation_mode"):
        enforce_conservation(
            {"P": np.zeros(5), "ET": np.zeros(5), "Q": np.zeros(5), "dS": np.zeros(5)},
            "water_balance",
            compensation_mode="quantum",
            event_bus=bus, audit_log=log,
        )


def test_register_law_decorator_adds_to_registry():
    @register_law("__test_law_temp__")
    def _fake(X_all, mode, aux):
        return X_all, 0.0, 0.0

    try:
        assert "__test_law_temp__" in LAW_REGISTRY
        assert LAW_REGISTRY["__test_law_temp__"] is _fake
    finally:
        del LAW_REGISTRY["__test_law_temp__"]


# ---------------------------------------------------------------------------
# water_balance — soft law
# ---------------------------------------------------------------------------


def test_water_balance_local_zeroes_residual_below_1e_minus_6():
    """AC: synthetic (P, ET, Q, dS) with known residual; post-projection
    residual < 1e-6 in any non-naive mode."""
    P = np.array([10.0, 12.0, 8.0])
    ET = np.array([3.0, 4.0, 2.0])
    Q = np.array([2.0, 3.0, 1.0])
    dS = np.array([4.0, 4.0, 4.0])
    bus, log = _isolated_bus()

    X_edit, result = enforce_conservation(
        {"P": P, "ET": ET, "Q": Q, "dS": dS},
        "water_balance",
        compensation_mode="local",
        event_bus=bus, audit_log=log,
    )
    final = X_edit["P"] - X_edit["ET"] - X_edit["Q"] - X_edit["dS"]
    assert np.max(np.abs(final)) < 1e-6
    assert result.converged is True


def test_water_balance_coupled_distributes_residual_evenly():
    P = np.array([10.0])
    ET = np.array([3.0])
    Q = np.array([2.0])
    dS = np.array([4.0])  # residual = 10 - 3 - 2 - 4 = 1
    bus, log = _isolated_bus()

    X_edit, result = enforce_conservation(
        {"P": P, "ET": ET, "Q": Q, "dS": dS},
        "water_balance",
        compensation_mode="coupled",
        event_bus=bus, audit_log=log,
    )
    expected_delta = 1.0 / 4.0
    assert X_edit["P"][0] == pytest.approx(10.0 - expected_delta)
    assert X_edit["ET"][0] == pytest.approx(3.0 + expected_delta)
    assert X_edit["Q"][0] == pytest.approx(2.0 + expected_delta)
    assert X_edit["dS"][0] == pytest.approx(4.0 + expected_delta)
    assert result.converged is True


def test_water_balance_naive_does_not_modify_signals():
    P = np.array([10.0])
    ET = np.array([3.0])
    Q = np.array([2.0])
    dS = np.array([4.0])
    bus, log = _isolated_bus()

    X_edit, result = enforce_conservation(
        {"P": P, "ET": ET, "Q": Q, "dS": dS},
        "water_balance",
        compensation_mode="naive",
        event_bus=bus, audit_log=log,
    )
    assert X_edit["P"][0] == 10.0
    assert X_edit["dS"][0] == 4.0
    # Naive ⇒ initial == final residual
    assert result.initial_residual == result.final_residual


def test_water_balance_already_balanced_input_stays_balanced():
    P = np.array([5.0])
    ET = np.array([1.0])
    Q = np.array([1.0])
    dS = np.array([3.0])  # residual = 0
    bus, log = _isolated_bus()
    _, result = enforce_conservation(
        {"P": P, "ET": ET, "Q": Q, "dS": dS},
        "water_balance",
        compensation_mode="coupled",
        event_bus=bus, audit_log=log,
    )
    assert result.converged is True


# ---------------------------------------------------------------------------
# moment_balance — soft law
# ---------------------------------------------------------------------------


def test_moment_balance_local_zeroes_trace():
    """AC: Mxx + Myy + Mzz != 0; post-projection == 0 within tolerance."""
    M = np.array([
        [1.0, 0.5, 0.0],
        [0.5, 2.0, 0.3],
        [0.0, 0.3, 3.0],  # trace = 6
    ])
    bus, log = _isolated_bus()
    X_edit, result = enforce_conservation(
        {"M": M},
        "moment_balance",
        compensation_mode="local",
        event_bus=bus, audit_log=log,
    )
    M_new = X_edit["M"]
    assert math.isclose(np.trace(M_new), 0.0, abs_tol=1e-9)
    assert result.converged is True


def test_moment_balance_coupled_subtracts_trace_over_three_per_diagonal():
    M = np.diag([1.0, 2.0, 3.0])  # trace = 6
    bus, log = _isolated_bus()
    X_edit, _ = enforce_conservation(
        {"M": M},
        "moment_balance",
        compensation_mode="coupled",
        event_bus=bus, audit_log=log,
    )
    M_new = X_edit["M"]
    np.testing.assert_allclose(np.diag(M_new), [-1.0, 0.0, 1.0], atol=1e-9)
    assert math.isclose(np.trace(M_new), 0.0, abs_tol=1e-9)


def test_moment_balance_local_only_modifies_mzz():
    M = np.diag([1.0, 2.0, 3.0])
    bus, log = _isolated_bus()
    X_edit, _ = enforce_conservation(
        {"M": M},
        "moment_balance",
        compensation_mode="local",
        event_bus=bus, audit_log=log,
    )
    M_new = X_edit["M"]
    # Mxx, Myy unchanged in local mode
    assert M_new[0, 0] == 1.0
    assert M_new[1, 1] == 2.0
    assert M_new[2, 2] == pytest.approx(3.0 - 6.0)


def test_moment_balance_off_diagonal_preserved():
    M = np.array([
        [1.0, 0.5, -0.2],
        [0.5, 2.0, 0.3],
        [-0.2, 0.3, 3.0],
    ])
    bus, log = _isolated_bus()
    X_edit, _ = enforce_conservation(
        {"M": M},
        "moment_balance",
        compensation_mode="coupled",
        event_bus=bus, audit_log=log,
    )
    M_new = X_edit["M"]
    # Off-diagonals untouched by trace-zero projection
    assert M_new[0, 1] == 0.5
    assert M_new[0, 2] == -0.2
    assert M_new[1, 2] == 0.3


def test_moment_balance_invalid_shape_raises():
    bus, log = _isolated_bus()
    with pytest.raises(ValueError, match=r"\(3,3\)"):
        enforce_conservation(
            {"M": np.zeros((2, 2))},
            "moment_balance",
            compensation_mode="local",
            event_bus=bus, audit_log=log,
        )


# ---------------------------------------------------------------------------
# phase_closure — hard law
# ---------------------------------------------------------------------------


def test_phase_closure_coupled_drives_residual_below_tolerance():
    """AC: three interferograms with deliberate closure error; post-projection
    closure ≤ 0.1 rad."""
    n = 50
    base = np.linspace(0.0, 1.0, n)
    p12 = base.copy()
    p23 = base.copy() + 0.5
    p13 = base.copy() + 1.0  # so closure = p12+p23-p13 = 0.5 rad (fixed)

    # Add deliberate closure error of 0.3 rad
    p13 = p13 - 0.3
    bus, log = _isolated_bus()
    _, result = enforce_conservation(
        {"phi_12": p12, "phi_23": p23, "phi_13": p13},
        "phase_closure",
        compensation_mode="coupled",
        event_bus=bus, audit_log=log,
    )
    assert np.max(np.abs(result.final_residual)) <= 0.1
    assert result.converged is True


def test_phase_closure_local_drives_residual_to_zero():
    p12 = np.array([0.5])
    p23 = np.array([0.4])
    p13 = np.array([0.6])  # closure = 0.5 + 0.4 - 0.6 = 0.3 rad
    bus, log = _isolated_bus()
    X_edit, result = enforce_conservation(
        {"phi_12": p12, "phi_23": p23, "phi_13": p13},
        "phase_closure",
        compensation_mode="local",
        event_bus=bus, audit_log=log,
    )
    assert np.max(np.abs(result.final_residual)) <= 1e-9
    # local mode adds the closure to phi_13: phi_13_new = 0.6 + 0.3 = 0.9
    assert X_edit["phi_13"][0] == pytest.approx(0.9)
    # phi_12, phi_23 unchanged
    assert X_edit["phi_12"][0] == 0.5
    assert X_edit["phi_23"][0] == 0.4


def test_phase_closure_naive_reports_initial_residual_unchanged():
    p12 = np.array([0.5])
    p23 = np.array([0.4])
    p13 = np.array([0.6])
    bus, log = _isolated_bus()
    _, result = enforce_conservation(
        {"phi_12": p12, "phi_23": p23, "phi_13": p13},
        "phase_closure",
        compensation_mode="naive",
        event_bus=bus, audit_log=log,
    )
    assert result.initial_residual == result.final_residual


def test_phase_closure_wraps_2pi_ambiguity():
    """A closure of ~2π should wrap to ~0 — projection is a no-op (already
    closed modulo 2π)."""
    p12 = np.array([0.0])
    p23 = np.array([0.0])
    # closure = 0 + 0 - (-2π) = 2π → wraps to 0
    p13 = np.array([-2.0 * math.pi + 1e-12])
    bus, log = _isolated_bus()
    _, result = enforce_conservation(
        {"phi_12": p12, "phi_23": p23, "phi_13": p13},
        "phase_closure",
        compensation_mode="naive",
        event_bus=bus, audit_log=log,
    )
    assert abs(float(np.asarray(result.initial_residual).item())) < 1e-6


def test_phase_closure_is_a_hard_law():
    assert "phase_closure" in HARD_LAWS


# ---------------------------------------------------------------------------
# nnr_frame — hard law
# ---------------------------------------------------------------------------


def test_nnr_frame_subtracts_net_rotation():
    """AC: three stations with net rotation; post-projection NNR satisfied.

    Construct positions in 3-D and synthetic velocities = ω_known × r so the
    projection should recover ω_known and zero the residual."""
    positions = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ])
    omega_true = np.array([0.0, 0.0, 0.5])  # rotation about z
    velocities = np.cross(omega_true[None, :], positions)
    bus, log = _isolated_bus()
    X_edit, result = enforce_conservation(
        {"positions": positions, "velocities": velocities},
        "nnr_frame",
        compensation_mode="coupled",
        event_bus=bus, audit_log=log,
    )
    assert np.max(np.abs(result.final_residual)) <= 1e-9
    np.testing.assert_allclose(X_edit["velocities"], np.zeros_like(velocities), atol=1e-9)
    assert result.converged is True


def test_nnr_frame_no_rotation_input_passes_through():
    """A pure-translation field (each station has the same velocity) has
    Σ r × v non-zero in general, but NNR projects out the global rotation
    only; the per-station velocity should change minimally if there is no
    coherent rotation in the field."""
    positions = np.array([
        [2.0, 0.0, 0.0],
        [0.0, 2.0, 0.0],
        [0.0, 0.0, 2.0],
    ])
    velocities = np.zeros_like(positions)
    bus, log = _isolated_bus()
    _, result = enforce_conservation(
        {"positions": positions, "velocities": velocities},
        "nnr_frame",
        compensation_mode="coupled",
        event_bus=bus, audit_log=log,
    )
    assert np.max(np.abs(result.initial_residual)) < 1e-9
    assert np.max(np.abs(result.final_residual)) < 1e-9


def test_nnr_frame_naive_reports_residual_without_correcting():
    positions = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ])
    velocities = np.cross(np.array([0.0, 0.0, 0.5])[None, :], positions)
    bus, log = _isolated_bus()
    X_edit, result = enforce_conservation(
        {"positions": positions, "velocities": velocities},
        "nnr_frame",
        compensation_mode="naive",
        event_bus=bus, audit_log=log,
    )
    np.testing.assert_array_equal(X_edit["velocities"], velocities)
    assert result.initial_residual == result.final_residual


def test_nnr_frame_requires_at_least_three_stations():
    bus, log = _isolated_bus()
    with pytest.raises(ValueError, match="at least 3 stations"):
        enforce_conservation(
            {
                "positions": np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
                "velocities": np.zeros((2, 3)),
            },
            "nnr_frame",
            compensation_mode="coupled",
            event_bus=bus, audit_log=log,
        )


def test_nnr_frame_shape_mismatch_raises():
    bus, log = _isolated_bus()
    with pytest.raises(ValueError, match="N, 3"):
        enforce_conservation(
            {
                "positions": np.zeros((4, 3)),
                "velocities": np.zeros((4, 2)),
            },
            "nnr_frame",
            compensation_mode="coupled",
            event_bus=bus, audit_log=log,
        )


def test_nnr_frame_is_a_hard_law():
    assert "nnr_frame" in HARD_LAWS


# ---------------------------------------------------------------------------
# Audit emission
# ---------------------------------------------------------------------------


def test_audit_entry_appended_to_audit_log():
    bus, log = _isolated_bus()
    P = np.array([5.0])
    ET = np.array([1.0])
    Q = np.array([1.0])
    dS = np.array([3.0])
    enforce_conservation(
        {"P": P, "ET": ET, "Q": Q, "dS": dS},
        "water_balance",
        compensation_mode="coupled",
        event_bus=bus, audit_log=log,
    )
    assert len(log) == 1
    record = log.records[0]
    assert isinstance(record, ConservationAudit)
    assert record.op_name == "enforce_conservation"
    assert record.tier == 3
    assert record.law == "water_balance"
    assert record.compensation_mode == "coupled"


def test_audit_records_initial_and_final_residuals():
    bus, log = _isolated_bus()
    enforce_conservation(
        {"M": np.diag([1.0, 2.0, 3.0])},  # trace = 6
        "moment_balance",
        compensation_mode="coupled",
        event_bus=bus, audit_log=log,
    )
    record = log.records[0]
    assert math.isclose(float(record.initial_residual), 6.0, abs_tol=1e-9)
    assert math.isclose(float(record.final_residual), 0.0, abs_tol=1e-9)


def test_audit_records_tolerance():
    bus, log = _isolated_bus()
    p12 = np.array([0.5])
    p23 = np.array([0.4])
    p13 = np.array([0.6])
    enforce_conservation(
        {"phi_12": p12, "phi_23": p23, "phi_13": p13},
        "phase_closure",
        compensation_mode="local",
        tolerance=0.05,
        event_bus=bus, audit_log=log,
    )
    record = log.records[0]
    assert record.tolerance == 0.05


def test_audit_event_published_on_event_bus():
    bus, log = _isolated_bus()
    received: list[ConservationAudit] = []
    bus.subscribe("enforce_conservation", received.append)
    enforce_conservation(
        {"M": np.eye(3)},  # trace = 3
        "moment_balance",
        compensation_mode="coupled",
        event_bus=bus, audit_log=log,
    )
    assert len(received) == 1
    assert received[0].law == "moment_balance"


# ---------------------------------------------------------------------------
# ConservationResult shape
# ---------------------------------------------------------------------------


def test_conservation_result_carries_law_and_mode():
    bus, log = _isolated_bus()
    P = np.array([5.0])
    ET = np.array([1.0])
    Q = np.array([1.0])
    dS = np.array([3.0])
    _, result = enforce_conservation(
        {"P": P, "ET": ET, "Q": Q, "dS": dS},
        "water_balance",
        compensation_mode="local",
        event_bus=bus, audit_log=log,
    )
    assert isinstance(result, ConservationResult)
    assert result.law == "water_balance"
    assert result.compensation_mode == "local"
    assert result.tolerance == DEFAULT_TOLERANCE["water_balance"]


def test_conservation_result_residuals_are_serialisable():
    """ndarray residuals are converted to tuples of floats so the audit
    log can be serialised."""
    bus, log = _isolated_bus()
    P = np.array([10.0, 20.0])
    ET = np.array([3.0, 4.0])
    Q = np.array([2.0, 5.0])
    dS = np.array([4.0, 10.0])
    _, result = enforce_conservation(
        {"P": P, "ET": ET, "Q": Q, "dS": dS},
        "water_balance",
        compensation_mode="local",
        event_bus=bus, audit_log=log,
    )
    assert isinstance(result.initial_residual, tuple)
    assert all(isinstance(x, float) for x in result.initial_residual)


# ---------------------------------------------------------------------------
# Idempotence: applying the projection twice does not change the output
# ---------------------------------------------------------------------------


def test_water_balance_projection_is_idempotent():
    P = np.array([10.0, 12.0, 8.0])
    ET = np.array([3.0, 4.0, 2.0])
    Q = np.array([2.0, 3.0, 1.0])
    dS = np.array([4.0, 4.0, 4.0])
    bus, log = _isolated_bus()

    once_X, _ = enforce_conservation(
        {"P": P, "ET": ET, "Q": Q, "dS": dS},
        "water_balance",
        compensation_mode="coupled",
        event_bus=bus, audit_log=log,
    )
    twice_X, twice_result = enforce_conservation(
        once_X,
        "water_balance",
        compensation_mode="coupled",
        event_bus=bus, audit_log=log,
    )
    np.testing.assert_allclose(once_X["P"], twice_X["P"], atol=1e-12)
    np.testing.assert_allclose(once_X["dS"], twice_X["dS"], atol=1e-12)
    assert twice_result.converged is True


def test_moment_balance_projection_is_idempotent():
    M = np.array([
        [1.0, 0.5, 0.0],
        [0.5, 2.0, 0.3],
        [0.0, 0.3, 3.0],
    ])
    bus, log = _isolated_bus()
    once_X, _ = enforce_conservation(
        {"M": M}, "moment_balance",
        compensation_mode="coupled",
        event_bus=bus, audit_log=log,
    )
    twice_X, _ = enforce_conservation(
        once_X, "moment_balance",
        compensation_mode="coupled",
        event_bus=bus, audit_log=log,
    )
    np.testing.assert_allclose(once_X["M"], twice_X["M"], atol=1e-12)


# ---------------------------------------------------------------------------
# Hard-law non-convergence does NOT raise (converged=False instead)
# ---------------------------------------------------------------------------


def test_hard_law_non_convergent_returns_converged_false_without_raising():
    """Naive mode on a hard law leaves the residual untouched.  The function
    must not raise; it sets converged=False and logs a warning."""
    p12 = np.array([0.5])
    p23 = np.array([0.4])
    p13 = np.array([0.6])  # closure = 0.3 > 0.1 tolerance
    bus, log = _isolated_bus()
    _, result = enforce_conservation(
        {"phi_12": p12, "phi_23": p23, "phi_13": p13},
        "phase_closure",
        compensation_mode="naive",
        event_bus=bus, audit_log=log,
    )
    assert result.converged is False


def test_soft_law_non_convergent_does_not_raise():
    """Naive mode on a soft law also returns converged=False with no raise."""
    bus, log = _isolated_bus()
    _, result = enforce_conservation(
        {"M": np.diag([1.0, 2.0, 3.0])},
        "moment_balance",
        compensation_mode="naive",
        event_bus=bus, audit_log=log,
    )
    assert result.converged is False
