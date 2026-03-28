from typing import Any

import numpy as np


class SignalTransformError(RuntimeError):
    """Raised when a signal transform cannot be applied safely."""


def shift_level(series: Any, start_index: int, end_index: int, *, delta: float) -> Any:
    normalized, restore = _normalize_series(series)
    _validate_segment_bounds(normalized, start_index, end_index)

    edited = normalized.copy()
    edited[start_index : end_index + 1] += float(delta)
    return restore(edited)


def change_slope(series: Any, start_index: int, end_index: int, *, slope_delta: float) -> Any:
    normalized, restore = _normalize_series(series)
    _validate_segment_bounds(normalized, start_index, end_index)

    edited = normalized.copy()
    segment = edited[start_index : end_index + 1]
    positions = np.arange(segment.shape[0], dtype=np.float64)
    centered_positions = positions - float(np.mean(positions))
    ramp = centered_positions[:, None] * float(slope_delta)
    edited[start_index : end_index + 1] = segment + ramp
    return restore(edited)


def scale_spike(series: Any, start_index: int, end_index: int, *, scale_factor: float) -> Any:
    normalized, restore = _normalize_series(series)
    _validate_segment_bounds(normalized, start_index, end_index)
    if scale_factor < 0:
        raise SignalTransformError("Spike scale_factor must be non-negative.")

    edited = normalized.copy()
    segment = edited[start_index : end_index + 1]
    segment_mean = np.mean(segment, axis=0, keepdims=True)
    edited[start_index : end_index + 1] = segment_mean + float(scale_factor) * (segment - segment_mean)
    return restore(edited)


def suppress_spike(series: Any, start_index: int, end_index: int) -> Any:
    return scale_spike(series, start_index, end_index, scale_factor=0.0)


def shift_event(series: Any, start_index: int, end_index: int, *, offset: int) -> Any:
    normalized, restore = _normalize_series(series)
    _validate_segment_bounds(normalized, start_index, end_index)

    edited = normalized.copy()
    segment = normalized[start_index : end_index + 1]
    positions = np.arange(segment.shape[0], dtype=np.float64)
    source_positions = positions - int(offset)

    shifted_channels = []
    for channel_index in range(segment.shape[1]):
        channel = segment[:, channel_index]
        shifted_channels.append(
            np.interp(
                source_positions,
                positions,
                channel,
                left=float(channel[0]),
                right=float(channel[-1]),
            )
        )

    edited[start_index : end_index + 1] = np.stack(shifted_channels, axis=1)
    return restore(edited)


def remove_event(series: Any, start_index: int, end_index: int) -> Any:
    normalized, restore = _normalize_series(series)
    _validate_segment_bounds(normalized, start_index, end_index)

    if start_index == 0 and end_index == normalized.shape[0] - 1:
        raise SignalTransformError("Cannot remove an event that spans the entire series without context.")

    edited = normalized.copy()
    segment_length = end_index - start_index + 1

    if start_index > 0:
        left_value = normalized[start_index - 1]
    else:
        left_value = None

    if end_index < normalized.shape[0] - 1:
        right_value = normalized[end_index + 1]
    else:
        right_value = None

    if left_value is not None and right_value is not None:
        weights = np.linspace(0.0, 1.0, num=segment_length + 2, dtype=np.float64)[1:-1].reshape(-1, 1)
        fill = (1.0 - weights) * left_value + weights * right_value
    elif left_value is not None:
        fill = np.repeat(left_value.reshape(1, -1), segment_length, axis=0)
    elif right_value is not None:
        fill = np.repeat(right_value.reshape(1, -1), segment_length, axis=0)
    else:
        raise SignalTransformError("RemoveEvent requires at least one neighboring context value.")

    edited[start_index : end_index + 1] = fill
    return restore(edited)


def _normalize_series(series: Any) -> tuple[np.ndarray, Any]:
    array = np.asarray(series, dtype=np.float64)
    if array.ndim == 1:
        return array.reshape(-1, 1), lambda edited: edited[:, 0].copy()
    if array.ndim == 2:
        return array.copy(), lambda edited: edited.copy()
    raise SignalTransformError(
        f"Signal transforms require a 1D or 2D time-major series; received shape {array.shape}."
    )


def _validate_segment_bounds(series: np.ndarray, start_index: int, end_index: int) -> None:
    if start_index < 0 or end_index < 0:
        raise SignalTransformError("Segment bounds must be non-negative.")
    if start_index > end_index:
        raise SignalTransformError("Segment start_index cannot be greater than end_index.")
    if end_index >= series.shape[0]:
        raise SignalTransformError(
            f"Segment end_index {end_index} is out of range for series length {series.shape[0]}."
        )
