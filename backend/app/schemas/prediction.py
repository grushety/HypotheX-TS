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
