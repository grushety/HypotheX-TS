from importlib import import_module

_EXPORTS = {
    "SegmentStatistics": ("app.domain.stats", "SegmentStatistics"),
    "SegmentStatisticsError": ("app.domain.stats", "SegmentStatisticsError"),
    "compute_context_contrast": ("app.domain.stats", "compute_context_contrast"),
    "compute_peak_score": ("app.domain.stats", "compute_peak_score"),
    "compute_periodicity_score": ("app.domain.stats", "compute_periodicity_score"),
    "compute_residual_to_line": ("app.domain.stats", "compute_residual_to_line"),
    "compute_segment_statistics": ("app.domain.stats", "compute_segment_statistics"),
    "compute_sign_consistency": ("app.domain.stats", "compute_sign_consistency"),
    "compute_slope": ("app.domain.stats", "compute_slope"),
    "compute_variance": ("app.domain.stats", "compute_variance"),
    "ChunkAssignment": ("app.domain.chunk_assignment", "ChunkAssignment"),
    "assign_chunk_type": ("app.domain.chunk_assignment", "assign_chunk_type"),
    "ChunkScores": ("app.domain.chunk_scoring", "ChunkScores"),
    "ChunkScoringError": ("app.domain.chunk_scoring", "ChunkScoringError"),
    "compute_chunk_scores": ("app.domain.chunk_scoring", "compute_chunk_scores"),
    "ConstraintTargetSegment": ("app.domain.constraints", "ConstraintTargetSegment"),
    "ConstraintViolation": ("app.domain.constraints", "ConstraintViolation"),
    "evaluate_constraints": ("app.domain.constraints", "evaluate_constraints"),
    "OperationRegistryCatalog": ("app.domain.operations_registry", "OperationRegistryCatalog"),
    "build_operation_registry_catalog": ("app.domain.operations_registry", "build_operation_registry_catalog"),
    "get_legal_operations_for_chunk": ("app.domain.operations_registry", "get_legal_operations_for_chunk"),
    "OperationLegalityResult": ("app.domain.validation", "OperationLegalityResult"),
    "validate_operation_legality": ("app.domain.validation", "validate_operation_legality"),
    "StateSegment": ("app.domain.state_models", "StateSegment"),
    "SegmentationSnapshot": ("app.domain.state_models", "SegmentationSnapshot"),
    "SegmentationHistoryEntry": ("app.domain.state_models", "SegmentationHistoryEntry"),
    "SegmentationState": ("app.domain.state_models", "SegmentationState"),
    "SegmentationStateError": ("app.domain.state_models", "SegmentationStateError"),
    "create_snapshot_from_payload": ("app.domain.state_models", "create_snapshot_from_payload"),
    "SignalTransformError": ("app.domain.signal_transforms", "SignalTransformError"),
    "shift_level": ("app.domain.signal_transforms", "shift_level"),
    "change_slope": ("app.domain.signal_transforms", "change_slope"),
    "scale_spike": ("app.domain.signal_transforms", "scale_spike"),
    "suppress_spike": ("app.domain.signal_transforms", "suppress_spike"),
    "shift_event": ("app.domain.signal_transforms", "shift_event"),
    "remove_event": ("app.domain.signal_transforms", "remove_event"),
}


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module 'app.domain' has no attribute '{name}'")

    module_name, attribute_name = _EXPORTS[name]
    module = import_module(module_name)
    return getattr(module, attribute_name)


__all__ = list(_EXPORTS)
