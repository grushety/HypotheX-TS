from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any


class EvaluationMetricError(RuntimeError):
    """Raised when metric inputs are malformed."""


@dataclass(frozen=True)
class EvaluationSegment:
    segment_id: str
    start_index: int
    end_index: int
    label: str

    @property
    def length(self) -> int:
        return self.end_index - self.start_index + 1


def coerce_segments(segmentation_payload: dict[str, Any], *, series_length: int) -> tuple[EvaluationSegment, ...]:
    segments_payload = segmentation_payload.get("segments")
    if not isinstance(segments_payload, list) or not segments_payload:
        raise EvaluationMetricError("Segmentation payload must include a non-empty segments list.")

    segments = tuple(
        EvaluationSegment(
            segment_id=str(segment["segmentId"]),
            start_index=int(segment["startIndex"]),
            end_index=int(segment["endIndex"]),
            label=str(segment["label"]),
        )
        for segment in segments_payload
    )
    _validate_segments(segments, series_length=series_length)
    return segments


def compute_macro_iou(
    ground_truth: tuple[EvaluationSegment, ...],
    prediction: tuple[EvaluationSegment, ...],
    *,
    series_length: int,
) -> float:
    gt_labels = _expand_labels(ground_truth, series_length=series_length)
    pred_labels = _expand_labels(prediction, series_length=series_length)
    labels = sorted(set(gt_labels) | set(pred_labels))
    intersections: list[float] = []
    for label in labels:
        intersection = sum(1 for index in range(series_length) if gt_labels[index] == label and pred_labels[index] == label)
        union = sum(1 for index in range(series_length) if gt_labels[index] == label or pred_labels[index] == label)
        intersections.append(1.0 if union == 0 else intersection / union)
    return round(mean(intersections), 6)


def compute_boundary_f1(
    ground_truth: tuple[EvaluationSegment, ...],
    prediction: tuple[EvaluationSegment, ...],
    *,
    tolerance: int = 0,
) -> dict[str, float]:
    gt_boundaries = _boundary_indices(ground_truth)
    pred_boundaries = _boundary_indices(prediction)
    matched_gt: set[int] = set()
    true_positives = 0
    for boundary in pred_boundaries:
        matched_index = next(
            (
                gt_index
                for gt_index, gt_boundary in enumerate(gt_boundaries)
                if gt_index not in matched_gt and abs(gt_boundary - boundary) <= tolerance
            ),
            None,
        )
        if matched_index is None:
            continue
        matched_gt.add(matched_index)
        true_positives += 1

    precision = 1.0 if not pred_boundaries and not gt_boundaries else true_positives / max(1, len(pred_boundaries))
    recall = 1.0 if not pred_boundaries and not gt_boundaries else true_positives / max(1, len(gt_boundaries))
    f1 = 0.0 if precision + recall == 0 else (2 * precision * recall) / (precision + recall)
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def compute_covering(
    ground_truth: tuple[EvaluationSegment, ...],
    prediction: tuple[EvaluationSegment, ...],
) -> float:
    weighted_cover = 0.0
    total_length = sum(segment.length for segment in ground_truth)
    for gt_segment in ground_truth:
        best_overlap = max(_segment_iou(gt_segment, predicted_segment) for predicted_segment in prediction)
        weighted_cover += gt_segment.length * best_overlap
    return round(weighted_cover / max(1, total_length), 6)


def compute_over_segmentation_rate(
    ground_truth: tuple[EvaluationSegment, ...],
    prediction: tuple[EvaluationSegment, ...],
) -> float:
    expected_segments = max(1, len(ground_truth))
    return round(max(0.0, (len(prediction) - len(ground_truth)) / expected_segments), 6)


def compute_prototype_drift_metrics(drift_values: tuple[float, ...]) -> dict[str, float | int | None]:
    if not drift_values:
        return {
            "count": 0,
            "mean": None,
            "max": None,
        }
    return {
        "count": len(drift_values),
        "mean": round(mean(drift_values), 6),
        "max": round(max(drift_values), 6),
    }


def compute_constraint_violation_rate(session_log: dict[str, Any] | None) -> dict[str, float | int]:
    if not session_log:
        return {
            "operationEventCount": 0,
            "violatingEventCount": 0,
            "violationRate": 0.0,
        }

    events = session_log.get("events", [])
    if not isinstance(events, list):
        raise EvaluationMetricError("Session log events must be a list.")

    operation_events = [
        event
        for event in events
        if isinstance(event, dict) and str(event.get("eventType")) in {"operation_applied", "operation_rejected", "projection_applied"}
    ]
    violating_events = 0
    for event in operation_events:
        constraint_evaluation = event.get("constraintEvaluation")
        if isinstance(constraint_evaluation, dict) and str(constraint_evaluation.get("status")) in {"WARN", "FAIL"}:
            violating_events += 1
            continue
        operation_result = event.get("operationResult")
        if isinstance(operation_result, dict) and str(operation_result.get("status")) in {"WARN", "FAIL"}:
            violating_events += 1

    event_count = len(operation_events)
    return {
        "operationEventCount": event_count,
        "violatingEventCount": violating_events,
        "violationRate": round(violating_events / max(1, event_count), 6) if event_count else 0.0,
    }


def _expand_labels(segments: tuple[EvaluationSegment, ...], *, series_length: int) -> list[str]:
    labels = [""] * series_length
    for segment in segments:
        for index in range(segment.start_index, segment.end_index + 1):
            labels[index] = segment.label
    if any(label == "" for label in labels):
        raise EvaluationMetricError("Segments must cover the full series without gaps.")
    return labels


def _boundary_indices(segments: tuple[EvaluationSegment, ...]) -> list[int]:
    return [segment.end_index + 1 for segment in segments[:-1]]


def _segment_iou(left: EvaluationSegment, right: EvaluationSegment) -> float:
    overlap_start = max(left.start_index, right.start_index)
    overlap_end = min(left.end_index, right.end_index)
    if overlap_end < overlap_start:
        return 0.0
    intersection = overlap_end - overlap_start + 1
    union = left.length + right.length - intersection
    return intersection / max(1, union)


def _validate_segments(segments: tuple[EvaluationSegment, ...], *, series_length: int) -> None:
    previous_end = -1
    for segment in segments:
        if segment.start_index != previous_end + 1:
            raise EvaluationMetricError("Evaluation segments must be contiguous and non-overlapping.")
        if segment.end_index < segment.start_index:
            raise EvaluationMetricError(f"Segment '{segment.segment_id}' has endIndex before startIndex.")
        previous_end = segment.end_index
    if previous_end != series_length - 1:
        raise EvaluationMetricError("Evaluation segments must terminate at the final series index.")
