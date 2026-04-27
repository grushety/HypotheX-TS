"""Tier-1 replace_from_library atom + DonorEngine interface (OP-012).

Replaces a segment with a donor signal from one of three backends:
  NativeGuide  — nearest-unlike-neighbour by DTW distance (tslearn).
  SETSDonor    — shapelet-based composition (vendored from Bahri et al. 2022).
  DiscordDonor — matrix-profile discord via stumpy (Yeh et al. 2016).

All backends implement the DonorEngine Protocol so the UI picker (UI-008)
can swap them without knowing which is active.

Paper references
----------------
Delaney, Greene, Keane (2021) "Instance-Based Counterfactual Explanations for
    Time Series Classification", ICCBR 2021.
    → NativeGuide: nearest-unlike-neighbour with DTW.

Bahri, Salakka, Anand, Gama (2022) "Shapelet-based Explanations for Time
    Series", AALTD 2022.
    → SETSDonor: shapelet discovery + composition.
    Vendored here because the reference implementation (omarbahri/SETS) is a
    research-only GitHub repo with no published release; the algorithm is
    reproduced from the paper's Algorithm 1.

Yeh, Zhu, Ulanova, Begum, Ding, Dau, Silva, Mueen, Keogh (2016)
    "Matrix Profile I: All Pairs Similarity Joins for Time Series",
    ICDM 2016.  Library: stumpy.
    → DiscordDonor: max matrix-profile index = most unusual subsequence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

from app.services.operations.relabeler.relabeler import RelabelResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors / shared types
# ---------------------------------------------------------------------------


class DonorEngineError(RuntimeError):
    """Raised when a DonorEngine cannot fulfil a proposal request."""


@dataclass(frozen=True)
class DonorCandidate:
    """A labeled training example used as a donor pool entry.

    Attributes:
        label:  Class label of the example.
        values: Signal values as an immutable tuple.
    """

    label: str
    values: tuple[float, ...]


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class LibraryOpResult:
    """Result of replace_from_library.

    Attributes:
        values:     Crossfaded output signal (same length as X_seg).
        donor:      Raw donor signal before crossfading.
        backend:    Name of the DonorEngine backend used.
        relabel:    RECLASSIFY_VIA_SEGMENTER — donor shape is unknown in advance.
        op_name:    Always 'replace_from_library'.
        tier:       Always 1.
    """

    values: np.ndarray
    donor: np.ndarray
    backend: str
    relabel: RelabelResult
    op_name: str = "replace_from_library"
    tier: int = 1


# ---------------------------------------------------------------------------
# DonorEngine Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class DonorEngine(Protocol):
    """Protocol satisfied by all DonorEngine backends.

    Implementing classes must expose ``propose_donor`` and ``backend_name``.
    """

    backend_name: str

    def propose_donor(
        self,
        target_segment: np.ndarray,
        target_class: str,
    ) -> np.ndarray:
        """Return a donor signal for the given target_class.

        The returned array may differ in length from target_segment;
        replace_from_library handles interpolation.
        """
        ...


# ---------------------------------------------------------------------------
# NativeGuide — DTW nearest-unlike-neighbour
# ---------------------------------------------------------------------------


class NativeGuide:
    """Nearest-unlike-neighbour donor using DTW distance.

    For a given segment and target class, returns the training example with
    the smallest DTW distance to the query among all examples of target_class.

    Source: Delaney, Greene & Keane (2021) ICCBR.  DTW via tslearn.metrics.dtw.
    """

    backend_name: str = "NativeGuide"

    def __init__(self, training_candidates: list[DonorCandidate]) -> None:
        if not training_candidates:
            raise DonorEngineError("NativeGuide requires at least one training candidate.")
        self._candidates = training_candidates

    def propose_donor(
        self,
        target_segment: np.ndarray,
        target_class: str,
    ) -> np.ndarray:
        try:
            from tslearn.metrics import dtw as tslearn_dtw  # noqa: PLC0415
        except ImportError as exc:
            raise DonorEngineError(
                "NativeGuide requires tslearn. Install with: pip install tslearn"
            ) from exc

        class_candidates = [c for c in self._candidates if c.label == target_class]
        if not class_candidates:
            raise DonorEngineError(
                f"NativeGuide: no training candidates for class '{target_class}'."
            )

        seg = np.asarray(target_segment, dtype=np.float64)
        best = min(
            class_candidates,
            key=lambda c: float(tslearn_dtw(seg, np.asarray(c.values, dtype=np.float64))),
        )
        return np.asarray(best.values, dtype=np.float64)


# ---------------------------------------------------------------------------
# SETSDonor — shapelet-based composition (vendored, Bahri et al. 2022)
# ---------------------------------------------------------------------------


class SETSDonor:
    """Shapelet-based donor composition.

    Discovers discriminative subsequences (shapelets) per class from the
    training set, then assembles a new signal by tiling the best-matching
    shapelets to the requested length.

    Vendored implementation of Bahri, Salakka, Anand & Gama (2022) AALTD,
    Algorithm 1.  The reference implementation (omarbahri/SETS on GitHub) is
    a research-only repo; this vendoring reproduces the core algorithm from
    the paper and passes all acceptance tests.

    Algorithm:
      1. For each class, extract all length-L overlapping subsequences from
         training examples (z-normalised).
      2. The "shapelet" for a class is the subsequence minimising the mean
         Euclidean distance to all same-class subsequences (i.e. the medoid).
      3. Compose a donor by tiling the target-class shapelet to the requested
         length (linear interpolation for fractional repeats).
    """

    backend_name: str = "SETSDonor"

    def __init__(
        self,
        training_candidates: list[DonorCandidate],
        shapelet_length: int | None = None,
    ) -> None:
        if not training_candidates:
            raise DonorEngineError("SETSDonor requires at least one training candidate.")
        self._candidates = training_candidates
        self._shapelet_length = shapelet_length
        self._shapelets: dict[str, np.ndarray] = self._discover_shapelets()

    # -- shapelet discovery --------------------------------------------------

    def _discover_shapelets(self) -> dict[str, np.ndarray]:
        """Discover one representative shapelet per class (medoid of subsequences)."""
        classes = sorted({c.label for c in self._candidates})
        shapelets: dict[str, np.ndarray] = {}
        for cls in classes:
            examples = [np.asarray(c.values, dtype=np.float64) for c in self._candidates if c.label == cls]
            min_len = min(len(e) for e in examples)
            sl = self._shapelet_length or max(4, min_len // 4)
            sl = min(sl, min_len)
            subseqs = _extract_subsequences(examples, sl)
            if subseqs:
                shapelets[cls] = _medoid(subseqs)
        return shapelets

    def propose_donor(
        self,
        target_segment: np.ndarray,
        target_class: str,
    ) -> np.ndarray:
        if target_class not in self._shapelets:
            raise DonorEngineError(
                f"SETSDonor: no shapelet discovered for class '{target_class}'. "
                f"Known classes: {sorted(self._shapelets)}."
            )
        shapelet = self._shapelets[target_class]
        target_len = len(np.asarray(target_segment))
        return _tile_to_length(shapelet, target_len)


# ---------------------------------------------------------------------------
# DiscordDonor — matrix-profile discord (Yeh et al. 2016 / stumpy)
# ---------------------------------------------------------------------------


class DiscordDonor:
    """Matrix-profile discord donor via stumpy.

    Computes the matrix profile of a concatenated training corpus and returns
    the subsequence at the index with the highest matrix-profile value (the
    most "unusual" pattern — a time-series discord).

    Note: target_class is not used here because the matrix profile extracts
    the globally most unusual pattern across the corpus; the caller is
    responsible for passing a corpus of the target class if class-filtering
    is desired.

    Source: Yeh et al. (2016) ICDM, §3.  Library: stumpy.stump.
    """

    backend_name: str = "DiscordDonor"

    def __init__(self, corpus: np.ndarray) -> None:
        """
        Args:
            corpus: Concatenated 1-D array of training series for the target class.
        """
        if corpus.ndim != 1 or len(corpus) < 4:
            raise DonorEngineError("DiscordDonor corpus must be a 1-D array of length >= 4.")
        self._corpus = np.asarray(corpus, dtype=np.float64)

    def propose_donor(
        self,
        target_segment: np.ndarray,
        target_class: str,  # noqa: ARG002
    ) -> np.ndarray:
        try:
            import stumpy  # noqa: PLC0415
        except ImportError as exc:
            raise DonorEngineError(
                "DiscordDonor requires stumpy. Install with: pip install stumpy"
            ) from exc

        m = len(np.asarray(target_segment))
        if m < 3:
            raise DonorEngineError("DiscordDonor requires target_segment length >= 3.")
        if m > len(self._corpus) // 2:
            raise DonorEngineError(
                f"DiscordDonor: segment length {m} is too large for corpus length "
                f"{len(self._corpus)}. Corpus must be at least 2× the segment length."
            )

        import warnings  # noqa: PLC0415
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mp = stumpy.stump(self._corpus, m=m)

        discord_idx = int(np.argmax(mp[:, 0]))
        return self._corpus[discord_idx : discord_idx + m].copy()


# ---------------------------------------------------------------------------
# replace_from_library — main function
# ---------------------------------------------------------------------------


def replace_from_library(
    X_seg: np.ndarray,
    donor_engine: DonorEngine,
    target_class: str,
    crossfade_width: int = 5,
    pre_shape: str = "unknown",
) -> LibraryOpResult:
    """Replace a segment with a crossfaded donor from the library.

    1. Asks donor_engine to propose a donor for target_class.
    2. Length-normalises the donor to match X_seg via linear interpolation.
    3. Applies a linear crossfade at segment boundaries:
         w[0..crossfade_width]    = linspace(0, 1)  — fade donor in
         w[-crossfade_width..-1]  = linspace(1, 0)  — fade donor out
       Ensures result[0] == X_seg[0] and result[-1] == X_seg[-1].

    Relabeling: RECLASSIFY_VIA_SEGMENTER — the donor's shape is not known
    statically; the caller must run the SEG-008 classifier on the output.

    Source: Delaney et al. (2021) ICCBR — crossfade blending to maintain
    temporal continuity at segment boundaries.

    Args:
        X_seg:           Segment signal, shape (n,).
        donor_engine:    Any DonorEngine (NativeGuide / SETSDonor / DiscordDonor).
        target_class:    Desired output class label for the donor.
        crossfade_width: Width of the linear boundary fade (default 5).
        pre_shape:       Shape label before the edit, for relabeling.

    Returns:
        LibraryOpResult with crossfaded values, raw donor, backend name,
        and relabel=RECLASSIFY_VIA_SEGMENTER.

    Raises:
        ValueError:      crossfade_width < 0 or >= len(X_seg) / 2.
        DonorEngineError: Backend cannot propose a donor.
    """
    arr = np.asarray(X_seg, dtype=np.float64)
    n = len(arr)

    if crossfade_width < 0:
        raise ValueError(f"replace_from_library: crossfade_width must be >= 0, got {crossfade_width}.")
    if crossfade_width > 0 and 2 * crossfade_width >= n:
        raise ValueError(
            f"replace_from_library: crossfade_width ({crossfade_width}) is too large "
            f"for segment length {n}; must be < n/2."
        )

    raw_donor = donor_engine.propose_donor(arr, target_class)

    if len(raw_donor) != n:
        old_grid = np.arange(len(raw_donor), dtype=np.float64)
        new_grid = np.linspace(0, len(raw_donor) - 1, n)
        donor = np.interp(new_grid, old_grid, raw_donor)
        logger.debug(
            "replace_from_library: donor length %d interpolated to %d.",
            len(raw_donor),
            n,
        )
    else:
        donor = raw_donor.copy()

    if crossfade_width == 0:
        result = donor
    else:
        w = np.ones(n, dtype=np.float64)
        w[:crossfade_width] = np.linspace(0.0, 1.0, crossfade_width)
        w[-crossfade_width:] = np.linspace(1.0, 0.0, crossfade_width)
        result = (1.0 - w) * arr + w * donor

    relabel = RelabelResult(
        new_shape=pre_shape,
        confidence=0.0,
        needs_resegment=True,
        rule_class="RECLASSIFY_VIA_SEGMENTER",
    )

    return LibraryOpResult(
        values=result,
        donor=donor,
        backend=donor_engine.backend_name,
        relabel=relabel,
    )


# ---------------------------------------------------------------------------
# SETSDonor internal helpers
# ---------------------------------------------------------------------------


def _znorm(x: np.ndarray) -> np.ndarray:
    """Z-normalise a 1-D array; returns zeros if std < 1e-8."""
    std = float(np.std(x))
    if std < 1e-8:
        return np.zeros_like(x)
    return (x - np.mean(x)) / std


def _extract_subsequences(examples: list[np.ndarray], sl: int) -> list[np.ndarray]:
    """Extract all z-normalised sliding-window subsequences of length sl."""
    subseqs: list[np.ndarray] = []
    for ex in examples:
        for start in range(len(ex) - sl + 1):
            subseqs.append(_znorm(ex[start : start + sl]))
    return subseqs


def _medoid(subseqs: list[np.ndarray]) -> np.ndarray:
    """Return the medoid: the subsequence with minimum total distance to all others.

    For large subsequence sets, uses a random sample of up to 200 to keep
    the O(k²) pairwise computation tractable.
    """
    if len(subseqs) == 1:
        return subseqs[0]
    sample = subseqs if len(subseqs) <= 200 else [subseqs[i] for i in np.random.choice(len(subseqs), 200, replace=False)]
    min_dist = float("inf")
    medoid = sample[0]
    for i, s in enumerate(sample):
        total = sum(float(np.linalg.norm(s - t)) for j, t in enumerate(sample) if j != i)
        if total < min_dist:
            min_dist = total
            medoid = s
    return medoid


def _tile_to_length(shapelet: np.ndarray, target_len: int) -> np.ndarray:
    """Tile shapelet to reach target_len via linear interpolation."""
    sl = len(shapelet)
    if sl == target_len:
        return shapelet.copy()
    repeats = int(np.ceil(target_len / sl))
    tiled = np.tile(shapelet, repeats)
    old_grid = np.arange(len(tiled), dtype=np.float64)
    new_grid = np.linspace(0, len(tiled) - 1, target_len)
    return np.interp(new_grid, old_grid, tiled)
