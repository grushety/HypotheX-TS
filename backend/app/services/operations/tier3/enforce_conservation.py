"""enforce_conservation — Tier-3 user-invocable conservation projection (OP-032).

Project a multi-segment edit onto the manifold satisfying a named
conservation law.  Four laws ship in the MVP:

================================== ===================================================
Law                                Residual
================================== ===================================================
``water_balance``                  ``P − ET − Q − ΔS`` (per Eckhardt 2005)
``moment_balance``                 ``trace(M) = M_xx + M_yy + M_zz`` (Aki & Richards 2002)
``phase_closure``                  ``φ_12 + φ_23 − φ_13`` (De Zan 2015 triplet)
``nnr_frame``                      ``Σ r_i × v_i`` (Altamimi 2011 NNR)
================================== ===================================================

Each law is registered via :func:`register_law` so external packs can
extend the table without editing this file.

Compensation modes (consumed by every law) govern *how* the residual is
distributed across the signals:

- ``naive``    — report residual but apply no projection (identity).
- ``local``    — apply the entire residual to one preferred signal
                 (per-law choice).
- ``coupled``  — distribute the residual equally / least-squares over
                 every relevant signal so that the manifold-projected
                 result minimises ``||X_edit − X_in||²``.

OP-051 contract
---------------
The ticket says "delegates to OP-051 for the actual projection math".
OP-051 is not yet shipped on main; the cf_coordinator already does a
``try/except ImportError`` fallback (`compensation.py`).  Each law's
projection in this module is the math itself — OP-051 will eventually
own a *more general* compensation engine, at which point each law-
specific function can be re-routed through it.  The current
``compensation_mode`` parameter is honoured locally per law.

Audit emission
--------------
A :class:`ConservationAudit` is published on the OP-041 event bus
(event type ``'enforce_conservation'``) and appended to the default
audit log.  Both the *initial* and *final* residuals are recorded for
the UI-010 residual-budget panel.

Hard vs soft laws
-----------------
- ``phase_closure`` and ``nnr_frame`` are **hard** laws: post-projection
  residual must be ≤ tolerance, otherwise a warning is logged and
  ``ConservationResult.converged`` is ``False``.  The function never
  raises in this case (the user retains control).
- ``water_balance`` and ``moment_balance`` are **soft** laws:
  non-convergence is logged at INFO level only.

References
----------
Eckhardt, K. (2005).  Hydrological Processes 19(2):507–515.  Water-balance
    decomposition.
Aki, K. & Richards, P. (2002).  Quantitative Seismology, 2nd ed., Ch. 3.
    Moment-tensor isotropic / deviatoric split.
De Zan, F., Zonno, M., & López-Dekker, P. (2015).  IEEE TGRS
    53(12):6608.  Phase-triplet closure.
Altamimi, Z., Collilieux, X., & Métivier, L. (2011).  J. Geodesy
    85:457–473.  ITRF NNR criterion.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

import numpy as np

from app.services.events import (
    AuditLog,
    EventBus,
    default_audit_log,
    default_event_bus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


CompensationMode = Literal["naive", "local", "coupled"]
LawName = str
ResidualLike = float | tuple[float, ...] | np.ndarray


HARD_LAWS: frozenset[str] = frozenset({"phase_closure", "nnr_frame"})
SOFT_LAWS: frozenset[str] = frozenset({"water_balance", "moment_balance"})

DEFAULT_TOLERANCE: dict[str, float] = {
    "water_balance": 1e-6,
    "moment_balance": 1e-9,
    "phase_closure": 0.1,  # rad
    "nnr_frame": 1e-9,
}


class UnknownLaw(ValueError):
    """Raised when ``enforce_conservation`` is called with an unregistered law."""


@dataclass(frozen=True)
class ConservationResult:
    """Outcome surfaced to UI-010 residual-budget panel."""

    law: str
    compensation_mode: str
    initial_residual: ResidualLike
    final_residual: ResidualLike
    converged: bool
    tolerance: float
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConservationAudit:
    """Tier-3 audit entry emitted by :func:`enforce_conservation`.

    Recorded on :data:`default_audit_log`; published as event type
    ``'enforce_conservation'`` on :data:`default_event_bus`.
    """

    op_name: str
    tier: int
    law: str
    compensation_mode: str
    initial_residual: ResidualLike
    final_residual: ResidualLike
    converged: bool
    tolerance: float


# ---------------------------------------------------------------------------
# Law registry
# ---------------------------------------------------------------------------


LawFn = Callable[..., tuple[dict[str, Any], ResidualLike, ResidualLike]]
LAW_REGISTRY: dict[str, LawFn] = {}


def register_law(name: str) -> Callable[[LawFn], LawFn]:
    """Decorator that registers a conservation-law projection function.

    The registered function must accept ``(X_all, compensation_mode, aux)``
    and return ``(X_edit, initial_residual, final_residual)``.
    """

    def decorator(fn: LawFn) -> LawFn:
        if name in LAW_REGISTRY and LAW_REGISTRY[name] is not fn:
            logger.warning(
                "register_law: re-registering %r — previous callable replaced.",
                name,
            )
        LAW_REGISTRY[name] = fn
        return fn

    return decorator


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def enforce_conservation(
    X_all: dict[str, Any],
    law: str,
    compensation_mode: CompensationMode = "local",
    aux: dict[str, Any] | None = None,
    *,
    tolerance: float | None = None,
    event_bus: EventBus | None = None,
    audit_log: AuditLog | None = None,
) -> tuple[dict[str, Any], ConservationResult]:
    """Apply a named conservation projection to a bundle of signals.

    Args:
        X_all:              Dict of named signal arrays (law-specific keys —
                            see each registered law's docstring).
        law:                One of ``LAW_REGISTRY`` keys.
        compensation_mode:  ``'naive'`` | ``'local'`` | ``'coupled'``.
        aux:                Optional law-specific auxiliary data.
        tolerance:          Override the default convergence tolerance.
        event_bus:          Override the default event bus (test isolation).
        audit_log:          Override the default audit log (test isolation).

    Returns:
        ``(X_edit, ConservationResult)`` — ``X_edit`` is a *new* dict
        with the projected signals; the input is not mutated.

    Raises:
        UnknownLaw: ``law`` is not registered.
    """
    if law not in LAW_REGISTRY:
        known = sorted(LAW_REGISTRY)
        raise UnknownLaw(
            f"enforce_conservation: unknown law {law!r}.  Registered laws: {known}."
        )
    if compensation_mode not in ("naive", "local", "coupled"):
        raise ValueError(
            f"enforce_conservation: unknown compensation_mode "
            f"{compensation_mode!r}; expected 'naive' | 'local' | 'coupled'."
        )

    eff_tol = float(
        tolerance if tolerance is not None
        else DEFAULT_TOLERANCE.get(law, 1e-6)
    )
    eff_aux: dict[str, Any] = aux or {}

    law_fn = LAW_REGISTRY[law]
    X_edit, initial_residual, final_residual = law_fn(X_all, compensation_mode, eff_aux)

    converged = _converged(final_residual, eff_tol)
    if law in HARD_LAWS and not converged:
        logger.warning(
            "enforce_conservation: %r did not converge "
            "(final residual %s > tolerance %g, mode=%s).",
            law, _residual_repr(final_residual), eff_tol, compensation_mode,
        )
    elif law in SOFT_LAWS and not converged:
        logger.info(
            "enforce_conservation: %r soft-law residual %s > tolerance %g (mode=%s).",
            law, _residual_repr(final_residual), eff_tol, compensation_mode,
        )

    bus = event_bus if event_bus is not None else default_event_bus
    log = audit_log if audit_log is not None else default_audit_log
    audit = ConservationAudit(
        op_name="enforce_conservation",
        tier=3,
        law=law,
        compensation_mode=compensation_mode,
        initial_residual=_residual_to_serialisable(initial_residual),
        final_residual=_residual_to_serialisable(final_residual),
        converged=converged,
        tolerance=eff_tol,
    )
    log.append(audit)
    bus.publish("enforce_conservation", audit)

    return X_edit, ConservationResult(
        law=law,
        compensation_mode=compensation_mode,
        initial_residual=_residual_to_serialisable(initial_residual),
        final_residual=_residual_to_serialisable(final_residual),
        converged=converged,
        tolerance=eff_tol,
    )


# ---------------------------------------------------------------------------
# Residual helpers
# ---------------------------------------------------------------------------


def _residual_norm(residual: ResidualLike) -> float:
    """L∞ norm of the residual; treats scalar / tuple / ndarray uniformly."""
    if isinstance(residual, np.ndarray):
        if residual.size == 0:
            return 0.0
        return float(np.max(np.abs(residual)))
    if isinstance(residual, (tuple, list)):
        if not residual:
            return 0.0
        return float(max(abs(float(x)) for x in residual))
    return float(abs(float(residual)))


def _converged(residual: ResidualLike, tolerance: float) -> bool:
    return _residual_norm(residual) <= tolerance


def _residual_repr(residual: ResidualLike) -> str:
    if isinstance(residual, np.ndarray):
        return f"ndarray|max|={_residual_norm(residual):.3g}"
    if isinstance(residual, (tuple, list)):
        return f"tuple|max|={_residual_norm(residual):.3g}"
    return f"{float(residual):.3g}"


def _residual_to_serialisable(residual: ResidualLike) -> ResidualLike:
    """Convert a residual to a stable, JSON-serialisable form for audit."""
    if isinstance(residual, np.ndarray):
        return tuple(float(x) for x in residual.ravel())
    if isinstance(residual, (tuple, list)):
        return tuple(float(x) for x in residual)
    return float(residual)


# ---------------------------------------------------------------------------
# Law: water_balance — P − ET − Q − ΔS = 0  (Eckhardt 2005)
# ---------------------------------------------------------------------------


_WATER_KEYS: tuple[str, ...] = ("P", "ET", "Q", "dS")


@register_law("water_balance")
def project_water_balance(
    X_all: dict[str, Any],
    compensation_mode: str,
    aux: dict[str, Any],
) -> tuple[dict[str, Any], ResidualLike, ResidualLike]:
    """Water-balance projection — ``P − ET − Q − ΔS = 0``.

    Per-element residual (every key is shape ``(n,)`` or scalar).

    Compensation modes:
      - ``naive``: report residual; do not project.
      - ``local``: absorb the entire residual into ``ΔS`` (storage is the
        unobserved residual term in basic hydrology bookkeeping).
      - ``coupled``: distribute the residual evenly across all four
        signals — minimises ``Σ Δᵢ²`` for the constraint
        ``ΔP − ΔET − ΔQ − ΔdS = −residual``.
    """
    P = np.asarray(X_all["P"], dtype=np.float64)
    ET = np.asarray(X_all["ET"], dtype=np.float64)
    Q = np.asarray(X_all["Q"], dtype=np.float64)
    dS = np.asarray(X_all["dS"], dtype=np.float64)

    initial_residual = P - ET - Q - dS

    if compensation_mode == "naive":
        return dict(X_all), initial_residual.copy(), initial_residual.copy()

    if compensation_mode == "local":
        dS_new = dS + initial_residual
        X_edit = {**X_all, "dS": dS_new}
        final_residual = P - ET - Q - dS_new
        return X_edit, initial_residual, final_residual

    # coupled — minimum-norm correction over (P, ET, Q, dS)
    # Constraint: dP − dET − dQ − dDs = −r → minimise dP² + dET² + dQ² + dDs²
    # Lagrange: dP = −r/4, dET = +r/4, dQ = +r/4, dDs = +r/4
    delta = initial_residual / 4.0
    P_new, ET_new, Q_new, dS_new = P - delta, ET + delta, Q + delta, dS + delta
    X_edit = {
        **X_all,
        "P": P_new,
        "ET": ET_new,
        "Q": Q_new,
        "dS": dS_new,
    }
    final_residual = P_new - ET_new - Q_new - dS_new
    return X_edit, initial_residual, final_residual


# ---------------------------------------------------------------------------
# Law: moment_balance — trace(M) = 0  (Aki & Richards 2002)
# ---------------------------------------------------------------------------


@register_law("moment_balance")
def project_moment_tensor(
    X_all: dict[str, Any],
    compensation_mode: str,
    aux: dict[str, Any],
) -> tuple[dict[str, Any], ResidualLike, ResidualLike]:
    """Trace-zero projection of a 3×3 moment tensor (deviatoric part).

    Reads ``X_all['M']`` (shape ``(3, 3)``).  ``trace(M) = M_xx + M_yy +
    M_zz`` — physically the isotropic explosion / implosion component;
    setting it to zero leaves the deviatoric (shear) part.

    Compensation modes:
      - ``naive``: report; no projection.
      - ``local``: subtract the entire trace from ``M_zz``.
      - ``coupled``: subtract ``trace/3`` from each diagonal element
        (least-squares projection onto the deviatoric subspace).
    """
    M = np.asarray(X_all["M"], dtype=np.float64)
    if M.shape != (3, 3):
        raise ValueError(
            f"moment_balance: M must have shape (3,3); got {M.shape}."
        )
    initial_trace = float(M[0, 0] + M[1, 1] + M[2, 2])

    if compensation_mode == "naive":
        return dict(X_all), initial_trace, initial_trace

    M_new = M.copy()
    if compensation_mode == "local":
        M_new[2, 2] -= initial_trace
    else:  # coupled
        M_new[0, 0] -= initial_trace / 3.0
        M_new[1, 1] -= initial_trace / 3.0
        M_new[2, 2] -= initial_trace / 3.0

    final_trace = float(M_new[0, 0] + M_new[1, 1] + M_new[2, 2])
    X_edit = {**X_all, "M": M_new}
    return X_edit, initial_trace, final_trace


# ---------------------------------------------------------------------------
# Law: phase_closure — arg(φ₁₂ + φ₂₃ − φ₁₃) = 0  (De Zan 2015)
# ---------------------------------------------------------------------------


def _wrap_phase(phi: np.ndarray) -> np.ndarray:
    """Wrap a phase array into ``(−π, π]``."""
    return (np.asarray(phi, dtype=np.float64) + math.pi) % (2.0 * math.pi) - math.pi


@register_law("phase_closure")
def enforce_triplet_closure(
    X_all: dict[str, Any],
    compensation_mode: str,
    aux: dict[str, Any],
) -> tuple[dict[str, Any], ResidualLike, ResidualLike]:
    """Triplet-closure projection — ``φ₁₂ + φ₂₃ − φ₁₃ ≡ 0  (mod 2π)``.

    Reads ``X_all['phi_12']``, ``X_all['phi_23']``, ``X_all['phi_13']``
    (each shape ``(n,)`` or scalar).  Closure phase is wrapped into
    ``(−π, π]`` before projection so that the natural 2π-multiple
    ambiguity does not inflate the residual.

    Compensation modes:
      - ``naive``: report; no projection.
      - ``local``: add the closure to ``φ_13`` (φ_13 sits in the
        equation with a minus sign, so ``φ_13 += closure`` zeros the
        wrap-corrected residual).
      - ``coupled``: minimise ``Δφ_12² + Δφ_23² + Δφ_13²`` subject to
        ``Δφ_12 + Δφ_23 − Δφ_13 = −closure``; Lagrange gives
        ``Δφ_12 = Δφ_23 = −closure/3`` and ``Δφ_13 = +closure/3``.
    """
    p12 = np.asarray(X_all["phi_12"], dtype=np.float64)
    p23 = np.asarray(X_all["phi_23"], dtype=np.float64)
    p13 = np.asarray(X_all["phi_13"], dtype=np.float64)

    closure = _wrap_phase(p12 + p23 - p13)
    initial_residual = closure.copy()

    if compensation_mode == "naive":
        return dict(X_all), initial_residual, initial_residual.copy()

    if compensation_mode == "local":
        p13_new = p13 + closure
        X_edit = {**X_all, "phi_13": p13_new}
        final_residual = _wrap_phase(p12 + p23 - p13_new)
        return X_edit, initial_residual, final_residual

    # coupled
    delta = closure / 3.0
    p12_new = p12 - delta
    p23_new = p23 - delta
    p13_new = p13 + delta
    X_edit = {**X_all, "phi_12": p12_new, "phi_23": p23_new, "phi_13": p13_new}
    final_residual = _wrap_phase(p12_new + p23_new - p13_new)
    return X_edit, initial_residual, final_residual


# ---------------------------------------------------------------------------
# Law: nnr_frame — Σ rᵢ × vᵢ = 0  (Altamimi 2011)
# ---------------------------------------------------------------------------


@register_law("nnr_frame")
def enforce_nnr(
    X_all: dict[str, Any],
    compensation_mode: str,
    aux: dict[str, Any],
) -> tuple[dict[str, Any], ResidualLike, ResidualLike]:
    """No-net-rotation projection of a station-velocity field.

    Reads ``X_all['positions']`` (shape ``(N, 3)``) and
    ``X_all['velocities']`` (shape ``(N, 3)``).  Solves for the global
    angular velocity ``ω`` minimising ``Σ ‖vᵢ − ω × rᵢ‖²`` and
    subtracts the implied rigid rotation (Altamimi 2011 Eq. 4–6).

    Compensation modes:
      - ``naive``: report; no projection.
      - ``local`` / ``coupled``: same projection (the least-squares ω is
        already the unique minimum-norm correction; there is no
        per-station alternative).
    """
    positions = np.asarray(X_all["positions"], dtype=np.float64)
    velocities = np.asarray(X_all["velocities"], dtype=np.float64)
    if positions.shape != velocities.shape or positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError(
            "nnr_frame: positions and velocities must both have shape (N, 3); "
            f"got {positions.shape} and {velocities.shape}."
        )
    if positions.shape[0] < 3:
        raise ValueError(
            f"nnr_frame: need at least 3 stations to constrain the global "
            f"angular velocity; got {positions.shape[0]}."
        )

    initial_net = np.sum(np.cross(positions, velocities), axis=0)

    if compensation_mode == "naive":
        return dict(X_all), initial_net, initial_net.copy()

    # ω satisfies A ω = b where A = Σ (‖rᵢ‖² I − rᵢ rᵢᵀ),  b = Σ rᵢ × vᵢ
    A = np.zeros((3, 3), dtype=np.float64)
    b = initial_net.copy()
    for r in positions:
        rr = float(r @ r)
        A += rr * np.eye(3) - np.outer(r, r)
    try:
        omega = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        omega = np.linalg.lstsq(A, b, rcond=None)[0]

    velocities_corrected = velocities - np.cross(omega[None, :], positions)
    final_net = np.sum(np.cross(positions, velocities_corrected), axis=0)

    X_edit = {**X_all, "velocities": velocities_corrected}
    return X_edit, initial_net, final_net
