"""Tier-3 user-invocable composite operations."""
from __future__ import annotations

from .aggregate import METRIC_REGISTRY, aggregate, register_metric
from .align_warp import (
    ALIGN_METHODS,
    APPROX_SHAPES,
    COMPATIBLE_SHAPES,
    DEFAULT_SOFT_DTW_GAMMA,
    DEFAULT_WARPING_BAND,
    INCOMPATIBLE_SHAPES,
    AlignableSegment,
    AlignMethod,
    AlignWarpAudit,
    IncompatibleOp,
    align_warp,
)
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
    "ALIGN_METHODS",
    "APPROX_SHAPES",
    "AlignMethod",
    "AlignWarpAudit",
    "AlignableSegment",
    "COMPATIBLE_SHAPES",
    "CompensationMode",
    "ConservationAudit",
    "ConservationResult",
    "DEFAULT_SOFT_DTW_GAMMA",
    "DEFAULT_TOLERANCE",
    "DEFAULT_WARPING_BAND",
    "DecomposeAudit",
    "DecomposedSegment",
    "HARD_LAWS",
    "HasJacobian",
    "INCOMPATIBLE_SHAPES",
    "IncompatibleOp",
    "LAW_REGISTRY",
    "METRIC_REGISTRY",
    "REFIT_REASON",
    "SOFT_LAWS",
    "UnknownLaw",
    "aggregate",
    "align_warp",
    "decompose",
    "default_compensation_mode_for_domain",
    "enforce_conservation",
    "project",
    "register_law",
    "register_metric",
]
