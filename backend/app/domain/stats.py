from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from app.core.domain_config import load_domain_config


class SegmentStatisticsError(RuntimeError):
    """Raised when segment statistics cannot be computed safely."""


@dataclass(frozen=True)
class SegmentStatistics:
    schemaVersion: str
    seriesLength: int
    startIndex: int
    endIndex: int
    segmentLength: int
    channelCount: int
    mean: tuple[float, ...]
    variance: float
    slope: float
    signConsistency: float
    residualToLine: float
    contextContrast: float
    peakScore: float

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mean"] = list(self.mean)
        return payload


def compute_segment_statistics(
    series: Any,
    start_index: int,
    end_index: int,
    *,
    smoothing_window: int = 1,
    context_window: int | None = None,
    peak_window: int = 3,
    min_segment_length: int | None = None,
) -> SegmentStatistics:
    normalized = _normalize_series(series)
    _validate_segment_bounds(normalized, start_index, end_index)

    if min_segment_length is None:
        min_segment_length = load_domain_config().duration_limits["minimumSegmentLength"]

    segment = _slice_segment(normalized, start_index, end_index)
    _validate_segment_length(segment, min_segment_length)

    smoothed = _smooth_series(segment, smoothing_window)
    mean = tuple(float(value) for value in np.mean(segment, axis=0))

    return SegmentStatistics(
        schemaVersion="1.0.0",
        seriesLength=int(normalized.shape[0]),
        startIndex=start_index,
        endIndex=end_index,
        segmentLength=int(segment.shape[0]),
        channelCount=int(segment.shape[1]),
        mean=mean,
        variance=compute_variance(segment),
        slope=compute_slope(smoothed),
        signConsistency=compute_sign_consistency(smoothed),
        residualToLine=compute_residual_to_line(smoothed),
        contextContrast=compute_context_contrast(
            normalized,
            start_index,
            end_index,
            context_window=context_window,
        ),
        peakScore=compute_peak_score(segment, window_size=peak_window),
    )


def compute_variance(segment: Any) -> float:
    normalized = _normalize_segment(segment, minimum_length=1)
    mean = np.mean(normalized, axis=0, keepdims=True)
    return float(np.mean(np.sum((normalized - mean) ** 2, axis=1)))


def compute_slope(segment: Any) -> float:
    normalized = _normalize_segment(segment, minimum_length=2)
    x = np.arange(normalized.shape[0], dtype=np.float64)
    centered_x = x - np.mean(x)
    denominator = float(np.sum(centered_x ** 2))
    if denominator == 0:
        raise SegmentStatisticsError("Cannot compute slope for a zero-variance time index.")

    slopes = []
    for channel_index in range(normalized.shape[1]):
        y = normalized[:, channel_index]
        centered_y = y - np.mean(y)
        slopes.append(float(np.sum(centered_x * centered_y) / denominator))
    return float(np.mean(slopes))


def compute_sign_consistency(segment: Any) -> float:
    normalized = _normalize_segment(segment, minimum_length=2)
    diffs = np.diff(normalized, axis=0)
    positive_ratio = float(np.mean(diffs > 0))
    negative_ratio = float(np.mean(diffs < 0))
    return max(positive_ratio, negative_ratio)


def compute_residual_to_line(segment: Any) -> float:
    normalized = _normalize_segment(segment, minimum_length=2)
    x = np.arange(normalized.shape[0], dtype=np.float64)
    residuals = []

    for channel_index in range(normalized.shape[1]):
        y = normalized[:, channel_index]
        slope, intercept = np.polyfit(x, y, deg=1)
        fitted = intercept + slope * x
        residuals.append(float(np.mean((y - fitted) ** 2)))

    return float(np.mean(residuals))


def compute_context_contrast(
    series: Any,
    start_index: int,
    end_index: int,
    *,
    context_window: int | None = None,
) -> float:
    normalized = _normalize_series(series)
    _validate_segment_bounds(normalized, start_index, end_index)

    segment = _slice_segment(normalized, start_index, end_index)
    if context_window is None:
        context_window = max(1, segment.shape[0])
    if context_window < 1:
        raise SegmentStatisticsError("Context window must be at least 1.")

    left_start = max(0, start_index - context_window)
    left_context = normalized[left_start:start_index]
    right_end = min(normalized.shape[0], end_index + 1 + context_window)
    right_context = normalized[end_index + 1:right_end]

    if left_context.size == 0 and right_context.size == 0:
        return 0.0

    segment_mean = np.mean(segment, axis=0)

    if left_context.size == 0:
        context_mean = np.mean(right_context, axis=0)
    elif right_context.size == 0:
        context_mean = np.mean(left_context, axis=0)
    else:
        context_mean = (np.mean(left_context, axis=0) + np.mean(right_context, axis=0)) / 2

    return float(np.linalg.norm(segment_mean - context_mean))


def compute_peak_score(segment: Any, *, window_size: int = 3, epsilon: float = 1e-8) -> float:
    normalized = _normalize_segment(segment, minimum_length=1)
    if window_size < 1:
        raise SegmentStatisticsError("Peak-score window_size must be at least 1.")

    peak_scores = []
    for channel_index in range(normalized.shape[1]):
        channel = normalized[:, channel_index]
        local_means = np.array([_neighbor_mean(channel, index, window_size) for index in range(channel.shape[0])])
        local_stds = np.array([_neighbor_std(channel, index, window_size) for index in range(channel.shape[0])])
        z_scores = np.abs((channel - local_means) / (local_stds + epsilon))
        peak_scores.append(float(np.max(z_scores)))

    return float(np.max(peak_scores))


def _normalize_series(series: Any) -> np.ndarray:
    array = np.asarray(series, dtype=np.float64)
    if array.ndim == 1:
        return array.reshape(-1, 1)
    if array.ndim == 2:
        return array
    raise SegmentStatisticsError(
        f"Series input must be 1D or 2D time-major data; received array with shape {array.shape}."
    )


def _normalize_segment(segment: Any, minimum_length: int) -> np.ndarray:
    normalized = _normalize_series(segment)
    _validate_segment_length(normalized, minimum_length)
    return normalized


def _validate_segment_bounds(series: np.ndarray, start_index: int, end_index: int) -> None:
    if start_index < 0 or end_index < 0:
        raise SegmentStatisticsError("Segment bounds must be non-negative.")
    if start_index > end_index:
        raise SegmentStatisticsError("Segment start_index cannot be greater than end_index.")
    if end_index >= series.shape[0]:
        raise SegmentStatisticsError(
            f"Segment end_index {end_index} is out of range for series length {series.shape[0]}."
        )


def _validate_segment_length(segment: np.ndarray, minimum_length: int) -> None:
    if segment.shape[0] < minimum_length:
        raise SegmentStatisticsError(
            f"Segment length {segment.shape[0]} is too short; minimum length is {minimum_length}."
        )


def _slice_segment(series: np.ndarray, start_index: int, end_index: int) -> np.ndarray:
    return series[start_index : end_index + 1]


def _smooth_series(segment: np.ndarray, window_size: int) -> np.ndarray:
    if window_size <= 1:
        return segment
    if window_size < 1:
        raise SegmentStatisticsError("Smoothing window must be at least 1.")

    kernel = np.ones(window_size, dtype=np.float64) / window_size
    smoothed_channels = [
        np.convolve(segment[:, channel_index], kernel, mode="same")
        for channel_index in range(segment.shape[1])
    ]
    return np.stack(smoothed_channels, axis=1)


def _neighbor_mean(channel: np.ndarray, center_index: int, window_size: int) -> float:
    window = _neighbor_window(channel, center_index, window_size)
    return float(np.mean(window))


def _neighbor_std(channel: np.ndarray, center_index: int, window_size: int) -> float:
    window = _neighbor_window(channel, center_index, window_size)
    return float(np.std(window))


def _neighbor_window(channel: np.ndarray, center_index: int, window_size: int) -> np.ndarray:
    left = max(0, center_index - window_size)
    right = min(channel.shape[0], center_index + window_size + 1)
    window = channel[left:right]
    if window.shape[0] <= 1:
        return window
    relative_index = center_index - left
    return np.delete(window, relative_index)
