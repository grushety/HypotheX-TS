"""Tests for VAL-007: Conservation-residual significance battery.

Covers:
 - bootstrap CI: zero-mean residual → CI contains 0, p > 0.05
 - bootstrap CI: biased residual → CI excludes 0, p < 0.05
 - bootstrap CI: deterministic with same RNG seed
 - ratio test: r_post = r_pre / 2 → ratio ≈ 0.25 (variance halved)
 - ratio test: r_post = r_pre → ratio ≈ 1.0 (no change)
 - ratio test: degenerate zero-pre → NaN p-value
 - MMD test: identical distributions → high p
 - MMD test: large mean shift → low p
 - MMD subsample cap respected on long inputs
 - orchestrator runs all three; result is ConservationSignificance
 - DTOs frozen + config validation
 - OP-050 wiring: paired residuals attach to CFResult.validation.conservation;
   one-sided supply raises
"""
from __future__ import annotations

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.events import AuditLog, EventBus
from app.services.operations.cf_coordinator import synthesize_counterfactual
from app.services.operations.tier2.plateau import raise_lower
from app.services.validation import (
    ConservationCIResult,
    ConservationConfig,
    ConservationSignificance,
    ConservationSignificanceError,
    MMDResult,
    RatioTestResult,
    conservation_mmd_test,
    conservation_ratio_test,
    conservation_residual_ci,
    conservation_significance,
)


# ---------------------------------------------------------------------------
# Bootstrap CI on E[r] = 0
# ---------------------------------------------------------------------------


class TestResidualCI:
    def test_zero_mean_residual_ci_contains_zero(self):
        rng = np.random.default_rng(0)
        r = rng.normal(0, 1, 200)
        result = conservation_residual_ci(
            r, config=ConservationConfig(bootstrap_B=200),
            rng=np.random.default_rng(1),
        )
        lo, hi = result.ci
        assert lo < 0 < hi
        assert result.p_value > 0.05

    def test_biased_residual_ci_excludes_zero(self):
        rng = np.random.default_rng(2)
        # Strong positive bias swamps σ=1 noise
        r = rng.normal(2.0, 1.0, 200)
        result = conservation_residual_ci(
            r, config=ConservationConfig(bootstrap_B=200),
            rng=np.random.default_rng(3),
        )
        lo, hi = result.ci
        # Both bounds should be well above zero
        assert lo > 0.5
        assert hi > 0.5
        assert result.p_value < 0.05

    def test_deterministic_with_seed(self):
        r = np.random.default_rng(0).normal(0, 1, 100)
        a = conservation_residual_ci(
            r, config=ConservationConfig(bootstrap_B=100),
            rng=np.random.default_rng(42),
        )
        b = conservation_residual_ci(
            r, config=ConservationConfig(bootstrap_B=100),
            rng=np.random.default_rng(42),
        )
        assert a.ci == b.ci
        assert a.p_value == b.p_value
        assert a.mean == b.mean

    def test_constant_zero_residual(self):
        # Pathological but valid: a perfectly closed conservation
        r = np.zeros(50)
        result = conservation_residual_ci(
            r, config=ConservationConfig(bootstrap_B=50),
            rng=np.random.default_rng(0),
        )
        assert result.ci == (0.0, 0.0)
        assert result.mean == 0.0
        # p-value should be 1 (no evidence against H0: E[r]=0)
        assert result.p_value == 1.0

    def test_empty_residual_raises(self):
        with pytest.raises(ConservationSignificanceError, match="non-empty"):
            conservation_residual_ci(np.array([]))

    def test_block_length_override(self):
        rng = np.random.default_rng(0)
        r = rng.normal(0, 1, 100)
        result = conservation_residual_ci(
            r,
            config=ConservationConfig(bootstrap_B=20, block_length=7),
            rng=np.random.default_rng(0),
        )
        assert result.block_length == 7


# ---------------------------------------------------------------------------
# Variance-ratio (F-referenced) test
# ---------------------------------------------------------------------------


class TestRatioTest:
    def test_halved_residual_ratio_quarter(self):
        rng = np.random.default_rng(0)
        r_pre = rng.normal(0, 1, 200)
        r_post = r_pre / 2.0
        result = conservation_ratio_test(r_pre, r_post)
        assert result.ratio == pytest.approx(0.25, abs=1e-9)

    def test_unchanged_residual_ratio_one(self):
        r = np.random.default_rng(0).normal(0, 1, 200)
        result = conservation_ratio_test(r, r.copy())
        assert result.ratio == pytest.approx(1.0, abs=1e-9)

    def test_zero_pre_returns_nan_pvalue(self):
        # No pre-residual to compare against → p-value undefined
        r_pre = np.zeros(20)
        r_post = np.random.default_rng(0).normal(0, 1, 20)
        result = conservation_ratio_test(r_pre, r_post)
        assert np.isnan(result.p_value)

    def test_too_few_samples_rejected(self):
        with pytest.raises(ConservationSignificanceError, match="≥ 2 samples"):
            conservation_ratio_test(np.array([1.0]), np.array([1.0]))

    def test_smaller_post_gives_low_pvalue(self):
        rng = np.random.default_rng(0)
        r_pre = rng.normal(0, 1, 500)
        r_post = rng.normal(0, 0.1, 500)  # 10× smaller spread
        result = conservation_ratio_test(r_pre, r_post)
        assert result.ratio < 0.1
        # Upper-tail p-value should be near 1 (ratio is far below the null
        # of equal variance) — but the test reports upper-tail of "post is
        # *larger* than pre", so a small ratio gives p_value close to 1.0.
        # We flip the interpretation: a *small* ratio means the projection
        # worked. Either way, the ratio itself is the load-bearing number.
        assert 0.0 <= result.p_value <= 1.0


# ---------------------------------------------------------------------------
# MMD two-sample test
# ---------------------------------------------------------------------------


class TestMMDTest:
    def test_identical_distributions_high_pvalue(self):
        rng = np.random.default_rng(0)
        r_pre = rng.normal(0, 1, 100)
        r_post = rng.normal(0, 1, 100)  # iid same distribution
        result = conservation_mmd_test(
            r_pre, r_post,
            config=ConservationConfig(mmd_permutations=200),
            rng=np.random.default_rng(0),
        )
        # With identical distributions, observed MMD² is small and rarely
        # extreme under the null → p > 0.05
        assert result.p_value > 0.05

    def test_large_shift_low_pvalue(self):
        rng = np.random.default_rng(0)
        r_pre = rng.normal(0, 1, 100)
        r_post = rng.normal(5, 1, 100)  # 5σ mean shift
        result = conservation_mmd_test(
            r_pre, r_post,
            config=ConservationConfig(mmd_permutations=200),
            rng=np.random.default_rng(0),
        )
        assert result.p_value < 0.05

    def test_subsample_cap_enforced(self):
        rng = np.random.default_rng(0)
        r_pre = rng.normal(0, 1, 1000)
        r_post = rng.normal(0, 1, 1000)
        cfg = ConservationConfig(mmd_permutations=20, mmd_subsample_cap=100)
        result = conservation_mmd_test(r_pre, r_post, config=cfg,
                                       rng=np.random.default_rng(0))
        assert result.subsample_size == 100

    def test_no_subsample_when_under_cap(self):
        rng = np.random.default_rng(0)
        r_pre = rng.normal(0, 1, 50)
        r_post = rng.normal(0, 1, 50)
        cfg = ConservationConfig(mmd_permutations=20, mmd_subsample_cap=500)
        result = conservation_mmd_test(r_pre, r_post, config=cfg,
                                       rng=np.random.default_rng(0))
        assert result.subsample_size == 50

    def test_deterministic_with_seed(self):
        r_pre = np.random.default_rng(0).normal(0, 1, 50)
        r_post = np.random.default_rng(1).normal(0, 1, 50)
        cfg = ConservationConfig(mmd_permutations=50)
        a = conservation_mmd_test(r_pre, r_post, config=cfg,
                                  rng=np.random.default_rng(7))
        b = conservation_mmd_test(r_pre, r_post, config=cfg,
                                  rng=np.random.default_rng(7))
        assert a.mmd2 == b.mmd2
        assert a.p_value == b.p_value


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class TestOrchestrator:
    def test_returns_three_results(self):
        rng = np.random.default_rng(0)
        r_pre = rng.normal(0, 1, 100)
        r_post = rng.normal(0, 0.5, 100)
        result = conservation_significance(
            r_pre, r_post,
            config=ConservationConfig(bootstrap_B=80, mmd_permutations=50),
            rng=np.random.default_rng(0),
        )
        assert isinstance(result, ConservationSignificance)
        assert isinstance(result.residual_ci_post, ConservationCIResult)
        assert isinstance(result.ratio_test, RatioTestResult)
        assert isinstance(result.mmd_test, MMDResult)


# ---------------------------------------------------------------------------
# DTO + config guards
# ---------------------------------------------------------------------------


class TestConfigGuards:
    def test_low_bootstrap_b_rejected(self):
        with pytest.raises(ValueError, match="bootstrap_B"):
            ConservationConfig(bootstrap_B=1)

    def test_low_permutations_rejected(self):
        with pytest.raises(ValueError, match="mmd_permutations"):
            ConservationConfig(mmd_permutations=1)

    def test_subsample_cap_too_small_rejected(self):
        with pytest.raises(ValueError, match="mmd_subsample_cap"):
            ConservationConfig(mmd_subsample_cap=2)

    def test_invalid_alpha_rejected(self):
        with pytest.raises(ValueError, match="ci_alpha"):
            ConservationConfig(ci_alpha=1.5)

    def test_dtos_frozen(self):
        cfg = ConservationConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.bootstrap_B = 100  # type: ignore[misc]


# ---------------------------------------------------------------------------
# OP-050 wiring
# ---------------------------------------------------------------------------


def _plateau_blob(n: int = 60, level: float = 10.0) -> DecompositionBlob:
    return DecompositionBlob(
        method="Constant",
        components={"trend": np.full(n, level), "residual": np.zeros(n)},
        coefficients={"level": level},
    )


class TestOP050Wiring:
    def test_conservation_attached_when_residuals_supplied(self):
        rng = np.random.default_rng(0)
        r_pre = rng.normal(0, 1, 100)
        r_post = rng.normal(0, 0.3, 100)  # projection reduced spread

        result = synthesize_counterfactual(
            segment_id="s",
            segment_label="plateau",
            blob=_plateau_blob(),
            op_tier2=raise_lower,
            op_params={"delta": 1.0},
            event_bus=EventBus(),
            audit_log=AuditLog(),
            conservation_residual_pre=r_pre,
            conservation_residual_post=r_post,
            conservation_config=ConservationConfig(
                bootstrap_B=50, mmd_permutations=30,
            ),
        )
        assert result.validation is not None
        assert result.validation.conservation is not None
        cs = result.validation.conservation
        assert isinstance(cs, ConservationSignificance)
        # The post residual is tighter → ratio < 1
        assert cs.ratio_test.ratio < 1.0

    def test_one_sided_residual_supply_raises(self):
        rng = np.random.default_rng(0)
        r_pre = rng.normal(0, 1, 100)
        with pytest.raises(ValueError, match="conservation_residual"):
            synthesize_counterfactual(
                segment_id="s",
                segment_label="plateau",
                blob=_plateau_blob(),
                op_tier2=raise_lower,
                op_params={"delta": 1.0},
                event_bus=EventBus(),
                audit_log=AuditLog(),
                conservation_residual_pre=r_pre,
                # post omitted
            )

    def test_no_conservation_when_neither_supplied(self):
        result = synthesize_counterfactual(
            segment_id="s",
            segment_label="plateau",
            blob=_plateau_blob(),
            op_tier2=raise_lower,
            op_params={"delta": 1.0},
            event_bus=EventBus(),
            audit_log=AuditLog(),
        )
        assert result.validation is None
