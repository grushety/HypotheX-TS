"""Rule-based shape classifier for cold-start segment labeling (SEG-008).

Classifies a time-series segment into one of 7 shape primitives:
  plateau, trend, step, spike, cycle, transient, noise

Algorithm sources:
- Theil-Sen slope / sign consistency: Theil (1950), Sen (1968).
- Spectral peak via FFT + autocorrelation:
    Cleveland et al. (1990) "STL: A Seasonal-Trend Decomposition Procedure",
    J. Official Statistics 6(1):3-73.
- Catch22 features: Lubba, Sethi, Knaute, Schultz, Fulcher, Jones (2019)
    "Catch22: CAnonical Time-series CHaracteristics",
    Data Min. Knowl. Discov. 33:1821-1852. Library: pycatch22.
- Change-point / transition detection:
    Truong, Oudre, Vayatis (2020) "Selective review of offline change-point
    detection methods", Signal Processing 167:107299.
"""

from __future__ import annotations

import logging
import math
import pathlib
from dataclasses import dataclass
from typing import Sequence

import numpy as np

logger = logging.getLogger(__name__)

_YAML_PATH = pathlib.Path(__file__).parent / "shape_thresholds.yaml"

_SHAPE_LABELS: tuple[str, ...] = (
    "plateau", "trend", "step", "spike", "cycle", "transient", "noise"
)

# Fallback defaults mirror shape_thresholds.yaml exactly.
_DEFAULT_THRESHOLDS: dict[str, float] = {
    # slope_rel = slope * (n-1) / arr_range; in [0,1] for pure trend
    "slope": 0.5,
    "var": 0.02,
    "per": 0.55,
    "peak": 2.5,
    "step": 0.4,
    "ctx": 0.35,
    "sign": 0.65,
    "lin": 0.12,
    # trans = fraction of segment in the "transition band" (near the centre)
    "trans": 0.3,
    "spike_max_len": 20.0,
    # margin: top-2 gate gap below this → uncertain flag set (Platt 1999)
    "uncertainty_delta": 0.15,
}


@dataclass(frozen=True)
class ShapeLabel:
    """Output of RuleBasedShapeClassifier.classify_shape.

    Attributes:
        label:            Argmax shape class from the 7-primitive vocabulary.
        confidence:       Softmax probability of the argmax class, in [0, 1].
        per_class_scores: Raw gate scores before softmax, keyed by shape name.
        uncertain:        True when top-2 gate gap < uncertainty_delta (Platt 1999).
    """

    label: str
    confidence: float
    per_class_scores: dict[str, float]
    uncertain: bool = False


def uncertainty_margin(scores: dict, delta: float = 0.15) -> bool:
    """Return True when the top-2 gate score gap is below delta.

    A small gap means two classes are nearly tied — the classifier is uncertain.
    Ref: Platt (1999) "Probabilistic outputs for SVMs", p. 61-74;
         Niculescu-Mizil & Caruana (2005) ICML — margin-based confidence.
    """
    sorted_q = sorted(scores.values(), reverse=True)
    if len(sorted_q) < 2:
        return False
    return (sorted_q[0] - sorted_q[1]) < delta


class RuleBasedShapeClassifier:
    """Deterministic rule-based shape classifier over 7 shape primitives.

    Thresholds are loaded from ``shape_thresholds.yaml`` on init; falls back
    to hardcoded defaults if the file is absent or malformed.

    Usage::

        clf = RuleBasedShapeClassifier()
        result = clf.classify_shape(X_seg, ctx_pre, ctx_post)
        print(result.label, result.confidence)
    """

    def __init__(self, thresholds_path: str | pathlib.Path | None = None) -> None:
        path = pathlib.Path(thresholds_path) if thresholds_path else _YAML_PATH
        self._thresholds = _load_thresholds(path)
        self._uncertainty_delta = float(self._thresholds.get("uncertainty_delta", 0.15))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify_shape(
        self,
        X_seg: Sequence[float] | np.ndarray,
        ctx_pre: Sequence[float] | np.ndarray | None = None,
        ctx_post: Sequence[float] | np.ndarray | None = None,
    ) -> ShapeLabel:
        """Classify the shape of a time-series segment.

        Args:
            X_seg:    1-D array of segment values (the segment itself).
            ctx_pre:  Context window immediately before the segment (may be empty).
            ctx_post: Context window immediately after the segment (may be empty).

        Returns:
            ShapeLabel with argmax label, softmax confidence, and raw gate scores.
            Returns ``ShapeLabel("noise", 1.0, ...)`` for segments shorter than 3.
        """
        arr = np.asarray(X_seg, dtype=np.float64).ravel()
        pre = np.asarray(ctx_pre, dtype=np.float64).ravel() if ctx_pre is not None else np.array([])
        post = np.asarray(ctx_post, dtype=np.float64).ravel() if ctx_post is not None else np.array([])

        if len(arr) < 3:
            scores = {label: 0.0 for label in _SHAPE_LABELS}
            scores["noise"] = 1.0
            return ShapeLabel(label="noise", confidence=1.0, per_class_scores=scores)

        tau = self._thresholds
        slope, sign_cons = _theil_sen(arr)
        arr_range = float(arr.max() - arr.min())
        # slope_rel: normalised slope ∈ ~[0, 1] for a pure trend regardless of scale
        slope_rel = slope * (len(arr) - 1) / (arr_range + 1e-8)
        var = float(np.var(arr))
        residual_lin = _residual_to_line(arr, slope)
        fft_peak, acf_peak = _spectral_peaks(arr)
        z_max, peak_w = _peak_score(arr, pre, post)
        step_mag = _step_magnitude(arr, pre, post)
        c22 = _catch22_features(arr)
        transition_frac = _transition_time(arr)
        context_con = _context_contrast(arr, pre, post)

        q: dict[str, float] = {
            "plateau":   _plateau_gate(slope_rel, var, acf_peak, tau),
            "trend":     _trend_gate(slope_rel, sign_cons, residual_lin, tau),
            "step":      _step_gate(step_mag, transition_frac, tau),
            "spike":     _spike_gate(len(arr), z_max, context_con, tau),
            "cycle":     _cycle_gate(arr, acf_peak, tau),
            "transient": _transient_gate(arr, c22),
            "noise":     _noise_gate(c22),
        }

        scores = _softmax(list(q.values()))
        label = max(q, key=q.__getitem__)
        conf = scores[list(q.keys()).index(label)]
        return ShapeLabel(
            label=label,
            confidence=float(conf),
            per_class_scores=dict(q),
            uncertain=uncertainty_margin(q, self._uncertainty_delta),
        )


# ---------------------------------------------------------------------------
# Per-class gate functions (unit-testable helpers)
# ---------------------------------------------------------------------------


def _plateau_gate(
    slope: float,
    var: float,
    acf_peak: float,
    tau: dict[str, float],
) -> float:
    """Gate score for 'plateau': flat, low-variance, non-periodic.

    Combines: |slope| below threshold, variance low, no strong periodicity.
    Returns value in [0, 1].
    """
    slope_ok = _sigmoid_below(abs(slope), tau["slope"], k=20.0)
    var_ok = _sigmoid_below(var, tau["var"], k=30.0)
    no_cycle = 1.0 - _sigmoid_above(acf_peak, tau["per"], k=10.0)
    return slope_ok * var_ok * no_cycle


def _trend_gate(
    slope: float,
    sign_cons: float,
    residual_lin: float,
    tau: dict[str, float],
) -> float:
    """Gate score for 'trend': significant monotone slope, low residual.

    Theil-Sen slope magnitude above threshold, sign consistency high, residual
    to best-fit line low.  Ref: Sen (1968) eq. for slope estimator.
    Returns value in [0, 1].
    """
    slope_ok = _sigmoid_above(abs(slope), tau["slope"], k=20.0)
    sign_ok = _sigmoid_above(sign_cons, tau["sign"], k=15.0)
    lin_ok = _sigmoid_below(residual_lin, tau["lin"], k=20.0)
    return slope_ok * sign_ok * lin_ok


def _step_gate(
    step_mag: float,
    transition_frac: float,
    tau: dict[str, float],
) -> float:
    """Gate score for 'step': large mean shift, fast transition.

    Mean(post) - Mean(pre) large; transition completes quickly relative to
    segment length.  Ref: Truong et al. (2020) change-point magnitude.
    Returns value in [0, 1].
    """
    mag_ok = _sigmoid_above(abs(step_mag), tau["step"], k=10.0)
    fast_ok = _sigmoid_below(transition_frac, tau["trans"], k=15.0)
    return mag_ok * fast_ok


def _spike_gate(
    seg_len: int,
    z_max: float,
    context_con: float,
    tau: dict[str, float],
) -> float:
    """Gate score for 'spike': short, high z-score, strong context contrast.

    Segment length bounded, peak z-score above threshold, values return to
    context baseline.
    Returns value in [0, 1].
    """
    len_ok = _sigmoid_below(float(seg_len), tau["spike_max_len"], k=0.5)
    peak_ok = _sigmoid_above(z_max, tau["peak"], k=2.0)
    ctx_ok = _sigmoid_above(context_con, tau["ctx"], k=10.0)
    return len_ok * peak_ok * ctx_ok


def _cycle_gate(
    arr: np.ndarray,
    acf_peak: float,
    tau: dict[str, float],
) -> float:
    """Gate score for 'cycle': strong ACF peak, segment contains >= 2 periods.

    Ref: Cleveland et al. (1990) STL — periodicity as autocorrelation peak.
    Returns value in [0, 1].
    """
    acf_ok = _sigmoid_above(acf_peak, tau["per"], k=10.0)
    period_est = _estimated_period(arr)
    if period_est > 0 and len(arr) >= 2 * period_est:
        length_ok = 1.0
    elif period_est > 0:
        length_ok = float(len(arr)) / (2.0 * period_est)
        length_ok = max(0.0, min(1.0, length_ok))
    else:
        length_ok = 0.0
    return acf_ok * length_ok


def _transient_gate(
    arr: np.ndarray,
    c22: dict[str, float],
) -> float:
    """Gate score for 'transient': exponential bump shape (rises then decays).

    Uses SB_MotifThree_quantile_hh from Catch22 as a proxy for structured
    non-periodicity combined with a bump-fit residual.
    Ref: Lubba et al. (2019) Catch22 feature SB_MotifThree_quantile_hh.
    Returns value in [0, 1].
    """
    bump = _exp_bump_score(arr)
    motif = float(c22.get("SB_MotifThree_quantile_hh", 0.0))
    motif_norm = min(1.0, abs(motif) / 5.0)
    return bump * (0.5 + 0.5 * motif_norm)


def _noise_gate(c22: dict[str, float]) -> float:
    """Gate score for 'noise': near-white-noise, no structure.

    Uses CO_f1ecac (first autocorrelation crossing) and DN_HistogramMode_5.
    High CO_f1ecac lag → more structure (less noise).
    Low DN_HistogramMode_5 → uniform histogram → more noise.
    Ref: Lubba et al. (2019) Catch22.
    Returns value in [0, 1].
    """
    f1ecac = float(c22.get("CO_f1ecac", 0.0))
    hist_mode = float(c22.get("DN_HistogramMode_5", 0.0))
    # f1ecac is a lag index [0, 1] (normalised): low = fast decorrelation = noise
    no_autocorr = 1.0 - min(1.0, max(0.0, f1ecac))
    # DN_HistogramMode_5 near 0 means uniform (noisy), large means modal (structured)
    low_modality = 1.0 - min(1.0, abs(hist_mode) / 3.0)
    return no_autocorr * low_modality


# ---------------------------------------------------------------------------
# Feature helpers
# ---------------------------------------------------------------------------


def _theil_sen(arr: np.ndarray) -> tuple[float, float]:
    """Theil-Sen slope estimate and sign consistency.

    Slope: median of pairwise slopes (i,j), i<j.
    Sign consistency: fraction of consecutive differences with the majority sign.

    For large arrays uses a random subsample (max 200 pairs) for O(n) speed.
    Returns (slope, sign_consistency) both as floats.
    """
    n = len(arr)
    if n < 2:
        return 0.0, 0.0

    # Compute pairwise slopes with subsampling for large arrays.
    rng = np.random.default_rng(seed=0)  # deterministic seed
    if n <= 20:
        i_idx, j_idx = np.triu_indices(n, k=1)
    else:
        n_pairs = min(200, n * (n - 1) // 2)
        i_idx = rng.integers(0, n, n_pairs)
        j_idx = rng.integers(0, n, n_pairs)
        mask = i_idx != j_idx
        i_idx, j_idx = i_idx[mask], j_idx[mask]

    dx = j_idx.astype(float) - i_idx.astype(float)
    dy = arr[j_idx] - arr[i_idx]
    valid = dx != 0
    slopes = dy[valid] / dx[valid]
    slope = float(np.median(slopes)) if len(slopes) else 0.0

    diffs = np.diff(arr)
    if len(diffs) == 0:
        return slope, 0.0
    pos = np.sum(diffs > 0)
    neg = np.sum(diffs < 0)
    majority = max(pos, neg)
    sign_cons = float(majority) / float(len(diffs))
    return slope, sign_cons


def _residual_to_line(arr: np.ndarray, slope: float | None = None) -> float:
    """Mean absolute residual after subtracting a best-fit line, normalised by std.

    Returns 0 for constant series.
    """
    n = len(arr)
    if n < 2:
        return 0.0
    xs = np.arange(n, dtype=np.float64)
    fit = np.polyfit(xs, arr, 1)
    fitted = np.polyval(fit, xs)
    residuals = arr - fitted
    std = float(np.std(arr))
    if std < 1e-8:
        return 0.0
    return float(np.mean(np.abs(residuals))) / std


def _spectral_peaks(arr: np.ndarray) -> tuple[float, float]:
    """Dominant FFT power fraction and normalised ACF peak.

    FFT peak: fraction of total power in the dominant non-DC frequency bin.
    ACF peak: max autocorrelation at lags 1..n//2 (normalised to [0,1]).

    Ref: Cleveland et al. (1990) STL — periodicity via spectral analysis.
    Returns (fft_peak, acf_peak) in [0, 1].
    """
    from scipy.fft import rfft  # noqa: PLC0415

    n = len(arr)
    if n < 4:
        return 0.0, 0.0

    arr_centered = arr - float(np.mean(arr))
    spectrum = np.abs(rfft(arr_centered)) ** 2
    if spectrum.sum() < 1e-10:
        return 0.0, 0.0
    fft_peak = float(np.max(spectrum[1:])) / float(spectrum[1:].sum() + 1e-10)
    fft_peak = min(1.0, fft_peak)

    # Autocorrelation via FFT (unbiased, max lag = n//2).
    max_lag = max(1, n // 2)
    acf_full = np.correlate(arr_centered, arr_centered, mode="full")
    mid = len(acf_full) // 2
    acf = acf_full[mid + 1: mid + 1 + max_lag]
    denom = float(acf_full[mid])
    if denom < 1e-10:
        return fft_peak, 0.0
    acf_norm = acf / denom
    acf_peak = float(np.max(acf_norm)) if len(acf_norm) else 0.0
    acf_peak = max(0.0, min(1.0, acf_peak))
    return fft_peak, acf_peak


def _estimated_period(arr: np.ndarray) -> float:
    """Estimate dominant period via FFT (returns 0 if no clear peak)."""
    from scipy.fft import rfft, rfftfreq  # noqa: PLC0415

    n = len(arr)
    if n < 4:
        return 0.0
    arr_c = arr - float(np.mean(arr))
    spectrum = np.abs(rfft(arr_c))
    freqs = rfftfreq(n)
    if len(freqs) <= 1 or spectrum[1:].max() < 1e-8:
        return 0.0
    peak_idx = int(np.argmax(spectrum[1:])) + 1
    freq = float(freqs[peak_idx])
    if freq < 1e-8:
        return 0.0
    return 1.0 / freq


def _peak_score(
    arr: np.ndarray,
    pre: np.ndarray,
    post: np.ndarray,
) -> tuple[float, float]:
    """Max z-score in segment and peak width (fraction of segment length).

    Reference level: context mean when available (more accurate for spikes
    that are short relative to their context), otherwise segment median.

    Returns (z_max, peak_width_fraction) with z_max in [0, inf), width in [0, 1].
    """
    std = float(np.std(arr))
    if std < 1e-8:
        return 0.0, 0.0

    ctx = np.concatenate([pre, post]) if len(pre) + len(post) > 0 else np.array([])
    ref = float(np.mean(ctx)) if len(ctx) > 0 else float(np.median(arr))

    z_max = float(np.max(np.abs(arr - ref))) / std

    threshold = ref + std
    above = int(np.sum(arr > threshold))
    peak_w = above / len(arr)
    return z_max, peak_w


def _step_magnitude(
    arr: np.ndarray,
    pre: np.ndarray,
    post: np.ndarray,
) -> float:
    """Step magnitude: mean(post_context) - mean(pre_context).

    If context windows are empty, uses segment halves as surrogates.
    """
    if len(pre) > 0 and len(post) > 0:
        return float(np.mean(post)) - float(np.mean(pre))
    mid = len(arr) // 2
    if mid < 1 or mid >= len(arr) - 1:
        return 0.0
    return float(np.mean(arr[mid:])) - float(np.mean(arr[:mid]))


def _transition_time(arr: np.ndarray) -> float:
    """Fraction of within-half variance relative to total variance.

    A sharp two-level step has near-zero within-half variance → ratio ≈ 0.
    A gradual ramp or noisy signal has high within-half variance → ratio near 1.

    Used to distinguish instantaneous steps from gradual transitions.
    Ref: Truong et al. (2020) change-point sharpness (CUSUM variance ratio).
    """
    n = len(arr)
    if n < 4:
        return 1.0
    total_var = float(np.var(arr))
    if total_var < 1e-8:
        return 0.0
    mid = n // 2
    within_var = (float(np.var(arr[:mid])) + float(np.var(arr[mid:]))) / 2.0
    return min(1.0, within_var / total_var)


def _context_contrast(
    arr: np.ndarray,
    pre: np.ndarray,
    post: np.ndarray,
) -> float:
    """Contrast between segment peak and surrounding context mean.

    Returns ratio in [0, inf); clipped to [0, 1] via gate sigmoid.
    """
    if len(pre) == 0 and len(post) == 0:
        return 0.0
    ctx_vals = []
    if len(pre) > 0:
        ctx_vals.extend(pre.tolist())
    if len(post) > 0:
        ctx_vals.extend(post.tolist())
    ctx_mean = float(np.mean(ctx_vals))
    ctx_std = float(np.std(ctx_vals)) if len(ctx_vals) > 1 else 1.0
    if ctx_std < 1e-8:
        ctx_std = 1.0
    peak_val = float(np.max(np.abs(arr - ctx_mean)))
    return peak_val / ctx_std


def _catch22_features(arr: np.ndarray) -> dict[str, float]:
    """Compute selected Catch22 features; returns 0.0 on failure.

    Features used in current gates:
      DN_HistogramMode_5, SB_MotifThree_quantile_hh, CO_f1ecac.
    Rest of the 22 are computed and available for future ablation.

    Ref: Lubba et al. (2019) Catch22.
    """
    try:
        import pycatch22  # noqa: PLC0415
    except ImportError:
        logger.warning("pycatch22 not installed; catch22 features will be zero.")
        return {}

    try:
        result = pycatch22.catch22_all(arr.tolist(), catch24=False)
        return {name: float(val) if (val is not None and not math.isnan(float(val))) else 0.0
                for name, val in zip(result["names"], result["values"], strict=True)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("catch22 computation failed: %s", exc)
        return {}


def _exp_bump_score(arr: np.ndarray) -> float:
    """Score how well the segment fits a bump (rise then decay to baseline).

    Requires: peak is in the middle half, signal rises before the peak, and
    *falls back toward baseline* after it (end value < 50% of peak height).
    A step function fails the last criterion (stays high after the "peak").

    Normalised: 1.0 = perfect symmetric bump, 0.0 = no bump structure.
    """
    n = len(arr)
    if n < 4:
        return 0.0
    baseline = float(arr[0] + arr[-1]) / 2.0
    arr_centered = arr - baseline
    peak_signed = float(arr_centered.max()) if abs(float(arr_centered.max())) >= abs(float(arr_centered.min())) else float(arr_centered.min())
    if abs(peak_signed) < 1e-8:
        return 0.0
    arr_norm = arr_centered / abs(peak_signed)
    peak_idx = int(np.argmax(np.abs(arr_norm)))
    # Bump: peak must be in the inner half (not too close to edges)
    if peak_idx < n // 4 or peak_idx > 3 * n // 4:
        return 0.0
    # Signal must return toward baseline: end value < 50% of peak height
    end_val = float(arr_norm[-1])
    if abs(end_val) > 0.5:
        return 0.0
    rise = arr_norm[:peak_idx + 1]
    fall = arr_norm[peak_idx:]
    rise_mono = float(np.mean(np.diff(rise) >= -0.1)) if len(rise) > 1 else 1.0
    fall_toward_zero = float(np.mean(np.diff(np.abs(fall)) <= 0.1)) if len(fall) > 1 else 1.0
    return rise_mono * fall_toward_zero


# ---------------------------------------------------------------------------
# Math utilities
# ---------------------------------------------------------------------------


def _sigmoid_above(x: float, threshold: float, k: float = 10.0) -> float:
    """Smooth step: 0 well below threshold, 1 well above. Differentiable gate."""
    return float(1.0 / (1.0 + math.exp(-k * (x - threshold))))


def _sigmoid_below(x: float, threshold: float, k: float = 10.0) -> float:
    """Smooth step: 1 well below threshold, 0 well above."""
    return _sigmoid_above(-x, -threshold, k)


def _softmax(values: list[float]) -> list[float]:
    """Numerically stable softmax."""
    arr = np.asarray(values, dtype=np.float64)
    arr = arr - float(np.max(arr))
    exp_arr = np.exp(arr)
    total = float(exp_arr.sum())
    if total < 1e-12:
        n = len(arr)
        return [1.0 / n] * n
    return [float(v) for v in exp_arr / total]


# ---------------------------------------------------------------------------
# Threshold loading
# ---------------------------------------------------------------------------


def _load_thresholds(path: pathlib.Path) -> dict[str, float]:
    """Load thresholds from YAML; return hardcoded defaults on any failure."""
    try:
        import yaml  # noqa: PLC0415
        with path.open() as fh:
            data = yaml.safe_load(fh)
        raw = data.get("thresholds", {})
        merged = dict(_DEFAULT_THRESHOLDS)
        for key in _DEFAULT_THRESHOLDS:
            if key in raw:
                merged[key] = float(raw[key])
        return merged
    except Exception as exc:  # noqa: BLE001
        logger.warning("shape_thresholds.yaml could not be loaded (%s); using defaults.", exc)
        return dict(_DEFAULT_THRESHOLDS)