from app.domain.chunk_assignment import ChunkAssignment, assign_chunk_type
from app.domain.chunk_scoring import ChunkScores, ChunkScoringError, compute_chunk_scores
from app.domain.operations_registry import (
    OperationRegistryCatalog,
    build_operation_registry_catalog,
    get_legal_operations_for_chunk,
)
from app.domain.stats import (
    SegmentStatistics,
    SegmentStatisticsError,
    compute_context_contrast,
    compute_peak_score,
    compute_periodicity_score,
    compute_residual_to_line,
    compute_segment_statistics,
    compute_sign_consistency,
    compute_slope,
    compute_variance,
)
from app.domain.validation import OperationLegalityResult, validate_operation_legality

__all__ = [
    "SegmentStatistics",
    "SegmentStatisticsError",
    "ChunkAssignment",
    "ChunkScores",
    "ChunkScoringError",
    "OperationLegalityResult",
    "OperationRegistryCatalog",
    "assign_chunk_type",
    "build_operation_registry_catalog",
    "compute_chunk_scores",
    "compute_context_contrast",
    "compute_peak_score",
    "compute_periodicity_score",
    "compute_residual_to_line",
    "compute_segment_statistics",
    "compute_sign_consistency",
    "compute_slope",
    "compute_variance",
    "get_legal_operations_for_chunk",
    "validate_operation_legality",
]
