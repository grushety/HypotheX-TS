"""Schemas for the saliency overlay (REWORK-08)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SaliencyResult:
    """Per-timestep attribution aligned to the input series.

    Each entry of ``attribution`` is the model's predicted-class probability
    drop when that timestep is masked to the input's mean — i.e. the
    "informativeness" of that point for the prediction. Larger positive
    values mean the model relied on that timestep more heavily. Negative
    values indicate timesteps whose masking actually improved the model's
    confidence in the baseline class (sometimes the case for outlier
    points fighting the prediction).

    Attributes:
        artifact_id:    Echo of the request — which model produced this.
        baseline_class: The model's prediction on the unmasked input.
        attribution:    Per-timestep score, length == len(input values).
        method:         Short label for the algorithm used (e.g.
                        "occlusion (mean-masked, prototype)").
        reference:      Paper / source the algorithm was lifted from.
    """

    artifact_id: str
    baseline_class: str
    attribution: tuple[float, ...]
    method: str
    reference: str
