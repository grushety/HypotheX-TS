"""NoiseModel Protocol and built-in implementations (OP-026).

References
----------
Timmer, J. & König, M. (1995) "On generating power law noise",
    Astron. Astrophys. 300:707-710.
    → FlickerNoiseModel (pink/red colored noise via colorednoise).

Box, G. E. P., Jenkins, G. M., & Reinsel, G. C. (1994).
    Time Series Analysis: Forecasting and Control (3rd ed.). Prentice Hall.
    → AR1NoiseModel: x_k = alpha * x_{k-1} + eps_k.

Goodman, J. W. (1985). Statistical Optics. Wiley.
    → GammaSpeckleModel: multiplicative Gamma speckle with mean=1.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class NoiseModel(Protocol):
    """Protocol for noise models used by inject_synthetic (OP-026).

    Any object with a compatible .sample(n) signature satisfies this protocol.
    """

    def sample(self, n: int, seed: int | None = None) -> np.ndarray:
        """Draw n samples from this noise model.

        Args:
            n:    Number of samples to draw.
            seed: Optional integer seed for reproducibility.

        Returns:
            np.ndarray of shape (n,).
        """
        ...


# ---------------------------------------------------------------------------
# AR(1) noise
# ---------------------------------------------------------------------------


class AR1NoiseModel:
    """First-order autoregressive (AR(1)) noise: x_k = alpha * x_{k-1} + eps_k.

    Reference: Box, Jenkins & Reinsel (1994) — AR(1) process definition.

    Args:
        alpha: AR coefficient in (-1, 1). Higher |alpha| → more temporal correlation.
        sigma: Standard deviation of the white driving noise eps_k.
    """

    def __init__(self, alpha: float = 0.7, sigma: float = 1.0) -> None:
        if not (-1.0 < float(alpha) < 1.0):
            raise ValueError(f"AR1NoiseModel: alpha must be in (-1, 1), got {alpha!r}.")
        if float(sigma) < 0.0:
            raise ValueError(f"AR1NoiseModel: sigma must be >= 0, got {sigma!r}.")
        self.alpha = float(alpha)
        self.sigma = float(sigma)

    def sample(self, n: int, seed: int | None = None) -> np.ndarray:
        rng = np.random.default_rng(seed)
        out = np.zeros(n, dtype=np.float64)
        eps = rng.normal(0.0, self.sigma, n)
        for i in range(1, n):
            out[i] = self.alpha * out[i - 1] + eps[i]
        return out


# ---------------------------------------------------------------------------
# Flicker / colored noise
# ---------------------------------------------------------------------------


class FlickerNoiseModel:
    """Power-law (colored) noise with spectral exponent beta.

    beta=0 → white, beta=1 → pink (1/f), beta=2 → red (Brownian).

    Reference: Timmer & König (1995) — power-law noise generation.
               Implemented via the `colorednoise` library.

    Args:
        sigma: Target standard deviation of the output.
        beta:  Spectral exponent (0=white, 1=pink, 2=red).
    """

    def __init__(self, sigma: float = 1.0, beta: float = 1.0) -> None:
        if float(sigma) < 0.0:
            raise ValueError(f"FlickerNoiseModel: sigma must be >= 0, got {sigma!r}.")
        if float(beta) < 0.0:
            raise ValueError(f"FlickerNoiseModel: beta must be >= 0, got {beta!r}.")
        self.sigma = float(sigma)
        self.beta = float(beta)

    def sample(self, n: int, seed: int | None = None) -> np.ndarray:
        try:
            import colorednoise  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "FlickerNoiseModel requires colorednoise. "
                "Install with: pip install colorednoise"
            ) from exc
        rng = np.random.default_rng(seed)
        raw = colorednoise.powerlaw_psd_gaussian(self.beta, n, random_state=rng)
        raw_std = float(np.std(raw))
        if raw_std > 1e-12:
            return (raw * (self.sigma / raw_std)).astype(np.float64)
        return np.zeros(n, dtype=np.float64)


# ---------------------------------------------------------------------------
# Gamma speckle
# ---------------------------------------------------------------------------


class GammaSpeckleModel:
    """Multiplicative Gamma speckle with unit mean.

    Draws factors gamma ~ Gamma(shape, 1/shape) so E[factor]=1.
    The inject_synthetic op adds this as a noise sample; callers that want
    multiplicative speckle should multiply X_seg by the sample instead.

    Reference: Goodman (1985) Statistical Optics — Gamma-distributed speckle.

    Args:
        shape: Gamma shape parameter (number of looks). Higher → less variance.
               Must be > 0.
    """

    def __init__(self, shape: float = 5.0) -> None:
        if float(shape) <= 0.0:
            raise ValueError(f"GammaSpeckleModel: shape must be > 0, got {shape!r}.")
        self.shape = float(shape)

    def sample(self, n: int, seed: int | None = None) -> np.ndarray:
        rng = np.random.default_rng(seed)
        return rng.gamma(self.shape, 1.0 / self.shape, n).astype(np.float64)
