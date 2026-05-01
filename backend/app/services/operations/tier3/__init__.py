"""Tier-3 user-invocable composite operations."""
from __future__ import annotations

from .aggregate import METRIC_REGISTRY, aggregate, register_metric
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
    "ConservationAudit",
    "ConservationResult",
    "DEFAULT_TOLERANCE",
    "DecomposeAudit",
    "DecomposedSegment",
    "HARD_LAWS",
    "LAW_REGISTRY",
    "METRIC_REGISTRY",
    "REFIT_REASON",
    "SOFT_LAWS",
    "UnknownLaw",
    "aggregate",
    "decompose",
    "enforce_conservation",
    "register_law",
    "register_metric",
]
