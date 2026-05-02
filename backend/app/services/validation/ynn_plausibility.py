"""yNN k-NN plausibility under DTW (VAL-003).

Computes

    yNN_K(x') = (1/K) · |{ x_j ∈ NN_K^DTW(x') : ŷ(x_j) = ŷ(x') }|

— the fraction of the K nearest training neighbours (under DTW with a
Sakoe-Chiba band) that share the CF's target class. Higher = more
plausible / on-manifold; ``yNN < 0.5`` is the VAL-020 trigger for
"edited series has few same-class neighbours — likely off-manifold."

Sources:

  - Pawelczyk et al., "CARLA," NeurIPS 2021 D&B, arXiv:2108.00783 — defines yNN.
  - Höllig, Kulbach, Thoma, "TSEvo," ICMLA 2022,
    DOI:10.1109/ICMLA55696.2022.00013 — yNN for TSC counterfactuals.
  - Wang, Samsten, Miliou, Mochaourab, Papapetrou, "Glacier,"
    *Machine Learning* 113:4639 (2024), DOI:10.1007/s10994-023-06502-x.
  - Sakoe & Chiba, *IEEE ASSP* 26(1):43 (1978) — warping band convention.

Implementation notes:
  * DTW comes from ``tslearn.metrics.dtw`` (already required for OP-031);
    we never reimplement DTW.
  * LB_Keogh is implemented locally — tslearn does not expose it as a
    standalone primitive. It is the standard O(n) lower bound on DTW
    used to prune candidates before the O(n·T·band) DTW pass.
  * Index lives in a single ``.npz`` per dataset under ``cache_dir``;
    no pickle, only contiguous numpy arrays + scalar config values.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class YnnIndexError(RuntimeError):
    """Raised when the yNN index cannot be built or loaded."""


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


DEFAULT_K = 5
DEFAULT_DTW_BAND = 0.1
DEFAULT_CANDIDATE_MULTIPLIER = 4


@dataclass(frozen=True)
class YnnConfig:
    """Configuration for the yNN validator.

    K:                     number of neighbours; default 5 per CARLA.
    dtw_band:              Sakoe-Chiba radius as a fraction of segment length;
                           default 0.1 per Sakoe & Chiba 1978 convention.
    candidate_multiplier:  LB_Keogh shortlist size = ``candidate_multiplier · K``
                           — refines top-K by full DTW. Larger = safer (fewer
                           false rejections by the lower bound), slower.
    """

    K: int = DEFAULT_K
    dtw_band: float = DEFAULT_DTW_BAND
    candidate_multiplier: int = DEFAULT_CANDIDATE_MULTIPLIER

    def __post_init__(self) -> None:
        if self.K < 0:
            raise ValueError(f"K must be ≥ 0; got {self.K}")
        if not 0.0 < self.dtw_band <= 1.0:
            raise ValueError(f"dtw_band must be in (0, 1]; got {self.dtw_band}")
        if self.candidate_multiplier < 1:
            raise ValueError(
                f"candidate_multiplier must be ≥ 1; got {self.candidate_multiplier}"
            )


@dataclass(frozen=True)
class YnnResult:
    """Per-edit yNN plausibility outcome.

    Attributes:
        ynn:                   Fraction in [0, 1]; ``nan`` if K = 0.
        target_class:          The target class label compared against neighbours.
        K:                     Effective K used (clipped to training-set size).
        n_neighbours_evaluated: Actual neighbour count (≤ K; equal unless the
                                training set is smaller than K).
    """

    ynn: float
    target_class: object
    K: int
    n_neighbours_evaluated: int


# ---------------------------------------------------------------------------
# Index path helper
# ---------------------------------------------------------------------------


def _default_cache_dir() -> Path:
    return Path(__file__).resolve().parent / "cache"


def _index_path(cache_dir: Path, dataset_name: str) -> Path:
    safe = "".join(ch for ch in dataset_name if ch.isalnum() or ch in ("-", "_"))
    if not safe:
        raise YnnIndexError(
            f"dataset_name {dataset_name!r} produces an empty cache filename"
        )
    return cache_dir / f"ynn_index_{safe}.npz"


# ---------------------------------------------------------------------------
# LB_Keogh primitives
# ---------------------------------------------------------------------------


def keogh_envelope(x: np.ndarray, radius: int) -> tuple[np.ndarray, np.ndarray]:
    """Compute Sakoe-Chiba bounded upper / lower envelopes for series x.

        U[i] = max(x[max(0, i−r):min(n, i+r+1)])
        L[i] = min(x[max(0, i−r):min(n, i+r+1)])

    Used as a precomputable summary of x for LB_Keogh queries. Reference:
    Keogh & Ratanamahatana, "Exact indexing of dynamic time warping,"
    Knowledge and Information Systems 7(3):358 (2005).
    """
    if radius < 0:
        raise ValueError(f"radius must be ≥ 0; got {radius}")
    arr = np.asarray(x, dtype=np.float64).reshape(-1)
    n = arr.shape[0]
    upper = np.empty(n, dtype=np.float64)
    lower = np.empty(n, dtype=np.float64)
    for i in range(n):
        lo = max(0, i - radius)
        hi = min(n, i + radius + 1)
        window = arr[lo:hi]
        upper[i] = window.max()
        lower[i] = window.min()
    return upper, lower


def lb_keogh(query: np.ndarray, upper: np.ndarray, lower: np.ndarray) -> float:
    """LB_Keogh distance from ``query`` to a reference summarised by (U, L).

    Squared-error excess outside the envelope, then square-rooted to match
    the Euclidean / DTW units. Returns 0 when the query lies entirely
    inside the envelope.
    """
    q = np.asarray(query, dtype=np.float64).reshape(-1)
    if q.shape != upper.shape or q.shape != lower.shape:
        raise ValueError(
            f"query / envelope shape mismatch: q={q.shape}, U={upper.shape}, L={lower.shape}"
        )
    above = np.maximum(q - upper, 0.0)
    below = np.maximum(lower - q, 0.0)
    return float(math.sqrt(np.sum(above * above + below * below)))


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class YnnPlausibilityValidator:
    """K-NN plausibility under DTW with Sakoe-Chiba band + LB_Keogh prefilter.

    Build path: pass ``training_series`` (n × T float) and ``training_labels``
    (length n). Optionally pass ``dataset_name`` to cache the index to a
    single ``.npz`` under ``cache_dir`` — subsequent constructions with the
    same ``dataset_name`` rehydrate the cached envelopes without recomputing.

    Per-query:
      1. Compute LB_Keogh between ``x_prime`` and every training envelope.
      2. Take the lowest ``candidate_multiplier · K`` candidates as a shortlist.
      3. Compute true DTW with Sakoe-Chiba band on the shortlist; take the
         top K by DTW distance.
      4. Return the fraction whose label equals ``target_class``.

    All training series must share length T; mixed-length training sets are
    out of scope for this validator (call site can resample / truncate first).
    """

    def __init__(
        self,
        training_series: Sequence[Sequence[float]] | np.ndarray | None = None,
        training_labels: Sequence[object] | np.ndarray | None = None,
        config: YnnConfig | None = None,
        *,
        dataset_name: str | None = None,
        cache_dir: Path | str | None = None,
        load_cached: bool = True,
    ) -> None:
        self.config = config or YnnConfig()
        self._cache_dir = Path(cache_dir) if cache_dir is not None else _default_cache_dir()
        self._dataset_name = dataset_name

        cache_path = (
            _index_path(self._cache_dir, dataset_name) if dataset_name else None
        )
        cache_hit = bool(load_cached and cache_path is not None and cache_path.exists())

        if cache_hit:
            self._load(cache_path)  # type: ignore[arg-type]
        elif training_series is not None and training_labels is not None:
            self._build(training_series, training_labels)
            if cache_path is not None:
                self._save(cache_path)
        else:
            raise YnnIndexError(
                "YnnPlausibilityValidator requires either (training_series + training_labels) "
                "or a cached dataset_name; both were missing."
            )

    # -------- build ---------------------------------------------------------

    def _build(
        self,
        training_series: Sequence[Sequence[float]] | np.ndarray,
        training_labels: Sequence[object] | np.ndarray,
    ) -> None:
        series = np.asarray(training_series, dtype=np.float64)
        if series.ndim != 2:
            raise YnnIndexError(
                f"training_series must be 2-D (n_train, T); got shape {series.shape}"
            )
        if series.shape[0] == 0:
            raise YnnIndexError("training_series is empty")
        labels = np.asarray(training_labels)
        if labels.shape[0] != series.shape[0]:
            raise YnnIndexError(
                f"training_labels length {labels.shape[0]} ≠ training_series length {series.shape[0]}"
            )

        radius = self._radius_for_length(series.shape[1])
        upper = np.empty_like(series)
        lower = np.empty_like(series)
        for i in range(series.shape[0]):
            u, l = keogh_envelope(series[i], radius)
            upper[i] = u
            lower[i] = l
        self._series = series
        self._labels = labels
        self._upper = upper
        self._lower = lower
        self._freeze_index_arrays()

    def _radius_for_length(self, length: int) -> int:
        return max(1, int(round(self.config.dtw_band * length)))

    # -------- query (yNN) ---------------------------------------------------

    def ynn(self, x_prime: np.ndarray, target_class: object) -> YnnResult:
        """Return ``YnnResult`` for ``x_prime`` against the indexed training set."""
        q = np.asarray(x_prime, dtype=np.float64).reshape(-1)
        if q.shape[0] != self._series.shape[1]:
            raise ValueError(
                f"x_prime length {q.shape[0]} ≠ indexed series length {self._series.shape[1]}"
            )

        K_eff = min(self.config.K, self._series.shape[0])
        if K_eff <= 0:
            warnings.warn(
                "yNN called with K = 0 (or empty training set); returning nan.",
                RuntimeWarning,
                stacklevel=2,
            )
            return YnnResult(
                ynn=float("nan"),
                target_class=target_class,
                K=0,
                n_neighbours_evaluated=0,
            )

        # Step 1: LB_Keogh prefilter
        n_candidates = min(self._series.shape[0], self.config.candidate_multiplier * K_eff)
        lb_distances = self._lb_keogh_all(q)
        shortlist = np.argpartition(lb_distances, n_candidates - 1)[:n_candidates]

        # Step 2: full DTW on the shortlist
        from tslearn.metrics import dtw as tslearn_dtw  # noqa: PLC0415

        radius = self._radius_for_length(q.shape[0])
        dtw_pairs = [
            (
                float(tslearn_dtw(q, self._series[idx], sakoe_chiba_radius=radius)),
                int(idx),
            )
            for idx in shortlist
        ]
        dtw_pairs.sort(key=lambda p: p[0])
        top_k = dtw_pairs[:K_eff]

        # Step 3: target-class fraction
        agree = sum(1 for _, idx in top_k if self._labels[idx] == target_class)
        return YnnResult(
            ynn=agree / K_eff,
            target_class=target_class,
            K=K_eff,
            n_neighbours_evaluated=len(top_k),
        )

    def _lb_keogh_all(self, q: np.ndarray) -> np.ndarray:
        """Vectorised LB_Keogh from q to every indexed training point."""
        # broadcast: (n, T) − (T,) → per-row excess above U / below L.
        above = np.maximum(q[None, :] - self._upper, 0.0)
        below = np.maximum(self._lower - q[None, :], 0.0)
        sq = above * above + below * below
        return np.sqrt(sq.sum(axis=1))

    # -------- introspection ------------------------------------------------

    @property
    def n_train(self) -> int:
        return int(self._series.shape[0])

    @property
    def series_length(self) -> int:
        return int(self._series.shape[1])

    @property
    def cache_path(self) -> Path | None:
        if self._dataset_name is None:
            return None
        return _index_path(self._cache_dir, self._dataset_name)

    # -------- I/O ----------------------------------------------------------

    def _save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            series=self._series,
            labels=self._labels,
            upper=self._upper,
            lower=self._lower,
            K=np.int32(self.config.K),
            dtw_band=np.float64(self.config.dtw_band),
            candidate_multiplier=np.int32(self.config.candidate_multiplier),
        )

    def _load(self, path: Path) -> None:
        try:
            data = np.load(path, allow_pickle=False)
        except OSError as exc:
            raise YnnIndexError(f"failed to read yNN index at {path}: {exc}") from exc
        for key in ("series", "labels", "upper", "lower", "K", "dtw_band", "candidate_multiplier"):
            if key not in data.files:
                raise YnnIndexError(
                    f"yNN index at {path} missing required field {key!r}"
                )
        cached = YnnConfig(
            K=int(data["K"]),
            dtw_band=float(data["dtw_band"]),
            candidate_multiplier=int(data["candidate_multiplier"]),
        )
        if cached != self.config:
            raise YnnIndexError(
                f"cached config {cached} does not match configured {self.config}"
            )
        self._series = np.asarray(data["series"], dtype=np.float64)
        self._labels = np.asarray(data["labels"])
        self._upper = np.asarray(data["upper"], dtype=np.float64)
        self._lower = np.asarray(data["lower"], dtype=np.float64)
        self._freeze_index_arrays()

    def _freeze_index_arrays(self) -> None:
        """Mark index arrays read-only so an accidental write loudly fails.

        The index is built once per dataset and shared across queries; in-place
        mutation would invalidate the LB_Keogh envelopes without rebuilding.
        """
        for arr in (self._series, self._labels, self._upper, self._lower):
            arr.setflags(write=False)
