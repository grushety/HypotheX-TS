"""Cherry-picking risk score (VAL-013).

Quantifies the extent to which the CFs the user has *accepted* deviate
systematically from the utility distribution of the *admissible* CF
space. Operationalises:

  Hinns, Goethals, Van der Veeken, Evgeniou, Martens, "On the Definition
  and Detection of Cherry-Picking in Counterfactual Explanations,"
  arXiv:2601.04977 (Jan 2026)

for time series. The Hinns et al. paper is **tabular-only**; this module
is the first deployment of the data-access-level detector to TS-CF, and
the first interactive deployment to any modality. Methodological caveats:

  1. **Data-access level only.** Hinns 2026 §3 distinguishes the
     explanation-only and data-access-level detectors. HypotheX-TS has
     model access by construction, so the (more powerful) data-access
     detector is feasible. The explanation-only detector is "extremely
     limited in practice" (Hinns 2026 §6) and is not implemented here.

  2. **Utility function is plug-in.** The AC's default weighting is
     ``0.4·plausibility + 0.3·sparsity + 0.3·validity`` — this is a
     project-specific choice, not derived from the paper. The choice of
     u in §4 of Hinns 2026 is left open; the weighting must be reported
     in publications using this metric.

  3. **Admissible-CF distribution comes from the project's typed-op
     random walk.** Hinns 2026 assumes uniform sampling from ``E(x)``;
     we approximate this by drawing 200 random Tier-1/2/3 ops via the
     existing operations registries. This is the project-local sampling
     distribution and is *not* uniform on the manifold; the score
     measures bias relative to that distribution, not relative to a
     theoretical optimum.

The KS test against uniform is the operational predicate: if the user
is unbiased, the per-CF utility quantiles ``q_i = F(u_i)`` (where ``F``
is the empirical CDF of the admissible-CF utility distribution) are
distributed uniform[0, 1]. Systematic cherry-picking — toward high or
low utility — creates a non-uniform distribution that the KS test
rejects.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Callable, Hashable, Iterable, Protocol

import numpy as np


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CherryPickingError(RuntimeError):
    """Raised when sampling or utility evaluation fails on otherwise-valid input."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


DEFAULT_N_SAMPLES = 200
DEFAULT_MIN_ACCEPTED = 3
DEFAULT_TIP_SCORE_THRESHOLD = 0.7

DEFAULT_UTILITY_WEIGHTS: tuple[float, float, float] = (0.4, 0.3, 0.3)
# (plausibility, sparsity, validity) — AC-default weighting.


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


class AdmissibleCFSampler(Protocol):
    """Plugs into :class:`CherryPickingDetector` to draw admissible CFs.

    Production sampler delegates to OP-012 (replace_from_library) and
    OP-020..026 (Tier-2 ops) to draw ``n`` admissible CFs for a given
    original instance ``x_original``. The detector caches the resulting
    utility distribution per ``instance_key`` so the sampler is invoked
    at most once per original.
    """

    def sample(self, x_original: Any, n: int) -> list[Any]:  # pragma: no cover - protocol
        ...


# A utility function maps a CF-like object to a scalar in [0, 1].
UtilityFn = Callable[[Any], float]


# ---------------------------------------------------------------------------
# Default utility function
# ---------------------------------------------------------------------------


def default_utility_fn(
    cf: Any,
    *,
    weights: tuple[float, float, float] = DEFAULT_UTILITY_WEIGHTS,
) -> float:
    """AC-default utility: ``0.4·plausibility + 0.3·sparsity + 0.3·validity``.

    Expects ``cf`` to expose three attributes:
      * ``plausibility`` ∈ [0, 1] — typically ``YnnResult.ynn``.
      * ``sparsity`` ∈ [0, 1] — typically ``NativeGuideResult.sparsity``.
      * ``is_valid`` (bool or 0/1 numeric) — model-flipped-to-target.

    Each component is clipped to [0, 1] before weighting; missing
    attributes default to 0. The final value is clipped to [0, 1] to
    guarantee the contract for downstream KS testing.

    Callers who maintain a different utility definition should pass
    their own ``UtilityFn`` to ``CherryPickingDetector``.
    """
    p = float(getattr(cf, "plausibility", 0.0))
    s = float(getattr(cf, "sparsity", 0.0))
    v = float(getattr(cf, "is_valid", 0.0))
    p = max(0.0, min(1.0, p))
    s = max(0.0, min(1.0, s))
    v = max(0.0, min(1.0, v))
    w_p, w_s, w_v = weights
    if not np.isclose(w_p + w_s + w_v, 1.0, atol=1e-9):
        warnings.warn(
            f"default_utility_fn: weights do not sum to 1 (got {weights}); "
            "the AC-default weighting is (0.4, 0.3, 0.3).",
            RuntimeWarning,
            stacklevel=2,
        )
    u = w_p * p + w_s * s + w_v * v
    return float(max(0.0, min(1.0, u)))


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CherryPickingScore:
    """Outcome of the cherry-picking detector at a session snapshot.

    Attributes:
        score:                   1 − p_value of the KS test against uniform[0, 1];
                                 ∈ [0, 1], higher = more suspicious.
                                 0 when ``n_accepted < min_accepted`` (under-sampled).
        accepted_quantile_mean:  Mean utility-quantile of accepted CFs.
                                 0.5 under unbiased selection.
        expected_under_random:   The null mean (always 0.5 for uniform).
        p_value:                 Two-sided KS p-value; 1.0 when ``n_accepted < min_accepted``.
        recommendation:          Plain-text guidance string for the tip
                                 engine; ``None`` when ``score < tip_score_threshold``.
        n_accepted:              Number of accepted CFs the score saw.
        tip_should_fire:         ``score > tip_score_threshold``;
                                 precomputed so the UI doesn't have to.
    """

    score: float
    accepted_quantile_mean: float
    expected_under_random: float
    p_value: float
    recommendation: str | None
    n_accepted: int
    tip_should_fire: bool


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class CherryPickingDetector:
    """Session-level cherry-picking risk tracker.

    Lifecycle:

        detector = CherryPickingDetector(sampler, utility_fn)
        detector.on_accepted(cf, x_original, instance_key="series-42")
        ...
        result = detector.score()

    The ``instance_key`` is the cache key for the per-original utility
    distribution — same key ⇒ the sampler is invoked at most once.
    Defaults to ``id(x_original)`` if not supplied; callers with
    a stable identifier (series_id, audit-log row id) should pass it
    explicitly so the cache survives object-identity churn.

    ``sample_size`` (n in Hinns 2026 §4) defaults to 200 per the AC.
    """

    def __init__(
        self,
        sampler: AdmissibleCFSampler,
        utility_fn: UtilityFn = default_utility_fn,
        *,
        sample_size: int = DEFAULT_N_SAMPLES,
        min_accepted: int = DEFAULT_MIN_ACCEPTED,
        tip_score_threshold: float = DEFAULT_TIP_SCORE_THRESHOLD,
        rng: np.random.Generator | None = None,
    ) -> None:
        if sample_size < 1:
            raise ValueError(f"sample_size must be ≥ 1; got {sample_size}")
        if min_accepted < 1:
            raise ValueError(f"min_accepted must be ≥ 1; got {min_accepted}")
        if not 0.0 <= tip_score_threshold <= 1.0:
            raise ValueError(
                f"tip_score_threshold must be in [0, 1]; got {tip_score_threshold}"
            )

        self._sampler = sampler
        self._utility_fn = utility_fn
        self.sample_size = int(sample_size)
        self.min_accepted = int(min_accepted)
        self.tip_score_threshold = float(tip_score_threshold)
        self._rng = rng if rng is not None else np.random.default_rng()

        # cache: instance_key → sorted list of admissible-CF utilities.
        self._utility_cache: dict[Hashable, list[float]] = {}
        self._accepted_quantiles: list[float] = []

    # -------- ingest -------------------------------------------------------

    def on_accepted(
        self,
        cf: Any,
        x_original: Any,
        *,
        instance_key: Hashable | None = None,
    ) -> float:
        """Record an accepted CF; return its utility quantile.

        The quantile is the empirical CDF of the admissible-CF utility
        distribution at the accepted CF's utility — i.e. the fraction
        of admissible draws whose utility is ≤ the accepted utility.
        """
        u_accepted = float(self._utility_fn(cf))
        if not np.isfinite(u_accepted):
            raise CherryPickingError(
                f"utility_fn returned non-finite value {u_accepted} for accepted CF"
            )

        key = instance_key if instance_key is not None else id(x_original)
        if key not in self._utility_cache:
            samples = self._sampler.sample(x_original, self.sample_size)
            if not samples:
                raise CherryPickingError(
                    f"sampler returned no admissible CFs for instance_key={key!r}"
                )
            utilities = [float(self._utility_fn(s)) for s in samples]
            utilities = [u for u in utilities if np.isfinite(u)]
            if not utilities:
                raise CherryPickingError(
                    f"all admissible-CF utilities are non-finite for instance_key={key!r}"
                )
            self._utility_cache[key] = sorted(utilities)

        dist = self._utility_cache[key]
        # Empirical CDF: fraction of dist ≤ u_accepted (right-side
        # searchsorted matches the pseudocode's "u <= u_accepted").
        rank = int(np.searchsorted(dist, u_accepted, side="right"))
        quantile = rank / len(dist)
        self._accepted_quantiles.append(float(quantile))
        return float(quantile)

    # -------- query --------------------------------------------------------

    def score(self) -> CherryPickingScore:
        n = len(self._accepted_quantiles)
        if n < self.min_accepted:
            return CherryPickingScore(
                score=0.0,
                accepted_quantile_mean=(
                    float(np.mean(self._accepted_quantiles)) if n else 0.0
                ),
                expected_under_random=0.5,
                p_value=1.0,
                recommendation=None,
                n_accepted=n,
                tip_should_fire=False,
            )

        quantiles = np.asarray(self._accepted_quantiles, dtype=np.float64)
        from scipy.stats import kstest  # noqa: PLC0415
        stat, p_value = kstest(quantiles, "uniform")
        score_val = float(1.0 - float(p_value))
        mean_q = float(np.mean(quantiles))

        recommendation = self._recommend(quantiles, score_val, mean_q)
        return CherryPickingScore(
            score=score_val,
            accepted_quantile_mean=mean_q,
            expected_under_random=0.5,
            p_value=float(p_value),
            recommendation=recommendation,
            n_accepted=n,
            tip_should_fire=bool(score_val > self.tip_score_threshold),
        )

    def _recommend(
        self,
        quantiles: np.ndarray,
        score_val: float,
        mean_q: float,
    ) -> str | None:
        if score_val < self.tip_score_threshold:
            return None
        if mean_q > 0.8:
            return (
                "All accepted CFs sit in the top utility quantile — try one with "
                "intermediate plausibility for contrast."
            )
        if mean_q < 0.2:
            return (
                "All accepted CFs sit in the bottom utility quantile — surface "
                "the model's preferred CF for comparison."
            )
        return (
            "Quantile distribution of accepted CFs is non-uniform — "
            "consider exploring a less-explored region."
        )

    # -------- introspection -----------------------------------------------

    @property
    def n_accepted(self) -> int:
        return len(self._accepted_quantiles)

    @property
    def accepted_quantiles(self) -> list[float]:
        """Read-only snapshot of the per-CF utility quantiles."""
        return list(self._accepted_quantiles)

    @property
    def cached_instance_keys(self) -> list[Hashable]:
        return list(self._utility_cache.keys())

    # -------- lifecycle ---------------------------------------------------

    def reset(self) -> None:
        """Zero accepted-CF quantiles and the per-instance utility cache.

        The session-vs-task split is the caller's choice: a session
        guardrail calls ``reset`` on session end; a task guardrail on
        CF-task complete. The utility cache is also cleared because the
        admissible-CF distribution is meaningful only relative to the
        original instances of the *current* session.
        """
        self._accepted_quantiles.clear()
        self._utility_cache.clear()

    def replay(
        self,
        accepted: Iterable[tuple[Any, Any, Hashable | None]],
    ) -> None:
        """Replay an ``(cf, x_original, instance_key)`` history.

        Equivalent to calling ``on_accepted`` for each tuple in order.
        Mirrors the persistence-replay pattern of VAL-010..012; the
        utility cache is rebuilt by re-sampling, so this is an honest
        replay rather than a snapshot reload.
        """
        for cf, x_original, key in accepted:
            self.on_accepted(cf, x_original, instance_key=key)
