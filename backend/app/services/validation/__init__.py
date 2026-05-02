"""Validation services — per-edit statistical checks (VAL-001 onward).

Currently exposes:
  - ``conformal_pid`` — Conformal-PID prediction-band check (VAL-001).

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

__all__ = [
    "BandCheckResult",
    "ConformalCalibrationError",
    "ConformalConfig",
    "ConformalPIDValidator",
    "Forecaster",
    "ValidationResult",
]
