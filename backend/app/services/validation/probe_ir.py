"""PROBE invalidation rate (VAL-002).

Closed-form first-order linearised bound on

    IR(x') = E_ε[ M(x' + ε) ≠ M(x') ],   ε ~ N(0, σ² I)

from:

  Pawelczyk, Datta, van-den-Heuvel, Kasneci, Lakkaraju,
  "Probabilistically Robust Recourse," ICLR 2023, arXiv:2203.06768.

For a binary decision rule ``M(x) = 1{f(x) > τ}`` and a small Gaussian
perturbation ε on x', the Taylor expansion ``f(x' + ε) ≈ f(x') + ∇f(x')·ε``
gives ``f(x' + ε) ~ N(f(x'), σ²·‖∇f(x')‖²)``. The probability that
``M(x' + ε) ≠ M(x')`` is one-sided: it is the probability that the score
crosses the threshold τ in the *one* direction that flips the prediction.
That collapses (Pawelczyk 2023 Eq. 5) to

    IR(x') ≈ 1 − Φ( |f(x') − τ| / (σ · ‖∇f(x')‖) )

where Φ is the standard normal CDF.

Pseudocode-vs-paper note (load-bearing): the VAL-002 ticket pseudocode
shows ``2 · (1 − Φ(margin / std_f))``, which is a two-sided test (probability
that the score deviates by more than the margin in *either* direction).
A binary prediction can only flip in one direction for a fixed x', so the
factor of 2 is incorrect for IR; the AC binds correctness to Eq. 5 (the
one-sided form). This module follows the paper.

The Monte-Carlo path is provided as a slow-path fallback for
non-differentiable models (those that do not implement ``gradient(x)``).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProbeMethodError(ValueError):
    """Raised when the requested PROBE method cannot run on this model."""


# ---------------------------------------------------------------------------
# Model protocol
# ---------------------------------------------------------------------------


class ProbeModel(Protocol):
    """Contract a model must satisfy to be probed by ``probe_invalidation_rate``.

    ``threshold`` is the binary decision boundary (``M(x) = 1{score(x) > τ}``).
    ``score`` and ``predict`` are required for both methods; ``gradient`` is
    required only for the linearised path. Models without ``gradient`` must
    use ``method='monte_carlo'``.
    """

    threshold: float

    def score(self, x: np.ndarray) -> float:  # pragma: no cover - protocol
        ...

    def predict(self, x: np.ndarray) -> int:  # pragma: no cover - protocol
        ...

    def gradient(self, x: np.ndarray) -> np.ndarray:  # pragma: no cover - protocol
        ...


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


METHOD_LINEARISED = "linearised"
METHOD_MONTE_CARLO = "monte_carlo"
_ALLOWED_METHODS = frozenset({METHOD_LINEARISED, METHOD_MONTE_CARLO})

DEFAULT_SIGMA = 0.1
DEFAULT_MC_SAMPLES = 200

# Domain-specific σ defaults per Tier-2 op (AC: "amplitude ops: σ on coefficient;
# time ops: σ on shift"). σ is interpreted in the op's natural parameter space —
# coefficient units for amplitude/value ops, sample units for time ops.
TIER2_DEFAULT_SIGMA: dict[str, float] = {
    "raise_lower": 0.05,
    "amplitude_scale": 0.05,
    "invert": 0.05,
    "replace_with_trend": 0.05,
    "flatten": 0.10,
    "change_slope": 0.05,
    "stretch_compress": 0.5,
    "shift_phase": 0.5,
}


def default_sigma_for_op(op_name: str) -> float:
    """Return the recommended σ for a Tier-2 op; falls back to ``DEFAULT_SIGMA``."""
    return TIER2_DEFAULT_SIGMA.get(op_name, DEFAULT_SIGMA)


@dataclass(frozen=True)
class ProbeIRResult:
    """Per-edit invalidation-rate result.

    Attributes:
        invalidation_rate: IR ∈ [0, 1].
        sigma:             σ used for the perturbation.
        method:            'linearised' | 'monte_carlo'.
        margin:            |f(x') − τ| (linearised path only).
        grad_norm:         ‖∇f(x')‖₂ (linearised path only).
        n_samples:         Number of MC draws (MC path only).
    """

    invalidation_rate: float
    sigma: float
    method: str
    margin: float | None = None
    grad_norm: float | None = None
    n_samples: int | None = None

    def __post_init__(self) -> None:
        if self.method not in _ALLOWED_METHODS:
            raise ProbeMethodError(
                f"method must be one of {sorted(_ALLOWED_METHODS)}; got {self.method!r}"
            )
        if not 0.0 <= self.invalidation_rate <= 1.0:
            raise ValueError(
                f"invalidation_rate must be in [0, 1]; got {self.invalidation_rate}"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_SQRT_2 = math.sqrt(2.0)


def _normal_survival(x: float) -> float:
    """1 − Φ(x) via ``erfc``; numerically stable in the deep tail.

    The naïve ``1 − 0.5·(1 + erf(x/√2))`` underflows once erf saturates near
    1; ``0.5·erfc(x/√2)`` retains precision out to x ≈ 25.
    """
    return 0.5 * math.erfc(x / _SQRT_2)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def probe_invalidation_rate(
    model: ProbeModel,
    x_prime: np.ndarray,
    *,
    sigma: float = DEFAULT_SIGMA,
    method: Literal["linearised", "monte_carlo"] = METHOD_LINEARISED,
    n_samples: int = DEFAULT_MC_SAMPLES,
    rng: np.random.Generator | None = None,
) -> ProbeIRResult:
    """Estimate ``IR(x') = P_ε[M(x' + ε) ≠ M(x')]``, ε ~ N(0, σ² I).

    Args:
        model:     ProbeModel; ``gradient(x)`` is required for ``method='linearised'``.
        x_prime:   Edited point (1-D array). Higher-dim inputs are flattened.
        sigma:     Perturbation scale in the input space; default 0.1.
        method:    'linearised' (default; closed-form Pawelczyk Eq. 5) or
                   'monte_carlo' (slow-path fallback for non-differentiable models).
        n_samples: MC draws when ``method='monte_carlo'``; default 200.
        rng:       Optional ``np.random.Generator`` for reproducible MC.

    Returns:
        ``ProbeIRResult`` with ``invalidation_rate ∈ [0, 1]`` and per-method
        diagnostics.

    Raises:
        ProbeMethodError: ``method='linearised'`` requested on a model without
            ``gradient``; or ``method`` is not one of the allowed values.
        ValueError: ``sigma <= 0`` or ``n_samples <= 0``.
    """
    if sigma <= 0:
        raise ValueError(f"sigma must be positive; got {sigma}")
    x = np.asarray(x_prime, dtype=np.float64).reshape(-1)

    if method == METHOD_LINEARISED:
        if not hasattr(model, "gradient"):
            raise ProbeMethodError(
                "linearised method requires model.gradient(x); pass method='monte_carlo' "
                "for non-differentiable models."
            )
        f0 = float(model.score(x))
        grad = np.asarray(model.gradient(x), dtype=np.float64).reshape(-1)
        if grad.shape != x.shape:
            raise ProbeMethodError(
                f"model.gradient(x) returned shape {grad.shape}; expected {x.shape}. "
                "Silently flattening would produce a meaningless invalidation rate."
            )
        margin = abs(f0 - float(model.threshold))
        grad_norm = float(np.linalg.norm(grad))
        std_f = sigma * grad_norm

        if std_f <= 0.0:
            # Zero gradient → score is locally insensitive to ε; no flip.
            ir = 0.0
        else:
            # Pawelczyk 2023 Eq. 5 (one-sided closed form).
            ir = float(_normal_survival(margin / std_f))

        return ProbeIRResult(
            invalidation_rate=ir,
            sigma=float(sigma),
            method=METHOD_LINEARISED,
            margin=margin,
            grad_norm=grad_norm,
        )

    if method == METHOD_MONTE_CARLO:
        if n_samples <= 0:
            raise ValueError(f"n_samples must be positive; got {n_samples}")
        generator = rng if rng is not None else np.random.default_rng()
        base_class = int(model.predict(x))
        flips = 0
        for _ in range(n_samples):
            eps = sigma * generator.standard_normal(x.shape[0])
            if int(model.predict(x + eps)) != base_class:
                flips += 1
        return ProbeIRResult(
            invalidation_rate=float(flips) / n_samples,
            sigma=float(sigma),
            method=METHOD_MONTE_CARLO,
            n_samples=n_samples,
        )

    raise ProbeMethodError(
        f"method must be one of {sorted(_ALLOWED_METHODS)}; got {method!r}"
    )
