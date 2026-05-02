"""Validation services — per-edit statistical checks (VAL-001 onward).

Currently exposes:
  - ``conformal_pid`` — Conformal-PID prediction-band check (VAL-001).
  - ``probe_ir`` — PROBE invalidation-rate check (VAL-002).

Keep this package free of Flask / DB imports so the validators can be reused
inside the coordinator and offline calibration scripts.
"""
from app.services.validation.conformal_pid import (
    BandCheckResult,
    ConformalCalibrationError,
    ConformalConfig,
    ConformalPIDValidator,
    Forecaster,
    ValidationResult,
)
from app.services.validation.probe_ir import (
    DEFAULT_MC_SAMPLES,
    DEFAULT_SIGMA,
    METHOD_LINEARISED,
    METHOD_MONTE_CARLO,
    TIER2_DEFAULT_SIGMA,
    ProbeIRResult,
    ProbeMethodError,
    ProbeModel,
    default_sigma_for_op,
    probe_invalidation_rate,
)

__all__ = [
    "BandCheckResult",
    "ConformalCalibrationError",
    "ConformalConfig",
    "ConformalPIDValidator",
    "DEFAULT_MC_SAMPLES",
    "DEFAULT_SIGMA",
    "Forecaster",
    "METHOD_LINEARISED",
    "METHOD_MONTE_CARLO",
    "TIER2_DEFAULT_SIGMA",
    "ProbeIRResult",
    "ProbeMethodError",
    "ProbeModel",
    "ValidationResult",
    "default_sigma_for_op",
    "probe_invalidation_rate",
]
