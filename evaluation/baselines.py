from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BaselineFlowDefinition:
    flow_id: str
    title: str
    description: str
    steps: tuple[str, ...]
    expected_event_types: tuple[str, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "flowId": self.flow_id,
            "title": self.title,
            "description": self.description,
            "steps": list(self.steps),
            "expectedEventTypes": list(self.expected_event_types),
            "notes": list(self.notes),
        }


def build_baseline_flow_catalog() -> tuple[BaselineFlowDefinition, ...]:
    return (
        BaselineFlowDefinition(
            flow_id="semantic-interface",
            title="Semantic Interface Reference Flow",
            description=(
                "Reference condition using the full semantic timeline, operation palette, warnings, and model suggestion workflow."
            ),
            steps=(
                "Open the assigned sample and review the current segmentation.",
                "Optionally load a model suggestion and decide whether to accept or override it.",
                "Complete the task using semantic split, merge, reclassify, or boundary edits.",
                "Export the session log at task completion.",
            ),
            expected_event_types=("operation_applied", "operation_rejected", "projection_applied", "suggestion_accepted", "suggestion_overridden"),
            notes=(
                "This is the primary interface condition for later pilot sessions.",
                "Suggestion events may be absent when the participant does not request model help.",
            ),
        ),
        BaselineFlowDefinition(
            flow_id="rule-only-baseline",
            title="Rule-Only Baseline Flow",
            description=(
                "Comparison condition that uses semantic editing and constraint feedback but avoids the suggestion workflow."
            ),
            steps=(
                "Open the assigned sample without requesting a model suggestion.",
                "Complete the task using manual semantic operations only.",
                "Rely on constraint feedback but do not use proposal acceptance or override controls.",
                "Export the session log at task completion.",
            ),
            expected_event_types=("operation_applied", "operation_rejected", "projection_applied"),
            notes=(
                "This baseline is chosen over raw waveform manipulation because it is already fully instrumented in the shipped product.",
                "Any suggestion_* event in this condition should be treated as protocol drift.",
            ),
        ),
    )
