"""Cohort confirmation service (REWORK-10).

Apply the same semantic operation across N series, aggregate per-series
deltas + flip rate + bootstrap confidence intervals so the user can
distinguish a real effect from cherry-picking.

Algorithm
---------

For each sample index in the cohort:
  1. Load values from the dataset registry (same path PredictionService
     uses, so the model "sees this" via REWORK-05's transform chain).
  2. Apply the scalar op (``amplify`` x → α·x, ``shift`` x → x + δ).
  3. Score baseline + edit via PredictionService.predict_values. Both
     calls go through the same softmax convention as the OUTPUT zone.
  4. δ_i = P(c*_baseline | edit) − P(c*_baseline | baseline). Flipped
     when argmax(current) ≠ argmax(baseline).

Aggregates:
  * flip_rate = mean(flipped_i)
  * mean_delta = mean(δ_i)
  * Percentile bootstrap CI (Efron 1979) at the requested confidence
    level on both flip_rate and mean_delta. B = 1000 resamples by
    default — iid resampling-with-replacement over the per-sample
    outcomes, since the samples are drawn from the dataset split (no
    temporal autocorrelation between samples to worry about).
  * Δ-magnitude histogram on a small bin grid for the OUTPUT panel.
  * biggest_mover_index = the sample whose |δ_i| is largest.

References
----------

- Efron, "Bootstrap Methods: Another Look at the Jackknife,"
  Annals of Statistics 7:1 (1979) — origin of the percentile bootstrap.
- Hall & Wilson, "Two Guidelines for Bootstrap Hypothesis Testing,"
  Biometrics 47:2 (1991) — calibration discussion.

Out-of-scope notes
------------------

For time-series-internal bootstrap (e.g. resampling time within one
series) the stationary / moving-block bootstrap in
``services/validation/mbb.py`` is the right tool. The cohort flow
resamples across *independent samples*, so the iid percentile
bootstrap is the correct method here.

The repo's session-level ``cherry_picking.py`` (VAL-013) is an
event-bus-driven detector for an ongoing user session — different
problem from the cohort statistical sanity check. The cohort response
returns the raw CIs and counts; the **client** derives a cherry-picking
caveat heuristic from CI-width / CI-crosses-zero rules so the user
sees an honest "is the effect real?" warning paired with the numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from app.schemas.cohort import (
    BootstrapCI,
    CohortAggregates,
    CohortApplyResponse,
    CohortSeriesResult,
)
from app.services.datasets import DatasetRegistry
from app.services.inference import InferenceServiceError, PredictionService


class CohortServiceError(RuntimeError):
    """Raised when the cohort service cannot run safely."""


_MAX_COHORT_SIZE = 64
_DEFAULT_BOOTSTRAP_ITERATIONS = 1000
_DEFAULT_CONFIDENCE = 0.95
_DELTA_HISTOGRAM_BINS = 9
_METHOD = "scalar-op cohort with iid percentile bootstrap"
_REFERENCE = (
    "Efron, Ann. Statist. 7:1 (1979) — percentile bootstrap; "
    "Hall & Wilson, Biometrics 47:2 (1991) — CI calibration"
)


@dataclass(frozen=True)
class CohortOpRequest:
    op_name: str
    params: dict


def _apply_scalar_op(values: np.ndarray, op_name: str, params: dict) -> np.ndarray:
    """Apply the cohort op to one series. Pure values-space transform."""
    if op_name == "amplify":
        alpha = float(params.get("alpha", 1.0))
        return values * alpha
    if op_name == "shift":
        delta = float(params.get("delta", 0.0))
        return values + delta
    raise CohortServiceError(
        f"Unsupported cohort op '{op_name}'. Supported: amplify, shift."
    )


def _validate_op_params(op_name: str, params: dict) -> None:
    if op_name == "amplify":
        alpha = params.get("alpha")
        if not isinstance(alpha, (int, float)) or isinstance(alpha, bool):
            raise CohortServiceError("Field 'op_params.alpha' must be a number for amplify.")
        if not np.isfinite(alpha) or alpha == 0:
            raise CohortServiceError("Field 'op_params.alpha' must be a non-zero finite number.")
        return
    if op_name == "shift":
        delta = params.get("delta")
        if not isinstance(delta, (int, float)) or isinstance(delta, bool):
            raise CohortServiceError("Field 'op_params.delta' must be a number for shift.")
        if not np.isfinite(delta):
            raise CohortServiceError("Field 'op_params.delta' must be a finite number.")
        return
    raise CohortServiceError(
        f"Unsupported cohort op '{op_name}'. Supported: amplify, shift."
    )


class CohortService:
    """Apply a scalar op across N samples and aggregate the outcomes.

    Reuses :class:`PredictionService.predict_values` for every prediction
    so the cohort answers come from the exact same scoring path as the
    OUTPUT zone — no parallel scoring code.
    """

    def __init__(
        self,
        dataset_registry: DatasetRegistry | None = None,
        prediction_service: PredictionService | None = None,
    ) -> None:
        self._dataset_registry = dataset_registry or DatasetRegistry()
        self._prediction_service = prediction_service or PredictionService(
            dataset_registry=self._dataset_registry,
        )

    def apply(
        self,
        *,
        artifact_id: str,
        dataset_name: str,
        split: str,
        sample_indices: Sequence[int],
        op_name: str,
        op_params: dict | None = None,
        bootstrap_iterations: int = _DEFAULT_BOOTSTRAP_ITERATIONS,
        confidence_level: float = _DEFAULT_CONFIDENCE,
        seed: int = 0,
    ) -> CohortApplyResponse:
        params = dict(op_params or {})
        _validate_op_params(op_name, params)

        if not sample_indices:
            raise CohortServiceError("sample_indices must be non-empty.")
        if len(sample_indices) > _MAX_COHORT_SIZE:
            raise CohortServiceError(
                f"Cohort size {len(sample_indices)} exceeds cap {_MAX_COHORT_SIZE}."
            )
        if split not in ("train", "test"):
            raise CohortServiceError(f"split must be 'train' or 'test'; got '{split}'.")

        dataset = self._dataset_registry.load_dataset(dataset_name)
        series = dataset.train_series if split == "train" else dataset.test_series
        n_samples = int(series.shape[0])

        per_series: list[CohortSeriesResult] = []
        for sample_index in sample_indices:
            if not isinstance(sample_index, int) or sample_index < 0 or sample_index >= n_samples:
                raise CohortServiceError(
                    f"sample_index {sample_index!r} is out of range for split '{split}' "
                    f"with {n_samples} samples."
                )

            sample = np.asarray(series[sample_index], dtype=np.float64).reshape(-1)
            edited = _apply_scalar_op(sample, op_name, params)

            try:
                baseline_pred = self._prediction_service.predict_values(
                    artifact_id=artifact_id, values=sample.tolist()
                )
                edit_pred = self._prediction_service.predict_values(
                    artifact_id=artifact_id, values=edited.tolist()
                )
            except InferenceServiceError as exc:
                raise CohortServiceError(str(exc)) from exc

            baseline_class = baseline_pred.predicted_label
            current_class = edit_pred.predicted_label
            baseline_prob = self._prob_for(baseline_pred.scores, baseline_class)
            current_prob = self._prob_for(edit_pred.scores, baseline_class)
            delta = float(current_prob - baseline_prob)
            flipped = current_class != baseline_class

            per_series.append(
                CohortSeriesResult(
                    sample_index=int(sample_index),
                    baseline_class=baseline_class,
                    current_class=current_class,
                    baseline_prob=float(baseline_prob),
                    current_prob=float(current_prob),
                    delta=delta,
                    flipped=bool(flipped),
                )
            )

        aggregates = self._aggregate(
            per_series,
            bootstrap_iterations=bootstrap_iterations,
            confidence_level=confidence_level,
            seed=seed,
        )

        return CohortApplyResponse(
            artifact_id=artifact_id,
            dataset_name=dataset_name,
            split=split,
            op_name=op_name,
            op_params=params,
            per_series=tuple(per_series),
            aggregates=aggregates,
            method=_METHOD,
            reference=_REFERENCE,
        )

    # ----- aggregation -------------------------------------------------

    def _aggregate(
        self,
        per_series: list[CohortSeriesResult],
        *,
        bootstrap_iterations: int,
        confidence_level: float,
        seed: int,
    ) -> CohortAggregates:
        total = len(per_series)
        flipped_count = sum(1 for r in per_series if r.flipped)
        deltas = np.asarray([r.delta for r in per_series], dtype=np.float64)
        flipped = np.asarray([1.0 if r.flipped else 0.0 for r in per_series], dtype=np.float64)

        flip_rate = float(flipped.mean()) if total else 0.0
        mean_delta = float(deltas.mean()) if total else 0.0

        flip_ci = self._percentile_bootstrap(
            flipped,
            statistic=lambda arr: float(arr.mean()),
            iterations=bootstrap_iterations,
            confidence_level=confidence_level,
            seed=seed,
        )
        delta_ci = self._percentile_bootstrap(
            deltas,
            statistic=lambda arr: float(arr.mean()),
            iterations=bootstrap_iterations,
            confidence_level=confidence_level,
            seed=seed + 1,
        )

        if total:
            biggest_index = int(np.argmax(np.abs(deltas)))
            biggest_mover_index = per_series[biggest_index].sample_index
        else:
            biggest_mover_index = None

        bin_edges, counts = self._delta_histogram(deltas)

        return CohortAggregates(
            flipped_count=flipped_count,
            total=total,
            flip_rate=flip_rate,
            flip_rate_ci=flip_ci,
            mean_delta=mean_delta,
            mean_delta_ci=delta_ci,
            delta_histogram_bin_edges=bin_edges,
            delta_histogram_counts=counts,
            biggest_mover_index=biggest_mover_index,
        )

    @staticmethod
    def _percentile_bootstrap(
        values: np.ndarray,
        *,
        statistic,
        iterations: int,
        confidence_level: float,
        seed: int,
    ) -> BootstrapCI:
        n = values.shape[0]
        if n == 0:
            return BootstrapCI(lower=0.0, upper=0.0, confidence_level=confidence_level, iterations=0)
        rng = np.random.default_rng(seed)
        stats = np.empty(iterations, dtype=np.float64)
        for i in range(iterations):
            sample = rng.choice(values, size=n, replace=True)
            stats[i] = statistic(sample)
        alpha = (1.0 - confidence_level) / 2.0
        lower = float(np.quantile(stats, alpha))
        upper = float(np.quantile(stats, 1.0 - alpha))
        return BootstrapCI(
            lower=lower,
            upper=upper,
            confidence_level=confidence_level,
            iterations=iterations,
        )

    @staticmethod
    def _delta_histogram(deltas: np.ndarray) -> tuple[tuple[float, ...], tuple[int, ...]]:
        if deltas.size == 0:
            return tuple(), tuple()
        # Symmetric bin grid spanning the max absolute delta so the
        # histogram is centred on zero and easy to read in the panel.
        max_abs = float(np.max(np.abs(deltas))) if deltas.size > 0 else 0.0
        if max_abs == 0.0:
            edges = np.linspace(-1.0, 1.0, _DELTA_HISTOGRAM_BINS + 1)
        else:
            edges = np.linspace(-max_abs, max_abs, _DELTA_HISTOGRAM_BINS + 1)
        counts, _ = np.histogram(deltas, bins=edges)
        return tuple(float(edge) for edge in edges), tuple(int(c) for c in counts)

    @staticmethod
    def _prob_for(scores, label: str) -> float:
        for score in scores:
            if score.label == label:
                return float(score.probability)
        return 0.0
