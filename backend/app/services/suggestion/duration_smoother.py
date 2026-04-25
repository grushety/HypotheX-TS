"""Duration-rule smoother — HSMM-lite post-classification cleanup (SEG-012).

Merges under-length segments with their most compatible neighbor until every
segment satisfies the per-class minimum duration ``L_min(y)``.

Algorithm is an iterative restart of the scan after each merge.  Because each
merge strictly reduces segment count, the loop terminates in at most n-1
iterations (where n is the initial segment count) — termination is guaranteed.

Ref: Yu (2010) "Hidden semi-Markov models", Artificial Intelligence 174(2):215-243.
     (Full HSMM decoder is a Phase-4 extension; this is the approximation.)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from app.services.suggestion.boundary_proposal import ProvisionalSegment

# ---------------------------------------------------------------------------
# Per-class minimum segment length defaults (7-primitive vocabulary)
# ---------------------------------------------------------------------------

_DEFAULT_L_MIN: dict[str, int] = {
    "plateau":   20,
    "trend":     15,
    "step":      3,
    "spike":     1,
    "cycle":     20,   # approximation for 2*period; override per-series when period is known
    "transient": 10,
    "noise":     5,
    # Domain-pack aliases (mapped by rule classifier)
    "transition": 3,
    "periodic":  20,
    "event":     10,
}

_DEFAULT_MIN_LENGTH = 5  # fallback for unknown labels


@dataclass
class DurationRuleSmoother:
    """Merge under-length segments with their most compatible neighbor.

    Attributes:
        L_min_per_class:   Per-shape minimum segment length (samples).
        default_min_length: Fallback for labels not in ``L_min_per_class``.
    """

    L_min_per_class: dict[str, int] = field(default_factory=lambda: dict(_DEFAULT_L_MIN))
    default_min_length: int = _DEFAULT_MIN_LENGTH

    def get_min_length(self, label: str | None) -> int:
        if not label:
            return self.default_min_length
        return self.L_min_per_class.get(label, self.default_min_length)

    def smooth(
        self,
        segments: tuple[ProvisionalSegment, ...] | list[ProvisionalSegment],
    ) -> tuple[ProvisionalSegment, ...]:
        """Merge under-length segments until all satisfy L_min(y).

        Args:
            segments: Labeled provisional segments in time order.

        Returns:
            Tuple of segments with all durations >= L_min(y), re-numbered
            from 001.  Returns the input unchanged when it has 0 or 1 segment.
        """
        if len(segments) <= 1:
            return tuple(segments)

        segs = list(segments)
        changed = True
        while changed and len(segs) > 1:
            changed = False
            for i, seg in enumerate(segs):
                if _seg_len(seg) >= self.get_min_length(seg.label):
                    continue
                neighbor_i = self._choose_merge_target(segs, i)
                segs = _merge(segs, i, neighbor_i)
                changed = True
                break  # restart scan after any mutation

        return tuple(
            ProvisionalSegment(
                segmentId=f"segment-{n:03d}",
                startIndex=s.startIndex,
                endIndex=s.endIndex,
                provenance=s.provenance,
                label=s.label,
                confidence=s.confidence,
                labelScores=s.labelScores,
            )
            for n, s in enumerate(segs, start=1)
        )

    def _choose_merge_target(self, segs: list[ProvisionalSegment], i: int) -> int:
        """Return the index of the neighbor to merge segment i into.

        Tiebreak rule (deterministic): prefer left when scores are equal.
        Full OP-040 rule-table integration is a planned extension (SEG-012 note).
        """
        if i <= 0:
            return 1
        if i >= len(segs) - 1:
            return len(segs) - 2

        target = segs[i]
        left = segs[i - 1]
        right = segs[i + 1]

        left_score = _compatibility(target, left)
        right_score = _compatibility(target, right)

        # Deterministic tiebreak: left wins ties (per acceptance criteria)
        if left_score >= right_score:
            return i - 1
        return i + 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seg_len(seg: ProvisionalSegment) -> int:
    return seg.endIndex - seg.startIndex + 1


def _compatibility(target: ProvisionalSegment, neighbor: ProvisionalSegment) -> float:
    """Score for merging target into neighbor (higher = more compatible).

    Sources of evidence (no OP-040 rule table yet — Phase-4 extension):
      1. Target's label-score distribution for the neighbor's label.
      2. Same-label bonus.
      3. Neighbor confidence * small weight.
      4. Neighbor length tiebreaker (prefer absorbing into longer neighbors).
    """
    score = 0.0

    # Evidence from classifier's label-score distribution
    if target.labelScores and neighbor.label:
        score += float(target.labelScores.get(neighbor.label, 0.0))

    # Same-label adjacency bonus
    if target.label and neighbor.label == target.label:
        score += 0.5

    # Neighbor confidence
    if neighbor.confidence is not None:
        score += float(neighbor.confidence) * 0.05

    # Length tiebreaker: slightly prefer absorbing into longer neighbors
    score += min(_seg_len(neighbor), 10) * 0.001

    return score


def _merge(
    segs: list[ProvisionalSegment],
    short_i: int,
    neighbor_i: int,
) -> list[ProvisionalSegment]:
    """Merge segs[short_i] into segs[neighbor_i], preserving full time coverage."""
    short = segs[short_i]
    nbr = segs[neighbor_i]
    keep_left = neighbor_i < short_i

    merged = ProvisionalSegment(
        segmentId=nbr.segmentId,
        startIndex=nbr.startIndex if keep_left else short.startIndex,
        endIndex=short.endIndex if keep_left else nbr.endIndex,
        provenance=nbr.provenance,
        label=nbr.label,
        confidence=_weighted_confidence(nbr, short),
        labelScores=_weighted_label_scores(nbr, short),
    )

    result: list[ProvisionalSegment] = []
    for idx, seg in enumerate(segs):
        if idx == short_i:
            continue
        if idx == neighbor_i:
            result.append(merged)
            continue
        result.append(seg)

    result.sort(key=lambda s: s.startIndex)
    return result


def _weighted_confidence(primary: ProvisionalSegment, absorbed: ProvisionalSegment) -> float | None:
    if primary.confidence is None and absorbed.confidence is None:
        return None
    if primary.confidence is None:
        return absorbed.confidence
    if absorbed.confidence is None:
        return primary.confidence
    pl = _seg_len(primary)
    al = _seg_len(absorbed)
    total = pl + al
    return round((primary.confidence * pl + absorbed.confidence * al) / total, 6)


def _weighted_label_scores(
    primary: ProvisionalSegment,
    absorbed: ProvisionalSegment,
) -> dict[str, float] | None:
    if primary.labelScores is None and absorbed.labelScores is None:
        return None
    if primary.labelScores is None:
        return dict(absorbed.labelScores or {})
    if absorbed.labelScores is None:
        return dict(primary.labelScores)

    pl = _seg_len(primary)
    al = _seg_len(absorbed)
    total = pl + al
    labels = set(primary.labelScores) | set(absorbed.labelScores)
    merged = {
        lbl: round(
            (primary.labelScores.get(lbl, 0.0) * pl + absorbed.labelScores.get(lbl, 0.0) * al)
            / total,
            6,
        )
        for lbl in labels
    }
    # Renormalise to sum=1.0 — assign residual to dominant label
    total_prob = round(sum(merged.values()), 6)
    if total_prob != 1.0 and merged:
        dominant = max(merged, key=merged.__getitem__)
        merged[dominant] = round(max(0.0, merged[dominant] + (1.0 - total_prob)), 6)
    return merged
