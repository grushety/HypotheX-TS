"""Tier-2 cycle ops: deseasonalise_remove, amplify_amplitude, dampen_amplitude,
phase_shift, change_period, change_harmonic_content, replace_with_flat (OP-024).

All ops edit STL or MSTL seasonal components directly:
  STL:  components['seasonal'] (single key)
  MSTL: components['seasonal_{T}'] for each period T

All mutating ops deepcopy the blob internally; the caller's blob is unchanged.

Relabeling:
  deseasonalise_remove       → RECLASSIFY_VIA_SEGMENTER
  amplify_amplitude(α=0)     → DETERMINISTIC('plateau')
  amplify_amplitude(α≠0)     → PRESERVED('cycle')
  dampen_amplitude           → PRESERVED('cycle')   (α validated in (0, 1])
  phase_shift                → PRESERVED('cycle')
  change_period              → PRESERVED('cycle')
  change_harmonic_content    → PRESERVED('cycle')
  replace_with_flat          → DETERMINISTIC('plateau')

References
----------
Cleveland, R. B., Cleveland, W. S., McRae, J. E., & Terpenning, I. (1990).
    STL: A Seasonal-Trend Decomposition Procedure Based on Loess.
    Journal of Official Statistics 6(1):3-73.
    → Seasonal component layout; trend + seasonal + residual == X.

Bandara, K., Hyndman, R. J., & Bergmeir, C. (2021).
    MSTL: A Seasonal-Trend Decomposition Algorithm for Time Series with
    Multiple Seasonal Patterns.  arXiv 2107.13462.
    → Multi-period seasonal_{T} component layout.

Oppenheim, A. V. & Schafer, R. W. (2010). Discrete-Time Signal Processing,
    3rd ed. Prentice Hall. Ch. 11.
    → Hilbert transform for analytic signal construction (phase_shift).

Verhoef, W. (1996). Application of harmonic analysis of NDVI time series.
    In Fourier Analysis of Temporal NDVI in the Southern African and American
    Tropics. ITC Publication 108.
    → Harmonic coefficient (a_k, b_k) manipulation (change_harmonic_content).
"""

from __future__ import annotations

import copy
import logging
from typing import Literal

import numpy as np

from app.models.decomposition import DecompositionBlob
from app.services.operations.tier2.plateau import Tier2OpResult
from app.services.operations.relabeler.relabeler import RelabelResult

logger = logging.getLogger(__name__)


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


def _deterministic(target_shape: str) -> RelabelResult:
    return RelabelResult(
        new_shape=target_shape,
        confidence=1.0,
        needs_resegment=False,
        rule_class="DETERMINISTIC",
    )


def _reclassify(pre_shape: str) -> RelabelResult:
    return RelabelResult(
        new_shape=pre_shape,
        confidence=0.0,
        needs_resegment=True,
        rule_class="RECLASSIFY_VIA_SEGMENTER",
    )


# ---------------------------------------------------------------------------
# Internal helpers — seasonal key discovery and period resolution
# ---------------------------------------------------------------------------


def _seasonal_keys(blob: DecompositionBlob) -> list[str]:
    """Return all seasonal component keys in blob.components.

    STL blobs have a single 'seasonal' key.
    MSTL blobs have 'seasonal_{T}' keys for each period T.
    """
    return [
        k for k in blob.components
        if k == "seasonal" or k.startswith("seasonal_")
    ]


def _get_period(blob: DecompositionBlob, key: str) -> int:
    """Return the period (samples) for a given seasonal component key.

    For 'seasonal': reads blob.coefficients['period'].
    For 'seasonal_{T}': parses T from the key name.
    """
    if key == "seasonal":
        return max(2, int(blob.coefficients.get("period", 2)))
    parts = key.split("_", 1)
    if len(parts) == 2:
        try:
            return max(2, int(parts[1]))
        except ValueError:
            pass
    return max(2, int(blob.coefficients.get("period", 2)))


def _scale_seasonal(blob: DecompositionBlob, alpha: float) -> None:
    """Scale all seasonal components in-place by alpha."""
    for k in _seasonal_keys(blob):
        blob.components[k] = blob.components[k] * alpha


def _zero_seasonal(blob: DecompositionBlob) -> None:
    """Zero all seasonal components in-place."""
    for k in _seasonal_keys(blob):
        blob.components[k] = np.zeros_like(blob.components[k])


def _resample_periodic(component: np.ndarray, beta: float) -> np.ndarray:
    """Resample a periodic component to a new period via modular linear interpolation.

    Maps each new sample position i to old position i/beta (modular), stretching
    (beta > 1) or compressing (beta < 1) the cycle.  For beta=1 this is identity.

    Reference: Oppenheim & Schafer (2010) Ch. 1 — sampling rate conversion.
    """
    n = len(component)
    new_t = (np.arange(n, dtype=np.float64) / float(beta)) % n
    lo = np.floor(new_t).astype(int) % n
    hi = (lo + 1) % n
    frac = new_t - np.floor(new_t)
    return component[lo] * (1.0 - frac) + component[hi] * frac


def _hilbert_phase_shift(arr: np.ndarray, delta_phi: float) -> np.ndarray:
    """Phase-shift arr by delta_phi radians using the Hilbert analytic signal.

    Constructs the analytic signal z(t) = x(t) + j·H(x(t)) via scipy Hilbert
    transform (FFT-based), then rotates: z_shifted = z · exp(j·delta_phi).
    Output = Re(z_shifted) = x·cos(phi) − H(x)·sin(phi).

    Edge artefacts from the FFT boundary assumption are reduced by a linear
    blend taper over min(4, n//4) samples at each end.

    Reference: Oppenheim & Schafer (2010) Ch. 11 — analytic signal via Hilbert.
    """
    from scipy.signal import hilbert  # noqa: PLC0415

    n = len(arr)
    analytic = hilbert(arr)
    shifted = np.real(analytic * np.exp(1j * float(delta_phi)))

    taper_w = min(4, n // 4)
    if taper_w > 0:
        ramp = np.linspace(0.0, 1.0, taper_w)
        shifted[:taper_w] = (1.0 - ramp) * arr[:taper_w] + ramp * shifted[:taper_w]
        shifted[-taper_w:] = ramp[::-1] * arr[-taper_w:] + (1.0 - ramp[::-1]) * shifted[-taper_w:]
    return shifted


def _harmonic_phase_shift(arr: np.ndarray, delta_phi: float) -> np.ndarray:
    """Phase-shift arr by delta_phi radians by rotating the rfft spectrum.

    Multiplies all positive-frequency rfft bins by exp(j·delta_phi), then
    reconstructs the real signal via irfft.  Equivalent to the Hilbert method
    for bandlimited signals; more stable when edge conditions are unfavourable.

    Reference: Oppenheim & Schafer (2010) Ch. 8 — DFT phase manipulation.
    """
    n = len(arr)
    S = np.fft.rfft(arr)
    S[1:] = S[1:] * np.exp(1j * float(delta_phi))
    return np.fft.irfft(S, n)


def _set_harmonic(
    component: np.ndarray,
    T: int,
    k: int,
    a_k: float,
    b_k: float,
    t: np.ndarray,
) -> np.ndarray:
    """Replace the k-th harmonic of component with a_k·cos + b_k·sin.

    The existing k-th harmonic is extracted and removed via OLS, then replaced
    with the new (a_k, b_k) coefficients.

    Reference: Verhoef (1996) ITC Publication 108 — harmonic (a_k, b_k) form.
    """
    omega_k = 2.0 * np.pi * float(k) / float(T)
    cos_k = np.cos(omega_k * t)
    sin_k = np.sin(omega_k * t)
    A = np.column_stack([cos_k, sin_k])
    coeff, _, _, _ = np.linalg.lstsq(A, component, rcond=None)
    existing_k = A @ coeff
    return component - existing_k + float(a_k) * cos_k + float(b_k) * sin_k


# ---------------------------------------------------------------------------
# deseasonalise_remove
# ---------------------------------------------------------------------------


def deseasonalise_remove(
    blob: DecompositionBlob,
    pre_shape: str = "cycle",
) -> Tier2OpResult:
    """Remove the seasonal component(s), leaving trend and residual.

    Zeros all 'seasonal' / 'seasonal_{T}' components.  The post-removal shape
    depends on the remaining trend + residual, so RECLASSIFY_VIA_SEGMENTER is
    signalled.

    Reference: Cleveland et al. (1990) — STL seasonal component zeroing.

    Args:
        blob:      STL or MSTL DecompositionBlob.
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with de-seasonalised values and RECLASSIFY relabeling.
    """
    blob = copy.deepcopy(blob)
    _zero_seasonal(blob)
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_reclassify(pre_shape),
        op_name="deseasonalise_remove",
    )


# ---------------------------------------------------------------------------
# amplify_amplitude
# ---------------------------------------------------------------------------


def amplify_amplitude(
    blob: DecompositionBlob,
    alpha: float,
    pre_shape: str = "cycle",
) -> Tier2OpResult:
    """Scale the amplitude of all seasonal components by alpha.

    alpha > 1  → amplifies the cycle.
    0 < alpha < 1  → dampens (use dampen_amplitude for validated dampening).
    alpha = 0  → equivalent to replace_with_flat but keeps trend; DETERMINISTIC('plateau').
    alpha < 0  → inverts the phase of the cycle; PRESERVED('cycle').

    Reference: Cleveland et al. (1990) — seasonal component scaling.

    Args:
        blob:      STL or MSTL DecompositionBlob.
        alpha:     Amplitude scale factor.
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with scaled seasonal values and appropriate relabeling.
    """
    blob = copy.deepcopy(blob)
    _scale_seasonal(blob, float(alpha))
    relabel = (
        _deterministic("plateau") if float(alpha) == 0.0 else _preserved(pre_shape)
    )
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=relabel,
        op_name="amplify_amplitude",
    )


# ---------------------------------------------------------------------------
# dampen_amplitude
# ---------------------------------------------------------------------------


def dampen_amplitude(
    blob: DecompositionBlob,
    alpha: float,
    pre_shape: str = "cycle",
) -> Tier2OpResult:
    """Reduce the amplitude of all seasonal components by alpha ∈ (0, 1].

    Validated wrapper around amplify_amplitude for the dampening use-case.
    alpha = 1 → identity; alpha → 0 → approaches flat (use amplify_amplitude(0)
    to explicitly flatten).

    Reference: Cleveland et al. (1990) — seasonal component scaling.

    Args:
        blob:      STL or MSTL DecompositionBlob.
        alpha:     Dampening factor in (0, 1].
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with dampened seasonal values and PRESERVED('cycle').

    Raises:
        ValueError: If alpha is not in (0, 1].
    """
    if not (0.0 < float(alpha) <= 1.0):
        raise ValueError(
            f"dampen_amplitude: alpha must be in (0, 1], got {alpha!r}. "
            "Use amplify_amplitude(alpha=0) to fully remove the seasonal."
        )
    blob = copy.deepcopy(blob)
    _scale_seasonal(blob, float(alpha))
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="dampen_amplitude",
    )


# ---------------------------------------------------------------------------
# phase_shift
# ---------------------------------------------------------------------------


def phase_shift(
    blob: DecompositionBlob,
    delta_phi: float,
    method: Literal["hilbert", "harmonic"] = "hilbert",
    pre_shape: str = "cycle",
) -> Tier2OpResult:
    """Shift the phase of all seasonal components by delta_phi radians.

    Two methods:
      'hilbert' (default) — Analytic signal rotation via Hilbert transform
          (Oppenheim & Schafer 2010, Ch. 11).  Edge artefacts are reduced by a
          linear blend taper over min(4, n//4) samples at each boundary.
      'harmonic' — FFT spectrum rotation: all rfft bins multiplied by
          exp(j·delta_phi), then irfft (Oppenheim & Schafer 2010, Ch. 8).
          More stable when Hilbert boundary conditions are unfavourable.

    For a pure cosine x(t) = A·cos(ωt), both methods give
    x_shifted(t) = A·cos(ωt + delta_phi).

    Reference: Oppenheim & Schafer (2010) Ch. 11 — Hilbert transform;
    Verhoef (1996) — phase of seasonal components.

    Args:
        blob:      STL or MSTL DecompositionBlob.
        delta_phi: Phase shift in radians.
        method:    'hilbert' (default) or 'harmonic'.
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with phase-shifted seasonal values and PRESERVED('cycle').

    Raises:
        ValueError: If method is not 'hilbert' or 'harmonic'.
    """
    if method not in ("hilbert", "harmonic"):
        raise ValueError(
            f"phase_shift: unknown method '{method}'. Choose 'hilbert' or 'harmonic'."
        )
    blob = copy.deepcopy(blob)
    for k in _seasonal_keys(blob):
        if method == "hilbert":
            blob.components[k] = _hilbert_phase_shift(blob.components[k], float(delta_phi))
        else:
            blob.components[k] = _harmonic_phase_shift(blob.components[k], float(delta_phi))
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="phase_shift",
    )


# ---------------------------------------------------------------------------
# change_period
# ---------------------------------------------------------------------------


def change_period(
    blob: DecompositionBlob,
    beta: float,
    pre_shape: str = "cycle",
) -> Tier2OpResult:
    """Rescale the period of all seasonal components by beta.

    Applies modular linear interpolation to each seasonal component so that
    the oscillation repeats at beta × the original period: beta > 1 slows
    the cycle; beta < 1 speeds it up.  beta = 1 is identity.

    For MSTL blobs, each 'seasonal_{T}' component is resampled and the key
    is renamed to 'seasonal_{round(T*beta)}' (minimum period: 2).

    Reference: Oppenheim & Schafer (2010) Ch. 1 — sampling rate conversion.

    Args:
        blob:      STL or MSTL DecompositionBlob.
        beta:      Period scale factor (> 0).
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with rescaled seasonal values and PRESERVED('cycle').

    Raises:
        ValueError: If beta <= 0.
    """
    if float(beta) <= 0.0:
        raise ValueError(f"change_period: beta must be > 0, got {beta!r}.")
    blob = copy.deepcopy(blob)

    new_components: dict = {}
    updated_periods: list[int] = []

    for k in list(blob.components.keys()):
        if k == "seasonal" or k.startswith("seasonal_"):
            T = _get_period(blob, k)
            T_new = max(2, int(round(T * float(beta))))
            resampled = _resample_periodic(blob.components[k], float(beta))
            new_key = f"seasonal_{T_new}" if k.startswith("seasonal_") else "seasonal"
            new_components[new_key] = resampled
            updated_periods.append(T_new)
        else:
            new_components[k] = blob.components[k]

    blob.components = new_components

    if blob.method == "STL" and updated_periods:
        blob.coefficients["period"] = updated_periods[0]
    elif blob.method == "MSTL" and updated_periods:
        blob.coefficients["valid_periods"] = updated_periods
        blob.coefficients["periods"] = updated_periods

    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="change_period",
    )


# ---------------------------------------------------------------------------
# change_harmonic_content
# ---------------------------------------------------------------------------


def change_harmonic_content(
    blob: DecompositionBlob,
    coeffs_dict: dict,
    pre_shape: str = "cycle",
) -> Tier2OpResult:
    """Replace specific harmonic coefficients in all seasonal components.

    For each k → (a_k, b_k) in coeffs_dict, the k-th harmonic of each
    seasonal component (relative to that component's period T) is replaced by
    a_k·cos(2πkt/T) + b_k·sin(2πkt/T).  The existing k-th harmonic content is
    extracted via OLS and subtracted before inserting the new harmonic.

    Reference: Verhoef (1996) ITC Publication 108 — harmonic (a_k, b_k) form
    for NDVI temporal analysis; Oppenheim & Schafer (2010) Ch. 8 — DFT.

    Args:
        blob:        STL or MSTL DecompositionBlob.
        coeffs_dict: Dict mapping harmonic index k (int) to (a_k, b_k) floats.
                     e.g. {1: (2.0, 0.0)} sets the fundamental to a pure cosine.
        pre_shape:   Shape label before the edit.

    Returns:
        Tier2OpResult with modified harmonic content and PRESERVED('cycle').
    """
    blob = copy.deepcopy(blob)
    for key in _seasonal_keys(blob):
        T = _get_period(blob, key)
        n = len(blob.components[key])
        t = np.arange(n, dtype=np.float64)
        component = blob.components[key].copy()
        for k, (a_k, b_k) in coeffs_dict.items():
            component = _set_harmonic(component, T, int(k), float(a_k), float(b_k), t)
        blob.components[key] = component
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="change_harmonic_content",
    )


# ---------------------------------------------------------------------------
# replace_with_flat
# ---------------------------------------------------------------------------


def replace_with_flat(
    blob: DecompositionBlob,
    pre_shape: str = "cycle",
) -> Tier2OpResult:
    """Replace the entire cycle with a constant plateau at the trend mean level.

    Zeros all seasonal components and flattens the trend to its mean, so that
    reassemble() returns a constant signal.  The DETERMINISTIC('plateau')
    relabeling is guaranteed by this construction.

    Reference: Cleveland et al. (1990) — seasonal component zeroing.

    Args:
        blob:      STL or MSTL DecompositionBlob.
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with constant plateau values and DETERMINISTIC('plateau').
    """
    blob = copy.deepcopy(blob)
    n = len(blob.components["trend"]) if "trend" in blob.components else len(
        next(iter(blob.components.values()))
    )

    _zero_seasonal(blob)

    if "trend" in blob.components:
        mean_trend = float(np.mean(blob.components["trend"]))
        blob.components["trend"] = np.full(n, mean_trend, dtype=np.float64)

    if "residual" in blob.components:
        blob.components["residual"] = np.zeros(n, dtype=np.float64)

    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_deterministic("plateau"),
        op_name="replace_with_flat",
    )
