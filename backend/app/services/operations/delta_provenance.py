"""Δ-provenance attribution service (REWORK-09).

Links the operation/edit sequence to the OUTPUT-zone Δ so the scientist
can read *which edit caused which movement*. The honest framing matters:
"I changed X and it moved" is NOT the same as "the model depends on X".

Algorithm — Leave-One-Out (LOO) over operations
-----------------------------------------------

Given:
  * baseline_values  v_0
  * current_values   v_N  (after N applied operations)
  * op_deltas        Δ_1, …, Δ_N  where Δ_i is the values-space change
                     that operation i contributed (v_i − v_{i-1})

For each op i:
  * leave_out_i   = v_N − Δ_i  (the current series with op i's
                                 perturbation algebraically removed)
  * contribution  = P(c* | v_N) − P(c* | leave_out_i)

where c* = the baseline-class label that the OUTPUT Δ tracks (matches
REWORK-02's predDelta convention). Positive contribution = "this op
moved the prediction in the Δ direction" (away from the baseline class).

Caveats — surfaced in the response `method` field
-------------------------------------------------

1. **Order-dependent.** Δ_i depends on the state v_{i-1} at the moment
   op i was applied. Replaying ops in a different order would produce a
   different LOO decomposition. The realized session order is what we
   attribute.
2. **Ignores higher-order interactions.** When two ops touch the same
   timesteps, their combined effect can be larger or smaller than the
   sum of their LOO contributions. The residual `total_delta −
   Σ contribution` is returned explicitly so the user can see how much
   of the Δ is left unexplained — a large residual means the ops
   interact and a Shapley-style attribution would tell a different
   story.
3. **Causal-misattribution honesty.** Per the ticket: "I changed X and
   it moved" ≠ "the model depends on X". LOO answers the first
   question, not the second. Pair with the REWORK-08 saliency overlay
   to triangulate.

Reference
---------

Štrumbelj & Kononenko, "An efficient explanation of individual
classifications using game theory," J. Machine Learning Research 11
(2010), §3 — establishes leave-one-out / marginal-contribution
attribution as the canonical baseline for feature-attribution problems
(and the cheap special case of Shapley when ordering is fixed). The
SOTA upgrade is a sampled Shapley over operation orderings (Lundberg &
Lee NeurIPS 2017, KernelSHAP); REWORK-09's docstring marks it as a
future opt-in path when op count and time budget allow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from app.schemas.delta_provenance import DeltaProvenanceResult, OpContribution
from app.services.inference import InferenceServiceError, PredictionService


class DeltaProvenanceError(RuntimeError):
    """Raised when provenance cannot be computed safely."""


_METHOD = "leave-one-out over operations"
_REFERENCE = (
    "Štrumbelj & Kononenko, JMLR 11 (2010) §3 (LOO marginal contribution); "
    "SOTA upgrade: Lundberg & Lee NeurIPS 2017 KernelSHAP"
)


@dataclass(frozen=True)
class OpDelta:
    """One operation's values-space perturbation, paired with its label."""

    op_id: str
    op_label: str
    values_delta: tuple[float, ...]


class DeltaProvenanceService:
    """Attribute the total prediction Δ to each applied operation.

    Reuses :class:`PredictionService.predict_values` for every required
    intermediate prediction — same model artifact, same softmax, same
    transform chain reported by the Fidelity strip (REWORK-05).
    """

    def __init__(self, prediction_service: PredictionService | None = None) -> None:
        self._prediction_service = prediction_service or PredictionService()

    def attribute(
        self,
        *,
        artifact_id: str,
        baseline_values: Sequence[float],
        current_values: Sequence[float],
        op_deltas: list[OpDelta],
    ) -> DeltaProvenanceResult:
        baseline = np.asarray(baseline_values, dtype=np.float64).reshape(-1)
        current = np.asarray(current_values, dtype=np.float64).reshape(-1)
        if baseline.size == 0 or current.size == 0:
            raise DeltaProvenanceError("baseline_values and current_values must be non-empty.")
        if baseline.shape != current.shape:
            raise DeltaProvenanceError(
                f"baseline length {baseline.shape[0]} must match current length {current.shape[0]}."
            )

        # 1. Score baseline + current to compute the total Δ.
        try:
            baseline_pred = self._prediction_service.predict_values(
                artifact_id=artifact_id, values=baseline.tolist()
            )
            current_pred = self._prediction_service.predict_values(
                artifact_id=artifact_id, values=current.tolist()
            )
        except InferenceServiceError as exc:
            raise DeltaProvenanceError(str(exc)) from exc

        baseline_class = baseline_pred.predicted_label
        baseline_class_index = _score_index_for_label(baseline_pred.scores, baseline_class)
        baseline_prob = baseline_pred.scores[baseline_class_index].probability
        current_prob = self._prob_for(current_pred.scores, baseline_class)
        total_delta = float(current_prob - baseline_prob)

        # 2. Leave-one-out: for each op, predict on (current − Δ_i) and
        # compute its signed contribution.
        contributions: list[OpContribution] = []
        for op in op_deltas:
            delta = np.asarray(op.values_delta, dtype=np.float64).reshape(-1)
            if delta.shape != current.shape:
                raise DeltaProvenanceError(
                    f"op '{op.op_id}' values_delta length {delta.shape[0]} does not match series length {current.shape[0]}."
                )
            leave_out = current - delta
            try:
                leave_out_pred = self._prediction_service.predict_values(
                    artifact_id=artifact_id, values=leave_out.tolist()
                )
            except InferenceServiceError as exc:
                raise DeltaProvenanceError(str(exc)) from exc
            leave_out_prob = self._prob_for(leave_out_pred.scores, baseline_class)
            contribution = float(current_prob - leave_out_prob)
            contributions.append(
                OpContribution(
                    op_id=op.op_id,
                    op_label=op.op_label,
                    contribution=contribution,
                )
            )

        sum_contribs = sum(c.contribution for c in contributions)
        residual = float(total_delta - sum_contribs)

        return DeltaProvenanceResult(
            artifact_id=artifact_id,
            baseline_class=baseline_class,
            total_delta=total_delta,
            contributions=tuple(contributions),
            residual=residual,
            method=_METHOD,
            reference=_REFERENCE,
        )

    @staticmethod
    def _prob_for(scores, label: str) -> float:
        for score in scores:
            if score.label == label:
                return float(score.probability)
        return 0.0


def _score_index_for_label(scores, label: str) -> int:
    for index, score in enumerate(scores):
        if score.label == label:
            return index
    raise DeltaProvenanceError(f"Baseline class '{label}' is not in the model's label space.")
