"""Counterfactual Stability in decomposition-coefficient space (VAL-032).

**Publishable contribution.** Transplants Counterfactual Stability
(Dutta et al. ICML 2022) from the tabular setting to the
*decomposition-coefficient space* of fitted parametric time-series
models. The novel piece is the **MBB-calibrated Gaussian noise model**
on the per-coefficient scale: ``θ_m = θ' + ε_m`` with
``ε_m ~ N(0, diag(σ_θ²))`` where ``σ_θ`` comes from VAL-031's
moving-block-bootstrap CIs (the canonical SE for dependent-data fits).

Sources (binding for ``algorithm-auditor``):

  - Dutta, Long, Mishra, Tilli, Magazzeni, "Robust Counterfactual
    Explanations for Tree-Based Ensembles," *ICML 2022* (PMLR 162:5742),
    arXiv:2207.02739 — canonical CS = ``μ − κσ`` formula at §3,
    default ``κ = 0.5`` at §4.
  - Hamman, Noorani, Mishra, Magazzeni, Dutta, "Robust Counterfactual
    Explanations for Neural Networks With Probabilistic Guarantees,"
    *ICML 2023* (PMLR 202:12351), arXiv:2305.11997 — closed-form
    analytic lower bound on Pr(robust) for differentiable models.
  - Pawelczyk, Datta, van-den-Heuvel, Kasneci, Lakkaraju,
    "Probabilistically Robust Recourse," *ICLR 2023*, arXiv:2203.06768
    — PROBE-IR (VAL-002 fast-path); this module is the *calibrated MC*
    counterpart in coefficient space.
  - Mishra, Dutta, Long, Magazzeni, "A Survey on the Robustness of
    Feature Importance and Counterfactual Explanations," arXiv:2111.00358.
  - Slack, Hilgard, Lakkaraju, Singh, "Counterfactual Explanations Can
    Be Manipulated," *NeurIPS 2021*, arXiv:2106.02666 — motivating
    threat model.

For the **MBB-calibrated noise model** (the publishable novel piece):
Politis-Romano 1994 (cited in VAL-031); Patton-Politis-White 2009;
Bedford & Bevis *JGR Solid Earth* 123:6992 (2018) for transient-fit SEs.

**Methodological honesty.** This module is a TS-decomposition transplant
of CS, not a derivation of new probabilistic-validity bounds. It assumes:
  1. **Per-coefficient Gaussian noise** — independence across
     coefficients. The MBB CIs already include marginal SE estimates;
     the cross-coefficient covariance from MBB bootstrap replicates is
     left for follow-up. The MMD-coupled noise model (Lopez-Paz et al.
     ICLR 2017) is also a follow-up.
  2. **Coefficient-space-only perturbations** — the function never
     perturbs the raw signal; perturbations live entirely in coefficient
     space and the series is *reassembled* through a caller-supplied
     ``reconstruct_fn``. This invariant is asserted in the test suite.

PUBLISHABLE CLAIM (paper-draft TODO, see VAL-032 ticket): CS in
fitted-parametric-decomposition coefficient space, with MBB-calibrated
noise model and dual MC + analytic bounds, has not been published in
2020-2026 (per the SOTA review's §"Open research gaps", contribution #1).
The required methodological honesty: choice of noise model is part of
the contribution — alternatives (full MBB-replicates covariance, MMD
coupling) deserve separate ablation in the paper.
"""
from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from typing import Any, Callable, Hashable, Mapping, Protocol

import numpy as np

from app.models.decomposition import DecompositionBlob

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CSCoefficientError(RuntimeError):
    """Raised when CS inputs are unusable (missing σ_θ, no reconstruct_fn, etc.)."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


DEFAULT_M_SAMPLES = 200
DEFAULT_KAPPA = 0.5  # Dutta 2022 §4 default
DEFAULT_ROBUST_THRESHOLD = 0.5
_VAR_FLOOR = 1e-12


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


class ProbaModel(Protocol):
    """Multiclass model with ``predict_proba(x) -> probability vector``."""

    def predict_proba(self, x: np.ndarray) -> np.ndarray:  # pragma: no cover - protocol
        ...


# ``reconstruct_fn(coefficients_dict, original_blob) -> components_dict``.
# Method-specific signal rebuild. The validator passes the perturbed
# coefficients to this function; the function returns a fresh
# ``components`` dict consistent with the new values. Caller's
# responsibility — VAL-032 cannot infer this generically across the
# 10 supported decomposition methods.
ReconstructFn = Callable[[dict[str, Any], DecompositionBlob], dict[str, np.ndarray]]


# ``coefficient_jacobian_fn(blob) -> {coeff_name: ∂x/∂coeff_n}``.
# Each entry is the partial derivative of the reassembled signal with
# respect to one coefficient. Used by the optional Hamman 2023 analytic
# bound. Like ``reconstruct_fn``, this is method-specific.
CoefficientJacobianFn = Callable[[DecompositionBlob], dict[str, np.ndarray]]


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CSResult:
    """Outcome of a coefficient-space CS query.

    Attributes:
        cs:                 ``μ − κσ`` per Dutta 2022 Def. 1.
        mu / sigma:         Mean / SD of the model's target-class
                            probability across the M perturbations.
        invalidation_rate:  Fraction of perturbations whose argmax-class
                            differs from the unperturbed CF — slow-path
                            counterpart to VAL-002 PROBE-IR.
        n_samples:          M used.
        kappa:              CS shape parameter; default 0.5 per Dutta 2022.
        sigma_theta:        Frozen tuple of ``(name, sigma)`` pairs used
                            for the noise model. Surfaces in the dialog.
        is_robust:          ``cs > robust_threshold`` (default 0.5).
        target_class:       The CF target class index.
        method:             Decomposition method of the input blob.
    """

    cs: float
    mu: float
    sigma: float
    invalidation_rate: float
    n_samples: int
    kappa: float
    sigma_theta: tuple[tuple[str, float], ...]
    is_robust: bool
    target_class: int
    method: str


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


_cs_cache: dict[str, CSResult] = {}


def cache_key(
    blob: DecompositionBlob,
    target_class: int,
    n_samples: int,
    kappa: float,
    seed: int,
    *,
    sigma_theta: Mapping[str, float] | None = None,
) -> str:
    """Stable cache key per ``(blob_hash, target_class, M, κ, seed, σ_θ)``."""
    h = hashlib.sha256()
    h.update(blob.method.encode())
    h.update(b"|coeffs|")
    for name in sorted(blob.coefficients):
        val = blob.coefficients[name]
        h.update(f"|{name}={val!r}".encode())
    h.update(b"|comps|")
    for key in sorted(blob.components):
        arr = np.ascontiguousarray(np.asarray(blob.components[key], dtype=np.float64))
        h.update(f"|{key}|".encode())
        h.update(arr.tobytes())
    if sigma_theta is not None:
        h.update(b"|sigma|")
        for name in sorted(sigma_theta):
            h.update(f"|{name}={float(sigma_theta[name])!r}".encode())
    h.update(f"|t={int(target_class)}|m={int(n_samples)}|k={float(kappa)!r}|s={int(seed)}".encode())
    return h.hexdigest()


def clear_cs_cache() -> None:
    """Drop every cached CS result."""
    _cs_cache.clear()


# ---------------------------------------------------------------------------
# σ_θ helper — derive from VAL-031 MBB CIs
# ---------------------------------------------------------------------------


def sigma_theta_from_mbb(
    blob: DecompositionBlob,
    refit_fn: Callable[[np.ndarray], DecompositionBlob],
    *,
    coefficient_names: list[str] | None = None,
    n_replicates: int = 999,
    seed: int = 0,
    series_id: Hashable | None = None,
) -> dict[str, float]:
    """Return ``{coefficient_name: σ_θ}`` derived from VAL-031 MBB CIs.

    For each scalar coefficient, runs ``mbb_coefficient_ci`` and converts
    the 95 % CI half-width into a Gaussian-equivalent SE
    ``(ci_upper − ci_lower) / (2 · 1.96)``. This is the AC-required
    "noise model calibrated to per-coefficient MBB SEs" — the publishable
    novel piece. Non-scalar coefficients are skipped (CS is undefined on
    vector coefficients here).

    Raises ``CSCoefficientError`` if no scalar coefficients survive — the
    caller almost certainly intended this fit to expose at least one.
    """
    from app.services.validation.mbb import mbb_coefficient_ci  # noqa: PLC0415

    names = coefficient_names if coefficient_names is not None else list(blob.coefficients)
    out: dict[str, float] = {}
    for name in names:
        val = blob.coefficients.get(name)
        if not isinstance(val, (int, float, np.integer, np.floating)):
            continue
        try:
            mbb = mbb_coefficient_ci(
                blob, name, refit_fn,
                n_replicates=n_replicates, seed=seed,
                series_id=series_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "sigma_theta_from_mbb: MBB failed for %r: %s; skipping coefficient.",
                name, exc,
            )
            continue
        ci_half_width = (mbb.ci_upper - mbb.ci_lower) / 2.0
        sigma_eq = ci_half_width / 1.959963984540054  # ≈ 1.96 (Φ⁻¹(0.975))
        out[name] = float(max(0.0, sigma_eq))
    if not out:
        raise CSCoefficientError(
            "sigma_theta_from_mbb: no scalar coefficients survived MBB calibration; "
            "supply sigma_theta explicitly or check the refit function."
        )
    return out


# ---------------------------------------------------------------------------
# CS in coefficient space (Monte Carlo)
# ---------------------------------------------------------------------------


def cs_coefficient_space(
    blob: DecompositionBlob,
    target_class: int,
    model: ProbaModel,
    sigma_theta: Mapping[str, float] | None,
    reconstruct_fn: ReconstructFn,
    *,
    n_samples: int = DEFAULT_M_SAMPLES,
    kappa: float = DEFAULT_KAPPA,
    seed: int = 0,
    robust_threshold: float = DEFAULT_ROBUST_THRESHOLD,
    use_cache: bool = True,
) -> CSResult:
    """CS on a CF blob via Dutta 2022 Def. 1 in coefficient space.

    Pipeline:
      1. For each scalar coefficient ``c`` with ``σ_θ[c] > 0``, draw M
         independent ``ε_c ~ N(0, σ_θ[c]²)`` perturbations.
      2. For each draw m: ``θ_m = θ' + ε_m``; rebuild components via
         ``reconstruct_fn(θ_m, blob)`` and reassemble; query model.
      3. Track target-class probability ``p_m`` and base-class flips.
      4. Return ``CS = μ − κσ`` of ``{p_m}`` plus invalidation rate.

    Args:
        blob:           Edited (CF) decomposition blob — ``θ'``.
        target_class:   The CF target-class index.
        model:          Object with ``predict_proba(x) -> ndarray``.
        sigma_theta:    Per-coefficient SE map. Required: pass the result
                        of ``sigma_theta_from_mbb`` or supply your own
                        calibration.
        reconstruct_fn: Callable that rebuilds ``components`` from
                        perturbed coefficients. Method-specific; see the
                        ``ReconstructFn`` type alias for the contract.
        n_samples:      M; default 200 per Dutta 2022.
        kappa:          ``κ`` in ``CS = μ − κσ``; default 0.5.
        seed:           RNG seed for reproducibility.
        robust_threshold: ``cs > threshold`` ⇒ ``is_robust=True``;
                        default 0.5 per the AC.
        use_cache:      Cache hit returns the same object.

    Raises:
        ``CSCoefficientError`` when ``sigma_theta is None`` (the AC
        requires explicit calibration — call ``sigma_theta_from_mbb``
        first), when the perturbation map has no scalar entries, or when
        ``reconstruct_fn`` is missing.
    """
    if n_samples < 2:
        raise ValueError(f"n_samples must be ≥ 2; got {n_samples}")
    if kappa < 0:
        raise ValueError(f"kappa must be ≥ 0; got {kappa}")
    if sigma_theta is None:
        raise CSCoefficientError(
            "cs_coefficient_space: sigma_theta is required — calibrate via "
            "sigma_theta_from_mbb (VAL-031) or supply your own per-coefficient "
            "SE dict; the AC binds correctness to MBB-calibrated noise."
        )
    if reconstruct_fn is None:
        raise CSCoefficientError(
            "cs_coefficient_space: reconstruct_fn is required — VAL-032 cannot "
            "rebuild components from perturbed coefficients generically across "
            "the 10 supported decomposition methods. Supply a method-specific "
            "ReconstructFn that maps a coefficients dict + original blob to a "
            "fresh components dict."
        )

    # Filter to scalar coefficients with positive σ_θ.
    scalar_names = [
        name for name, val in blob.coefficients.items()
        if isinstance(val, (int, float, np.integer, np.floating))
        and float(sigma_theta.get(name, 0.0)) > 0.0
    ]
    if not scalar_names:
        raise CSCoefficientError(
            "cs_coefficient_space: no scalar coefficients with positive σ_θ; "
            f"available coefficients: {sorted(blob.coefficients)}, "
            f"σ_θ: {dict(sigma_theta)}."
        )

    sigma_pairs = tuple(
        (name, float(sigma_theta.get(name, 0.0)))
        for name in sorted(blob.coefficients)
    )

    key = cache_key(blob, int(target_class), int(n_samples), float(kappa),
                     int(seed), sigma_theta=sigma_theta)
    if use_cache and key in _cs_cache:
        return _cs_cache[key]

    rng = np.random.default_rng(int(seed))
    base_proba = np.asarray(model.predict_proba(blob.reassemble()),
                             dtype=np.float64).reshape(-1)
    if not (0 <= int(target_class) < base_proba.shape[0]):
        raise CSCoefficientError(
            f"target_class {target_class!r} out of range for predict_proba "
            f"output of length {base_proba.shape[0]}"
        )
    base_pred = int(np.argmax(base_proba))

    sigma_vec = np.asarray(
        [float(sigma_theta.get(name, 0.0)) for name in scalar_names],
        dtype=np.float64,
    )

    samples = np.empty(n_samples, dtype=np.float64)
    n_invalid = 0
    edited = dict(blob.coefficients)

    for m in range(n_samples):
        eps = rng.normal(0.0, sigma_vec)
        perturbed = dict(edited)
        for name, e in zip(scalar_names, eps):
            perturbed[name] = float(edited[name]) + float(e)
        new_components = reconstruct_fn(perturbed, blob)
        perturbed_blob = blob.with_coefficients(perturbed, components=new_components)
        x_m = perturbed_blob.reassemble()
        proba = np.asarray(model.predict_proba(x_m), dtype=np.float64).reshape(-1)
        samples[m] = proba[int(target_class)]
        if int(np.argmax(proba)) != base_pred:
            n_invalid += 1

    mu = float(np.mean(samples))
    sigma = float(np.std(samples, ddof=0))
    cs = mu - float(kappa) * sigma

    result = CSResult(
        cs=float(cs),
        mu=mu,
        sigma=sigma,
        invalidation_rate=float(n_invalid) / n_samples,
        n_samples=int(n_samples),
        kappa=float(kappa),
        sigma_theta=sigma_pairs,
        is_robust=bool(cs > robust_threshold),
        target_class=int(target_class),
        method=blob.method,
    )
    if use_cache:
        _cs_cache[key] = result
    return result


# ---------------------------------------------------------------------------
# Optional Hamman 2023 analytic bound (gated)
# ---------------------------------------------------------------------------


_SQRT_2 = math.sqrt(2.0)


def _normal_survival(x: float) -> float:
    """``1 − Φ(x)`` via ``erfc``; numerically stable in the deep tail."""
    return 0.5 * math.erfc(x / _SQRT_2)


def cs_analytic_bound(
    blob: DecompositionBlob,
    target_class: int,
    model: Any,
    sigma_theta: Mapping[str, float],
    coefficient_jacobian: CoefficientJacobianFn,
    *,
    decision_threshold: float = 0.5,
    analytic_bound: bool = False,
) -> float:
    """Hamman 2023 closed-form lower bound on Pr(robust).

    Per Hamman et al. ICML 2023 Eq. 6: assuming the coefficient
    perturbation propagates linearly through the reconstruction Jacobian
    and through the model's gradient, the prediction-shift is Gaussian
    with std ``σ_pred = √( Σ_c σ_θ[c]² · (∂P_target / ∂c)² )``. The
    closed-form lower bound on the robustness probability is then
    ``1 − Φ(−margin / σ_pred)`` where ``margin = P_target − decision_threshold``.

    Off by default (gated behind ``analytic_bound=True``) — the AC
    requires this to be opt-in because (a) it relies on the model
    exposing a gradient and (b) the linearisation may misrepresent
    nonlinear models. Toy-model tests verify the bound is ≤ the MC CS
    on a piecewise-linear fixture; production callers should treat this
    as a *confirmatory* number alongside the MC value.
    """
    if not analytic_bound:
        raise CSCoefficientError(
            "cs_analytic_bound: pass analytic_bound=True to opt in. The MC CS "
            "from cs_coefficient_space is the AC's primary metric; the "
            "Hamman 2023 bound is confirmatory and gated by design."
        )
    if not hasattr(model, "gradient"):
        raise CSCoefficientError(
            "cs_analytic_bound: model must expose .gradient(x) for the Hamman "
            "2023 closed-form. Use the MC path (cs_coefficient_space) for "
            "non-differentiable models."
        )
    jac = coefficient_jacobian(blob)
    x_orig = blob.reassemble()
    grad_x = np.asarray(model.gradient(x_orig), dtype=np.float64).reshape(-1)
    if grad_x.shape != x_orig.shape:
        raise CSCoefficientError(
            f"model.gradient returned shape {grad_x.shape}; expected {x_orig.shape}."
        )

    proba = np.asarray(model.predict_proba(x_orig), dtype=np.float64).reshape(-1)
    p_target = float(proba[int(target_class)])
    margin = p_target - float(decision_threshold)

    var_pred = 0.0
    for name, dx_dc in jac.items():
        sigma_c = float(sigma_theta.get(name, 0.0))
        if sigma_c <= 0.0:
            continue
        dx = np.asarray(dx_dc, dtype=np.float64).reshape(-1)
        if dx.shape != x_orig.shape:
            raise CSCoefficientError(
                f"coefficient_jacobian[{name!r}] shape {dx.shape}; expected "
                f"{x_orig.shape}."
            )
        # Chain rule: dP/dc = grad_x · dx/dc
        dp_dc = float(np.dot(grad_x, dx))
        var_pred += (sigma_c ** 2) * (dp_dc ** 2)
    if var_pred <= 0.0:
        # No sensitivity; bound is trivially 1.0 (always robust under linearisation).
        return 1.0
    sigma_pred = math.sqrt(var_pred)
    # Pr[P_perturbed > decision_threshold] ≈ 1 − Φ(−margin / σ_pred) = Φ(margin / σ_pred)
    return float(1.0 - _normal_survival(margin / max(sigma_pred, math.sqrt(_VAR_FLOOR))))
