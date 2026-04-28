"""Tier-2 noise ops: suppress_denoise, amplify, change_color,
inject_synthetic, whiten (OP-026).

All mutating ops that work on a blob deepcopy it internally; the caller's
blob is unchanged.

suppress_denoise operates directly on a raw signal array (X_seg) because
a noise segment has no structural parametric components to preserve.
amplify, change_color, inject_synthetic, whiten operate on blob.components
['residual'] to preserve any underlying trend/cycle structure.

Relabeling:
  suppress_denoise  → RECLASSIFY_VIA_SEGMENTER
  amplify           → PRESERVED('noise')
  change_color      → PRESERVED('noise')
  inject_synthetic  → PRESERVED('noise')
  whiten            → PRESERVED('noise')

References
----------
Chang, S. G., Yu, B., & Vetterli, M. (2000). Adaptive wavelet thresholding for
    image denoising and compression. IEEE T. Image Proc. 9(9):1532-1546.
    → suppress_denoise 'bayesshrink': BayesShrink soft-thresholding.

Rudin, L. I., Osher, S., & Fatemi, E. (1992). Nonlinear total variation based
    noise removal algorithms. Physica D, 60(1-4):259-268.
    → suppress_denoise 'tv': Chambolle TV denoising (via scikit-image).

Savitzky, A. & Golay, M. J. E. (1964). Smoothing and differentiation of data
    by simplified least squares procedures. Anal. Chem. 36(8):1627-1639.
    → suppress_denoise 'sg': Savitzky-Golay filter.

Timmer, J. & König, M. (1995). On generating power law noise.
    Astron. Astrophys. 300:707-710.
    → change_color: colored noise via colorednoise library.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Literal

import numpy as np

from app.models.decomposition import DecompositionBlob
from app.services.noise_models.models import NoiseModel
from app.services.operations.tier2.plateau import Tier2OpResult
from app.services.operations.relabeler.relabeler import RelabelResult

logger = logging.getLogger(__name__)

_DENOISE_METHODS = ("bayesshrink", "sg", "tv", "kalman", "gacos")
_NOISE_COLORS = ("white", "pink", "red")
_COLOR_BETA = {"white": 0.0, "pink": 1.0, "red": 2.0}


# ---------------------------------------------------------------------------
# Inline relabeler helpers
# ---------------------------------------------------------------------------


def _preserved(pre_shape: str) -> RelabelResult:
    return RelabelResult(
        new_shape=pre_shape,
        confidence=1.0,
        needs_resegment=False,
        rule_class="PRESERVED",
    )


def _reclassify(pre_shape: str) -> RelabelResult:
    return RelabelResult(
        new_shape=pre_shape,
        confidence=0.0,
        needs_resegment=True,
        rule_class="RECLASSIFY_VIA_SEGMENTER",
    )


# ---------------------------------------------------------------------------
# suppress_denoise
# ---------------------------------------------------------------------------


def suppress_denoise(
    X_seg: np.ndarray,
    method: Literal["bayesshrink", "sg", "tv", "kalman", "gacos"] = "bayesshrink",
    pre_shape: str = "noise",
    **kwargs: Any,
) -> Tier2OpResult:
    """Denoise a noise segment using one of five methods.

    Methods:
      bayesshrink — Wavelet soft-thresholding with BayesShrink threshold
                    (Chang et al. 2000, Eq. 19). Uses sym8 wavelet.
      sg          — Savitzky-Golay smoothing (Savitzky & Golay 1964).
                    kwargs: window (int, default 11), poly (int, default 3).
      tv          — Total variation Chambolle denoising (Rudin et al. 1992).
                    kwargs: weight (float, default 0.1).
      kalman      — 1D Kalman–RTS smoother (constant-velocity + noise model).
                    kwargs: q (process noise, default 1e-4), r (obs noise, default 1.0).
      gacos       — Atmospheric correction: subtract gacos_correction array.
                    kwargs: gacos_correction (np.ndarray, required).

    Relabeling: RECLASSIFY_VIA_SEGMENTER — the denoised signal shape depends
    on what structure was underneath the noise.

    Reference: Chang, Yu & Vetterli (2000) — BayesShrink.

    Args:
        X_seg:     Noise segment signal, shape (n,).
        method:    Denoising method (see above). Default 'bayesshrink'.
        pre_shape: Shape label before the edit.
        **kwargs:  Method-specific parameters.

    Returns:
        Tier2OpResult with denoised values and RECLASSIFY relabeling.

    Raises:
        ValueError: Unknown method, or required kwargs missing.
    """
    if method not in _DENOISE_METHODS:
        raise ValueError(
            f"suppress_denoise: unknown method '{method}'. "
            f"Valid methods: {_DENOISE_METHODS}."
        )
    arr = np.asarray(X_seg, dtype=np.float64)
    denoised = _denoise(arr, method, kwargs)
    return Tier2OpResult(
        values=denoised,
        relabel=_reclassify(pre_shape),
        op_name="suppress_denoise",
    )


def _denoise(arr: np.ndarray, method: str, kwargs: dict) -> np.ndarray:
    n = len(arr)
    if method == "bayesshrink":
        return _denoise_bayesshrink(arr)
    if method == "sg":
        return _denoise_sg(arr, kwargs)
    if method == "tv":
        return _denoise_tv(arr, kwargs)
    if method == "kalman":
        return _denoise_kalman(arr, kwargs)
    if method == "gacos":
        return _denoise_gacos(arr, kwargs)
    raise ValueError(f"suppress_denoise: unhandled method '{method}'.")  # unreachable


def _denoise_bayesshrink(arr: np.ndarray) -> np.ndarray:
    """BayesShrink soft-threshold wavelet denoising.

    Reference: Chang, Yu & Vetterli (2000) IEEE T. Image Proc. 9(9):1532-1546.
    Threshold: T_B = sigma_n^2 / sigma_x,  sigma_x = sqrt(max(0, var_y - sigma_n^2)).
    """
    try:
        import pywt  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "suppress_denoise bayesshrink requires PyWavelets. "
            "Install with: pip install PyWavelets"
        ) from exc
    n = len(arr)
    wavelet = "sym8"
    # Ensure the signal is long enough for at least one decomposition level
    max_level = pywt.dwt_max_level(n, wavelet)
    level = max(1, min(max_level, 4))
    coeffs = pywt.wavedec(arr, wavelet, level=level, mode="periodization")
    # Estimate noise std from finest detail coefficients (MAD estimator)
    sigma_n = float(np.median(np.abs(coeffs[-1]))) / 0.6745
    # BayesShrink signal std per subband
    var_y = float(np.var(arr))
    sigma_x = float(np.sqrt(max(var_y - sigma_n ** 2, 0.0)))
    if sigma_x < 1e-12:
        # Signal is pure noise — apply conservative threshold
        threshold = sigma_n
    else:
        threshold = sigma_n ** 2 / sigma_x
    coeffs_thresh = [coeffs[0]] + [
        pywt.threshold(c, threshold, mode="soft") for c in coeffs[1:]
    ]
    reconstructed = pywt.waverec(coeffs_thresh, wavelet, mode="periodization")
    return reconstructed[:n].astype(np.float64)


def _denoise_sg(arr: np.ndarray, kwargs: dict) -> np.ndarray:
    """Savitzky-Golay filter.

    Reference: Savitzky & Golay (1964) Anal. Chem. 36(8):1627-1639.
    """
    from scipy.signal import savgol_filter  # noqa: PLC0415

    n = len(arr)
    window = int(kwargs.get("window", 11))
    poly = int(kwargs.get("poly", 3))
    # window must be odd and >= poly+2; clamp to signal length
    window = min(window, n if n % 2 == 1 else n - 1)
    window = max(window, poly + 2 if (poly + 2) % 2 == 1 else poly + 3)
    if window > n:
        window = n if n % 2 == 1 else n - 1
    return savgol_filter(arr, window, poly).astype(np.float64)


def _denoise_tv(arr: np.ndarray, kwargs: dict) -> np.ndarray:
    """Total variation Chambolle denoising.

    Reference: Rudin, Osher & Fatemi (1992) Physica D 60:259-268.
    """
    try:
        from skimage.restoration import denoise_tv_chambolle  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "suppress_denoise tv requires scikit-image. "
            "Install with: pip install scikit-image"
        ) from exc
    weight = float(kwargs.get("weight", 0.1))
    return denoise_tv_chambolle(arr, weight=weight).flatten().astype(np.float64)


def _denoise_kalman(arr: np.ndarray, kwargs: dict) -> np.ndarray:
    """1D Kalman-RTS smoother (constant state + Gaussian noise).

    Model: x_k = x_{k-1} + w_k,  w_k ~ N(0, q)
           y_k = x_k + v_k,       v_k ~ N(0, r)

    Implements the forward Kalman filter and backward Rauch-Tung-Striebel
    smoother for the scalar case.

    kwargs:
        q: process noise variance (default 1e-4).
        r: observation noise variance (default 1.0).
    """
    n = len(arr)
    q = float(kwargs.get("q", 1e-4))
    r = float(kwargs.get("r", 1.0))
    if q <= 0.0:
        raise ValueError(f"suppress_denoise kalman: q must be > 0, got {q!r}.")
    if r <= 0.0:
        raise ValueError(f"suppress_denoise kalman: r must be > 0, got {r!r}.")

    # Forward pass
    x_filt = np.zeros(n)
    p_filt = np.zeros(n)
    x_pred = np.zeros(n)
    p_pred = np.zeros(n)

    x_pred[0] = arr[0]
    p_pred[0] = r

    for k in range(n):
        if k > 0:
            x_pred[k] = x_filt[k - 1]
            p_pred[k] = p_filt[k - 1] + q
        gain = p_pred[k] / (p_pred[k] + r)
        x_filt[k] = x_pred[k] + gain * (arr[k] - x_pred[k])
        p_filt[k] = (1.0 - gain) * p_pred[k]

    # Backward RTS smoother pass
    x_smooth = x_filt.copy()
    for k in range(n - 2, -1, -1):
        g = p_filt[k] / (p_filt[k] + q)
        x_smooth[k] = x_filt[k] + g * (x_smooth[k + 1] - x_pred[k + 1])

    return x_smooth.astype(np.float64)


def _denoise_gacos(arr: np.ndarray, kwargs: dict) -> np.ndarray:
    """GACOS atmospheric correction: subtract correction array from signal.

    Reference: Yunjun, Fattahi & Amelung (2019) CAGEO 133:104331.

    kwargs:
        gacos_correction: np.ndarray of same length as arr (required).
    """
    correction = kwargs.get("gacos_correction")
    if correction is None:
        raise ValueError(
            "suppress_denoise gacos: kwargs['gacos_correction'] is required."
        )
    corr = np.asarray(correction, dtype=np.float64)
    if len(corr) != len(arr):
        raise ValueError(
            f"suppress_denoise gacos: gacos_correction length {len(corr)} "
            f"does not match segment length {len(arr)}."
        )
    return (arr - corr).astype(np.float64)


# ---------------------------------------------------------------------------
# amplify
# ---------------------------------------------------------------------------


def amplify(
    blob: DecompositionBlob,
    alpha: float,
    pre_shape: str = "noise",
) -> Tier2OpResult:
    """Scale the noise amplitude by alpha.

    Multiplies blob.components['residual'] by alpha. If no 'residual' key
    exists, all non-structural components are left unchanged (identity).

    Reference: Timmer & König (1995) — amplitude scaling of colored noise.

    Args:
        blob:      DecompositionBlob containing a 'residual' component.
        alpha:     Amplitude scale factor (any float; 0 → zeroes noise).
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with scaled values and PRESERVED('noise').
    """
    blob = copy.deepcopy(blob)
    if "residual" in blob.components:
        blob.components["residual"] = blob.components["residual"] * float(alpha)
    else:
        logger.warning(
            "amplify: blob has no 'residual' component; returning unchanged values."
        )
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="amplify",
    )


# ---------------------------------------------------------------------------
# change_color
# ---------------------------------------------------------------------------


def change_color(
    blob: DecompositionBlob,
    target_color: Literal["white", "pink", "red"],
    seed: int | None = None,
    pre_shape: str = "noise",
) -> Tier2OpResult:
    """Replace the noise component with colored noise of the same variance.

    Replaces blob.components['residual'] with new noise of spectral color
    target_color and the same standard deviation as the original residual.
    All other components (trend, seasonal, …) are unchanged, preserving
    the underlying signal structure.

    If no 'residual' key exists, falls back to treating blob.reassemble() as
    the full noise signal and returns a plain colored-noise array.

    Colors:
      white → flat power spectrum (β=0)
      pink  → 1/f spectrum (β=1)
      red   → Brownian 1/f² spectrum (β=2)

    Reference: Timmer & König (1995) — power-law noise via colorednoise.

    Args:
        blob:         DecompositionBlob with a 'residual' noise component.
        target_color: 'white', 'pink', or 'red'.
        seed:         Optional integer seed for reproducibility.
        pre_shape:    Shape label before the edit.

    Returns:
        Tier2OpResult with recolored values and PRESERVED('noise').

    Raises:
        ValueError: Unknown target_color.
    """
    if target_color not in _NOISE_COLORS:
        raise ValueError(
            f"change_color: unknown target_color '{target_color}'. "
            f"Valid colors: {_NOISE_COLORS}."
        )
    blob = copy.deepcopy(blob)
    if "residual" in blob.components:
        noise_arr = blob.components["residual"]
    else:
        logger.warning(
            "change_color: blob has no 'residual' component; using full signal."
        )
        noise_arr = blob.reassemble()

    n = len(noise_arr)
    sigma = float(np.std(noise_arr))
    new_noise = _generate_colored_noise(n, _COLOR_BETA[target_color], sigma, seed)

    if "residual" in blob.components:
        blob.components["residual"] = new_noise
    else:
        # No components to preserve — return colored noise centered on original mean
        mean_val = float(np.mean(noise_arr))
        return Tier2OpResult(
            values=mean_val + new_noise,
            relabel=_preserved(pre_shape),
            op_name="change_color",
        )

    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="change_color",
    )


def _generate_colored_noise(
    n: int, beta: float, sigma: float, seed: int | None
) -> np.ndarray:
    """Generate colored noise of length n with given spectral exponent and std.

    Reference: Timmer & König (1995) — powerlaw_psd_gaussian.
    """
    if beta == 0.0:
        rng = np.random.default_rng(seed)
        noise = rng.normal(0.0, max(sigma, 0.0), n)
        return noise.astype(np.float64)
    try:
        import colorednoise  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "change_color (pink/red) requires colorednoise. "
            "Install with: pip install colorednoise"
        ) from exc
    rng = np.random.default_rng(seed)
    raw = colorednoise.powerlaw_psd_gaussian(beta, n, random_state=rng)
    raw_std = float(np.std(raw))
    if raw_std > 1e-12:
        return (raw * (sigma / raw_std)).astype(np.float64)
    return np.zeros(n, dtype=np.float64)


# ---------------------------------------------------------------------------
# inject_synthetic
# ---------------------------------------------------------------------------


def inject_synthetic(
    blob: DecompositionBlob,
    noise_model: NoiseModel,
    seed: int | None = None,
    pre_shape: str = "noise",
) -> Tier2OpResult:
    """Add synthetic noise from a NoiseModel to the residual component.

    Draws n samples from noise_model.sample(n) and adds them to
    blob.components['residual']. If no 'residual' component exists, adds
    the noise to the full reassembled signal and returns without blob structure.

    Reference: Timmer & König (1995) — additive noise injection.

    Args:
        blob:        DecompositionBlob with a 'residual' noise component.
        noise_model: Any object implementing the NoiseModel Protocol.
                     Built-ins: AR1NoiseModel, FlickerNoiseModel,
                     GammaSpeckleModel.
        seed:        Optional integer seed forwarded to noise_model.sample.
        pre_shape:   Shape label before the edit.

    Returns:
        Tier2OpResult with noise-injected values and PRESERVED('noise').
    """
    blob = copy.deepcopy(blob)
    if "residual" in blob.components:
        n = len(blob.components["residual"])
        noise_arr = np.asarray(noise_model.sample(n, seed=seed), dtype=np.float64)
        if len(noise_arr) != n:
            raise ValueError(
                f"inject_synthetic: noise_model.sample({n}) returned array of "
                f"length {len(noise_arr)}."
            )
        blob.components["residual"] = blob.components["residual"] + noise_arr
    else:
        logger.warning(
            "inject_synthetic: blob has no 'residual' component; "
            "adding noise to full signal."
        )
        full = blob.reassemble()
        n = len(full)
        noise_arr = np.asarray(noise_model.sample(n, seed=seed), dtype=np.float64)
        if len(noise_arr) != n:
            raise ValueError(
                f"inject_synthetic: noise_model.sample({n}) returned array of "
                f"length {len(noise_arr)}."
            )
        return Tier2OpResult(
            values=full + noise_arr,
            relabel=_preserved(pre_shape),
            op_name="inject_synthetic",
        )
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="inject_synthetic",
    )


# ---------------------------------------------------------------------------
# whiten
# ---------------------------------------------------------------------------


def whiten(
    blob: DecompositionBlob,
    pre_shape: str = "noise",
) -> Tier2OpResult:
    """Whiten the noise component via Welch PSD estimation and spectral division.

    Estimates the power spectral density of blob.components['residual'] using
    Welch's method, then divides the spectrum by sqrt(PSD) to flatten the
    spectral density to approximately white noise. The output is normalised to
    preserve the original residual's standard deviation.

    Reference: Timmer & König (1995) — spectral whitening.

    Args:
        blob:      DecompositionBlob with a 'residual' noise component.
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with whitened values and PRESERVED('noise').
    """
    from scipy.signal import welch  # noqa: PLC0415

    blob = copy.deepcopy(blob)
    if "residual" in blob.components:
        noise_arr = blob.components["residual"]
    else:
        logger.warning(
            "whiten: blob has no 'residual' component; whitening full signal."
        )
        noise_arr = blob.reassemble()

    n = len(noise_arr)
    target_std = float(np.std(noise_arr))

    # Welch PSD
    nperseg = min(n, 256)
    f, psd = welch(noise_arr, nperseg=nperseg)

    # Spectral division
    freqs = np.fft.rfftfreq(n)
    psd_interp = np.interp(freqs, f, psd).astype(np.float64)
    spectrum = np.fft.rfft(noise_arr)
    whitening = 1.0 / (np.sqrt(psd_interp) + 1e-12)
    white = np.fft.irfft(spectrum * whitening, n=n).astype(np.float64)[:n]

    # Fall back to original if near-constant input drives PSD→0 → Inf→NaN
    if not np.all(np.isfinite(white)):
        logger.warning(
            "whiten: non-finite values after spectral division (near-constant input); "
            "returning original residual."
        )
        white = noise_arr.copy().astype(np.float64)

    # Normalise to preserve original standard deviation
    white_std = float(np.std(white))
    if white_std > 1e-12 and target_std > 0.0:
        white = white * (target_std / white_std)

    if "residual" in blob.components:
        blob.components["residual"] = white
        return Tier2OpResult(
            values=blob.reassemble(),
            relabel=_preserved(pre_shape),
            op_name="whiten",
        )
    return Tier2OpResult(
        values=white,
        relabel=_preserved(pre_shape),
        op_name="whiten",
    )
