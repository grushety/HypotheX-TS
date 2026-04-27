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
    build_default_support_segments,
    LabeledSupportSegment,
    PrototypeMemoryBank,
    PrototypeMemoryConfig,
    PrototypeClassification,
    PrototypeChunkClassifier,
    PrototypeClassifierConfig,
    PrototypeClassifierError,
    PrototypeUpdateResult,
    PrototypeShapeClassifier,
    SHAPE_LABELS,
    SupportSegment,
)
from .segment_encoder import SegmentEmbedding, SegmentEncoderConfig, SegmentEncodingError, encode_segment, normalize_series
from .support_buffer import AcceptResult, SupportBuffer, SupportBufferConfig

__all__ = [
    "AcceptResult",
    "SupportBuffer",
    "SupportBufferConfig",
    "BoundaryCandidate",
    "BoundaryProposal",
    "BoundaryProposalError",
    "BoundaryProposerConfig",
    "build_default_support_segments",
    "LabeledSupportSegment",
    "PrototypeMemoryBank",
    "PrototypeMemoryConfig",
    "ProvisionalSegment",
    "PrototypeClassification",
    "PrototypeChunkClassifier",
    "PrototypeClassifierConfig",
    "PrototypeClassifierError",
    "PrototypeUpdateResult",
    "PrototypeShapeClassifier",
    "SHAPE_LABELS",
    "SegmentEmbedding",
    "SegmentEncoderConfig",
    "SegmentEncodingError",
    "encode_segment",
    "normalize_series",
    "propose_boundaries",
    "SupportSegment",
]
