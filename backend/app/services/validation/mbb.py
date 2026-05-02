"""Full moving-block bootstrap, slow path (VAL-031).

Authoritative B=999 stationary block bootstrap with **Patton-Politis-White
2009 corrected** automatic block-length selection. Provides publication-grade
confidence intervals on:

  1. **Decomposition coefficients** — STL slope, MSTL seasonal amplitude,
     BFAST breakpoint magnitude, GrAtSiD feature amplitude, etc. Uses the
     Bergmeir-Hyndman-Benítez 2016 protocol: bootstrap is on the
     residual / remainder component, not the raw series, then refit and
     extract the coefficient on each replicate.
  2. **Aggregate metrics** — peak, area, BFI, period, τ, etc. (OP-033).
     Bootstrap is on the raw segment.

This is the slow-path companion to VAL-005's fast-path z-score (which uses
a pre-cached B=500 CI). Reviewers comparing edits to natural sampling
variability of the fit demand the B=999 + optimal-block-length form.

Sources (binding for ``algorithm-auditor``):

  - Politis & Romano, "The Stationary Bootstrap," *JASA* 89(428):1303–1313
    (1994), DOI:10.1080/01621459.1994.10476870 — stationary block bootstrap.
  - Politis & White, "Automatic Block-Length Selection for the Dependent
    Bootstrap," *Econometric Reviews* 23(1):53–70 (2004), with
  - Patton, Politis, White, "Correction to ...," *Econometric Reviews*
    28(4):372–375 (2009) — **the corrected 2009 formula** is what
    ``arch.bootstrap.optimal_block_length`` implements; we delegate.
  - Bergmeir, Hyndman, Benítez, "Bagging exponential smoothing methods
    using STL decomposition and Box–Cox transformation," *International
    Journal of Forecasting* 32(2):303–312 (2016) — STL bootstrap protocol
    for residuals (used by ``mbb_coefficient_ci``).
  - Lahiri, *Resampling Methods for Dependent Data*, Springer 2003,
    ISBN 978-0-387-00928-1 — overlapping vs. non-overlapping blocks.

**Methodological honesty.** MBB CI assumes weak stationarity *of the
resampled component*. For a decomposition's residual that's reasonable
by construction; for the *raw* series under structural-break edits it's
not, and the user should compare with the IAAFT (VAL-030) test in those
cases. The dialog UI surfaces this caveat in the footer; this module
documents it on the result DTO so the caveat travels with the data.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Callable, Hashable, Literal

import numpy as np

from app.models.decomposition import DecompositionBlob

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


DEFAULT_N_REPLICATES = 999
DEFAULT_ALPHA = 0.05
BOOTSTRAP_STATIONARY = "stationary"
BOOTSTRAP_CIRCULAR = "circular"
_ALLOWED_BOOTSTRAPS = frozenset({BOOTSTRAP_STATIONARY, BOOTSTRAP_CIRCULAR})


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MBBError(RuntimeError):
    """Raised when MBB inputs are unusable (empty, missing residual, etc.)."""


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MBBResult:
    """Outcome of a moving-block bootstrap run.

    Attributes:
        point_estimate:     ``statistic(x_unbootstrapped)`` — the central
                            value the dialog plots as a vertical line.
        ci_lower / ci_upper: ``alpha/2`` and ``1 − alpha/2`` quantiles of
                            the bootstrap replicate distribution.
        block_length:       Mean block length used (Patton-Politis-White
                            2009 if auto-selected, else caller-supplied).
        n_replicates:       B used.
        alpha:              Two-sided CI width parameter.
        replicates:         Tuple of B floats — full distribution for the
                            histogram; frozen tuple keeps the DTO immutable.
        statistic_name:     Function name of ``statistic`` — used in the
                            cache key and surfaced in the UI.
        bootstrap_type:     ``'stationary'`` or ``'circular'``.
        stationarity_caveat: Plain-text caveat tied to the resampled
                            component (raw series vs. residual). Surfaced
                            in the dialog footer.
    """

    point_estimate: float
    ci_lower: float
    ci_upper: float
    block_length: int
    n_replicates: int
    alpha: float
    replicates: tuple[float, ...]
    statistic_name: str
    bootstrap_type: str
    stationarity_caveat: str


# ---------------------------------------------------------------------------
# Politis-White-Patton block length (delegates to arch)
# ---------------------------------------------------------------------------


def politis_white_block_length(
    x: np.ndarray,
    *,
    bootstrap_type: Literal["stationary", "circular"] = BOOTSTRAP_STATIONARY,
) -> int:
    """Patton-Politis-White 2009 *corrected* optimal mean block length.

    Delegates to ``arch.bootstrap.optimal_block_length`` which implements
    the corrected formula (the original Politis-White 2004 had an algebra
    error pinpointed in Patton-Politis-White 2009). For the stationary
    bootstrap, returns ``ceil(arch.optimal['stationary'])``; for circular,
    ``ceil(arch.optimal['circular'])``.

    The arch reference is *the* canonical implementation referenced in the
    bootstrap-replicates literature; we do not reimplement it.
    """
    if bootstrap_type not in _ALLOWED_BOOTSTRAPS:
        raise ValueError(
            f"bootstrap_type must be one of {sorted(_ALLOWED_BOOTSTRAPS)}; "
            f"got {bootstrap_type!r}"
        )
    arr = np.asarray(x, dtype=np.float64).reshape(-1)
    if arr.size < 4:
        raise MBBError(
            f"politis_white_block_length requires ≥ 4 samples; got {arr.size}"
        )
    import warnings as _warnings
    from arch.bootstrap import optimal_block_length  # noqa: PLC0415
    with _warnings.catch_warnings():
        # arch's divide-by-zero on constant input is expected — we fall back below.
        _warnings.simplefilter("ignore", RuntimeWarning)
        df = optimal_block_length(arr)
    col = "stationary" if bootstrap_type == BOOTSTRAP_STATIONARY else "circular"
    raw = float(df[col].iloc[0])
    if not np.isfinite(raw) or raw <= 0:
        # Degenerate (constant input → division by zero in the formula);
        # fall back to the standard rule-of-thumb floor.
        return max(1, int(np.ceil(arr.size ** (1.0 / 3.0))))
    return max(1, int(np.ceil(raw)))


# ---------------------------------------------------------------------------
# Per-call cache
# ---------------------------------------------------------------------------


_mbb_cache: dict[str, MBBResult] = {}


def cache_key(
    series_id: Hashable,
    statistic_name: str,
    n_replicates: int,
    seed: int,
    *,
    bootstrap_type: str = BOOTSTRAP_STATIONARY,
    payload_bytes: bytes | None = None,
) -> str:
    """Stable hash for the MBB cache.

    Includes ``payload_bytes`` (the raw series bytes) when supplied, so a
    caller that mutates the series gets a fresh cache. SHA-256 is used
    for collision resistance only — not a security primitive.
    """
    h = hashlib.sha256()
    h.update(repr(series_id).encode())
    h.update(b"|")
    h.update(statistic_name.encode())
    h.update(f"|{int(n_replicates)}|{int(seed)}|{bootstrap_type}".encode())
    if payload_bytes is not None:
        h.update(b"|payload|")
        h.update(payload_bytes)
    return h.hexdigest()


def clear_mbb_cache() -> None:
    """Drop every cached MBB result."""
    _mbb_cache.clear()


# ---------------------------------------------------------------------------
# Bootstrap helpers
# ---------------------------------------------------------------------------


def _make_bootstrap(
    block_length: int,
    array: np.ndarray,
    *,
    bootstrap_type: str,
    seed: int,
) -> Any:
    from arch.bootstrap import (  # noqa: PLC0415
        CircularBlockBootstrap,
        StationaryBootstrap,
    )
    if bootstrap_type == BOOTSTRAP_STATIONARY:
        return StationaryBootstrap(block_length, array, seed=seed)
    return CircularBlockBootstrap(block_length, array, seed=seed)


_RAW_SERIES_CAVEAT = (
    "MBB CI assumes weak stationarity of the resampled component. The raw "
    "segment is bootstrapped here — under structural-break edits this "
    "assumption breaks and the IAAFT (VAL-030) test should be consulted "
    "instead."
)
_RESIDUAL_CAVEAT = (
    "MBB CI assumes weak stationarity of the resampled component. The "
    "decomposition residual is bootstrapped here — by construction this "
    "assumption is reasonable, but cross-check with VAL-030 (IAAFT) for "
    "any edit that may itself break the residual's stationarity."
)


# ---------------------------------------------------------------------------
# mbb_ci — raw-series statistic CI
# ---------------------------------------------------------------------------


def mbb_ci(
    x: np.ndarray,
    statistic: Callable[[np.ndarray], float],
    *,
    n_replicates: int = DEFAULT_N_REPLICATES,
    alpha: float = DEFAULT_ALPHA,
    block_length: int | None = None,
    seed: int = 0,
    bootstrap_type: Literal["stationary", "circular"] = BOOTSTRAP_STATIONARY,
    series_id: Hashable | None = None,
    use_cache: bool = True,
) -> MBBResult:
    """Stationary (or circular) block-bootstrap CI for any scalar statistic
    of ``x`` per Politis-Romano 1994.

    Block length auto-selected via Patton-Politis-White 2009 when
    ``block_length`` is not supplied. The statistic is recomputed on each
    of ``n_replicates`` resampled series; the CI is the
    ``[alpha/2, 1 − alpha/2]`` empirical quantile of the replicate
    distribution.

    The result is cached by ``(series_id, statistic.__name__, n_replicates,
    seed, bootstrap_type)`` so a tab-switching dialog does not re-run the
    slow path. Pass ``series_id`` for a stable key across object identity;
    when omitted, the cache key includes the raw series bytes.
    """
    if n_replicates < 2:
        raise ValueError(f"n_replicates must be ≥ 2; got {n_replicates}")
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1); got {alpha}")
    if bootstrap_type not in _ALLOWED_BOOTSTRAPS:
        raise ValueError(
            f"bootstrap_type must be one of {sorted(_ALLOWED_BOOTSTRAPS)}; "
            f"got {bootstrap_type!r}"
        )

    arr = np.asarray(x, dtype=np.float64).reshape(-1)
    if arr.size < 4:
        raise MBBError(f"mbb_ci requires ≥ 4 samples; got {arr.size}")

    statistic_name = getattr(statistic, "__name__", repr(statistic))
    key = cache_key(
        series_id if series_id is not None else "_no_id",
        statistic_name,
        n_replicates,
        seed,
        bootstrap_type=bootstrap_type,
        payload_bytes=arr.tobytes() if series_id is None else None,
    )
    if use_cache and key in _mbb_cache:
        return _mbb_cache[key]

    bl = block_length if block_length is not None else politis_white_block_length(
        arr, bootstrap_type=bootstrap_type,
    )
    point = float(statistic(arr))

    bs = _make_bootstrap(bl, arr, bootstrap_type=bootstrap_type, seed=seed)
    replicates: list[float] = []
    for data in bs.bootstrap(n_replicates):
        # arch yields ``(args, kwargs)`` — the resampled series is args[0].
        boot_x = data[0][0]
        replicates.append(float(statistic(boot_x)))

    arr_rep = np.asarray(replicates, dtype=np.float64)
    lo, hi = np.quantile(arr_rep, [alpha / 2.0, 1.0 - alpha / 2.0])

    result = MBBResult(
        point_estimate=point,
        ci_lower=float(lo),
        ci_upper=float(hi),
        block_length=int(bl),
        n_replicates=int(n_replicates),
        alpha=float(alpha),
        replicates=tuple(float(v) for v in arr_rep),
        statistic_name=statistic_name,
        bootstrap_type=bootstrap_type,
        stationarity_caveat=_RAW_SERIES_CAVEAT,
    )
    if use_cache:
        _mbb_cache[key] = result
    return result


# ---------------------------------------------------------------------------
# mbb_coefficient_ci — residual-bootstrap → refit → extract
# ---------------------------------------------------------------------------


def _residual_of(blob: DecompositionBlob) -> np.ndarray:
    """Pull the residual / remainder component out of ``blob``.

    Bergmeir et al. 2016 use 'remainder' (STL convention); other fitters
    use 'residual'. We try the dedicated ``blob.residual`` first, then
    ``components['residual']`` / ``components['remainder']``. Raises
    ``MBBError`` when none is found — without a residual the protocol is
    not applicable.
    """
    if blob.residual is not None:
        return np.asarray(blob.residual, dtype=np.float64).reshape(-1)
    for key in ("residual", "remainder"):
        comp = blob.components.get(key)
        if comp is not None:
            return np.asarray(comp, dtype=np.float64).reshape(-1)
    raise MBBError(
        f"blob method {blob.method!r} has no residual / remainder component; "
        "cannot apply Bergmeir-Hyndman-Benítez 2016 residual-bootstrap protocol."
    )


def _signal_part(blob: DecompositionBlob, residual: np.ndarray) -> np.ndarray:
    """The deterministic signal part: ``blob.reassemble() − residual``."""
    full = blob.reassemble()
    if full.shape != residual.shape:
        raise MBBError(
            f"reassembled signal shape {full.shape} does not match residual "
            f"shape {residual.shape}"
        )
    return full - residual


def mbb_coefficient_ci(
    blob: DecompositionBlob,
    coefficient_name: str,
    refit_fn: Callable[[np.ndarray], DecompositionBlob],
    *,
    n_replicates: int = DEFAULT_N_REPLICATES,
    alpha: float = DEFAULT_ALPHA,
    block_length: int | None = None,
    seed: int = 0,
    bootstrap_type: Literal["stationary", "circular"] = BOOTSTRAP_STATIONARY,
    series_id: Hashable | None = None,
    use_cache: bool = True,
) -> MBBResult:
    """Bergmeir-Hyndman-Benítez 2016 residual-bootstrap CI for one
    coefficient of a fitted decomposition.

    Pipeline:
      1. Pull ``residual = blob.residual`` (or ``components['residual'/'remainder']``).
      2. Compute the deterministic signal part ``X̂ = blob.reassemble() − residual``.
      3. Auto-select block length on the residual via Patton-Politis-White 2009.
      4. For B replicates: bootstrap-resample the residual, reassemble
         ``X_b = X̂ + r_b``, refit via ``refit_fn``, extract
         ``boot_blob.coefficients[coefficient_name]``.
      5. Empirical-quantile CI at ``alpha / 2`` and ``1 − alpha / 2``.

    Refits that fail (raise) are skipped and a debug message logged. If
    fewer than half the replicates succeed, an ``MBBError`` is raised so
    the caller doesn't silently consume a degenerate CI.
    """
    if n_replicates < 2:
        raise ValueError(f"n_replicates must be ≥ 2; got {n_replicates}")
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1); got {alpha}")
    if coefficient_name not in blob.coefficients:
        raise MBBError(
            f"blob coefficients do not include {coefficient_name!r}; "
            f"available: {sorted(blob.coefficients)}"
        )
    point_raw = blob.coefficients[coefficient_name]
    if not isinstance(point_raw, (int, float, np.integer, np.floating)):
        raise MBBError(
            f"coefficient {coefficient_name!r} is not a scalar (got {type(point_raw).__name__}); "
            "MBB CI is defined for scalar coefficients only."
        )

    residual = _residual_of(blob)
    signal_part = _signal_part(blob, residual)

    statistic_name = f"coef:{coefficient_name}"
    key = cache_key(
        series_id if series_id is not None else "_no_id",
        statistic_name,
        n_replicates,
        seed,
        bootstrap_type=bootstrap_type,
        payload_bytes=residual.tobytes() if series_id is None else None,
    )
    if use_cache and key in _mbb_cache:
        return _mbb_cache[key]

    bl = block_length if block_length is not None else politis_white_block_length(
        residual, bootstrap_type=bootstrap_type,
    )

    bs = _make_bootstrap(bl, residual, bootstrap_type=bootstrap_type, seed=seed)
    replicates: list[float] = []
    for data in bs.bootstrap(n_replicates):
        r_b = data[0][0]
        x_b = signal_part + r_b
        try:
            boot_blob = refit_fn(x_b)
        except Exception as exc:  # noqa: BLE001
            logger.debug("mbb_coefficient_ci: refit raised, skipping replicate: %s", exc)
            continue
        val = boot_blob.coefficients.get(coefficient_name)
        if isinstance(val, (int, float, np.integer, np.floating)):
            replicates.append(float(val))

    if len(replicates) < n_replicates // 2:
        raise MBBError(
            f"mbb_coefficient_ci: {len(replicates)}/{n_replicates} refits succeeded "
            f"for coefficient {coefficient_name!r}; CI would be unreliable."
        )

    arr_rep = np.asarray(replicates, dtype=np.float64)
    lo, hi = np.quantile(arr_rep, [alpha / 2.0, 1.0 - alpha / 2.0])

    result = MBBResult(
        point_estimate=float(point_raw),
        ci_lower=float(lo),
        ci_upper=float(hi),
        block_length=int(bl),
        n_replicates=int(len(replicates)),
        alpha=float(alpha),
        replicates=tuple(float(v) for v in arr_rep),
        statistic_name=statistic_name,
        bootstrap_type=bootstrap_type,
        stationarity_caveat=_RESIDUAL_CAVEAT,
    )
    if use_cache:
        _mbb_cache[key] = result
    return result
