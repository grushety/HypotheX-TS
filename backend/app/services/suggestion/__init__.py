"""Suggestion-model helpers for backend integration."""

from .boundary_proposal import (
    BoundaryCandidate,
    BoundaryProposal,
    BoundaryProposalError,
    BoundaryProposerConfig,
    ProvisionalSegment,
    propose_boundaries,
)

__all__ = [
    "BoundaryCandidate",
    "BoundaryProposal",
    "BoundaryProposalError",
    "BoundaryProposerConfig",
    "ProvisionalSegment",
    "propose_boundaries",
]
