from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import EvaluationCase, load_evaluation_case
from .metrics import (
    coerce_segments,
    compute_boundary_f1,
    compute_constraint_violation_rate,
    compute_covering,
    compute_macro_iou,
    compute_over_segmentation_rate,
    compute_prototype_drift_metrics,
)


@dataclass(frozen=True)
class EvaluationReport:
    schema_version: str
    fixture_id: str
    series_id: str
    segmentation_id: str
    notes: str
    metrics: dict[str, Any]
    unsupported_metrics: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "fixtureId": self.fixture_id,
            "seriesId": self.series_id,
            "segmentationId": self.segmentation_id,
            "notes": self.notes,
            "metrics": self.metrics,
            "unsupportedMetrics": self.unsupported_metrics,
        }


class EvaluationHarness:
    def evaluate_case(self, case: EvaluationCase) -> EvaluationReport:
        ground_truth_segments = coerce_segments(case.ground_truth, series_length=case.series_length)
        predicted_segments = coerce_segments(case.prediction, series_length=case.series_length)

        metrics = {
            "segmentationQuality": {
                "macroIoU": compute_macro_iou(
                    ground_truth_segments,
                    predicted_segments,
                    series_length=case.series_length,
                ),
                "boundaryF1": compute_boundary_f1(ground_truth_segments, predicted_segments, tolerance=0),
                "covering": compute_covering(ground_truth_segments, predicted_segments),
            },
            "stability": {
                "overSegmentationRate": compute_over_segmentation_rate(ground_truth_segments, predicted_segments),
                "prototypeDrift": compute_prototype_drift_metrics(case.prototype_drift_values),
            },
            "constraintAwareness": compute_constraint_violation_rate(case.session_log),
        }
        return EvaluationReport(
            schema_version="1.0.0",
            fixture_id=case.fixture_id,
            series_id=case.series_id,
            segmentation_id=case.segmentation_id,
            notes=case.notes,
            metrics=metrics,
            unsupported_metrics={
                "wari": "Not implemented in the MVP harness; requires the later pilot-analysis definition.",
                "sms": "Not implemented in the MVP harness; reserved for the later study metric pipeline.",
            },
        )


def evaluate_fixture_case(path: str | Path) -> EvaluationReport:
    harness = EvaluationHarness()
    return harness.evaluate_case(load_evaluation_case(path))
