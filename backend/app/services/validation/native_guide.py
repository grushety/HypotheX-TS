"""Native-Guide proximity & sparsity (VAL-004).

Computes the canonical TS-CF "minimality" metrics from:

  Delaney, Greene, Keane, "Instance-based Counterfactual Explanations for
  Time Series Classification," ICCBR 2021, LNCS 12877:32–47,
  DOI:10.1007/978-3-030-86957-1_3.

Two metrics, by design complementary:
  * **Proximity** — DTW (default) / Euclidean / L1 distance between the
    original series ``x`` and the edit ``x'``. Quantifies *how much* the
    series changed.
  * **Sparsity** — fraction of time-steps where ``|x − x'| < ε``. Quantifies
    *how localised* the change is. ε defaults to ``1e-6`` in normalised
    feature space; callers should pre-normalise before calling so this
    threshold is dataset-agnostic.

A combined density flag (``too_dense``) fires when an edit is both
non-local (sparsity < 0.7) and unusually large (proximity above the dataset's
90th-percentile nearest-unlike-neighbour distance). Calibration of the
NUN distribution is offline per dataset; results live in a JSON cache.

DTW comes from ``tslearn.metrics.dtw`` with a Sakoe-Chiba band (Sakoe &
Chiba, *IEEE ASSP* 26(1):43, 1978); we never reimplement DTW.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NativeGuideError(RuntimeError):
    """Raised when Native-Guide threshold I/O or validation fails."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


METRIC_DTW = "dtw"
METRIC_EUCLIDEAN = "euclidean"
METRIC_L1 = "l1"
_ALLOWED_METRICS = frozenset({METRIC_DTW, METRIC_EUCLIDEAN, METRIC_L1})

DEFAULT_DTW_BAND = 0.1
DEFAULT_EPS_PER_DIM = 1e-6
DEFAULT_SPARSITY_THRESHOLD = 0.7
DEFAULT_PROXIMITY_PERCENTILE = 0.9


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NativeGuideThresholds:
    """Per-dataset calibration of nearest-unlike-neighbour distances.

    Attributes:
        nun_distances: Sorted tuple of NUN distances over the calibration set
                       (one per training point). Used for percentile-rank
                       queries; sorted at construction.
        q90_nun:       90th percentile of ``nun_distances`` — the threshold
                       above which a CF is judged "unusually large" relative
                       to typical class-flipping movement on this dataset.
        metric:        Metric used during calibration; must match the metric
                       requested at validation time.
        dataset_name:  Optional identifier; used as the JSON cache key.
    """

    nun_distances: tuple[float, ...]
    q90_nun: float
    metric: str
    dataset_name: str | None = None

    def __post_init__(self) -> None:
        if self.metric not in _ALLOWED_METRICS:
            raise ValueError(
                f"metric must be one of {sorted(_ALLOWED_METRICS)}; got {self.metric!r}"
            )
        if not self.nun_distances:
            raise ValueError("nun_distances must contain at least one value")
        if self.q90_nun < 0:
            raise ValueError(f"q90_nun must be ≥ 0; got {self.q90_nun}")
        prior = -float("inf")
        for d in self.nun_distances:
            if d < prior:
                raise ValueError(
                    "nun_distances must be sorted non-decreasing — "
                    "use sorted(nun_distances) at construction"
                )
            prior = d


@dataclass(frozen=True)
class NativeGuideResult:
    """Per-edit Native-Guide outcome.

    Attributes:
        proximity:      Distance between ``x`` and ``x'`` under ``metric``.
        sparsity:       Fraction of unchanged time-steps in [0, 1].
        proximity_pct:  Percentile rank of ``proximity`` against the
                        calibrated NUN distribution, in [0, 1]; ``None`` when
                        no thresholds were supplied.
        too_dense:      True iff ``sparsity < sparsity_threshold`` *and*
                        ``proximity > q90_nun``. ``False`` when no thresholds
                        were supplied.
        metric:         Metric used.
    """

    proximity: float
    sparsity: float
    proximity_pct: float | None
    too_dense: bool
    metric: str


# ---------------------------------------------------------------------------
# Pure metrics
# ---------------------------------------------------------------------------


def native_guide_proximity(
    x: np.ndarray,
    x_prime: np.ndarray,
    *,
    metric: Literal["dtw", "euclidean", "l1"] = METRIC_DTW,
    dtw_band: float = DEFAULT_DTW_BAND,
) -> float:
    """Distance between ``x`` and ``x'``.

    DTW uses a Sakoe-Chiba radius of ``round(dtw_band × len(x))``, capped at
    1 to keep the band non-degenerate. Euclidean and L1 require equal length.
    """
    if metric not in _ALLOWED_METRICS:
        raise ValueError(
            f"metric must be one of {sorted(_ALLOWED_METRICS)}; got {metric!r}"
        )
    if not 0.0 < dtw_band <= 1.0:
        raise ValueError(f"dtw_band must be in (0, 1]; got {dtw_band}")

    a = np.asarray(x, dtype=np.float64).reshape(-1)
    b = np.asarray(x_prime, dtype=np.float64).reshape(-1)

    if metric == METRIC_DTW:
        from tslearn.metrics import dtw as tslearn_dtw  # noqa: PLC0415
        radius = max(1, int(round(dtw_band * a.shape[0])))
        return float(tslearn_dtw(a, b, sakoe_chiba_radius=radius))

    if a.shape != b.shape:
        raise ValueError(
            f"{metric} proximity requires equal-length series; got {a.shape} vs {b.shape}"
        )
    if metric == METRIC_EUCLIDEAN:
        return float(np.linalg.norm(a - b))
    return float(np.sum(np.abs(a - b)))  # L1


def native_guide_sparsity(
    x: np.ndarray,
    x_prime: np.ndarray,
    *,
    eps_per_dim: float = DEFAULT_EPS_PER_DIM,
) -> float:
    """Fraction of time-steps where ``|x − x'| < eps_per_dim``.

    Caller is responsible for normalising x and x' so ``eps_per_dim`` is
    meaningful — the AC requires the *same* noise floor across edits to
    avoid per-edit re-normalisation drift, so this function does not
    re-normalise.
    """
    if eps_per_dim < 0:
        raise ValueError(f"eps_per_dim must be ≥ 0; got {eps_per_dim}")
    a = np.asarray(x, dtype=np.float64).reshape(-1)
    b = np.asarray(x_prime, dtype=np.float64).reshape(-1)
    if a.shape != b.shape:
        raise ValueError(
            f"sparsity requires equal-length series; got {a.shape} vs {b.shape}"
        )
    diff = np.abs(a - b)
    unchanged = int(np.sum(diff < eps_per_dim))
    return unchanged / a.shape[0]


def percentile_rank(value: float, distribution: Sequence[float]) -> float:
    """Fraction of ``distribution`` values ≤ ``value``, in [0, 1].

    Distribution is expected sorted non-decreasing (``NativeGuideThresholds``
    enforces this at construction). Uses ``searchsorted(side='right')`` so
    ties on the right are counted as "≤ value" — consistent with empirical
    CDF conventions.
    """
    if not distribution:
        raise ValueError("distribution must be non-empty")
    arr = np.asarray(distribution, dtype=np.float64)
    rank = int(np.searchsorted(arr, value, side="right"))
    return rank / arr.shape[0]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def native_guide_validate(
    x: np.ndarray,
    x_prime: np.ndarray,
    thresholds: NativeGuideThresholds | None = None,
    *,
    metric: Literal["dtw", "euclidean", "l1"] = METRIC_DTW,
    dtw_band: float = DEFAULT_DTW_BAND,
    eps_per_dim: float = DEFAULT_EPS_PER_DIM,
    sparsity_threshold: float = DEFAULT_SPARSITY_THRESHOLD,
) -> NativeGuideResult:
    """Run the full Native-Guide check on a single edit.

    When ``thresholds`` is ``None``, ``proximity_pct`` and ``too_dense``
    are reported as ``None`` / ``False`` — proximity and sparsity remain
    valid (they don't require a calibrated distribution).
    """
    if thresholds is not None and thresholds.metric != metric:
        raise NativeGuideError(
            f"metric mismatch: thresholds calibrated with {thresholds.metric!r} "
            f"but validation requested {metric!r}"
        )

    proximity = native_guide_proximity(x, x_prime, metric=metric, dtw_band=dtw_band)
    sparsity = native_guide_sparsity(x, x_prime, eps_per_dim=eps_per_dim)

    if thresholds is None:
        return NativeGuideResult(
            proximity=proximity,
            sparsity=sparsity,
            proximity_pct=None,
            too_dense=False,
            metric=metric,
        )

    pct = percentile_rank(proximity, thresholds.nun_distances)
    too_dense = bool(sparsity < sparsity_threshold and proximity > thresholds.q90_nun)
    return NativeGuideResult(
        proximity=proximity,
        sparsity=sparsity,
        proximity_pct=pct,
        too_dense=too_dense,
        metric=metric,
    )


# ---------------------------------------------------------------------------
# Calibration helpers
# ---------------------------------------------------------------------------


def compute_nun_distances(
    series: np.ndarray,
    labels: Sequence[object] | np.ndarray,
    *,
    metric: Literal["dtw", "euclidean", "l1"] = METRIC_DTW,
    dtw_band: float = DEFAULT_DTW_BAND,
) -> tuple[float, ...]:
    """For each training point, find its nearest *unlike* neighbour and
    return the sorted tuple of those distances.

    Used by the offline calibration script. Pure function — no I/O — so
    it can be unit-tested directly.
    """
    arr = np.asarray(series, dtype=np.float64)
    if arr.ndim != 2:
        raise ValueError(f"series must be 2-D (n, T); got shape {arr.shape}")
    lbls = np.asarray(labels)
    if lbls.shape[0] != arr.shape[0]:
        raise ValueError(
            f"labels length {lbls.shape[0]} ≠ series length {arr.shape[0]}"
        )

    distances: list[float] = []
    for i in range(arr.shape[0]):
        best = float("inf")
        for j in range(arr.shape[0]):
            if i == j or lbls[j] == lbls[i]:
                continue
            d = native_guide_proximity(arr[i], arr[j], metric=metric, dtw_band=dtw_band)
            if d < best:
                best = d
        if best != float("inf"):
            distances.append(best)
    if not distances:
        raise NativeGuideError(
            "compute_nun_distances: no unlike-neighbour pairs found "
            "(training set has only one class?)"
        )
    distances.sort()
    return tuple(distances)


def thresholds_from_distances(
    nun_distances: Iterable[float],
    *,
    metric: Literal["dtw", "euclidean", "l1"] = METRIC_DTW,
    dataset_name: str | None = None,
    quantile: float = DEFAULT_PROXIMITY_PERCENTILE,
) -> NativeGuideThresholds:
    arr = np.asarray(list(nun_distances), dtype=np.float64)
    if arr.size == 0:
        raise ValueError("nun_distances is empty")
    if not 0.0 < quantile < 1.0:
        raise ValueError(f"quantile must be in (0, 1); got {quantile}")
    arr = np.sort(arr)
    q = float(np.quantile(arr, quantile))
    return NativeGuideThresholds(
        nun_distances=tuple(float(v) for v in arr),
        q90_nun=q,
        metric=metric,
        dataset_name=dataset_name,
    )


# ---------------------------------------------------------------------------
# Threshold cache I/O
# ---------------------------------------------------------------------------


def _default_cache_dir() -> Path:
    return Path(__file__).resolve().parent / "cache"


def _thresholds_path(cache_dir: Path, dataset_name: str) -> Path:
    safe = "".join(ch for ch in dataset_name if ch.isalnum() or ch in ("-", "_"))
    if not safe:
        raise NativeGuideError(
            f"dataset_name {dataset_name!r} produces an empty cache filename"
        )
    return cache_dir / f"native_guide_thresholds_{safe}.json"


def save_thresholds(
    thresholds: NativeGuideThresholds,
    *,
    cache_dir: Path | str | None = None,
) -> Path:
    if thresholds.dataset_name is None:
        raise NativeGuideError("save_thresholds requires thresholds.dataset_name")
    cache = Path(cache_dir) if cache_dir is not None else _default_cache_dir()
    path = _thresholds_path(cache, thresholds.dataset_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_name": thresholds.dataset_name,
        "metric": thresholds.metric,
        "q90_nun": thresholds.q90_nun,
        "nun_distances": list(thresholds.nun_distances),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_thresholds(
    dataset_name: str,
    *,
    cache_dir: Path | str | None = None,
) -> NativeGuideThresholds:
    cache = Path(cache_dir) if cache_dir is not None else _default_cache_dir()
    path = _thresholds_path(cache, dataset_name)
    if not path.exists():
        raise NativeGuideError(
            f"Native-Guide thresholds not found at {path}; run the calibration "
            f"script for dataset {dataset_name!r} first."
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NativeGuideError(
            f"failed to read Native-Guide thresholds at {path}: {exc}"
        ) from exc
    return NativeGuideThresholds(
        nun_distances=tuple(float(v) for v in raw["nun_distances"]),
        q90_nun=float(raw["q90_nun"]),
        metric=str(raw["metric"]),
        dataset_name=str(raw.get("dataset_name", dataset_name)),
    )
