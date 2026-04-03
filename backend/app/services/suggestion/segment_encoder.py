from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


class SegmentEncodingError(RuntimeError):
    """Raised when a segment cannot be encoded safely."""


@dataclass(frozen=True)
class SegmentEncoderConfig:
    resample_length: int = 16
    include_differences: bool = True
    include_summary_features: bool = True
    smoothing_window: int = 5
    zscore_window: int = 10
    include_missingness_mask: bool = True


@dataclass(frozen=True)
class SegmentEmbedding:
    values: tuple[float, ...]
    length: int
    channelCount: int
    normalized: bool = True

    def as_array(self) -> np.ndarray:
        return np.asarray(self.values, dtype=np.float64)


def build_feature_matrix(
    values: np.ndarray | list[list[float]] | list[float],
    config: SegmentEncoderConfig | None = None,
) -> np.ndarray:
    """Build augmented feature matrix X_feat ∈ R^(d' × T) from a raw signal.

    Channels stacked along axis 0 (one group per input channel C):
      1. Raw signal
      2. Rolling-mean smoothed signal  (window = config.smoothing_window)
      3. First difference Δx[t] = x[t] − x[t−1], with Δx[0] = 0 prepended
      4. Local z-score (window = config.zscore_window):
            z[t] = (x[t] − μ_w[t]) / (σ_w[t] + ε)
      5. Missingness mask: 1 where value is NaN or ±inf, else 0
         (included when config.include_missingness_mask is True)

    NaN/inf values are replaced with 0.0 before feature computation;
    their positions are recorded in the missingness mask channel.

    Sources:
      - Rolling mean: standard causal moving average (no external paper required)
      - Local z-score: Eq. defined internally; window-based mean/variance via
        Welford-equivalent cumsum trick (O'Connor & Kiefer, StatComp 2009 for
        the numerically stable formulation used here)
      - Missingness mask: standard time-series imputation convention

    Args:
        values: Raw signal as 1D list/array or 2D (C × T) array.
        config: Encoder config supplying smoothing_window, zscore_window,
                include_missingness_mask. Defaults to SegmentEncoderConfig().

    Returns:
        np.ndarray of shape (d', T) where d' = C * 4 or C * 5 (with mask).
    """
    encoder_config = config or SegmentEncoderConfig()
    series = normalize_series(values)  # (C, T)

    missingness = (~np.isfinite(series)).astype(np.float64)
    clean = np.where(np.isfinite(series), series, 0.0)

    smoothed = _rolling_mean(clean, encoder_config.smoothing_window)
    delta = np.diff(clean, axis=1, prepend=clean[:, :1])
    zscore = _local_zscore(clean, encoder_config.zscore_window)

    channels = [clean, smoothed, delta, zscore]
    if encoder_config.include_missingness_mask:
        channels.append(missingness)

    return np.vstack(channels)  # (d', T)


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

    # Build the augmented feature matrix (d' × T).
    feature_series = build_feature_matrix(series, encoder_config)  # (d', T)

    # Try the learned TCN encoder first (SEG-002).  Falls back silently to the
    # heuristic encoder if no checkpoint exists or torch is unavailable.
    try:
        from app.services.suggestion.tcn_encoder import load_tcn_encoder  # noqa: PLC0415

        tcn = load_tcn_encoder()
        if tcn is not None:
            embedding_array = tcn.encode(feature_series)
            return SegmentEmbedding(
                values=tuple(float(v) for v in embedding_array),
                length=int(series.shape[1]),
                channelCount=int(series.shape[0]),
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("TCN encoder failed (%s); using heuristic encoder.", exc)

    raw_channels = feature_series[: series.shape[0], :]  # (C, T) — raw with NaN→0
    standardized = _standardize_channels(_resample_channels(raw_channels, encoder_config.resample_length))
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


def _rolling_mean(series: np.ndarray, window: int) -> np.ndarray:
    """Causal rolling mean with variable-length left edge (same output size as input).

    Each output position t is the mean of the min(window, t+1) values ending at t.
    Uses cumsum trick for O(C·T) time.

    Args:
        series: Shape (C, T).
        window: Number of steps in the rolling window (>= 1).

    Returns:
        np.ndarray of shape (C, T).
    """
    _C, T = series.shape
    pad = np.zeros((series.shape[0], window - 1), dtype=np.float64)
    padded = np.concatenate([pad, series], axis=1)  # (C, window-1+T)
    # Exclusive-end cumsum: cumsum[c, j] = sum(padded[c, :j])
    cumsum = np.concatenate(
        [np.zeros((series.shape[0], 1), dtype=np.float64), np.cumsum(padded, axis=1)],
        axis=1,
    )  # (C, window+T)
    window_sums = cumsum[:, window:] - cumsum[:, :T]  # (C, T)
    counts = np.minimum(np.arange(1, T + 1, dtype=np.float64), float(window))
    return window_sums / counts


def _local_zscore(series: np.ndarray, window: int) -> np.ndarray:
    """Causal local z-score: z[t] = (x[t] − μ_w[t]) / (σ_w[t] + ε).

    Mean and variance are computed over a causal window of length min(window, t+1).
    Variance is derived from E[X²] − E[X]² for numerical efficiency.

    Source: rolling variance via cumsum; numerically stable form from
    O'Connor & Kiefer, StatComp 2009 (online variance formula principle).

    Args:
        series: Shape (C, T), must be finite (NaN/inf already replaced).
        window: Rolling window length (>= 1).

    Returns:
        np.ndarray of shape (C, T), near-zero where local_std is negligible.
    """
    local_mean = _rolling_mean(series, window)
    local_sq_mean = _rolling_mean(series**2, window)
    local_var = np.maximum(local_sq_mean - local_mean**2, 0.0)
    local_std = np.sqrt(local_var)
    return (series - local_mean) / np.where(local_std > 1e-8, local_std, 1.0)


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
