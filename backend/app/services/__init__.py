from importlib import import_module

_EXPORTS = {
    "CompatibilityValidator": ("app.services.compatibility", "CompatibilityValidator"),
    "ConstraintEngine": ("app.services.constraint_engine", "ConstraintEngine"),
    "DatasetRegistry": ("app.services.datasets", "DatasetRegistry"),
    "ModelRegistry": ("app.services.models", "ModelRegistry"),
    "PredictionService": ("app.services.inference", "PredictionService"),
    "SegmentationStateService": ("app.services.segmentation_state", "SegmentationStateService"),
    "StructuralOperationsService": ("app.services.operations.structural", "StructuralOperationsService"),
}


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module 'app.services' has no attribute '{name}'")

    module_name, attribute_name = _EXPORTS[name]
    module = import_module(module_name)
    return getattr(module, attribute_name)


__all__ = list(_EXPORTS)
