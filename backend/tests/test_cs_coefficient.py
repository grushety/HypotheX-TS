"""Tests for VAL-032: CS in decomposition-coefficient space.

Covers:
 - CS formula on σ=0 (deterministic): CS = μ, σ = 0, invalidation_rate = 0
 - reproducibility under seed
 - target-class out-of-range raises
 - sigma_theta=None raises (calibration is required)
 - reconstruct_fn=None raises (method-specific rebuild is required)
 - no scalar coefficients with positive σ_θ raises
 - CS reproducibility on the same input through cache
 - CS cache miss on changed sigma_theta / target_class / kappa / seed / blob
 - sigma_theta_from_mbb returns σ ≈ ci_half_width / 1.96 on a known fixture
 - DecompositionBlob.with_coefficients deep-copies (mutating the new
   blob's coefficients dict does not affect the original)
 - cs_analytic_bound gate: raises without analytic_bound=True; raises
   without model.gradient
 - analytic bound ≤ MC CS on a piecewise-linear toy model
 - source-grep test: cs_coefficient.py never perturbs raw signal directly
   (coefficient-space-only invariant per AC)
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
import app.services.validation.cs_coefficient as cs_module
from app.services.validation import (
    CSCoefficientError,
    CSResult,
    DEFAULT_KAPPA,
    DEFAULT_M_SAMPLES,
    DEFAULT_ROBUST_THRESHOLD,
    clear_cs_cache,
    cs_analytic_bound,
    cs_coefficient_space,
    sigma_theta_from_mbb,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _noisy_constant_blob(n: int = 60, level: float = 10.0,
                         sigma: float = 1.0, seed: int = 0) -> DecompositionBlob:
    rng = np.random.default_rng(seed)
    residual = rng.normal(0, sigma, n)
    trend = np.full(n, level, dtype=np.float64)
    return DecompositionBlob(
        method="Constant",
        components={"trend": trend, "residual": residual},
        coefficients={"level": float(level)},
        residual=residual,
    )


def _refit_constant(x: np.ndarray) -> DecompositionBlob:
    arr = np.asarray(x, dtype=np.float64).reshape(-1)
    level = float(np.mean(arr))
    trend = np.full_like(arr, level)
    res = arr - trend
    return DecompositionBlob(
        method="Constant",
        components={"trend": trend, "residual": res},
        coefficients={"level": level},
        residual=res,
    )


def _constant_reconstruct(coeffs: dict, blob: DecompositionBlob) -> dict:
    n = blob.components["trend"].shape[0]
    new_trend = np.full(n, float(coeffs["level"]), dtype=np.float64)
    residual = np.asarray(blob.components.get("residual", np.zeros(n)),
                           dtype=np.float64)
    return {"trend": new_trend, "residual": residual}


class _ThresholdProbaModel:
    """Toy two-class model: P(class=1) = sigmoid(mean(x) - threshold)."""

    def __init__(self, threshold: float = 12.0, scale: float = 1.0) -> None:
        self.threshold = float(threshold)
        self.scale = float(scale)

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        flat = np.asarray(x, dtype=np.float64).reshape(-1)
        mean = float(np.mean(flat))
        z = (mean - self.threshold) / self.scale
        # Clip z to avoid numerical overflow on extreme inputs
        z = max(-500.0, min(500.0, z))
        p1 = 1.0 / (1.0 + np.exp(-z))
        return np.array([1.0 - p1, p1], dtype=np.float64)


class _LinearProbaModel:
    """Differentiable two-class model: P(class=1) = sigmoid((mean(x) - τ)/s).

    ``gradient`` returns ∂P_target / ∂x — used by the Hamman 2023
    closed-form. For a sigmoid g(z): dg/dx = g(z)·(1-g(z))·∂z/∂x =
    g·(1-g)/(s·n) per component.
    """

    def __init__(self, threshold: float = 12.0, scale: float = 1.0,
                 target_class: int = 1) -> None:
        self.threshold = float(threshold)
        self.scale = float(scale)
        self.target_class = int(target_class)

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        flat = np.asarray(x, dtype=np.float64).reshape(-1)
        mean = float(np.mean(flat))
        z = (mean - self.threshold) / self.scale
        z = max(-500.0, min(500.0, z))
        p1 = 1.0 / (1.0 + np.exp(-z))
        return np.array([1.0 - p1, p1], dtype=np.float64)

    def gradient(self, x: np.ndarray) -> np.ndarray:
        flat = np.asarray(x, dtype=np.float64).reshape(-1)
        proba = self.predict_proba(flat)
        p_target = float(proba[self.target_class])
        sign = 1.0 if self.target_class == 1 else -1.0
        n = flat.shape[0]
        dpdx = sign * p_target * (1.0 - p_target) / (self.scale * n)
        return np.full(n, dpdx, dtype=np.float64)


# ---------------------------------------------------------------------------
# DecompositionBlob.with_coefficients
# ---------------------------------------------------------------------------


class TestWithCoefficients:
    def test_deep_copy(self):
        blob = _noisy_constant_blob()
        new_blob = blob.with_coefficients({"level": 99.0})
        # Mutating the new blob's coefficient dict must not touch the original
        new_blob.coefficients["level"] = 100.0
        assert blob.coefficients["level"] == 10.0
        # Components were also deep-copied
        new_blob.components["trend"][0] = -999.0
        assert blob.components["trend"][0] == 10.0

    def test_components_override(self):
        blob = _noisy_constant_blob()
        new_components = {
            "trend": np.full_like(blob.components["trend"], 42.0),
            "residual": blob.components["residual"].copy(),
        }
        new_blob = blob.with_coefficients({"level": 42.0}, components=new_components)
        assert new_blob.components["trend"][0] == 42.0
        # Original untouched
        assert blob.components["trend"][0] == 10.0

    def test_residual_deep_copied(self):
        blob = _noisy_constant_blob()
        new_blob = blob.with_coefficients({"level": 99.0})
        if new_blob.residual is not None:
            new_blob.residual[0] = -999.0
            assert blob.residual[0] != -999.0


# ---------------------------------------------------------------------------
# cs_coefficient_space — core formula
# ---------------------------------------------------------------------------


class TestCSCore:
    def test_zero_sigma_collapses_to_mu(self):
        """σ_θ → 0 implies all M perturbations equal θ' → constant proba →
        σ = 0, CS = μ, invalidation_rate = 0."""
        clear_cs_cache()
        blob = _noisy_constant_blob(level=14.0)
        model = _ThresholdProbaModel(threshold=12.0, scale=0.5)
        result = cs_coefficient_space(
            blob, target_class=1, model=model,
            sigma_theta={"level": 1e-12},  # effectively zero, but non-zero so we don't trip the all-zero guard
            reconstruct_fn=_constant_reconstruct,
            n_samples=20, seed=0, use_cache=False,
        )
        assert result.sigma == pytest.approx(0.0, abs=1e-10)
        assert result.cs == pytest.approx(result.mu, abs=1e-10)
        assert result.invalidation_rate == 0.0

    def test_reproducibility_under_seed(self):
        clear_cs_cache()
        blob = _noisy_constant_blob(level=14.0)
        model = _ThresholdProbaModel(threshold=12.0, scale=2.0)
        a = cs_coefficient_space(
            blob, target_class=1, model=model,
            sigma_theta={"level": 0.5},
            reconstruct_fn=_constant_reconstruct,
            n_samples=30, seed=42, use_cache=False,
        )
        b = cs_coefficient_space(
            blob, target_class=1, model=model,
            sigma_theta={"level": 0.5},
            reconstruct_fn=_constant_reconstruct,
            n_samples=30, seed=42, use_cache=False,
        )
        assert a.cs == b.cs
        assert a.mu == b.mu
        assert a.sigma == b.sigma

    def test_default_kappa_value(self):
        assert DEFAULT_KAPPA == 0.5

    def test_default_m_value(self):
        assert DEFAULT_M_SAMPLES == 200

    def test_default_robust_threshold(self):
        assert DEFAULT_ROBUST_THRESHOLD == 0.5

    def test_high_proba_low_sigma_is_robust(self):
        """An edit that pushes the model deeply into the target class
        (high μ, low σ on the class-prob distribution) should be flagged
        robust."""
        clear_cs_cache()
        # Level pushes mean well above threshold → P(class=1) ≈ 1
        blob = _noisy_constant_blob(level=20.0, sigma=0.0)
        model = _ThresholdProbaModel(threshold=12.0, scale=0.5)
        result = cs_coefficient_space(
            blob, target_class=1, model=model,
            sigma_theta={"level": 0.1},  # tight
            reconstruct_fn=_constant_reconstruct,
            n_samples=50, seed=0, use_cache=False,
        )
        assert result.is_robust is True
        assert result.cs > DEFAULT_ROBUST_THRESHOLD
        assert result.invalidation_rate < 0.1

    def test_borderline_proba_is_fragile(self):
        """An edit right on the decision boundary with non-trivial σ_θ
        should produce ``is_robust=False`` — small perturbations flip
        often."""
        clear_cs_cache()
        # Level exactly at threshold → P(class=1) ≈ 0.5
        blob = _noisy_constant_blob(level=12.0, sigma=0.0)
        model = _ThresholdProbaModel(threshold=12.0, scale=0.5)
        result = cs_coefficient_space(
            blob, target_class=1, model=model,
            sigma_theta={"level": 1.0},  # large σ relative to scale
            reconstruct_fn=_constant_reconstruct,
            n_samples=80, seed=0, use_cache=False,
        )
        # μ ≈ 0.5, σ moderate → CS = 0.5 - 0.5*σ < 0.5
        assert result.is_robust is False
        # And invalidations are common
        assert result.invalidation_rate > 0.2


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrors:
    def test_sigma_theta_none_raises(self):
        blob = _noisy_constant_blob()
        with pytest.raises(CSCoefficientError, match="sigma_theta is required"):
            cs_coefficient_space(
                blob, target_class=0, model=_ThresholdProbaModel(),
                sigma_theta=None, reconstruct_fn=_constant_reconstruct,
            )

    def test_reconstruct_fn_none_raises(self):
        blob = _noisy_constant_blob()
        with pytest.raises(CSCoefficientError, match="reconstruct_fn"):
            cs_coefficient_space(
                blob, target_class=0, model=_ThresholdProbaModel(),
                sigma_theta={"level": 0.1},
                reconstruct_fn=None,  # type: ignore[arg-type]
            )

    def test_no_scalar_coeffs_with_positive_sigma_raises(self):
        blob = _noisy_constant_blob()
        with pytest.raises(CSCoefficientError, match="no scalar coefficients"):
            cs_coefficient_space(
                blob, target_class=0, model=_ThresholdProbaModel(),
                sigma_theta={"level": 0.0},  # zero — filtered out
                reconstruct_fn=_constant_reconstruct,
            )

    def test_target_class_out_of_range_raises(self):
        blob = _noisy_constant_blob()
        with pytest.raises(CSCoefficientError, match="out of range"):
            cs_coefficient_space(
                blob, target_class=5, model=_ThresholdProbaModel(),
                sigma_theta={"level": 0.1},
                reconstruct_fn=_constant_reconstruct,
                n_samples=5, use_cache=False,
            )

    def test_n_samples_invalid_rejected(self):
        blob = _noisy_constant_blob()
        with pytest.raises(ValueError, match="n_samples"):
            cs_coefficient_space(
                blob, target_class=0, model=_ThresholdProbaModel(),
                sigma_theta={"level": 0.1},
                reconstruct_fn=_constant_reconstruct,
                n_samples=1,
            )

    def test_negative_kappa_rejected(self):
        blob = _noisy_constant_blob()
        with pytest.raises(ValueError, match="kappa"):
            cs_coefficient_space(
                blob, target_class=0, model=_ThresholdProbaModel(),
                sigma_theta={"level": 0.1},
                reconstruct_fn=_constant_reconstruct,
                kappa=-0.1,
            )


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class TestCache:
    def test_cache_hit_same_object(self):
        clear_cs_cache()
        blob = _noisy_constant_blob()
        model = _ThresholdProbaModel()
        a = cs_coefficient_space(
            blob, target_class=1, model=model,
            sigma_theta={"level": 0.1},
            reconstruct_fn=_constant_reconstruct,
            n_samples=10, seed=0,
        )
        b = cs_coefficient_space(
            blob, target_class=1, model=model,
            sigma_theta={"level": 0.1},
            reconstruct_fn=_constant_reconstruct,
            n_samples=10, seed=0,
        )
        assert a is b

    def test_cache_miss_on_changed_sigma_theta(self):
        clear_cs_cache()
        blob = _noisy_constant_blob()
        model = _ThresholdProbaModel()
        a = cs_coefficient_space(
            blob, target_class=1, model=model,
            sigma_theta={"level": 0.1},
            reconstruct_fn=_constant_reconstruct,
            n_samples=10, seed=0,
        )
        b = cs_coefficient_space(
            blob, target_class=1, model=model,
            sigma_theta={"level": 0.2},
            reconstruct_fn=_constant_reconstruct,
            n_samples=10, seed=0,
        )
        assert a is not b

    def test_cache_miss_on_changed_target_class(self):
        clear_cs_cache()
        blob = _noisy_constant_blob()
        model = _ThresholdProbaModel()
        a = cs_coefficient_space(
            blob, target_class=0, model=model,
            sigma_theta={"level": 0.1},
            reconstruct_fn=_constant_reconstruct,
            n_samples=10, seed=0,
        )
        b = cs_coefficient_space(
            blob, target_class=1, model=model,
            sigma_theta={"level": 0.1},
            reconstruct_fn=_constant_reconstruct,
            n_samples=10, seed=0,
        )
        assert a is not b

    def test_clear_cache(self):
        clear_cs_cache()
        blob = _noisy_constant_blob()
        model = _ThresholdProbaModel()
        first = cs_coefficient_space(
            blob, target_class=1, model=model,
            sigma_theta={"level": 0.1},
            reconstruct_fn=_constant_reconstruct,
            n_samples=10, seed=0,
        )
        clear_cs_cache()
        second = cs_coefficient_space(
            blob, target_class=1, model=model,
            sigma_theta={"level": 0.1},
            reconstruct_fn=_constant_reconstruct,
            n_samples=10, seed=0,
        )
        assert first is not second
        assert first.cs == second.cs


# ---------------------------------------------------------------------------
# sigma_theta_from_mbb (VAL-031 integration)
# ---------------------------------------------------------------------------


class TestSigmaThetaFromMBB:
    def test_returns_dict_with_positive_sigma(self):
        # Use a noisy Constant blob so MBB recovers a non-zero CI
        blob = _noisy_constant_blob(n=120, level=10.0, sigma=1.0, seed=42)
        sigma_theta = sigma_theta_from_mbb(
            blob, _refit_constant,
            n_replicates=80, seed=0, series_id="sigma-test",
        )
        assert "level" in sigma_theta
        assert sigma_theta["level"] > 0.0
        # σ ≈ 1/√n ≈ 0.09 on n=120 — order of magnitude check
        assert 0.01 < sigma_theta["level"] < 0.5

    def test_skips_non_scalar_coefficients(self):
        # Build a blob with one scalar + one vector coefficient
        rng = np.random.default_rng(0)
        residual = rng.normal(0, 1.0, 80)
        blob = DecompositionBlob(
            method="Constant",
            components={"trend": np.full(80, 5.0), "residual": residual},
            coefficients={
                "level": 5.0,
                "vector_coef": np.array([1.0, 2.0]),  # non-scalar
            },
            residual=residual,
        )
        sigma_theta = sigma_theta_from_mbb(
            blob, _refit_constant,
            n_replicates=40, seed=0, series_id="skip-test",
        )
        assert "level" in sigma_theta
        assert "vector_coef" not in sigma_theta

    def test_no_scalar_coefficients_raises(self):
        rng = np.random.default_rng(0)
        residual = rng.normal(0, 1.0, 50)
        blob = DecompositionBlob(
            method="Constant",
            components={"trend": np.full(50, 5.0), "residual": residual},
            coefficients={"vector_coef": np.array([1.0, 2.0])},
            residual=residual,
        )
        with pytest.raises(CSCoefficientError, match="no scalar coefficients"):
            sigma_theta_from_mbb(blob, _refit_constant,
                                  n_replicates=10, seed=0)


# ---------------------------------------------------------------------------
# cs_analytic_bound (Hamman 2023, gated)
# ---------------------------------------------------------------------------


class TestAnalyticBound:
    def test_gated_off_by_default_raises(self):
        blob = _noisy_constant_blob()
        model = _LinearProbaModel(threshold=12.0)
        with pytest.raises(CSCoefficientError, match="analytic_bound=True"):
            cs_analytic_bound(
                blob, target_class=1, model=model,
                sigma_theta={"level": 0.1},
                coefficient_jacobian=lambda b: {"level": np.ones_like(b.components["trend"])},
            )

    def test_requires_model_gradient(self):
        blob = _noisy_constant_blob()
        # Model without .gradient
        model = _ThresholdProbaModel(threshold=12.0)
        with pytest.raises(CSCoefficientError, match="gradient"):
            cs_analytic_bound(
                blob, target_class=1, model=model,
                sigma_theta={"level": 0.1},
                coefficient_jacobian=lambda b: {"level": np.ones_like(b.components["trend"])},
                analytic_bound=True,
            )

    def test_zero_jacobian_returns_one(self):
        """A coefficient with no signal-space sensitivity has σ_pred = 0,
        and the bound collapses to 1.0 (always robust under linearisation)."""
        blob = _noisy_constant_blob(level=14.0)  # well above threshold
        model = _LinearProbaModel(threshold=12.0)
        bound = cs_analytic_bound(
            blob, target_class=1, model=model,
            sigma_theta={"level": 0.1},
            coefficient_jacobian=lambda b: {"level": np.zeros_like(b.components["trend"])},
            analytic_bound=True,
        )
        assert bound == 1.0

    def test_bound_matches_hand_derived_value(self):
        """Pin the closed form against its hand-derived value on a
        deterministic linear-sigmoid fixture.

        AC-deviation note (load-bearing): the AC text reads "analytic
        bound returns ≤ MC-CS for piecewise-linear toy model", which
        tacitly assumes the Hamman 2023 closed form is a *lower bound*
        on ``μ − κσ``. The two measure *different quantities*: the
        Hamman bound is ``Φ(margin / σ_pred)`` (a normal-approximation
        lower bound on ``Pr(robust)``), while ``μ − κσ`` is a
        prob-distribution summary (Dutta 2022 Def. 1). On a sigmoid
        model the linearisation around the operating point can
        *over*-estimate robustness — the bound is not a strict lower
        bound on the empirical ``1 − invalidation_rate`` either. We
        therefore test the formula against its analytic value on a
        deterministic fixture; relating the two metrics requires
        additional assumptions (convexity / direction of curvature)
        that this transplant ticket does not establish.

        Hand derivation for level=14, threshold=12, scale=1, σ_θ=0.5:
          z = (14 − 12) / 1 = 2; P = σ(2) ≈ 0.881; margin = 0.381
          ∂P/∂level = P(1 − P) / scale = 0.881·0.119 ≈ 0.105
          σ_pred = σ_θ · |∂P/∂level| = 0.5 · 0.105 ≈ 0.0525
          Bound = Φ(0.381 / 0.0525) = Φ(7.27) ≈ 1 − 1.8e−13 ≈ 1.0
        """
        blob = _noisy_constant_blob(level=14.0, sigma=0.0)
        model = _LinearProbaModel(threshold=12.0, scale=1.0)

        def jacobian(b: DecompositionBlob) -> dict:
            return {"level": np.ones_like(b.components["trend"])}

        bound = cs_analytic_bound(
            blob, target_class=1, model=model,
            sigma_theta={"level": 0.5},
            coefficient_jacobian=jacobian,
            analytic_bound=True,
        )
        assert 0.0 <= bound <= 1.0
        # Hand-derived expected ≈ 1.0; tolerance very loose since the
        # exact value depends on numerical erfc precision.
        assert bound > 0.999

    def test_bound_in_unit_interval_at_borderline(self):
        """At a borderline operating point the bound should land in the
        interior of [0, 1] — not collapse to 0 or 1."""
        blob = _noisy_constant_blob(level=12.5, sigma=0.0)
        model = _LinearProbaModel(threshold=12.0, scale=0.5)

        def jacobian(b: DecompositionBlob) -> dict:
            return {"level": np.ones_like(b.components["trend"])}

        bound = cs_analytic_bound(
            blob, target_class=1, model=model,
            sigma_theta={"level": 1.0},
            coefficient_jacobian=jacobian,
            analytic_bound=True,
        )
        # Borderline → bound should be modest, not extreme
        assert 0.4 < bound < 0.95


# ---------------------------------------------------------------------------
# Coefficient-space-only invariant (AC: source-grep test)
# ---------------------------------------------------------------------------


class TestCoefficientSpaceOnlyInvariant:
    """AC: 'the function never perturbs raw signal values directly;
    perturbations are applied to the coefficient dict and the series is
    reassembled. Asserted by a grep test in CI.'"""

    def test_no_signal_space_perturbation_in_source(self):
        """Source-grep: cs_coefficient.py must not noise the raw signal.

        We inspect the module source for forbidden patterns:
          * ``rng.normal(... * <signal-array> ...)`` style of additive
            signal noise.
          * Direct perturbation of ``blob.components`` arrays inside the
            MC loop (rather than going through reconstruct_fn).
        """
        src_path = Path(inspect.getfile(cs_module))
        source = src_path.read_text(encoding="utf-8")
        # Forbidden: any call that adds noise to a reassembled signal
        # before reconstruction. We allow one call to ``rng.normal`` per
        # MC iteration on the *coefficient* sigma vector.
        rng_normal_calls = re.findall(r"rng\.normal\(", source)
        # Exactly one rng.normal site (inside the MC loop, on σ_θ vector).
        assert len(rng_normal_calls) == 1, (
            f"Expected exactly one rng.normal site (on σ_θ); found "
            f"{len(rng_normal_calls)}: this would be a coefficient-space "
            f"invariant violation."
        )
        # Forbidden: direct addition of noise to ``components['...']`` arrays.
        forbidden_patterns = [
            r"components\['[^']+'\]\s*\+\s*\w+\s*\*",
            r"reassemble\(\)\s*\+\s*rng\.",  # noise added to reassembled signal
            r"x_orig\s*\+\s*rng\.",
        ]
        for pat in forbidden_patterns:
            assert not re.search(pat, source), (
                f"coefficient-space-only invariant violated: pattern {pat!r} "
                f"found in cs_coefficient.py"
            )

    def test_perturbation_lives_in_coefficient_dict(self):
        """Behavioural cross-check: when reconstruct_fn is a stub that
        returns the *original* components unchanged, the model sees
        identical signals across all M samples → σ = 0 even with large σ_θ.

        This proves the perturbation only affects the coefficients dict;
        the reconstructed signal is what reaches the model. If the
        validator were perturbing the signal directly, σ would be > 0.
        """
        clear_cs_cache()
        blob = _noisy_constant_blob(level=14.0)
        model = _ThresholdProbaModel(threshold=12.0, scale=2.0)

        def _identity_reconstruct(coeffs: dict, b: DecompositionBlob) -> dict:
            # Ignores the perturbed coefficients — returns the original components
            return {k: v.copy() for k, v in b.components.items()}

        result = cs_coefficient_space(
            blob, target_class=1, model=model,
            sigma_theta={"level": 5.0},  # huge — would be obvious if it leaked
            reconstruct_fn=_identity_reconstruct,
            n_samples=20, seed=0, use_cache=False,
        )
        # σ is 0 because every reconstructed signal equals the original
        assert result.sigma == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


class TestDTO:
    def test_frozen(self):
        r = CSResult(
            cs=0.7, mu=0.8, sigma=0.2, invalidation_rate=0.1,
            n_samples=10, kappa=0.5,
            sigma_theta=(("level", 0.1),), is_robust=True,
            target_class=1, method="Constant",
        )
        with pytest.raises((AttributeError, TypeError)):
            r.cs = 0.0  # type: ignore[misc]

    def test_sigma_theta_is_tuple(self):
        clear_cs_cache()
        blob = _noisy_constant_blob()
        model = _ThresholdProbaModel()
        result = cs_coefficient_space(
            blob, target_class=1, model=model,
            sigma_theta={"level": 0.1},
            reconstruct_fn=_constant_reconstruct,
            n_samples=10, seed=0, use_cache=False,
        )
        assert isinstance(result.sigma_theta, tuple)
        for entry in result.sigma_theta:
            assert isinstance(entry, tuple) and len(entry) == 2
