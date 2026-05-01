"""Tier-3 user-invocable composite operations."""
from __future__ import annotations

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
    "REFIT_REASON",
    "SOFT_LAWS",
    "UnknownLaw",
    "decompose",
    "enforce_conservation",
    "register_law",
]
