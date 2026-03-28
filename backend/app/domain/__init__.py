from app.domain.chunk_assignment import ChunkAssignment, assign_chunk_type
from app.domain.chunk_scoring import ChunkScores, ChunkScoringError, compute_chunk_scores
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

__all__ = [
    "SegmentStatistics",
    "SegmentStatisticsError",
    "ChunkAssignment",
    "ChunkScores",
    "ChunkScoringError",
    "assign_chunk_type",
    "compute_chunk_scores",
    "compute_context_contrast",
    "compute_peak_score",
    "compute_periodicity_score",
    "compute_residual_to_line",
    "compute_segment_statistics",
    "compute_sign_consistency",
    "compute_slope",
    "compute_variance",
]
