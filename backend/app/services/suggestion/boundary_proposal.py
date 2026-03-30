from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class BoundaryProposalError(RuntimeError):
    """Raised when a series cannot be proposed safely."""


@dataclass(frozen=True)
class BoundaryProposerConfig:
    window_size: int = 6
    min_segment_length: int = 5
    score_threshold: float = 0.35
    max_boundaries: int = 8

    @classmethod
    def from_mapping(cls, payload: dict[str, object] | None = None) -> BoundaryProposerConfig:
        if payload is None:
            return cls()
        return cls(
            window_size=int(payload.get("window_size", cls.window_size)),
            min_segment_length=int(payload.get("min_segment_length", cls.min_segment_length)),
            score_threshold=float(payload.get("score_threshold", cls.score_threshold)),
            max_boundaries=int(payload.get("max_boundaries", cls.max_boundaries)),
        )


@dataclass(frozen=True)
class BoundaryCandidate:
    boundaryIndex: int
    score: float
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return {
            "boundaryIndex": self.boundaryIndex,
            "score": self.score,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ProvisionalSegment:
    segmentId: str
    startIndex: int
    endIndex: int
    provenance: str = "model"
    label: str | None = None
    confidence: float | None = None
    labelScores: dict[str, float] | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "segmentId": self.segmentId,
            "startIndex": self.startIndex,
            "endIndex": self.endIndex,
            "provenance": self.provenance,
        }
        if self.label is not None:
            payload["label"] = self.label
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        if self.labelScores is not None:
            payload["labelScores"] = dict(self.labelScores)
        return payload


@dataclass(frozen=True)
class BoundaryProposal:
    seriesLength: int
    channelCount: int
    candidateBoundaries: tuple[BoundaryCandidate, ...]
    provisionalSegments: tuple[ProvisionalSegment, ...]
    config: BoundaryProposerConfig


def propose_boundaries(
    values: np.ndarray | list[list[float]] | list[float],
    config: BoundaryProposerConfig | dict[str, object] | None = None,
) -> BoundaryProposal:
    proposer_config = config if isinstance(config, BoundaryProposerConfig) else BoundaryProposerConfig.from_mapping(config)
    series = _normalize_series(values)
    channel_count, series_length = series.shape
    if series_length < 2:
        raise BoundaryProposalError("Boundary proposer requires a series with at least 2 time steps.")
    if proposer_config.window_size < 2:
        raise BoundaryProposalError("Boundary proposer window_size must be at least 2.")
    if proposer_config.min_segment_length < 1:
        raise BoundaryProposalError("Boundary proposer min_segment_length must be at least 1.")
    if proposer_config.max_boundaries < 1:
        raise BoundaryProposalError("Boundary proposer max_boundaries must be at least 1.")

    scores = _compute_boundary_scores(series, proposer_config)
    candidate_boundaries = _select_candidate_boundaries(scores, proposer_config)
    provisional_segments = _build_segments(series_length, candidate_boundaries)
    return BoundaryProposal(
        seriesLength=series_length,
        channelCount=channel_count,
        candidateBoundaries=tuple(candidate_boundaries),
        provisionalSegments=tuple(provisional_segments),
        config=proposer_config,
    )


def _normalize_series(values: np.ndarray | list[list[float]] | list[float]) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim == 1:
        array = array[np.newaxis, :]
    elif array.ndim != 2:
        raise BoundaryProposalError("Boundary proposer expects a 1D or 2D numeric series.")

    if array.shape[0] > array.shape[1]:
        array = array.T
    return array


def _compute_boundary_scores(series: np.ndarray, config: BoundaryProposerConfig) -> np.ndarray:
    _, series_length = series.shape
    scores = np.zeros(series_length, dtype=float)
    if series_length < (config.min_segment_length * 2):
        return scores

    window = min(config.window_size, max(config.min_segment_length, series_length // 3))
    baseline = float(np.std(series))
    normalizer = baseline if baseline > 1e-6 else 1.0

    for boundary_index in range(config.min_segment_length, series_length - config.min_segment_length + 1):
        left_start = max(0, boundary_index - window)
        right_end = min(series_length, boundary_index + window)
        left = series[:, left_start:boundary_index]
        right = series[:, boundary_index:right_end]
        if left.shape[1] < 2 or right.shape[1] < 2:
            continue

        mean_shift = float(np.linalg.norm(np.mean(right, axis=1) - np.mean(left, axis=1)))
        slope_shift = float(np.linalg.norm(_estimate_slope(right) - _estimate_slope(left)))
        score = (mean_shift + (0.5 * slope_shift)) / normalizer
        scores[boundary_index - 1] = score

    max_score = float(np.max(scores))
    if max_score > 0:
        scores = scores / max_score
    return scores


def _estimate_slope(window: np.ndarray) -> np.ndarray:
    xs = np.arange(window.shape[1], dtype=float)
    xs_centered = xs - xs.mean()
    denominator = float(np.sum(xs_centered**2))
    if denominator <= 0:
        return np.zeros(window.shape[0], dtype=float)

    slopes: list[float] = []
    for channel_values in window:
        ys_centered = channel_values - float(np.mean(channel_values))
        slopes.append(float(np.dot(xs_centered, ys_centered) / denominator))
    return np.asarray(slopes, dtype=float)


def _select_candidate_boundaries(scores: np.ndarray, config: BoundaryProposerConfig) -> list[BoundaryCandidate]:
    candidates: list[tuple[int, float]] = []
    for score_index in range(1, len(scores) - 1):
        score = float(scores[score_index])
        if score < config.score_threshold:
            continue
        if score < float(scores[score_index - 1]) or score < float(scores[score_index + 1]):
            continue
        candidates.append((score_index + 1, score))

    candidates.sort(key=lambda item: item[1], reverse=True)

    selected: list[tuple[int, float]] = []
    for boundary_index, score in candidates:
        if len(selected) >= config.max_boundaries:
            break
        if any(abs(boundary_index - existing_boundary) < config.min_segment_length for existing_boundary, _ in selected):
            continue
        selected.append((boundary_index, score))

    selected.sort(key=lambda item: item[0])
    return [
        BoundaryCandidate(
            boundaryIndex=boundary_index,
            score=round(score, 6),
            confidence=round(min(1.0, max(0.0, score)), 6),
        )
        for boundary_index, score in selected
    ]


def _build_segments(series_length: int, boundaries: list[BoundaryCandidate]) -> list[ProvisionalSegment]:
    provisional_segments: list[ProvisionalSegment] = []
    start_index = 0
    for segment_number, candidate in enumerate(boundaries, start=1):
        provisional_segments.append(
            ProvisionalSegment(
                segmentId=f"segment-{segment_number:03d}",
                startIndex=start_index,
                endIndex=candidate.boundaryIndex - 1,
            )
        )
        start_index = candidate.boundaryIndex

    provisional_segments.append(
        ProvisionalSegment(
            segmentId=f"segment-{len(provisional_segments) + 1:03d}",
            startIndex=start_index,
            endIndex=series_length - 1,
        )
    )
    return provisional_segments
