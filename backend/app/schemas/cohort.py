"""Schemas for the cohort confirmation mode (REWORK-10)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CohortSeriesResult:
    """Per-series outcome of applying the cohort op.

    `delta` is the signed change in baseline-class probability — same
    sign convention as REWORK-02's OUTPUT-zone Δ. `flipped` is True when
    the argmax class changed between baseline and current.
    """

    sample_index: int
    baseline_class: str
    current_class: str
    baseline_prob: float
    current_prob: float
    delta: float
    flipped: bool


@dataclass(frozen=True)
class BootstrapCI:
    """Percentile-bootstrap confidence interval.

    `lower` and `upper` are the percentile bounds at the requested
    confidence level. `iterations` is the number of resamples used (B).
    """

    lower: float
    upper: float
    confidence_level: float
    iterations: int


@dataclass(frozen=True)
class CohortAggregates:
    flipped_count: int
    total: int
    flip_rate: float
    flip_rate_ci: BootstrapCI
    mean_delta: float
    mean_delta_ci: BootstrapCI
    delta_histogram_bin_edges: tuple[float, ...]
    delta_histogram_counts: tuple[int, ...]
    biggest_mover_index: int | None


@dataclass(frozen=True)
class CohortApplyResponse:
    """Top-level response for `POST /api/cohort/apply`."""

    artifact_id: str
    dataset_name: str
    split: str
    op_name: str
    op_params: dict
    per_series: tuple[CohortSeriesResult, ...]
    aggregates: CohortAggregates
    method: str
    reference: str
