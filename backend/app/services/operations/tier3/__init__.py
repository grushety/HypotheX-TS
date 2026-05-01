"""Tier-3 user-invocable composite operations."""
from __future__ import annotations

from .aggregate import METRIC_REGISTRY, aggregate, register_metric
from .compensation import (
    CompensationMode,
    HasJacobian,
    default_compensation_mode_for_domain,
    project,
)
from .decompose import (
    REFIT_REASON,
    DecomposeAudit,
    DecomposedSegment,
    decompose,
)
from .enforce_conservation import (
    DEFAULT_TOLERANCE,
    HARD_LAWS,
    LAW_REGISTRY,
    SOFT_LAWS,
    ConservationAudit,
    ConservationResult,
    UnknownLaw,
    enforce_conservation,
    register_law,
)

__all__ = [
    "CompensationMode",
    "ConservationAudit",
    "ConservationResult",
    "DEFAULT_TOLERANCE",
    "DecomposeAudit",
    "DecomposedSegment",
    "HARD_LAWS",
    "HasJacobian",
    "LAW_REGISTRY",
    "METRIC_REGISTRY",
    "REFIT_REASON",
    "SOFT_LAWS",
    "UnknownLaw",
    "aggregate",
    "decompose",
    "default_compensation_mode_for_domain",
    "enforce_conservation",
    "project",
    "register_law",
    "register_metric",
]
