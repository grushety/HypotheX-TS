from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.domain_config import load_domain_config
from app.services.suggestion.segment_encoder import SegmentEncoderConfig, SegmentEncodingError, encode_segment


class PrototypeClassifierError(RuntimeError):
    """Raised when prototype classification cannot be completed safely."""


@dataclass(frozen=True)
class PrototypeClassifierConfig:
    temperature: float = 0.2
    missing_label_similarity: float = -1.0


@dataclass(frozen=True)
class LabeledSupportSegment:
    label: str
    values: tuple[tuple[float, ...], ...] | tuple[float, ...] | list[list[float]] | list[float]


@dataclass(frozen=True)
class PrototypeClassification:
    label: str
    confidence: float
    probabilities: dict[str, float]
    embedding: tuple[float, ...]


class PrototypeChunkClassifier:
    def __init__(
        self,
        *,
        active_labels: tuple[str, ...] | None = None,
        encoder_config: SegmentEncoderConfig | None = None,
        classifier_config: PrototypeClassifierConfig | None = None,
    ):
        self._active_labels = active_labels or load_domain_config().active_chunk_types
        self._encoder_config = encoder_config or SegmentEncoderConfig()
        self._classifier_config = classifier_config or PrototypeClassifierConfig()

    @property
    def active_labels(self) -> tuple[str, ...]:
        return self._active_labels

    def build_prototypes(
        self,
        support_segments: list[LabeledSupportSegment] | tuple[LabeledSupportSegment, ...],
    ) -> dict[str, np.ndarray]:
        if not support_segments:
            raise PrototypeClassifierError("Prototype classifier requires at least one support segment.")

        grouped: dict[str, list[np.ndarray]] = {label: [] for label in self._active_labels}
        for support_segment in support_segments:
            if support_segment.label not in grouped:
                raise PrototypeClassifierError(
                    f"Support segment label '{support_segment.label}' is not active in the domain config."
                )
            try:
                embedding = encode_segment(support_segment.values, self._encoder_config).as_array()
            except SegmentEncodingError as exc:
                raise PrototypeClassifierError(str(exc)) from exc
            grouped[support_segment.label].append(embedding)

        prototypes: dict[str, np.ndarray] = {}
        for label, embeddings in grouped.items():
            if not embeddings:
                continue
            mean_embedding = np.mean(np.stack(embeddings, axis=0), axis=0)
            prototypes[label] = _normalize(mean_embedding)
        return prototypes

    def classify_segment(
        self,
        values: tuple[tuple[float, ...], ...] | tuple[float, ...] | list[list[float]] | list[float],
        *,
        prototypes: dict[str, np.ndarray],
    ) -> PrototypeClassification:
        if self._classifier_config.temperature <= 0:
            raise PrototypeClassifierError("Prototype classifier temperature must be greater than 0.")

        try:
            embedding = encode_segment(values, self._encoder_config).as_array()
        except SegmentEncodingError as exc:
            raise PrototypeClassifierError(str(exc)) from exc

        similarities: dict[str, float] = {}
        for label in self._active_labels:
            prototype = prototypes.get(label)
            if prototype is None:
                similarities[label] = self._classifier_config.missing_label_similarity
                continue
            similarities[label] = float(np.dot(embedding, prototype))

        probabilities = _softmax_probabilities(similarities, self._classifier_config.temperature)
        predicted_label = max(probabilities, key=probabilities.get)
        return PrototypeClassification(
            label=predicted_label,
            confidence=probabilities[predicted_label],
            probabilities=probabilities,
            embedding=tuple(float(value) for value in embedding),
        )


def build_default_support_segments(
    active_labels: tuple[str, ...] | None = None,
    *,
    length: int = 24,
) -> list[LabeledSupportSegment]:
    if length < 8:
        raise PrototypeClassifierError("Default support segments require a minimum length of 8.")

    labels = active_labels or load_domain_config().active_chunk_types
    mid = length // 2
    quarter = max(2, length // 4)

    templates = {
        "trend": [index / max(1, length - 1) for index in range(length)],
        "plateau": [0.25] * length,
        "spike": ([0.0] * (mid - 1)) + [3.0] + ([0.0] * (length - mid)),
        "event": ([0.0] * quarter) + ([1.0] * (length - (quarter * 2))) + ([0.0] * quarter),
        "transition": ([0.0] * quarter)
        + [index / max(1, (length - (quarter * 2)) - 1) for index in range(length - (quarter * 2))]
        + ([1.0] * quarter),
        "periodic": [float(np.sin(index * (2 * np.pi / 6))) for index in range(length)],
    }

    support_segments: list[LabeledSupportSegment] = []
    for label in labels:
        if label not in templates:
            raise PrototypeClassifierError(f"No default support template is available for label '{label}'.")
        support_segments.append(
            LabeledSupportSegment(
                label=label,
                values=templates[label],
            )
        )
    return support_segments


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-8:
        raise PrototypeClassifierError("Prototype classifier received a near-zero prototype vector.")
    return vector / norm


def _softmax_probabilities(similarities: dict[str, float], temperature: float) -> dict[str, float]:
    labels = list(similarities)
    logits = np.asarray([similarities[label] / temperature for label in labels], dtype=np.float64)
    stabilized = logits - float(np.max(logits))
    weights = np.exp(stabilized)
    denominator = float(np.sum(weights))
    if denominator <= 0:
        raise PrototypeClassifierError("Prototype classifier could not normalize similarity scores.")
    probabilities = weights / denominator
    return {label: float(probability) for label, probability in zip(labels, probabilities, strict=True)}
