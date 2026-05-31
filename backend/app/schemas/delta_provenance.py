"""Schemas for Δ-provenance attribution (REWORK-09)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OpContribution:
    """One operation's signed contribution to the prediction Δ.

    `contribution` is in the same units as the OUTPUT-zone Δ (REWORK-02):
    the change in P(baseline_class) caused by leaving this op out vs. the
    full edited series. Positive means "this op moved the prediction
    further in the Δ direction" (away from the baseline class).
    """

    op_id: str
    op_label: str
    contribution: float


@dataclass(frozen=True)
class DeltaProvenanceResult:
    """Per-operation attribution of the total prediction Δ.

    The contributions sum to (total_delta − residual). The residual is
    surfaced honestly: it captures interactions between ops that the
    leave-one-out attribution cannot decompose. A small residual = clean
    additive decomposition; a large residual = ops interact and the
    attribution is order-dependent (see `method` caveat).

    Attributes:
        artifact_id:    Echo of the request.
        baseline_class: The model's prediction on the baseline series.
        total_delta:    P(baseline_class | current) − P(baseline_class | baseline).
        contributions:  One entry per op in the request order.
        residual:       total_delta − sum(contributions). Always returned.
        method:         Short label for the attribution algorithm.
        reference:      Paper / source for the algorithm.
    """

    artifact_id: str
    baseline_class: str
    total_delta: float
    contributions: tuple[OpContribution, ...]
    residual: float
    method: str
    reference: str
