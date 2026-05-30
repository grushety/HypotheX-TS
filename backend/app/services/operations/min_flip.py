"""Min-flip probe — smallest edit that flips a nearest-prototype classifier.

REWORK-07.

Algorithm
---------

For a nearest-prototype classifier ``M(x) = argmin_c ‖x − p_c‖²`` the
decision boundary between classes c* (current prediction) and c′ is the
**perpendicular bisector** of the line segment connecting p_{c*} and p_{c′}.
This is a hyperplane

    H_{c*,c′} = { x : ‖x − p_{c*}‖² = ‖x − p_{c′}‖² }
              = { x : (p_{c*} − p_{c′}) · x = (‖p_{c*}‖² − ‖p_{c′}‖²) / 2 }

The signed distance from a point ``x`` (currently classified as c*) to that
hyperplane is

    d(x; c′) = ((p_{c*} − p_{c′}) · x − (‖p_{c*}‖² − ‖p_{c′}‖²) / 2)
                / ‖p_{c*} − p_{c′}‖

which is positive when x is on the c*-side. The smallest L2 perturbation
that crosses the boundary toward c′ is therefore

    Δx_{c′} = (d(x; c′) + ε) · −(p_{c*} − p_{c′}) / ‖p_{c*} − p_{c′}‖

The minimum over c′ ≠ c* of ``d(x; c′)`` is the **distance to the decision
boundary**; the corresponding edit is the closed-form L2 minimal flip.

**Binary vs multi-class.** For binary classifiers (2 prototypes) this is
exact — the bisector IS the global decision boundary. For ≥3 classes the
``min over c′`` picks the nearest *pairwise* bisector, which is a lower
bound on the L2 distance to a true class-flip: the edit could land in a
*third* class's Voronoi cell. The implementation re-classifies the
resulting edit and downgrades to ``found=False`` (with a reason) when the
nearest-bisector edit doesn't actually flip into ``flipped_class``.

Reference: Wachter, Mittelstadt, Russell, "Counterfactual Explanations
without Opening the Black Box," HJLT 31 (2018), arXiv:1711.00399 §3.1
(Eq. 3). For models without an analytic boundary (e.g. deep CNNs), a
coefficient-space gradient or NSGA-II search over the segment
decomposition would be required instead; see ``cf_coordinator.py`` for
the decomposition-first edit path that future work can plug into.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.schemas.min_flip import MinFlipConfig, MinFlipResult
from app.services.inference import PrototypeInferenceAdapter
from app.services.models import ModelArtifactHandle, ModelRegistry


class MinFlipServiceError(RuntimeError):
    """Raised when the min-flip probe cannot run safely on its inputs."""


@dataclass(frozen=True)
class _CandidateFlip:
    target_class_index: int
    distance: float
    direction: np.ndarray


_METHOD_NAME = "closed-form L2-minimal flip (nearest-prototype geometry)"
_REFERENCE = (
    "Wachter, Mittelstadt, Russell, HJLT 31:841 (2018), arXiv:1711.00399 §3.1 Eq. 3"
)


class MinFlipService:
    """Find the smallest L2 edit that flips a nearest-prototype classifier.

    Reuses the prototype-vector access path of :class:`PrototypeInferenceAdapter`
    (read metadata.json → resample to the user's input length). No new
    optimizer dependency — pure numpy + the existing inference machinery.
    """

    def __init__(
        self,
        model_registry: ModelRegistry | None = None,
        config: MinFlipConfig | None = None,
    ) -> None:
        self._model_registry = model_registry or ModelRegistry()
        self._config = config or MinFlipConfig()
        # Reuse the adapter's prototype-vector loader; the family string is
        # cosmetic here (it only ever picks `_normalize_prototypes`).
        self._adapter = PrototypeInferenceAdapter(family="min_flip")

    def find_minimal_flip(
        self,
        *,
        artifact_id: str,
        baseline_values: list[float] | np.ndarray,
    ) -> MinFlipResult:
        baseline = np.asarray(baseline_values, dtype=np.float64).reshape(-1)
        if baseline.size == 0:
            raise MinFlipServiceError("baseline_values must be non-empty.")
        if baseline.size > self._config.max_values:
            raise MinFlipServiceError(
                f"baseline_values length {baseline.size} exceeds cap {self._config.max_values}."
            )

        handle = self._model_registry.load_artifact(artifact_id)
        prototypes, label_space = self._load_prototypes(handle, target_length=baseline.size)

        # Classify the baseline (argmin of L2 distance).
        sq_dists = np.sum((prototypes - baseline) ** 2, axis=1)
        baseline_index = int(np.argmin(sq_dists))
        baseline_class = label_space[baseline_index]
        p_star = prototypes[baseline_index]

        candidates: list[_CandidateFlip] = []
        coincident_count = 0
        for index in range(prototypes.shape[0]):
            if index == baseline_index:
                continue
            p_prime = prototypes[index]
            normal = p_star - p_prime  # points away from the c′ half-space
            norm = float(np.linalg.norm(normal))
            if norm < 1e-12:
                # Coincident prototypes — no boundary is well-defined for c′.
                coincident_count += 1
                continue
            offset = (float(np.dot(p_star, p_star)) - float(np.dot(p_prime, p_prime))) / 2.0
            signed_distance = float((np.dot(normal, baseline) - offset) / norm)
            if not math.isfinite(signed_distance):
                continue
            # The baseline sits on the c*-side, so signed_distance must be
            # >= 0. Strictly > 0 because = 0 would mean baseline already
            # sits ON the bisector (tied), which is also no-flip-needed.
            if signed_distance <= 0:
                continue
            direction = -normal / norm  # unit vector pointing toward c′
            candidates.append(
                _CandidateFlip(
                    target_class_index=index,
                    distance=signed_distance,
                    direction=direction,
                )
            )

        if not candidates:
            if coincident_count > 0:
                reason = (
                    "No reachable decision boundary — every non-baseline prototype "
                    "is coincident with the baseline prototype."
                )
            else:
                reason = (
                    "No reachable decision boundary — every candidate flip degenerates "
                    "(baseline lies on the bisector or numerical instability)."
                )
            return MinFlipResult(
                found=False,
                artifact_id=artifact_id,
                baseline_class=baseline_class,
                flipped_class=None,
                distance=None,
                edit_values=tuple(),
                method=_METHOD_NAME,
                reference=_REFERENCE,
                reason=reason,
            )

        # Closest decision boundary among all non-baseline classes.
        best = min(candidates, key=lambda c: c.distance)
        edit = baseline + (best.distance + self._config.epsilon) * best.direction

        # For ≥3-class settings the nearest-bisector edit can land in a third
        # Voronoi cell rather than `flipped_class`. Re-classify and surface
        # `found=False` honestly when that happens.
        edit_sq_dists = np.sum((prototypes - edit) ** 2, axis=1)
        landed_index = int(np.argmin(edit_sq_dists))
        if landed_index != best.target_class_index:
            return MinFlipResult(
                found=False,
                artifact_id=artifact_id,
                baseline_class=baseline_class,
                flipped_class=None,
                distance=None,
                edit_values=tuple(),
                method=_METHOD_NAME,
                reference=_REFERENCE,
                reason=(
                    f"Nearest-bisector edit lands in class '{label_space[landed_index]}' "
                    f"(Voronoi-cell containment) rather than '{label_space[best.target_class_index]}'. "
                    "A coefficient-space search would be required to escape this local minimum."
                ),
            )

        return MinFlipResult(
            found=True,
            artifact_id=artifact_id,
            baseline_class=baseline_class,
            flipped_class=label_space[best.target_class_index],
            distance=best.distance,
            edit_values=tuple(float(v) for v in edit),
            method=_METHOD_NAME,
            reference=_REFERENCE,
        )

    def _load_prototypes(
        self,
        handle: ModelArtifactHandle,
        *,
        target_length: int,
    ) -> tuple[np.ndarray, tuple[str, ...]]:
        metadata = _read_metadata(handle.metadata_path)
        if metadata.get("inference_adapter") != "nearest_prototype":
            raise MinFlipServiceError(
                f"Model artifact '{handle.artifact.artifact_id}' is not a nearest-prototype "
                "classifier; min-flip needs an analytic boundary."
            )
        prototype_vectors = metadata.get("prototype_vectors")
        if not isinstance(prototype_vectors, list) or not prototype_vectors:
            raise MinFlipServiceError(
                f"Model artifact '{handle.artifact.artifact_id}' has no prototype_vectors."
            )

        # Re-use the inference adapter's normalization (handles resample to
        # target_length and validates shape consistency).
        prototypes = self._adapter._normalize_prototypes(  # noqa: SLF001 — shared loader
            prototype_vectors,
            target_length=target_length,
            artifact_id=handle.artifact.artifact_id,
        )

        label_space = tuple(handle.artifact.label_space)
        if len(label_space) != prototypes.shape[0]:
            raise MinFlipServiceError(
                f"Model artifact '{handle.artifact.artifact_id}' label space size "
                f"{len(label_space)} does not match prototype count {prototypes.shape[0]}."
            )
        return prototypes, label_space


def _read_metadata(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MinFlipServiceError(f"Model artifact metadata is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MinFlipServiceError(f"Model artifact metadata is not valid JSON: {path}") from exc
