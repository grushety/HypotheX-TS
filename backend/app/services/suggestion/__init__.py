"""Suggestion-model helpers for backend integration."""

from .boundary_proposal import (
    BoundaryCandidate,
    BoundaryProposal,
    BoundaryProposalError,
    BoundaryProposerConfig,
    ProvisionalSegment,
    propose_boundaries,
)
from .prototype_classifier import (
    LabeledSupportSegment,
    PrototypeClassification,
    PrototypeChunkClassifier,
    PrototypeClassifierConfig,
    PrototypeClassifierError,
)
from .segment_encoder import SegmentEmbedding, SegmentEncoderConfig, SegmentEncodingError, encode_segment, normalize_series

__all__ = [
    "BoundaryCandidate",
    "BoundaryProposal",
    "BoundaryProposalError",
    "BoundaryProposerConfig",
    "LabeledSupportSegment",
    "ProvisionalSegment",
    "PrototypeClassification",
    "PrototypeChunkClassifier",
    "PrototypeClassifierConfig",
    "PrototypeClassifierError",
    "SegmentEmbedding",
    "SegmentEncoderConfig",
    "SegmentEncodingError",
    "encode_segment",
    "normalize_series",
    "propose_boundaries",
]
