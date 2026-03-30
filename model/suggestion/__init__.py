"""Suggestion-model components."""

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
    PrototypeMemoryBank,
    PrototypeMemoryConfig,
    PrototypeClassification,
    PrototypeChunkClassifier,
    PrototypeClassifierConfig,
    PrototypeClassifierError,
    PrototypeUpdateResult,
)
from .segment_encoder import SegmentEmbedding, SegmentEncoderConfig, SegmentEncodingError, encode_segment, normalize_series

__all__ = [
    "BoundaryCandidate",
    "BoundaryProposal",
    "BoundaryProposalError",
    "BoundaryProposerConfig",
    "LabeledSupportSegment",
    "PrototypeMemoryBank",
    "PrototypeMemoryConfig",
    "ProvisionalSegment",
    "PrototypeClassification",
    "PrototypeChunkClassifier",
    "PrototypeClassifierConfig",
    "PrototypeClassifierError",
    "PrototypeUpdateResult",
    "SegmentEmbedding",
    "SegmentEncoderConfig",
    "SegmentEncodingError",
    "encode_segment",
    "normalize_series",
    "propose_boundaries",
]
