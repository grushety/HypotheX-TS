"""Coefficient-CI z-score (VAL-005).

Bootstraps the per-coefficient distribution of a fitted ``DecompositionBlob``
and reports, per Tier-2 edit, how many σ the edited value lies from the
original fit's bootstrap mean. Surfaces "how extreme is this edit relative
to the model's own fitting uncertainty?"

Sources (binding for ``algorithm-auditor``):

  - Politis & Romano, "The Stationary Bootstrap," *JASA* 89:1303 (1994),
    DOI:10.1080/01621459.1994.10476870 — geometric-block resampler.
  - Politis & White, "Automatic Block-Length Selection," *Econometric
    Reviews* 23:53 (2004), with Patton (2009) correction —
    flat-top-kernel block-length selector.
  - Bergmeir, Hyndman, Benítez, "Bagging exponential smoothing methods
    using STL decomposition and Box–Cox transformation,"
    *Int. J. Forecasting* 32:303 (2016), DOI:10.1016/j.ijforecast.2015.07.002
    — residual-bootstrap-then-refit pipeline this module implements.

Pipeline per CI computation (offline, runs once per fit):

  1. Extract original residual ``r`` from ``blob.components['residual']`` (or
     ``blob.residual``); fall back to ``X − Σ non-residual components``.
  2. Auto-select block length via Politis-White 2004 if not supplied.
  3. ``B`` times: stationary-bootstrap ``r`` → ``r_b``; reassemble
     ``X_b = X̂ + r_b``; refit the *same* method; record scalar coefficients.
  4. Cache distributions to JSON keyed by ``(segment_id, blob_method)``.

Per-edit cost (hot path): O(1) lookup + arithmetic — z-score is just
``(value − mean) / max(std, 1e-12)``.

Native-CI fall-back: the AC notes that ETM and BFAST may expose native
CIs. The current decomposition fitters do not, so all seven methods route
through the residual bootstrap. Method-specific native-CI hooks can be
plugged in later without changing the validator's external API.
"""
from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import (
    FITTER_REGISTRY,
    _ensure_fitters_loaded,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CoefficientCIError(RuntimeError):
    """Raised when CI computation, cache I/O, or refit fails."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


DEFAULT_B = 500
DEFAULT_Z_THRESHOLD = 3.0
DEFAULT_CI_QUANTILES = (0.025, 0.975)  # 95% CI
_STD_FLOOR = 1e-12  # avoid div/0 on zero-variance distributions


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoefficientCIConfig:
    """Configuration for the coefficient-CI validator.

    B:           Number of bootstrap resamples; default 500.
    block_length: Stationary-bootstrap mean block length. ``None`` triggers
                 Politis-White (2004) auto-selection on the residual.
    z_threshold: Threshold above which ``is_extreme`` flips True; default 3σ.
    fit_kwargs:  Keyword arguments forwarded to the refit fitter (e.g. ``t``
                 for ETM). Empty by default — fitters fall back to their own
                 defaults.
    """

    B: int = DEFAULT_B
    block_length: int | None = None
    z_threshold: float = DEFAULT_Z_THRESHOLD
    fit_kwargs: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.B < 2:
            raise ValueError(f"B must be ≥ 2; got {self.B}")
        if self.block_length is not None and self.block_length < 1:
            raise ValueError(f"block_length must be ≥ 1; got {self.block_length}")
        if self.z_threshold <= 0:
            raise ValueError(f"z_threshold must be > 0; got {self.z_threshold}")


@dataclass(frozen=True)
class CoefficientCIResult:
    """Per-edit coefficient-CI outcome.

    Attributes:
        z_scores:        Mapping coefficient name → z-score.
        is_extreme:      Mapping coefficient name → ``|z| > z_threshold``.
        ci_95:           Mapping coefficient name → (lo, hi) 95% bootstrap CI.
        max_abs_z:       max(|z|) across all evaluated coefficients (NaN
                         when no scalar coefficients overlap).
        any_extreme:     True iff any coefficient is extreme.
        method:          Decomposition method used for the underlying fit.
        n_evaluated:     Number of coefficients with cached distributions.
    """

    z_scores: Mapping[str, float]
    is_extreme: Mapping[str, bool]
    ci_95: Mapping[str, tuple[float, float]]
    max_abs_z: float
    any_extreme: bool
    method: str
    n_evaluated: int


# ---------------------------------------------------------------------------
# Politis-Romano stationary bootstrap
# ---------------------------------------------------------------------------


def stationary_bootstrap(
    values: np.ndarray,
    block_length: int,
    *,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Generate a length-``n`` stationary-bootstrap resample of ``values``.

    Politis-Romano 1994: at each position the block continues with
    probability ``1 − 1/L`` (geometric block lengths, mean ``L``);
    otherwise a new starting index is drawn uniformly. Wrap-around at
    the end keeps stationarity.
    """
    if block_length < 1:
        raise ValueError(f"block_length must be ≥ 1; got {block_length}")
    arr = np.asarray(values, dtype=np.float64).reshape(-1)
    n = arr.shape[0]
    if n == 0:
        return arr.copy()
    generator = rng if rng is not None else np.random.default_rng()
    out = np.empty(n, dtype=np.float64)
    p = 1.0 / block_length
    idx = int(generator.integers(0, n))
    for t in range(n):
        out[t] = arr[idx]
        if generator.random() < p:
            idx = int(generator.integers(0, n))
        else:
            idx = (idx + 1) % n
    return out


# ---------------------------------------------------------------------------
# Politis-White 2004 + Patton 2009 block length
# ---------------------------------------------------------------------------


def _flat_top_kernel(x: float) -> float:
    """λ(x) per Politis-White 2004 — 1 if |x| ≤ 1/2, 2(1−|x|) if 1/2 < |x| ≤ 1, else 0."""
    a = abs(x)
    if a <= 0.5:
        return 1.0
    if a <= 1.0:
        return 2.0 * (1.0 - a)
    return 0.0


def _autocorrelations(values: np.ndarray, max_lag: int) -> np.ndarray:
    """Pearson autocorrelations ρ̂_k for k ∈ [0, max_lag]."""
    arr = np.asarray(values, dtype=np.float64).reshape(-1)
    n = arr.shape[0]
    centred = arr - arr.mean()
    var = float(np.dot(centred, centred) / n)
    if var <= 0.0:
        out = np.zeros(max_lag + 1, dtype=np.float64)
        out[0] = 1.0
        return out
    rhos = np.empty(max_lag + 1, dtype=np.float64)
    rhos[0] = 1.0
    for k in range(1, max_lag + 1):
        if k >= n:
            rhos[k] = 0.0
        else:
            rhos[k] = float(np.dot(centred[:-k], centred[k:]) / (n * var))
    return rhos


def politis_white_block_length(
    residual: np.ndarray,
    *,
    K_n: int | None = None,
) -> int:
    """Politis-White 2004 stationary-bootstrap block length on ``residual``.

    Implements §4 of Politis-White with the Patton (2009) correction:

        m̂ = smallest k > 0 such that 2 consecutive |ρ̂_k| are below
            2·√(log10(n)/n) for k > m̂; capped by ``K_n``.
        M  = max(2 m̂, 2)              # lag-window half-width
        b̂  = ⌈ (2·g(0)² / G)^(1/3) · n^(1/3) ⌉
        with  g(0) = Σ_{k=−M}^{M} λ(k/M) ρ̂_k
              G    = Σ_{k=−M}^{M} λ(k/M) |k| ρ̂_k

    Falls back to ``max(1, ⌈n^(1/3)⌉)`` when the data are degenerate
    (zero variance, or the spectral sums collapse to zero), the standard
    rule-of-thumb floor.
    """
    arr = np.asarray(residual, dtype=np.float64).reshape(-1)
    n = arr.shape[0]
    if n < 4:
        return max(1, int(math.ceil(n ** (1.0 / 3.0))) if n > 0 else 1)
    if K_n is None:
        K_n = max(5, int(math.ceil(math.sqrt(math.log10(n)))))
    K_n = min(K_n, n - 2)

    rhos = _autocorrelations(arr, max_lag=2 * K_n)
    if np.allclose(rhos[1:], 0.0):
        return max(1, int(math.ceil(n ** (1.0 / 3.0))))

    cutoff = 2.0 * math.sqrt(math.log10(n) / n)
    m_hat = 0
    for k in range(1, len(rhos) - 1):
        if abs(rhos[k]) < cutoff and abs(rhos[k + 1]) < cutoff:
            m_hat = k
            break
    if m_hat == 0:
        m_hat = max(1, K_n)
    M = max(2 * m_hat, 2)

    g0 = 0.0
    G = 0.0
    for k in range(-M, M + 1):
        weight = _flat_top_kernel(k / M)
        rho = rhos[abs(k)] if abs(k) < len(rhos) else 0.0
        g0 += weight * rho
        G += weight * abs(k) * rho
    if g0 <= 0.0 or G <= 0.0:
        return max(1, int(math.ceil(n ** (1.0 / 3.0))))

    b_hat = (2.0 * g0 ** 2 / G) ** (1.0 / 3.0) * n ** (1.0 / 3.0)
    return max(1, int(math.ceil(b_hat)))


# ---------------------------------------------------------------------------
# Refit dispatch
# ---------------------------------------------------------------------------


def refit_blob(
    method: str,
    X: np.ndarray,
    fit_kwargs: Mapping[str, Any] | None = None,
) -> DecompositionBlob:
    """Refit the named decomposition method on ``X``.

    Looks the method up in the dispatcher's ``FITTER_REGISTRY``; raises
    ``CoefficientCIError`` if no fitter is registered (typically because the
    fitter module was not loaded).
    """
    _ensure_fitters_loaded()
    fitter = FITTER_REGISTRY.get(method)
    if fitter is None:
        raise CoefficientCIError(
            f"No fitter registered for method {method!r}; refit is not possible. "
            f"Known methods: {sorted(FITTER_REGISTRY)}"
        )
    return fitter(X, **(fit_kwargs or {}))


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class CoefficientCIValidator:
    """Per-blob bootstrap CI on scalar coefficients.

    Construction runs the residual bootstrap immediately when no cached
    distributions are available. Pass ``segment_id`` (and optionally
    ``cache_dir``) to persist the distribution as JSON; subsequent
    constructions with the same ``segment_id`` rehydrate without
    recomputing — invalidate the cache by deleting the file or supplying
    ``rebuild=True``.

    Only *scalar* coefficients (int / float / numpy scalar) participate in
    the CI; non-scalar coefficient values (vectors, lists, dicts) are
    silently skipped.
    """

    def __init__(
        self,
        blob: DecompositionBlob,
        *,
        segment_id: str | None = None,
        config: CoefficientCIConfig | None = None,
        cache_dir: Path | str | None = None,
        rebuild: bool = False,
        rng: np.random.Generator | None = None,
    ) -> None:
        self._blob = blob
        self._segment_id = segment_id
        self.config = config or CoefficientCIConfig()
        self._cache_dir = Path(cache_dir) if cache_dir is not None else _default_cache_dir()
        self._rng = rng if rng is not None else np.random.default_rng()

        self.coeff_distributions: dict[str, np.ndarray] = {}
        self._block_length: int | None = self.config.block_length

        cache_path = self._cache_path()
        if not rebuild and cache_path is not None and cache_path.exists():
            self._load(cache_path)
        else:
            self._compute_ci()
            if cache_path is not None:
                self._save(cache_path)

    # -------- core CI computation -----------------------------------------

    def _compute_ci(self) -> None:
        residual = self._extract_residual()
        signal_part = self._signal_part()

        if self._block_length is None:
            self._block_length = politis_white_block_length(residual)

        scalar_coeffs = _scalar_coefficients(self._blob.coefficients)
        accumulator: dict[str, list[float]] = {name: [] for name in scalar_coeffs}

        for _ in range(self.config.B):
            r_b = stationary_bootstrap(
                residual, self._block_length, rng=self._rng
            ) if residual.size > 0 else residual.copy()
            X_b = signal_part + r_b
            try:
                blob_b = refit_blob(self._blob.method, X_b, self.config.fit_kwargs)
            except Exception as exc:  # noqa: BLE001
                # Skip this draw; warn once. Rare for the seven supported methods.
                warnings.warn(
                    f"Bootstrap refit raised on method {self._blob.method!r}: {exc}; "
                    "skipping this draw.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                continue
            for name in accumulator:
                value = blob_b.coefficients.get(name)
                if isinstance(value, (int, float, np.integer, np.floating)):
                    accumulator[name].append(float(value))

        self.coeff_distributions = {
            name: np.asarray(samples, dtype=np.float64)
            for name, samples in accumulator.items()
            if samples  # drop coefficients that disappeared on every refit
        }

    def _extract_residual(self) -> np.ndarray:
        if self._blob.residual is not None:
            return np.asarray(self._blob.residual, dtype=np.float64).reshape(-1)
        comp = self._blob.components.get("residual")
        if comp is not None:
            return np.asarray(comp, dtype=np.float64).reshape(-1)
        # Synthesise residual = X − sum(non-residual components).
        signal = self._blob.reassemble()
        return np.zeros_like(signal)

    def _signal_part(self) -> np.ndarray:
        signal = self._blob.reassemble()
        residual = self._extract_residual()
        if residual.shape == signal.shape:
            return signal - residual
        return signal

    # -------- per-edit (hot path) -----------------------------------------

    def z_score(self, coeff_name: str, edited_value: float) -> float:
        """Z-score of ``edited_value`` against the bootstrap distribution.

        Returns ``nan`` when ``coeff_name`` has no cached distribution.
        Floors the standard deviation at ``1e-12`` so a degenerate
        zero-variance distribution does not blow up to ``±inf`` for
        non-zero edits.
        """
        dist = self.coeff_distributions.get(coeff_name)
        if dist is None or dist.size == 0:
            return float("nan")
        mean = float(np.mean(dist))
        std = float(np.std(dist))
        return (float(edited_value) - mean) / max(std, _STD_FLOOR)

    def is_extreme(
        self,
        coeff_name: str,
        edited_value: float,
        *,
        threshold: float | None = None,
    ) -> bool:
        z = self.z_score(coeff_name, edited_value)
        if math.isnan(z):
            return False
        thr = self.config.z_threshold if threshold is None else float(threshold)
        return abs(z) > thr

    def ci(self, coeff_name: str, *, alpha: float = 0.05) -> tuple[float, float]:
        """Two-sided ``1 − α`` bootstrap CI; raises if the coefficient has no draws."""
        dist = self.coeff_distributions.get(coeff_name)
        if dist is None or dist.size == 0:
            raise CoefficientCIError(
                f"no cached distribution for coefficient {coeff_name!r}"
            )
        if not 0.0 < alpha < 1.0:
            raise ValueError(f"alpha must be in (0, 1); got {alpha}")
        lo, hi = np.quantile(dist, [alpha / 2, 1.0 - alpha / 2])
        return float(lo), float(hi)

    def validate(
        self,
        edited: DecompositionBlob | Mapping[str, Any] | np.ndarray,
    ) -> CoefficientCIResult:
        """Score every cached coefficient against the post-edit value.

        ``edited`` accepts:
          * ``np.ndarray`` — the post-edit signal (the typical OP-050 wiring).
            The validator refits the *same* decomposition method on the
            signal to recover post-edit coefficients. This is necessary
            because Tier-2 ops in this codebase deep-copy internally and
            return only ``Tier2OpResult.values``, leaving the caller's
            blob unchanged.
          * ``DecompositionBlob`` — when the caller already has a refit
            blob in hand; coefficients are read directly.
          * ``Mapping[str, Any]`` — a plain dict of coefficient overrides
            for tests / callers that extracted the values themselves.
        """
        if isinstance(edited, np.ndarray):
            try:
                refit = refit_blob(self._blob.method, edited, self.config.fit_kwargs)
            except Exception as exc:  # noqa: BLE001
                raise CoefficientCIError(
                    f"validate: refit on post-edit signal failed for method "
                    f"{self._blob.method!r}: {exc}"
                ) from exc
            edited_coeffs: Mapping[str, Any] = refit.coefficients
        elif isinstance(edited, DecompositionBlob):
            edited_coeffs = edited.coefficients
        else:
            edited_coeffs = dict(edited)

        z_scores: dict[str, float] = {}
        is_extreme: dict[str, bool] = {}
        ci_95: dict[str, tuple[float, float]] = {}

        for name, dist in self.coeff_distributions.items():
            if dist.size == 0:
                continue
            value = edited_coeffs.get(name)
            if not isinstance(value, (int, float, np.integer, np.floating)):
                continue
            z = self.z_score(name, float(value))
            z_scores[name] = z
            is_extreme[name] = (
                not math.isnan(z) and abs(z) > self.config.z_threshold
            )
            ci_95[name] = self.ci(name, alpha=0.05)

        finite_zs = [abs(z) for z in z_scores.values() if not math.isnan(z)]
        max_abs_z = max(finite_zs) if finite_zs else float("nan")
        return CoefficientCIResult(
            z_scores=z_scores,
            is_extreme=is_extreme,
            ci_95=ci_95,
            max_abs_z=max_abs_z,
            any_extreme=any(is_extreme.values()),
            method=self._blob.method,
            n_evaluated=len(z_scores),
        )

    # -------- introspection -----------------------------------------------

    @property
    def block_length(self) -> int:
        if self._block_length is None:
            raise CoefficientCIError("block_length not set; CI computation skipped")
        return self._block_length

    @property
    def cache_path(self) -> Path | None:
        return self._cache_path()

    # -------- cache I/O ---------------------------------------------------

    def _cache_path(self) -> Path | None:
        if self._segment_id is None:
            return None
        return _ci_cache_path(self._cache_dir, self._segment_id, self._blob.method)

    def _save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "segment_id": self._segment_id,
            "method": self._blob.method,
            "B": self.config.B,
            "z_threshold": self.config.z_threshold,
            "block_length": self._block_length,
            "coefficient_distributions": {
                name: dist.tolist() for name, dist in self.coeff_distributions.items()
            },
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _load(self, path: Path) -> None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CoefficientCIError(
                f"failed to read coefficient-CI cache at {path}: {exc}"
            ) from exc
        if raw.get("method") != self._blob.method:
            raise CoefficientCIError(
                f"cached method {raw.get('method')!r} does not match blob method "
                f"{self._blob.method!r}"
            )
        self._block_length = int(raw["block_length"]) if raw.get("block_length") else None
        distributions = raw.get("coefficient_distributions", {})
        self.coeff_distributions = {
            name: np.asarray(samples, dtype=np.float64)
            for name, samples in distributions.items()
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scalar_coefficients(coefficients: Mapping[str, Any]) -> dict[str, float]:
    """Filter a coefficients mapping down to the scalar entries."""
    return {
        name: float(value)
        for name, value in coefficients.items()
        if isinstance(value, (int, float, np.integer, np.floating))
    }


def _default_cache_dir() -> Path:
    return Path(__file__).resolve().parent / "cache"


def _ci_cache_path(cache_dir: Path, segment_id: str, method: str) -> Path:
    safe_seg = "".join(ch for ch in segment_id if ch.isalnum() or ch in ("-", "_"))
    safe_method = "".join(ch for ch in method if ch.isalnum() or ch in ("-", "_"))
    if not safe_seg or not safe_method:
        raise CoefficientCIError(
            f"unsafe cache key: segment_id={segment_id!r} method={method!r}"
        )
    return cache_dir / f"coefficient_ci_{safe_seg}_{safe_method}.json"
