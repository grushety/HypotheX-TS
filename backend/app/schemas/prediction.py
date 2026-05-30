from dataclasses import dataclass


@dataclass(frozen=True)
class PredictionScore:
    label: str
    score: float
    probability: float


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


@dataclass(frozen=True)
class AdHocPredictionResponse:
    """Prediction for an arbitrary value vector (counterfactual / edited series)."""

    artifact_id: str
    predicted_label: str
    scores: tuple[PredictionScore, ...]
    task: str = "classification"
