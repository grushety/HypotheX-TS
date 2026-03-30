from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class SegmentEncodingError(RuntimeError):
    """Raised when a segment cannot be encoded safely."""


@dataclass(frozen=True)
class SegmentEncoderConfig:
    resample_length: int = 16
    include_differences: bool = True
    include_summary_features: bool = True


@dataclass(frozen=True)
class SegmentEmbedding:
    values: tuple[float, ...]
    length: int
    channelCount: int
    normalized: bool = True

    def as_array(self) -> np.ndarray:
        return np.asarray(self.values, dtype=np.float64)


def encode_segment(
    values: np.ndarray | list[list[float]] | list[float],
    config: SegmentEncoderConfig | None = None,
) -> SegmentEmbedding:
    encoder_config = config or SegmentEncoderConfig()
    if encoder_config.resample_length < 4:
        raise SegmentEncodingError("Segment encoder resample_length must be at least 4.")

    series = normalize_series(values)
    if series.shape[1] < 2:
        raise SegmentEncodingError("Segment encoder requires at least 2 time steps.")

    standardized = _standardize_channels(_resample_channels(series, encoder_config.resample_length))
    components = [np.mean(standardized, axis=0)]
    if encoder_config.include_differences:
        differences = np.diff(standardized, axis=1, prepend=standardized[:, :1])
        components.append(np.mean(differences, axis=0))
    if encoder_config.include_summary_features:
        components.append(_summary_features(standardized, original_length=series.shape[1]))

    raw_vector = np.concatenate(components).astype(np.float64)
    normalized_vector = _l2_normalize(raw_vector)
    return SegmentEmbedding(
        values=tuple(float(value) for value in normalized_vector),
        length=int(series.shape[1]),
        channelCount=int(series.shape[0]),
    )


def normalize_series(values: np.ndarray | list[list[float]] | list[float]) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim == 1:
        return array[np.newaxis, :]
    if array.ndim != 2:
        raise SegmentEncodingError("Segment encoder expects a 1D or 2D numeric series.")
    if array.shape[0] > array.shape[1]:
        return array.T
    return array


def slice_series(
    values: np.ndarray | list[list[float]] | list[float],
    start_index: int,
    end_index: int,
) -> np.ndarray:
    series = normalize_series(values)
    if start_index < 0 or end_index < start_index or end_index >= series.shape[1]:
        raise SegmentEncodingError(
            f"Segment bounds [{start_index}, {end_index}] are invalid for series length {series.shape[1]}."
        )
    return series[:, start_index : end_index + 1]


def _resample_channels(series: np.ndarray, resample_length: int) -> np.ndarray:
    source_positions = np.linspace(0.0, 1.0, num=series.shape[1], dtype=np.float64)
    target_positions = np.linspace(0.0, 1.0, num=resample_length, dtype=np.float64)
    return np.vstack(
        [
            np.interp(target_positions, source_positions, channel_values).astype(np.float64)
            for channel_values in series
        ]
    )


def _standardize_channels(series: np.ndarray) -> np.ndarray:
    means = np.mean(series, axis=1, keepdims=True)
    stds = np.std(series, axis=1, keepdims=True)
    safe_stds = np.where(stds > 1e-8, stds, 1.0)
    return (series - means) / safe_stds


def _summary_features(series: np.ndarray, *, original_length: int) -> np.ndarray:
    absolute = np.abs(series)
    return np.asarray(
        [
            np.log1p(float(original_length)),
            float(np.mean(absolute)),
            float(np.std(series)),
            float(np.max(absolute)),
        ],
        dtype=np.float64,
    )


def _l2_normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-8:
        raise SegmentEncodingError("Segment encoder produced a near-zero embedding.")
    return vector / norm
