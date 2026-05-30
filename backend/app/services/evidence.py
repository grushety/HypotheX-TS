"""Evidence service — orchestrates plausibility gauges for the EVIDENCE zone.

Surfaces three of the four gauges from the existing validation library:

  * **Proximity / Sparsity** → VAL-004 :func:`native_guide_validate`.
  * **Plausibility (yNN)**   → VAL-003 :class:`YnnPlausibilityValidator`.

The fourth gauge (validity rate) is derived client-side from the audit log,
which already carries per-edit constraint outcomes — no backend call needed.

Calibration files (``native_guide_thresholds_<dataset>.json`` and
``ynn_index_<dataset>.npz``) are *optional*. When a threshold cache is
missing, :func:`native_guide_validate` still returns proximity + sparsity
(``proximity_pct`` and ``too_dense`` are simply ``None`` / ``False``). When a
yNN cache is missing, the validator is built lazily from the dataset's
training set; the in-process LRU keeps the cost amortised across requests.

When a yNN index cannot be built at all (degenerate dataset shape, missing
labels), the route reports ``plausibility=None`` rather than raising. The
frontend renders that as ``n/a`` — honest "no data" rather than a fabricated
placeholder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from app.services.datasets import (
    DatasetNotFoundError,
    DatasetRegistry,
    DatasetRegistryError,
    LoadedDataset,
)
from app.services.validation.native_guide import (
    NativeGuideError,
    NativeGuideThresholds,
    load_thresholds as load_native_guide_thresholds,
    native_guide_validate,
)
from app.services.validation.ynn_plausibility import (
    YnnIndexError,
    YnnPlausibilityValidator,
)


class EvidenceServiceError(RuntimeError):
    """Raised when the evidence service cannot compute gauges safely."""


@dataclass(frozen=True)
class PlausibilityGauges:
    """Per-edit plausibility numbers for the four gauges (sans validity).

    All fields may be ``None`` when the underlying validator could not run
    (e.g. yNN index could not be built because the training set is
    degenerate). The frontend treats ``None`` as "n/a" — never as zero.

    Attributes:
        proximity:       VAL-004 DTW distance between baseline and current.
        sparsity:        VAL-004 fraction of timesteps left unchanged.
        proximity_pct:   Percentile rank of proximity vs the dataset's NUN
                         distribution. ``None`` when calibration is absent.
        too_dense:       VAL-004 density flag (only meaningful with
                         thresholds; ``False`` otherwise).
        plausibility:    VAL-003 yNN fraction (top-K neighbours sharing
                         target_class). ``None`` when no index could be
                         built.
        plausibility_k:  Number of neighbours actually evaluated.
        coverage_target: The conformal target embedded in the yNN config
                         (here ``K_eff / K_configured`` — for UI display).
    """

    proximity: float | None
    sparsity: float | None
    proximity_pct: float | None
    too_dense: bool
    plausibility: float | None
    plausibility_k: int | None


class EvidenceService:
    """Lazily builds and caches plausibility validators per dataset.

    The cache is per-process, not per-request — building the yNN index is
    O(n_train) work that we don't want to pay on every gauge refresh.
    """

    def __init__(self, dataset_registry: DatasetRegistry | None = None) -> None:
        self._dataset_registry = dataset_registry or DatasetRegistry()
        self._ynn_cache: dict[str, YnnPlausibilityValidator | None] = {}
        self._thresholds_cache: dict[str, NativeGuideThresholds | None] = {}

    def plausibility_gauges(
        self,
        *,
        dataset_name: str,
        baseline_values: Sequence[float],
        current_values: Sequence[float],
        target_class: object,
    ) -> PlausibilityGauges:
        baseline = np.asarray(baseline_values, dtype=np.float64).reshape(-1)
        current = np.asarray(current_values, dtype=np.float64).reshape(-1)
        if baseline.size == 0 or current.size == 0:
            raise EvidenceServiceError("baseline_values and current_values must be non-empty.")
        if baseline.shape != current.shape:
            raise EvidenceServiceError(
                f"baseline length {baseline.shape[0]} must match current length {current.shape[0]}."
            )

        thresholds = self._thresholds_for(dataset_name)
        ng = native_guide_validate(baseline, current, thresholds=thresholds)

        ynn_validator = self._ynn_for(dataset_name)
        if ynn_validator is None:
            return PlausibilityGauges(
                proximity=float(ng.proximity),
                sparsity=float(ng.sparsity),
                proximity_pct=None if ng.proximity_pct is None else float(ng.proximity_pct),
                too_dense=bool(ng.too_dense),
                plausibility=None,
                plausibility_k=None,
            )

        try:
            ynn_result = ynn_validator.ynn(current, target_class)
        except ValueError as exc:
            raise EvidenceServiceError(str(exc)) from exc
        plausibility = float(ynn_result.ynn)
        if not np.isfinite(plausibility):
            plausibility = None  # yNN reports NaN when K=0; surface as n/a.

        return PlausibilityGauges(
            proximity=float(ng.proximity),
            sparsity=float(ng.sparsity),
            proximity_pct=None if ng.proximity_pct is None else float(ng.proximity_pct),
            too_dense=bool(ng.too_dense),
            plausibility=plausibility,
            plausibility_k=int(ynn_result.K),
        )

    # ---- lazy caches -------------------------------------------------------

    def _thresholds_for(self, dataset_name: str) -> NativeGuideThresholds | None:
        if dataset_name in self._thresholds_cache:
            return self._thresholds_cache[dataset_name]
        try:
            thresholds = load_native_guide_thresholds(dataset_name)
        except NativeGuideError:
            thresholds = None
        self._thresholds_cache[dataset_name] = thresholds
        return thresholds

    def _ynn_for(self, dataset_name: str) -> YnnPlausibilityValidator | None:
        if dataset_name in self._ynn_cache:
            return self._ynn_cache[dataset_name]
        try:
            dataset = self._dataset_registry.load_dataset(dataset_name)
        except (DatasetNotFoundError, DatasetRegistryError):
            # A genuinely-bad dataset name should reach the route as a 404, not
            # silently cache as "no yNN." Only catch the validation-domain
            # errors here; everything else propagates.
            raise
        validator = self._build_ynn(dataset)
        self._ynn_cache[dataset_name] = validator
        return validator

    @staticmethod
    def _build_ynn(dataset: LoadedDataset) -> YnnPlausibilityValidator | None:
        try:
            series = np.asarray(dataset.train_series, dtype=np.float64)
            labels = np.asarray(dataset.train_labels)
            if series.ndim != 2 or series.shape[0] == 0 or labels.shape[0] != series.shape[0]:
                return None
            return YnnPlausibilityValidator(training_series=series, training_labels=labels)
        except (YnnIndexError, ValueError):
            return None
