from dataclasses import dataclass, field


@dataclass(frozen=True)
class PredictionScore:
    label: str
    score: float
    probability: float


@dataclass(frozen=True)
class PredictionTransform:
    """One ordered step of the input preprocessing applied by PredictionService
    before the model adapter scores the sample.

    REWORK-05 surfaces this in the EVIDENCE-zone Fidelity strip so the user
    can verify the edited series reaches the model intact. The transform list
    IS the transform path — there is no parallel JS re-implementation.

    Shapes are reported as integer tuples (e.g. `(1, 150)` → `(150,)` for
    flatten). The fields `before_shape` / `after_shape` may be the same
    when the transform only changes dtype (e.g. cast_float64).
    """

    name: str
    params: dict
    before_shape: tuple[int, ...]
    after_shape: tuple[int, ...]


@dataclass(frozen=True)
class PredictionResponse:
    dataset_name: str
    artifact_id: str
    split: str
    sample_index: int
    predicted_label: str
    true_label: str | None
    scores: tuple[PredictionScore, ...]
    task: str = "classification"
    transforms: tuple[PredictionTransform, ...] = field(default_factory=tuple)
    model_input_length: int | None = None


@dataclass(frozen=True)
class AdHocPredictionResponse:
    """Prediction for an arbitrary value vector (counterfactual / edited series)."""

    artifact_id: str
    predicted_label: str
    scores: tuple[PredictionScore, ...]
    task: str = "classification"
    transforms: tuple[PredictionTransform, ...] = field(default_factory=tuple)
    model_input_length: int | None = None
