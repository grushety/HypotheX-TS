"""compensation — projection onto a constraint manifold (OP-051).

Given a perturbed series ``X_edit`` and an equality constraint
``g(X) = 0`` (typically a conservation law from OP-032 — water balance,
moment trace, phase closure, NNR), :func:`project` returns a corrected
series that satisfies the constraint.

Three compensation modes are exposed as a *user choice* — the atomic
novelty of HypotheX-TS's conservation-enforcement claim:

================ =====================================================
``naive``        No projection.  Residual is reported only.  UI-010
                 renders the residual gap in red so the user can see
                 that physical balance is broken.
``local``        Distribute the residual within ``segment_mask`` only.
                 Byte-identical preservation of values outside the mask.
``coupled``      Solve the equality-constrained QP

                     minimise ½‖X' − X_edit‖²
                     s.t.       g(X') = 0

                 across all elements of ``X_edit``.  For linear
                 constraints the closed-form solution is

                     X' = X_edit − Jᵀ (J Jᵀ)⁻¹ r

                 (Nocedal & Wright 2006 §17.1).  For nonlinear
                 constraints we iterate Newton-style projected-gradient
                 steps until ``‖r‖ ≤ tolerance`` or ``max_iter``.
================ =====================================================

Constraint contract
-------------------
The ``constraint`` argument must expose

* ``residual(X) → float | np.ndarray`` — the constraint value
  (zero when satisfied)

and *should* expose

* ``jacobian(X) → np.ndarray`` — partial derivatives ∂r/∂X with shape
  ``(m, n)`` (or ``(n,)`` for scalar residuals)

If ``jacobian`` is missing or raises, :func:`project` falls back to a
numerical Jacobian via central differences (``O(n)`` extra residual
evaluations per Newton step).  This keeps the OP-050 ``Constraint``
Protocol — which only requires ``residual`` and ``satisfied`` —
compatible with the OP-051 projector.

References
----------
Nocedal, J. & Wright, S. J. (2006).  Numerical Optimization, 2nd ed.,
    Ch. 17.  Equality-constrained QP closed-form via the KKT system;
    null-space / range-space splits.
Eckhardt, K. (2005).  Hydrological Processes 19(2):507–515 — local
    water-balance redistribution.
Ansari, H., De Zan, F., & Bamler, R. (2018).  IEEE TGRS 56:4109 — InSAR
    triplet-closure projection (least-squares closure phase removal).
"""
from __future__ import annotations

import logging
from typing import Any, Literal, Protocol, runtime_checkable

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public typing
# ---------------------------------------------------------------------------


CompensationMode = Literal["naive", "local", "coupled"]


@runtime_checkable
class HasJacobian(Protocol):
    """Optional structural extension of the OP-050 Constraint Protocol.

    Constraints that ship a closed-form Jacobian implement this; those
    that do not fall through to the numerical-Jacobian path inside
    :func:`project`.
    """

    def jacobian(self, X: np.ndarray) -> np.ndarray: ...


_DOMAIN_DEFAULTS: dict[str, str] = {
    "hydrology": "local",
    "seismo-geodesy": "coupled",
    "seismo_geodesy": "coupled",
    "geodesy": "coupled",
    "remote-sensing": "local",
    "remote_sensing": "local",
}


def default_compensation_mode_for_domain(
    domain_hint: str | None,
) -> CompensationMode:
    """Return the recommended compensation mode for a domain hint.

    Falls back to ``'naive'`` (with a warning at call-site) for unknown
    domains so that the user can explicitly opt into ``'local'`` /
    ``'coupled'`` if the heuristic does not match the use case.
    """
    if domain_hint is None:
        return "naive"
    return _DOMAIN_DEFAULTS.get(str(domain_hint).lower(), "naive")  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


_DEFAULT_TOLERANCE_LINEAR: float = 1e-6
_DEFAULT_TOLERANCE_NONLINEAR: float = 1e-4
_DEFAULT_MAX_ITER: int = 20
_NUMERICAL_JACOBIAN_EPS: float = 1e-7


def project(
    X_edit: np.ndarray,
    constraint: Any,
    compensation_mode: CompensationMode = "local",
    *,
    segment_mask: np.ndarray | None = None,
    tolerance: float = _DEFAULT_TOLERANCE_LINEAR,
    max_iter: int = _DEFAULT_MAX_ITER,
) -> np.ndarray:
    """Project ``X_edit`` onto the manifold satisfying ``constraint``.

    Args:
        X_edit:           Perturbed series, shape ``(n,)``.
        constraint:       Object exposing ``residual(X) → float | array``
                          and (preferably) ``jacobian(X) → array``.  If
                          ``jacobian`` is missing or raises, a numerical
                          Jacobian is computed via finite differences.
        compensation_mode: ``'naive'``, ``'local'``, or ``'coupled'``.
        segment_mask:     Required for ``'local'`` mode.  Boolean array of
                          shape ``(n,)``; only values where ``mask`` is
                          ``True`` may be modified.
        tolerance:        Convergence threshold on ``‖r‖``.  Default
                          ``1e-6`` (linear); nonlinear constraints may
                          need ``1e-4``.
        max_iter:         Maximum Newton-style iterations for
                          ``'coupled'`` and ``'local'``.

    Returns:
        Projected series, shape ``(n,)``.  A *new* array — the input is
        never mutated.

    Raises:
        ValueError: ``compensation_mode`` is unknown, ``segment_mask`` is
                    missing in ``'local'`` mode, or the mask shape does
                    not match ``X_edit``.
    """
    if compensation_mode not in ("naive", "local", "coupled"):
        raise ValueError(
            f"project: unknown compensation_mode {compensation_mode!r}; "
            "expected 'naive' | 'local' | 'coupled'."
        )

    X = np.asarray(X_edit, dtype=np.float64).ravel().copy()
    n = len(X)

    if compensation_mode == "naive":
        r0 = _residual_vector(constraint, X)
        logger.info(
            "compensation.project: naive mode — residual ‖r‖=%.3g reported "
            "but not corrected.",
            float(np.linalg.norm(r0)),
        )
        return X

    if compensation_mode == "local":
        if segment_mask is None:
            raise ValueError(
                "project: 'local' mode requires segment_mask."
            )
        mask = np.asarray(segment_mask, dtype=bool).ravel()
        if mask.shape != (n,):
            raise ValueError(
                f"project: segment_mask shape {mask.shape} does not match "
                f"X_edit length {n}."
            )
        if not mask.any():
            logger.warning(
                "compensation.project: 'local' mode received an all-False "
                "mask — residual cannot be redistributed; returning X "
                "unchanged."
            )
            return X
        return _project_iterative(constraint, X, mask, tolerance, max_iter)

    # coupled — global projection, mask = all True
    full_mask = np.ones(n, dtype=bool)
    return _project_iterative(constraint, X, full_mask, tolerance, max_iter)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _residual_vector(constraint: Any, X: np.ndarray) -> np.ndarray:
    """Coerce ``constraint.residual(X)`` to a 1-D float array."""
    r = constraint.residual(X)
    if np.isscalar(r):
        return np.array([float(r)], dtype=np.float64)
    return np.asarray(r, dtype=np.float64).ravel()


def _jacobian_matrix(constraint: Any, X: np.ndarray) -> np.ndarray:
    """Return ``constraint.jacobian(X)`` as a 2-D ``(m, n)`` array.

    Falls back to a numerical Jacobian via central differences if the
    constraint lacks ``jacobian`` or it raises.
    """
    n = len(X)
    if hasattr(constraint, "jacobian"):
        try:
            J = np.asarray(constraint.jacobian(X), dtype=np.float64)
            if J.ndim == 1:
                J = J.reshape(1, -1)
            if J.shape[1] != n:
                raise ValueError(
                    f"constraint.jacobian returned shape {J.shape}; "
                    f"expected (m, {n})."
                )
            return J
        except (NotImplementedError, ValueError, TypeError) as exc:
            logger.debug(
                "constraint.jacobian unavailable / invalid (%s); "
                "falling back to numerical central differences.",
                exc,
            )
    return _numerical_jacobian(constraint, X)


def _numerical_jacobian(
    constraint: Any,
    X: np.ndarray,
    eps: float = _NUMERICAL_JACOBIAN_EPS,
) -> np.ndarray:
    """Central-difference Jacobian: ``J[i, j] = ∂r_i/∂X_j``.

    Costs ``2n`` residual evaluations per call; acceptable for moderate
    ``n`` (up to ~10³).  Used only when the constraint does not ship a
    closed-form Jacobian.
    """
    n = len(X)
    r0 = _residual_vector(constraint, X)
    m = len(r0)
    J = np.zeros((m, n), dtype=np.float64)
    for j in range(n):
        Xp = X.copy()
        Xp[j] = X[j] + eps
        rp = _residual_vector(constraint, Xp)
        Xm = X.copy()
        Xm[j] = X[j] - eps
        rm = _residual_vector(constraint, Xm)
        J[:, j] = (rp - rm) / (2.0 * eps)
    return J


def _project_iterative(
    constraint: Any,
    X: np.ndarray,
    mask: np.ndarray,
    tolerance: float,
    max_iter: int,
) -> np.ndarray:
    """Newton-style projected-gradient until residual ≤ tolerance.

    For a *linear* constraint with constant Jacobian this converges in a
    single iteration (``X' = X − Jᵀ (J Jᵀ)⁻¹ r``).  For nonlinear
    constraints the same step is repeated, re-evaluating ``J`` each time.

    The free variables are the elements where ``mask == True`` —
    elements outside the mask are byte-identical pre/post.
    """
    X = X.copy()
    for iteration in range(max_iter):
        r = _residual_vector(constraint, X)
        r_norm = float(np.linalg.norm(r))
        if r_norm <= tolerance:
            break
        J_full = _jacobian_matrix(constraint, X)
        J_local = J_full[:, mask]  # (m, n_free)
        # Solve  (J_local J_localᵀ) y = r  via least-squares for stability,
        # then  correction_local = J_localᵀ y.
        try:
            y, *_ = np.linalg.lstsq(J_local @ J_local.T, r, rcond=None)
        except np.linalg.LinAlgError:
            logger.warning(
                "compensation.project: lstsq failed at iter %d; "
                "stopping with residual %.3g.",
                iteration, r_norm,
            )
            break
        correction_local = J_local.T @ y
        X[mask] = X[mask] - correction_local
    else:
        # Loop finished without break — we hit max_iter.
        final_r = float(np.linalg.norm(_residual_vector(constraint, X)))
        if final_r > tolerance:
            logger.warning(
                "compensation.project: did not converge in %d iterations "
                "(final residual %.3g > tolerance %.3g).",
                max_iter, final_r, tolerance,
            )
    return X
