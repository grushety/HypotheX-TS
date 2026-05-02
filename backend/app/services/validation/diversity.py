"""DPP log-det diversity for accepted CFs (VAL-011).

Session-level diversity metric that computes ``log det(K)`` over a kernel
matrix ``K_ij = k(c_i, c_j)`` of accepted counterfactuals — high log-det
= diverse exploration; low log-det (or ``-inf``) = repeated near-identical
CFs (a cherry-picking signal that the Guardrails sidebar surfaces).

Sources (binding for ``algorithm-auditor``):

  - Mothilal, Sharma, Tan, "DiCE," FAccT 2020,
    DOI:10.1145/3351095.3372850 — DPP definition for diversity at
    *generation* time. This module applies the same DPP framework at the
    *session* level.
  - Russell, "Efficient Search for Diverse Coherent Explanations,"
    FAT* 2019, DOI:10.1145/3287560.3287569.
  - Kulesza & Taskar, "Determinantal Point Processes for Machine
    Learning," *Foundations and Trends in ML* 5:123 (2012) — DPP
    foundational reference.

There is no peer-reviewed standard for a TS-DTW DPP kernel — this module
adapts the DiCE framework with a DTW-RBF kernel as default. The
``shapelet_edit`` kernel is a project-local stand-in (z-normalised
Euclidean) until a peer-reviewed shapelet-distance kernel emerges; the
``latent_euclidean`` kernel takes an optional encoder callable.

Incremental update (Schur complement) reduces the per-accept cost from
``O(n^3)`` to ``O(n^2)``. Numerical regularisation ``+ ε I`` keeps
``slogdet`` finite when two CFs are near-identical (without it the
matrix becomes singular and slogdet returns ``-inf`` even for tiny
similarity differences).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal, Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DiversityError(RuntimeError):
    """Raised when the diversity computation cannot run on the given inputs."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


KERNEL_DTW_RBF = "dtw_rbf"
KERNEL_SHAPELET_EDIT = "shapelet_edit"
KERNEL_LATENT_EUCLIDEAN = "latent_euclidean"
_ALLOWED_KERNELS = frozenset({
    KERNEL_DTW_RBF, KERNEL_SHAPELET_EDIT, KERNEL_LATENT_EUCLIDEAN,
})

DEFAULT_REGULARISATION = 1e-6
DEFAULT_DTW_BAND = 0.1


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiversityResult:
    """Snapshot of session diversity over the accepted-CF set.

    Attributes:
        log_det:        ``log det(K + εI)``; ``-inf`` for ``n_cfs < 2``
                        (DPP diversity is undefined on a single point).
        n_cfs:          Number of CFs that contributed to ``K``.
        kernel:         Kernel name used.
        bandwidth:      RBF / Gaussian bandwidth, when applicable;
                        ``None`` for non-Gaussian kernels.
        regularisation: ``ε`` added on the diagonal for numerical safety.
    """

    log_det: float
    n_cfs: int
    kernel: str
    bandwidth: float | None
    regularisation: float


# ---------------------------------------------------------------------------
# Helpers — series extraction + kernels
# ---------------------------------------------------------------------------


def _extract_series(cf: Any) -> np.ndarray:
    """Pull a 1-D float array out of an arbitrary "CF-like" input.

    Accepts:
      * ``np.ndarray`` / ``Sequence[float]`` — used directly.
      * Objects with ``edited_series`` (CFResult).
      * Objects with ``values`` (LibraryOpResult).
    """
    if isinstance(cf, np.ndarray):
        return np.asarray(cf, dtype=np.float64).reshape(-1)
    for attr in ("edited_series", "values"):
        if hasattr(cf, attr):
            return np.asarray(getattr(cf, attr), dtype=np.float64).reshape(-1)
    if isinstance(cf, (list, tuple)):
        return np.asarray(cf, dtype=np.float64).reshape(-1)
    raise DiversityError(
        f"_extract_series: cannot extract a series from {type(cf).__name__}; "
        "pass an np.ndarray, a CFResult, or an object with .edited_series/.values."
    )


def _dtw_distance(a: np.ndarray, b: np.ndarray, *, band: float = DEFAULT_DTW_BAND) -> float:
    from tslearn.metrics import dtw as tslearn_dtw  # noqa: PLC0415
    radius = max(1, int(round(band * max(a.shape[0], b.shape[0]))))
    return float(tslearn_dtw(a, b, sakoe_chiba_radius=radius))


def _znorm(x: np.ndarray) -> np.ndarray:
    """Z-normalise a 1-D array; falls back to centred-only when std ≈ 0."""
    mu = float(np.mean(x))
    sd = float(np.std(x))
    if sd < 1e-12:
        return x - mu
    return (x - mu) / sd


def _shapelet_edit_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Project-local stand-in for "shapelet edit distance".

    z-normalise both series, interpolate to a common length (length of the
    longer one), and return the L2 distance. The AC documents this kernel
    as project-specific; we keep it cheap (no shapelet extraction yet) and
    z-normalisation makes it scale-invariant — the property that motivates
    a "shapelet" interpretation in the first place.
    """
    n = max(a.shape[0], b.shape[0])
    if a.shape[0] != n:
        a = np.interp(np.linspace(0, a.shape[0] - 1, n),
                      np.arange(a.shape[0], dtype=np.float64), a)
    if b.shape[0] != n:
        b = np.interp(np.linspace(0, b.shape[0] - 1, n),
                      np.arange(b.shape[0], dtype=np.float64), b)
    return float(np.linalg.norm(_znorm(a) - _znorm(b)))


def _euclidean_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Plain Euclidean; for unequal lengths interpolate to the longer."""
    n = max(a.shape[0], b.shape[0])
    if a.shape[0] != n:
        a = np.interp(np.linspace(0, a.shape[0] - 1, n),
                      np.arange(a.shape[0], dtype=np.float64), a)
    if b.shape[0] != n:
        b = np.interp(np.linspace(0, b.shape[0] - 1, n),
                      np.arange(b.shape[0], dtype=np.float64), b)
    return float(np.linalg.norm(a - b))


def _pairwise_distances(
    series: list[np.ndarray],
    kernel: str,
    *,
    encoder: Callable[[np.ndarray], np.ndarray] | None = None,
) -> np.ndarray:
    """Symmetric n × n distance matrix in the chosen kernel's metric."""
    n = len(series)
    D = np.zeros((n, n), dtype=np.float64)
    if kernel == KERNEL_DTW_RBF:
        for i in range(n):
            for j in range(i + 1, n):
                d = _dtw_distance(series[i], series[j])
                D[i, j] = D[j, i] = d
    elif kernel == KERNEL_SHAPELET_EDIT:
        for i in range(n):
            for j in range(i + 1, n):
                d = _shapelet_edit_distance(series[i], series[j])
                D[i, j] = D[j, i] = d
    elif kernel == KERNEL_LATENT_EUCLIDEAN:
        encoded = (
            [np.asarray(encoder(s), dtype=np.float64).reshape(-1) for s in series]
            if encoder is not None else series
        )
        for i in range(n):
            for j in range(i + 1, n):
                d = _euclidean_distance(encoded[i], encoded[j])
                D[i, j] = D[j, i] = d
    else:
        raise DiversityError(
            f"unknown kernel {kernel!r}; expected one of {sorted(_ALLOWED_KERNELS)}"
        )
    return D


def _kernel_matrix(
    distances: np.ndarray,
    kernel: str,
    bandwidth: float | None,
) -> tuple[np.ndarray, float | None]:
    """Convert a distance matrix into a kernel (similarity) matrix."""
    n = distances.shape[0]
    if n == 0:
        return np.zeros((0, 0)), None

    if kernel == KERNEL_SHAPELET_EDIT:
        # Linear similarity 1 / (1 + d); no bandwidth.
        K = 1.0 / (1.0 + distances)
        return K, None

    # RBF for both DTW and latent_euclidean.
    if bandwidth is None:
        # Median-heuristic on upper-triangular off-diagonal entries.
        if n >= 2:
            iu = np.triu_indices(n, k=1)
            pair = distances[iu]
            med = float(np.median(pair)) if pair.size else 1.0
            sigma = med if med > 0.0 else 1.0
        else:
            sigma = 1.0
    else:
        sigma = float(bandwidth)
        if sigma <= 0:
            raise DiversityError(f"bandwidth must be > 0; got {sigma}")
    K = np.exp(-(distances ** 2) / (2.0 * sigma ** 2))
    return K, sigma


# ---------------------------------------------------------------------------
# One-shot diversity (full recompute)
# ---------------------------------------------------------------------------


def dpp_log_det_diversity(
    cfs: Iterable[Any],
    *,
    kernel: Literal["dtw_rbf", "shapelet_edit", "latent_euclidean"] = KERNEL_DTW_RBF,
    bandwidth: float | None = None,
    regularisation: float = DEFAULT_REGULARISATION,
    encoder: Callable[[np.ndarray], np.ndarray] | None = None,
) -> DiversityResult:
    """Compute ``log det(K + εI)`` over the kernel matrix of accepted CFs.

    Args:
        cfs:            Iterable of CF-like inputs; ``_extract_series``
                        pulls the underlying 1-D array.
        kernel:         ``'dtw_rbf'`` (default) | ``'shapelet_edit'`` |
                        ``'latent_euclidean'``.
        bandwidth:      Override the RBF bandwidth; ``None`` triggers
                        the median-heuristic on the pairwise distances.
                        Ignored for ``'shapelet_edit'``.
        regularisation: ``ε`` added on the diagonal; default ``1e-6``.
        encoder:        Optional ``np.ndarray → np.ndarray`` projection
                        used for ``'latent_euclidean'``; default identity.

    Returns:
        ``DiversityResult`` with ``log_det = -inf`` when ``n_cfs < 2``
        (a single point has no pairs; DPP diversity is undefined).

    Raises:
        ``DiversityError`` on unknown kernel, non-positive bandwidth,
        non-positive regularisation, or unextractable inputs.
    """
    if regularisation < 0:
        raise DiversityError(f"regularisation must be ≥ 0; got {regularisation}")
    if kernel not in _ALLOWED_KERNELS:
        raise DiversityError(
            f"unknown kernel {kernel!r}; expected one of {sorted(_ALLOWED_KERNELS)}"
        )

    series = [_extract_series(c) for c in cfs]
    n = len(series)
    if n < 2:
        return DiversityResult(
            log_det=float("-inf"),
            n_cfs=n,
            kernel=kernel,
            bandwidth=None,
            regularisation=regularisation,
        )

    distances = _pairwise_distances(series, kernel, encoder=encoder)
    K, sigma = _kernel_matrix(distances, kernel, bandwidth)
    K_reg = K + regularisation * np.eye(n)
    sign, log_det = np.linalg.slogdet(K_reg)
    if sign <= 0:
        log_det = float("-inf")
    return DiversityResult(
        log_det=float(log_det),
        n_cfs=n,
        kernel=kernel,
        bandwidth=sigma,
        regularisation=regularisation,
    )


# ---------------------------------------------------------------------------
# Incremental tracker (Schur-complement updates)
# ---------------------------------------------------------------------------


class IncrementalDiversityTracker:
    """Maintains ``log det(K)`` under incremental ``add(cf)`` calls.

    The Schur-complement update keeps the per-accept cost at ``O(n^2)``
    instead of ``O(n^3)``: when adding the n-th CF,

        K_new = [[K_old, k], [k^T, K_nn]]
        s = K_nn − k^T K_old^{-1} k
        log det(K_new) = log det(K_old) + log(s)
        K_new^{-1} = block-inverse using s, k, K_old^{-1}.

    The bandwidth caveat: with ``kernel='dtw_rbf'`` and
    ``bandwidth=None``, the median-heuristic σ is computed at the *first*
    incremental update that crosses ``n=2`` and frozen for the rest of
    the session. This keeps the running ``log det`` consistent — re-deriving
    σ on every accept would re-shape the kernel matrix and invalidate the
    cached ``K_old^{-1}``. Callers who need the median-heuristic to track
    new accepts should use the one-shot ``dpp_log_det_diversity`` instead,
    or supply an explicit ``bandwidth``.
    """

    def __init__(
        self,
        *,
        kernel: Literal["dtw_rbf", "shapelet_edit", "latent_euclidean"] = KERNEL_DTW_RBF,
        bandwidth: float | None = None,
        regularisation: float = DEFAULT_REGULARISATION,
        encoder: Callable[[np.ndarray], np.ndarray] | None = None,
    ) -> None:
        if kernel not in _ALLOWED_KERNELS:
            raise DiversityError(
                f"unknown kernel {kernel!r}; expected one of {sorted(_ALLOWED_KERNELS)}"
            )
        if regularisation < 0:
            raise DiversityError(f"regularisation must be ≥ 0; got {regularisation}")
        if bandwidth is not None and bandwidth <= 0:
            raise DiversityError(f"bandwidth must be > 0 or None; got {bandwidth}")
        self.kernel = kernel
        self._bandwidth_override = bandwidth
        self._frozen_bandwidth: float | None = None
        self.regularisation = float(regularisation)
        self._encoder = encoder

        self._series: list[np.ndarray] = []
        self._K: np.ndarray | None = None
        self._K_inv: np.ndarray | None = None
        self._log_det: float = float("-inf")

    # -------- incremental add ---------------------------------------------

    def add(self, cf: Any) -> None:
        """Append a CF and update ``K``, ``K_inv``, ``log_det`` in place."""
        new_series = _extract_series(cf)
        self._series.append(new_series)
        n = len(self._series)

        if n == 1:
            # Single point — log_det remains -inf per the AC.
            self._K = None
            self._K_inv = None
            self._log_det = float("-inf")
            return

        if n == 2:
            # First time the matrix is ≥ 2×2 → recompute from scratch so
            # the median-heuristic σ is set on the actual distance pair.
            self._full_recompute()
            return

        # n ≥ 3 — Schur-complement incremental update.
        # Compute the new kernel column k (length n-1) between the new
        # series and each existing series, plus the diagonal entry K_nn.
        k_col = self._kernel_column(new_series, self._series[:-1])
        K_nn = self._kernel_self() + self.regularisation

        K_old_inv = self._K_inv
        K_old = self._K
        if K_old is None or K_old_inv is None:  # pragma: no cover — n≥3 implies state set
            self._full_recompute()
            return

        v = K_old_inv @ k_col  # (n-1,)
        s = K_nn - float(k_col @ v)
        if s <= 0.0:
            # Numerical drift on near-duplicate inputs — fall back to a
            # full recompute. log_det may become -inf, which is the right
            # signal for "this CF is identical to one already accepted".
            self._full_recompute()
            return

        new_K = np.zeros((n, n), dtype=np.float64)
        new_K[:n - 1, :n - 1] = K_old
        new_K[:n - 1, n - 1] = k_col
        new_K[n - 1, :n - 1] = k_col
        new_K[n - 1, n - 1] = K_nn

        new_K_inv = np.zeros((n, n), dtype=np.float64)
        new_K_inv[:n - 1, :n - 1] = K_old_inv + np.outer(v, v) / s
        new_K_inv[:n - 1, n - 1] = -v / s
        new_K_inv[n - 1, :n - 1] = -v / s
        new_K_inv[n - 1, n - 1] = 1.0 / s

        self._K = new_K
        self._K_inv = new_K_inv
        self._log_det = self._log_det + float(np.log(s))

    # -------- recompute (used at n=2 or numerical fallback) ----------------

    def _full_recompute(self) -> None:
        n = len(self._series)
        if n < 2:
            self._K = None
            self._K_inv = None
            self._log_det = float("-inf")
            return
        distances = _pairwise_distances(self._series, self.kernel, encoder=self._encoder)
        if self._frozen_bandwidth is None and self._bandwidth_override is None:
            iu = np.triu_indices(n, k=1)
            med = float(np.median(distances[iu])) if distances[iu].size else 1.0
            self._frozen_bandwidth = med if med > 0.0 else 1.0
        K, sigma = _kernel_matrix(
            distances, self.kernel,
            self._bandwidth_override if self._bandwidth_override is not None
            else self._frozen_bandwidth,
        )
        K_reg = K + self.regularisation * np.eye(n)
        sign, log_det = np.linalg.slogdet(K_reg)
        self._K = K_reg
        self._K_inv = np.linalg.inv(K_reg)
        self._log_det = float(log_det) if sign > 0 else float("-inf")

    # -------- kernel pieces ------------------------------------------------

    def _effective_bandwidth(self) -> float | None:
        if self.kernel == KERNEL_SHAPELET_EDIT:
            return None
        if self._bandwidth_override is not None:
            return self._bandwidth_override
        return self._frozen_bandwidth

    def _kernel_column(self, new_series: np.ndarray,
                       existing: list[np.ndarray]) -> np.ndarray:
        # Per-pair distance.
        distances = np.empty(len(existing), dtype=np.float64)
        for i, s in enumerate(existing):
            distances[i] = self._pair_distance(new_series, s)
        return self._distance_to_kernel(distances)

    def _kernel_self(self) -> float:
        # k(x, x) — RBF gives 1, shapelet_edit gives 1/(1+0)=1 too.
        return 1.0

    def _pair_distance(self, a: np.ndarray, b: np.ndarray) -> float:
        if self.kernel == KERNEL_DTW_RBF:
            return _dtw_distance(a, b)
        if self.kernel == KERNEL_SHAPELET_EDIT:
            return _shapelet_edit_distance(a, b)
        if self.kernel == KERNEL_LATENT_EUCLIDEAN:
            if self._encoder is not None:
                a_e = np.asarray(self._encoder(a), dtype=np.float64).reshape(-1)
                b_e = np.asarray(self._encoder(b), dtype=np.float64).reshape(-1)
                return _euclidean_distance(a_e, b_e)
            return _euclidean_distance(a, b)
        raise DiversityError(  # pragma: no cover
            f"unknown kernel {self.kernel!r}"
        )

    def _distance_to_kernel(self, distances: np.ndarray) -> np.ndarray:
        if self.kernel == KERNEL_SHAPELET_EDIT:
            return 1.0 / (1.0 + distances)
        sigma = self._effective_bandwidth()
        if sigma is None or sigma <= 0:
            sigma = 1.0
        return np.exp(-(distances ** 2) / (2.0 * sigma ** 2))

    # -------- query --------------------------------------------------------

    def result(self) -> DiversityResult:
        return DiversityResult(
            log_det=float(self._log_det),
            n_cfs=len(self._series),
            kernel=self.kernel,
            bandwidth=self._effective_bandwidth(),
            regularisation=self.regularisation,
        )

    @property
    def log_det(self) -> float:
        return float(self._log_det)

    @property
    def n_cfs(self) -> int:
        return len(self._series)

    # -------- lifecycle ----------------------------------------------------

    def reset(self) -> None:
        self._series.clear()
        self._K = None
        self._K_inv = None
        self._log_det = float("-inf")
        # Note: frozen bandwidth from a previous session stays cleared too.
        self._frozen_bandwidth = None

    @classmethod
    def from_cfs(
        cls,
        cfs: Iterable[Any],
        *,
        kernel: Literal["dtw_rbf", "shapelet_edit", "latent_euclidean"] = KERNEL_DTW_RBF,
        bandwidth: float | None = None,
        regularisation: float = DEFAULT_REGULARISATION,
        encoder: Callable[[np.ndarray], np.ndarray] | None = None,
    ) -> "IncrementalDiversityTracker":
        """Replay constructor — equivalent to constructing then calling
        ``add`` for each CF in order. Used at server startup to recover
        state from the persisted audit log."""
        tracker = cls(
            kernel=kernel, bandwidth=bandwidth,
            regularisation=regularisation, encoder=encoder,
        )
        for c in cfs:
            tracker.add(c)
        return tracker
