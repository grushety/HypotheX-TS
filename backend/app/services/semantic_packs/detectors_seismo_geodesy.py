"""Seismo-geodesy semantic-pack detectors (SEG-022).

Each detector matches a shape-primitive segment against a seismology /
geodesy domain label.  Detectors share the contract

    detector(X_seg, shape_label, context) -> (matched, confidence)

and *mutate* the ``context`` dict in place to add the metrics that the
matching ``context_predicate`` (defined in ``seismo_geodesy.yaml``) will
reference.

Wherever possible, detectors **delegate** to existing fitters
(``fit_etm`` from SEG-013, ``fit_gratsid`` from SEG-018) instead of
re-implementing parametric models.

References
----------
Allen, R. V. (1978).  Automatic earthquake recognition and timing from
    single traces.  *Bulletin of the Seismological Society of America*
    68(5):1521–1532.  → STA/LTA picker.
Savage, J. C. (1983).  A dislocation model of strain accumulation and
    release at a subduction zone.  *J. Geophysical Research* 88(B6):
    4984–4996.  → Interseismic linear loading.
Bevis, M. & Brown, S. (2014).  J. Geodesy 88:283–311.  → ETM.
Bedford, J. & Bevis, M. (2018).  J. Geophys. Res. Solid Earth 123.
    DOI 10.1029/2017JB014987.  → GrAtSiD transient features (SSE).
Hooper, A., Bekaert, D., Spaans, K., & Arıkan, M. (2012).  Recent
    advances in SAR interferometry time series analysis for measuring
    crustal deformation.  *Tectonophysics* 514:1–13.  → APS / phase
    closure / unwrapping.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from .core import register_detector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _windowed_mean_via_cumsum(values: np.ndarray, window: int) -> np.ndarray:
    """Right-aligned trailing mean over ``window`` samples (cumsum-based, O(n))."""
    n = len(values)
    if n == 0:
        return values.astype(np.float64, copy=True)
    w = max(1, int(window))
    cum = np.concatenate([[0.0], np.cumsum(values, dtype=np.float64)])
    out = np.zeros(n, dtype=np.float64)
    for i in range(n):
        start = max(0, i - w + 1)
        out[i] = (cum[i + 1] - cum[start]) / float(i - start + 1)
    return out


def sta_lta_ratio(
    arr: np.ndarray,
    window_sta_samples: int,
    window_lta_samples: int,
) -> np.ndarray:
    """STA / LTA energy ratio per Allen (1978).

    Uses squared-amplitude energy ``arr**2`` with right-aligned trailing
    windows; LTA gets a small floor to avoid division by zero before the
    long window has filled.
    """
    energy = np.asarray(arr, dtype=np.float64) ** 2
    sta = _windowed_mean_via_cumsum(energy, window_sta_samples)
    lta = _windowed_mean_via_cumsum(energy, window_lta_samples)
    return sta / np.maximum(lta, 1e-12)


def _sampling_rate(context: dict[str, Any], default_hz: float = 1.0) -> float:
    return float(context.get("sampling_rate_hz", default_hz))


def _samples_per_day(context: dict[str, Any]) -> float:
    return float(context.get("samples_per_day", 1.0))


def _ols_slope(arr: np.ndarray) -> float:
    n = len(arr)
    if n < 2:
        return 0.0
    t = np.arange(n, dtype=np.float64)
    t_mean = t.mean()
    a_mean = float(arr.mean())
    denom = float(((t - t_mean) ** 2).sum())
    if denom <= 0.0:
        return 0.0
    return float(((t - t_mean) * (arr - a_mean)).sum()) / denom


def _step_magnitude(arr: np.ndarray) -> float:
    """Estimate the step amplitude as the difference of pre / post means
    around the segment midpoint."""
    n = len(arr)
    if n < 4:
        return float(arr[-1] - arr[0])
    mid = n // 2
    pre = float(np.mean(arr[: max(2, mid // 2)]))
    post = float(np.mean(arr[mid + max(2, mid // 2):]) if mid + max(2, mid // 2) < n else np.mean(arr[mid:]))
    return post - pre


def _envelope(arr: np.ndarray) -> np.ndarray:
    """Analytic-signal envelope via Hilbert transform; falls back to
    absolute value when scipy is missing."""
    try:
        from scipy.signal import hilbert  # noqa: PLC0415
        return np.abs(hilbert(arr))
    except Exception:  # noqa: BLE001 — scipy is in requirements but be safe
        return np.abs(arr)


def _dominant_period_samples(arr: np.ndarray) -> float:
    """Dominant period of ``arr`` in samples via FFT power maximum (DC excluded)."""
    n = len(arr)
    if n < 4:
        return 0.0
    centred = arr - float(arr.mean())
    power = np.abs(np.fft.rfft(centred)) ** 2
    if len(power) <= 1:
        return 0.0
    power[0] = 0.0
    if power.max() <= 0.0:
        return 0.0
    k = int(np.argmax(power))
    if k == 0:
        return 0.0
    return float(n) / float(k)


def snap_to_2pi(
    magnitude: float, tolerance_in_pi: float = 0.1
) -> tuple[float, bool, int]:
    """Snap ``magnitude`` to the nearest integer multiple of 2π.

    Returns ``(snapped_value, is_within_tolerance, multiple_count)`` where
    ``is_within_tolerance`` is True iff ``|magnitude − snapped| <
    tolerance_in_pi · π``.  Used by the unwrapping-error detector.
    """
    k = int(round(magnitude / (2.0 * np.pi)))
    snapped = float(k) * 2.0 * np.pi
    return snapped, abs(magnitude - snapped) < tolerance_in_pi * np.pi, k


# ---------------------------------------------------------------------------
# Seismic-arrival detectors
# ---------------------------------------------------------------------------


@register_detector("sta_lta")
def detect_p_arrival(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """STA/LTA P-arrival picker (Allen 1978).

    Mutates ``context`` with ``sta_lta_ratio_max``, ``trigger_index``
    (sample at first threshold crossing, or ``-1``), and the resolved
    ``window_sta_samples`` / ``window_lta_samples`` / ``threshold``.
    """
    if shape_label != "step":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 8:
        return False, 0.0

    sr = _sampling_rate(context)
    w_sta = max(2, int(round(float(context.get("window_sta_seconds", 1.0)) * sr)))
    w_lta = max(w_sta + 1, int(round(float(context.get("window_lta_seconds", 10.0)) * sr)))
    threshold = float(context.get("threshold", 4.0))

    ratio = sta_lta_ratio(arr, w_sta, w_lta)
    trigger_idx = int(np.argmax(ratio >= threshold)) if (ratio >= threshold).any() else -1
    ratio_max = float(ratio.max()) if ratio.size else 0.0

    context["sta_lta_ratio_max"] = ratio_max
    context["trigger_index"] = trigger_idx
    context["window_sta_samples"] = w_sta
    context["window_lta_samples"] = w_lta
    context["threshold"] = threshold

    matched = trigger_idx >= 0
    confidence = float(min(1.0, max(0.0, (ratio_max - threshold) / max(threshold, 1e-12))))
    return matched, confidence


@register_detector("sta_lta_with_polarization")
def detect_s_arrival(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """STA/LTA + polarisation S-arrival picker.

    For univariate input falls back to a relaxed-threshold STA/LTA pick
    (polarisation requires multi-component data which the segment
    encoder does not yet expose).  Mutates ``context`` with
    ``polarization_score`` (``None`` when single-component).
    """
    if shape_label != "step":
        return False, 0.0
    relaxed_ctx = dict(context)
    relaxed_ctx.setdefault("threshold", float(context.get("threshold", 3.0)))
    matched, confidence = detect_p_arrival(X_seg, shape_label, relaxed_ctx)
    # Forward STA/LTA outputs to caller's context.
    for k in (
        "sta_lta_ratio_max", "trigger_index",
        "window_sta_samples", "window_lta_samples", "threshold",
    ):
        if k in relaxed_ctx:
            context[k] = relaxed_ctx[k]
    context["polarization_score"] = None
    return matched, confidence


@register_detector("post_S_envelope_fit")
def detect_coda(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Coda detector: exponentially decaying envelope after S arrival.

    Fits ``log|env| ≈ a − t/τ`` over the segment via OLS.  A negative
    slope below ``-1/min_tau_samples`` qualifies.  Mutates ``context``
    with ``coda_tau_samples``, ``envelope_quality`` (R²-like in [0,1]).
    """
    if shape_label != "transient":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 8:
        return False, 0.0

    env = _envelope(arr)
    env_floor = float(np.median(np.abs(env)) * 1e-3) + 1e-12
    log_env = np.log(np.maximum(env, env_floor))
    t = np.arange(arr.size, dtype=np.float64)

    slope = _ols_slope(log_env)
    if slope >= 0.0:
        context["coda_tau_samples"] = float("inf")
        context["envelope_quality"] = 0.0
        return False, 0.0
    tau_samples = -1.0 / slope

    # Quality = 1 − residual variance / total variance after the OLS fit.
    intercept = float(np.mean(log_env)) - slope * float(np.mean(t))
    fitted = slope * t + intercept
    ss_res = float(np.sum((log_env - fitted) ** 2))
    ss_tot = float(np.sum((log_env - float(log_env.mean())) ** 2))
    quality = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 0.0
    quality = max(0.0, min(1.0, quality))

    context["coda_tau_samples"] = float(tau_samples)
    context["envelope_quality"] = float(quality)

    matched = tau_samples > 1.0
    return matched, float(quality)


@register_detector("dispersive_wave_detection")
def detect_surface_waves(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Surface-wave detector: dispersion ⇒ dominant frequency drifts in time.

    Splits the segment in half and compares the dominant period of each
    half; a non-trivial drift is the dispersion signature.  Mutates
    ``context`` with ``period_first_half``, ``period_second_half``,
    ``frequency_drift``.
    """
    if shape_label != "cycle":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 16:
        return False, 0.0

    mid = arr.size // 2
    p_first = _dominant_period_samples(arr[:mid])
    p_second = _dominant_period_samples(arr[mid:])
    drift = abs(p_first - p_second)

    context["period_first_half"] = p_first
    context["period_second_half"] = p_second
    context["frequency_drift"] = drift

    matched = drift > 1.0  # at least one-sample period change
    confidence = float(min(1.0, drift / max(p_first + p_second + 1e-12, 1.0)))
    return matched, confidence


@register_detector("envelope_correlation_plus_lfe")
def detect_tremor(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Tremor detector: sustained low-frequency envelope amplitude in noise.

    Computes the envelope, low-pass-equivalent amplitude (mean of the
    envelope smoothed over ``samples_per_minute`` samples), and the
    sustained duration.  Mutates ``context`` with
    ``low_frequency_amplitude``, ``sustained_minutes``, ``threshold``,
    ``sustained_threshold``.
    """
    if shape_label != "noise":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 16:
        return False, 0.0

    sr = _sampling_rate(context)
    samples_per_minute = max(1.0, 60.0 * sr)
    env = _envelope(arr)
    smoothed = _windowed_mean_via_cumsum(env, int(round(samples_per_minute)))
    lf_amp = float(np.mean(smoothed))
    sustained_minutes = float(arr.size) / samples_per_minute

    threshold = float(context.get("threshold", float(np.std(arr)) * 1.5))
    sustained_threshold = float(context.get("sustained_threshold", 1.0))

    context["low_frequency_amplitude"] = lf_amp
    context["sustained_minutes"] = sustained_minutes
    context["threshold"] = threshold
    context["sustained_threshold"] = sustained_threshold

    matched = lf_amp > threshold
    confidence = float(min(1.0, max(0.0, lf_amp / max(threshold, 1e-12) - 1.0)))
    return matched, confidence


# ---------------------------------------------------------------------------
# Geodesy (GNSS / InSAR) detectors — delegate to ETM / GrAtSiD
# ---------------------------------------------------------------------------


@register_detector("etm_step_from_known_origin")
def detect_coseismic_offset(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Coseismic-offset detector: requires a caller-supplied earthquake
    origin time and fits an ETM step at that epoch (Bevis & Brown 2014).

    Mutates ``context`` with ``step_magnitude``, ``origin_time_known``,
    ``detection_threshold``.
    """
    if shape_label != "step":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 4:
        return False, 0.0

    origin_time = context.get("origin_time")
    detection_threshold = float(context.get("detection_threshold", 0.0))

    if origin_time is None:
        magnitude = _step_magnitude(arr)
        origin_known = False
    else:
        try:
            from app.services.decomposition.fitters.etm import (  # noqa: PLC0415
                fit_etm,
            )
            blob = fit_etm(arr, known_steps=[float(origin_time)])
            mag_key = next(
                (k for k in blob.coefficients if k.startswith("step_at_")),
                None,
            )
            magnitude = (
                float(blob.coefficients[mag_key]) if mag_key is not None
                else _step_magnitude(arr)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("etm_step_from_known_origin: ETM fit failed (%s)", exc)
            magnitude = _step_magnitude(arr)
        origin_known = True

    context["step_magnitude"] = float(magnitude)
    context["origin_time_known"] = bool(origin_known)
    context["detection_threshold"] = detection_threshold

    matched = origin_known and abs(magnitude) > detection_threshold
    confidence = float(min(1.0, abs(magnitude) / max(detection_threshold + 1e-12, 1e-12)))
    return matched, confidence


@register_detector("fit_log_or_exp")
def detect_postseismic_relaxation(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Postseismic-relaxation detector: fits log and exp transient bases
    against the segment via ETM and selects the smaller-residual one.

    Mutates ``context`` with ``basis_type`` (``'log'`` | ``'exp'`` | ``''``),
    ``tau_days``, ``follows_coseismic_offset`` (caller-supplied bool,
    default ``False``).
    """
    if shape_label != "transient":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 8:
        return False, 0.0

    spd = _samples_per_day(context)
    tau_range = list(context.get("tau_range_days", [1.0, 1000.0]))
    tau_days = max(tau_range[0], min(tau_range[1], float(arr.size) / spd / 4.0))
    tau_samples = max(1.0, tau_days * spd)
    t_ref = 0.0

    try:
        from app.services.decomposition.fitters.etm import fit_etm  # noqa: PLC0415
        blob_log = fit_etm(arr, known_transients=[(t_ref, tau_samples, "log")])
        blob_exp = fit_etm(arr, known_transients=[(t_ref, tau_samples, "exp")])
        rmse_log = float(blob_log.fit_metadata.get("rmse", float("inf")))
        rmse_exp = float(blob_exp.fit_metadata.get("rmse", float("inf")))
    except Exception as exc:  # noqa: BLE001
        logger.warning("fit_log_or_exp: ETM unavailable (%s)", exc)
        rmse_log = rmse_exp = float("inf")

    if not (np.isfinite(rmse_log) or np.isfinite(rmse_exp)):
        context["basis_type"] = ""
        context["tau_days"] = tau_days
        context.setdefault("follows_coseismic_offset", False)
        return False, 0.0

    basis = "log" if rmse_log <= rmse_exp else "exp"
    rmse_chosen = rmse_log if basis == "log" else rmse_exp
    rmse_other = rmse_exp if basis == "log" else rmse_log
    confidence = (
        float(min(1.0, max(0.0, 1.0 - rmse_chosen / max(rmse_other, 1e-12))))
        if np.isfinite(rmse_other) else 0.5
    )

    context["basis_type"] = basis
    context["tau_days"] = float(tau_days)
    context.setdefault("follows_coseismic_offset", False)

    return True, float(confidence)


@register_detector("etm_linear_rate_ex_steps_ex_transients")
def detect_interseismic_loading(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Interseismic-loading detector: a near-linear trend that explicitly
    excludes any coseismic step or postseismic transient (Savage 1983).

    The shape filter (``trend``) already screens out steps and transients;
    this detector confirms the OLS slope is non-trivial and forwards the
    caller-supplied exclusion flags.
    """
    if shape_label != "trend":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 4:
        return False, 0.0

    slope = _ols_slope(arr)
    context["linear_rate"] = float(slope)
    context.setdefault("excludes_coseismic_offset", True)
    context.setdefault("excludes_postseismic_relaxation", True)

    std = float(np.std(arr))
    matched = abs(slope) > 0.0
    confidence = float(min(1.0, abs(slope) / max(std + 1e-12, 1e-12)))
    return matched, confidence


@register_detector("gratsid_bump")
def detect_sse(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Slow-slip-event (SSE) detector: a sustained transient bump with
    smooth onset and decay (Bedford & Bevis 2018).

    Mutates ``context`` with ``duration_days``, ``smooth_onset``,
    ``smooth_decay``, ``min_duration_days``, ``max_duration_days``.
    """
    if shape_label != "transient":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 8:
        return False, 0.0

    spd = _samples_per_day(context)
    duration_days = float(arr.size) / spd

    third = max(1, arr.size // 3)
    onset_slope = _ols_slope(arr[:third])
    decay_slope = _ols_slope(arr[-third:])
    onset_std = float(np.std(np.diff(arr[:third])))
    decay_std = float(np.std(np.diff(arr[-third:])))
    onset_jitter = onset_std / (abs(onset_slope) + 1e-9)
    decay_jitter = decay_std / (abs(decay_slope) + 1e-9)

    smooth_onset = onset_jitter < 5.0
    smooth_decay = decay_jitter < 5.0

    min_d = float(context.get("min_duration_days", 7.0))
    max_d = float(context.get("max_duration_days", 365.0))

    context["duration_days"] = duration_days
    context["smooth_onset"] = bool(smooth_onset)
    context["smooth_decay"] = bool(smooth_decay)
    context["min_duration_days"] = min_d
    context["max_duration_days"] = max_d

    matched = smooth_onset and smooth_decay
    confidence = float(0.5 + 0.5 * (smooth_onset + smooth_decay) / 2.0)
    return matched, confidence


@register_detector("etm_harmonics")
def detect_seasonal_signal(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Seasonal-signal detector: dominant FFT period sits at the annual
    (~365 d) or semi-annual (~182 d) band (geodesy convention).

    Mutates ``context`` with ``dominant_period_days``, ``is_annual``,
    ``is_semiannual``.
    """
    if shape_label != "cycle":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 8:
        return False, 0.0

    spd = _samples_per_day(context)
    period_samples = _dominant_period_samples(arr)
    period_days = period_samples / spd if period_samples > 0.0 else 0.0

    annual_tol = 30.0
    is_annual = abs(period_days - 365.25) <= annual_tol
    is_semiannual = abs(period_days - 182.625) <= annual_tol / 2.0

    context["dominant_period_days"] = period_days
    context["is_annual"] = bool(is_annual)
    context["is_semiannual"] = bool(is_semiannual)

    matched = is_annual or is_semiannual
    confidence = 1.0 if is_annual else (0.8 if is_semiannual else 0.0)
    return matched, float(confidence)


@register_detector("common_mode_pca")
def detect_common_mode(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Common-mode-error detector: needs a multi-station residual matrix
    in ``context['station_residuals']`` of shape ``(n_stations, n_samples)``.
    Single-station input is reported as ``not_applicable=True``.

    Computes the leading PCA component's variance fraction; if the first
    component explains > 50 % of the joint variance, the segment is
    flagged as spatially correlated (Hooper 2012).

    Mutates ``context`` with ``is_spatially_correlated``,
    ``not_applicable``, ``leading_eigenvalue_fraction``.
    """
    if shape_label != "noise":
        return False, 0.0
    station_data = context.get("station_residuals")
    if station_data is None:
        context["not_applicable"] = True
        context["is_spatially_correlated"] = False
        context["leading_eigenvalue_fraction"] = 0.0
        return False, 0.0

    matrix = np.asarray(station_data, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] < 2:
        context["not_applicable"] = True
        context["is_spatially_correlated"] = False
        context["leading_eigenvalue_fraction"] = 0.0
        return False, 0.0

    centred = matrix - matrix.mean(axis=1, keepdims=True)
    cov = (centred @ centred.T) / max(matrix.shape[1] - 1, 1)
    eigvals = np.linalg.eigvalsh(cov)
    eigvals = np.maximum(eigvals[::-1], 0.0)  # descending, non-negative
    total = float(np.sum(eigvals))
    leading_frac = float(eigvals[0] / total) if total > 0.0 else 0.0

    context["not_applicable"] = False
    context["is_spatially_correlated"] = leading_frac > 0.5
    context["leading_eigenvalue_fraction"] = leading_frac

    matched = leading_frac > 0.5
    return matched, leading_frac


@register_detector("gacos_or_pyaps_correction_residual")
def detect_tropospheric_delay(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Tropospheric-delay detector: low-frequency power dominance in the
    residual spectrum (Hooper 2012 §3).

    For MVP we treat "atmospheric" as "the low-frequency band carries
    > 60 % of the total spectral power".  Mutates ``context`` with
    ``low_frequency_power_fraction``, ``is_spatial_atmospheric_pattern``.
    """
    if shape_label != "noise":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 8:
        return False, 0.0

    centred = arr - float(arr.mean())
    power = np.abs(np.fft.rfft(centred)) ** 2
    if power.size <= 1:
        return False, 0.0
    power[0] = 0.0
    total = float(power.sum())
    if total <= 0.0:
        return False, 0.0
    cutoff = max(1, power.size // 8)  # lowest 1/8 of the spectrum
    lf_frac = float(power[: cutoff + 1].sum() / total)

    context["low_frequency_power_fraction"] = lf_frac
    context["is_spatial_atmospheric_pattern"] = lf_frac > 0.6

    matched = lf_frac > 0.6
    return matched, lf_frac


@register_detector("phase_jump_2pi_detector")
def detect_unwrapping_error(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Unwrapping-error detector: a step whose magnitude is within
    ``0.1 · π`` of an integer multiple of ``2π``.

    Mutates ``context`` with ``step_magnitude``, ``is_2pi_multiple``,
    ``snap_2pi_multiple_count``, ``snapped_magnitude``.
    """
    if shape_label != "step":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 4:
        return False, 0.0

    magnitude = _step_magnitude(arr)
    snapped, within_tol, k = snap_to_2pi(magnitude, tolerance_in_pi=0.1)

    context["step_magnitude"] = float(magnitude)
    context["is_2pi_multiple"] = bool(within_tol and k != 0)
    context["snap_2pi_multiple_count"] = int(k)
    context["snapped_magnitude"] = float(snapped)

    matched = within_tol and k != 0
    confidence = (
        1.0 - abs(magnitude - snapped) / (0.1 * np.pi)
        if within_tol else 0.0
    )
    return matched, float(max(0.0, min(1.0, confidence)))


@register_detector("metadata_driven_step")
def detect_antenna_offset(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Antenna-offset detector: looks up a maintenance-log entry covering
    this segment's timestamp range.  The caller is expected to supply
    ``maintenance_log`` (iterable of timestamps in the same units as
    ``segment_start_time`` / ``segment_end_time``) in ``context``.

    Mutates ``context`` with ``has_maintenance_log_entry`` and
    ``maintenance_log_match`` (the matching entry, if any).
    """
    if shape_label != "step":
        return False, 0.0
    log_entries = context.get("maintenance_log") or []
    start = context.get("segment_start_time")
    end = context.get("segment_end_time")

    match = None
    if start is not None and end is not None:
        for entry in log_entries:
            try:
                ts = float(entry)
            except (TypeError, ValueError):
                continue
            if float(start) <= ts <= float(end):
                match = ts
                break

    context["has_maintenance_log_entry"] = match is not None
    context["maintenance_log_match"] = match

    matched = match is not None
    return matched, 1.0 if matched else 0.0
