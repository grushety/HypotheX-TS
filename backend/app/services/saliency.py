"""Saliency / attribution service (REWORK-08).

Per-timestep attribution suggesting *where* the model is looking. Framed
as a what-if hypothesis — attribution proposes, editing confirms — so the
honest semantics are critical: we report per-timestep importance, the
method used, and the source paper so the user can interpret the heatmap
without confusion.

Method dispatch by model family
-------------------------------

The codebase ships exactly one inference family today: the prototype
(nearest-prototype) adapter. For that family we cannot use gradient-based
attribution (no analytic gradient), so we use the standard
**perturbation/occlusion** baseline:

  for each timestep t:
      x_masked      = x.copy()
      x_masked[t]   = mean(x)
      attribution[t] = P(baseline_class | x) − P(baseline_class | x_masked)

Mean-masking is a sensible "neutral" baseline for univariate float series
(it preserves the global scale of the input). The attribution is the drop
in baseline-class probability under the mask: positive means "masking this
timestep hurt the prediction → the model relied on it".

This is the perturbation analogue of the dynamic-mask method of
Crabbé & van der Schaar (ICML 2021) without the learned-mask
optimisation — a cheap, model-agnostic first pass. When a differentiable
adapter (TCN/FCN with gradients exposed) lands, this module's dispatch
should route to **Temporal Saliency Rescaling** over Integrated Gradients
(Ismail et al. NeurIPS 2020) for that family.

References
----------

- Ismail, Gunady, Corrada Bravo, Feizi, "Benchmarking Deep Learning
  Interpretability in Time Series Predictions," NeurIPS 2020 — establishes
  that naive saliency conflates time and feature importance and
  introduces Temporal Saliency Rescaling (TSR).
- Crabbé, van der Schaar, "Explaining Time Series Predictions with
  Dynamic Masks," ICML 2021 — SOTA model-agnostic perturbation method;
  our occlusion is the cheap special case (uniform per-timestep mask).
- Zeiler, Fergus, "Visualizing and Understanding Convolutional Networks,"
  ECCV 2014 §3.1 — origin of perturbation/occlusion attribution as a
  visualisation technique.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.schemas.saliency import SaliencyResult
from app.services.inference import PrototypeInferenceAdapter
from app.services.models import ModelArtifactHandle, ModelRegistry


class SaliencyServiceError(RuntimeError):
    """Raised when saliency cannot be computed safely."""


_MAX_VALUES = 65_536


@dataclass(frozen=True)
class _OcclusionMethod:
    name: str = "occlusion (mean-masked, prototype)"
    reference: str = (
        "Zeiler & Fergus, ECCV 2014 §3.1 (occlusion); "
        "Crabbé & van der Schaar, ICML 2021 (dynamic masks, uniform mask special case)"
    )


_PROTOTYPE_METHOD = _OcclusionMethod()


class SaliencyService:
    """Compute per-timestep saliency for the current inference family.

    For now: prototype family only → occlusion. The dispatch is centralised
    in :meth:`compute_saliency` so adding a TSR/IG path for a future
    differentiable family is a single ``elif`` plus a new method module.
    """

    def __init__(self, model_registry: ModelRegistry | None = None) -> None:
        self._model_registry = model_registry or ModelRegistry()
        # Re-use the inference adapter for prototype loading + softmax scoring
        # so saliency and prediction stay in lockstep on the same metadata.
        # The `family` argument is cosmetic — only `predict()` is invoked here.
        self._adapter = PrototypeInferenceAdapter(family="prototype")

    def compute_saliency(
        self,
        *,
        artifact_id: str,
        values: list[float] | np.ndarray,
    ) -> SaliencyResult:
        if values is None:
            raise SaliencyServiceError("values is required.")
        x = np.asarray(values, dtype=np.float64).reshape(-1)
        if x.size == 0:
            raise SaliencyServiceError("values must be non-empty.")
        if x.size > _MAX_VALUES:
            raise SaliencyServiceError(
                f"values length {x.size} exceeds cap {_MAX_VALUES}."
            )

        handle = self._model_registry.load_artifact(artifact_id)
        # Today every family routes through PrototypeInferenceAdapter; when a
        # differentiable family (e.g. TCN/FCN with gradient access) ships,
        # dispatch on `handle.artifact.family` here and route to a TSR/IG
        # path. Keeping the dispatch single-armed for now so the unused
        # branch can't rot in maintenance.
        attribution, baseline_class = self._occlusion_prototype(handle, x)

        return SaliencyResult(
            artifact_id=artifact_id,
            baseline_class=baseline_class,
            attribution=tuple(float(v) for v in attribution),
            method=_PROTOTYPE_METHOD.name,
            reference=_PROTOTYPE_METHOD.reference,
        )

    def _occlusion_prototype(
        self,
        handle: ModelArtifactHandle,
        x: np.ndarray,
    ) -> tuple[np.ndarray, str]:
        # Baseline prediction on the unmasked input. Re-use the adapter so the
        # softmax convention matches the prediction route exactly.
        baseline_scores, baseline_probs = self._adapter.predict(handle, x)
        baseline_index = int(np.argmax(baseline_scores))
        label_space = handle.artifact.label_space
        if len(label_space) != len(baseline_scores):
            raise SaliencyServiceError(
                f"Model artifact '{handle.artifact.artifact_id}' label space size "
                f"{len(label_space)} does not match score count {len(baseline_scores)}."
            )
        baseline_class = label_space[baseline_index]
        baseline_prob = float(baseline_probs[baseline_index])

        mean_value = float(np.mean(x))
        # Defensive copy so service callers that hand us a numpy array don't
        # see their array mutated by the masking loop. The route already
        # makes a copy via np.asarray on a list, but direct callers may not.
        working = x.copy()
        attribution = np.empty(working.shape[0], dtype=np.float64)
        for t in range(working.shape[0]):
            original = working[t]
            working[t] = mean_value
            try:
                _, masked_probs = self._adapter.predict(handle, working)
            finally:
                working[t] = original
            attribution[t] = baseline_prob - float(masked_probs[baseline_index])
        return attribution, baseline_class
