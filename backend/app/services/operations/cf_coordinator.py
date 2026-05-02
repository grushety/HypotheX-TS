"""CF synthesis coordinator — decomposition-first architecture (OP-050).

Orchestrates the decomposition-first counterfactual synthesis loop:

  1. Assert the segment has a fitted decomposition blob.
  2. Deepcopy the blob; apply the chosen Tier-2 op to produce X_edit via
     coefficient mutation + reassemble() — never via raw-signal L1 gradient.
  3. For each constraint: check residual; if violated, delegate to OP-051
     project() for compensation (naive / local / coupled).
  4. Relabel via OP-040 to determine post-edit shape.
  5. Emit a LabelChip via OP-041.

The ``edit_space`` field of CFResult is always the literal string
``'coefficient'`` for the decomposition-first path.  This field is used
by the paper benchmarking comparator to distinguish the novel contribution
from the raw-signal-gradient baseline methods (Wachter et al. 2017; DiCE
Mothilal et al. 2020; Native Guide Delaney et al. 2021).

Signal-space CF (Tier-1 ``replace_from_library``) is an intentionally
separate code path; callers must not route it through this function.

Reference: HypotheX-TS Formal Definitions §6; OP-050 ticket.
"""
from __future__ import annotations

import copy
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Literal

import numpy as np

from app.models.decomposition import DecompositionBlob
from app.services.events import AuditLog, EventBus
from app.services.operations.relabeler.label_chip import emit_label_chip
from app.services.operations.relabeler.relabeler import RelabelResult, relabel
from app.services.validation import (
    ConformalPIDValidator,
    ProbeModel,
    ValidationResult,
    default_sigma_for_op,
    probe_invalidation_rate,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MissingDecompositionError(ValueError):
    """Raised when synthesize_counterfactual is called without a fitted blob."""


# ---------------------------------------------------------------------------
# Constraint Protocol
# ---------------------------------------------------------------------------


class Constraint:
    """Protocol for conservation-law constraints (OP-032).

    Concrete implementations are provided by OP-032 (enforce_conservation).
    Tests may supply plain objects that implement the three required members.
    """

    @property
    def name(self) -> str:  # pragma: no cover
        raise NotImplementedError

    def satisfied(self, X: np.ndarray, *, aux: dict[str, Any] | None = None) -> bool:  # pragma: no cover
        raise NotImplementedError

    def residual(self, X: np.ndarray) -> float:  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
# CFResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CFResult:
    """Result of a decomposition-first CF synthesis.

    Attributes:
        edited_series:       Post-edit segment values (same length as segment).
        blob:                Deep-copied decomposition blob after coefficient edit.
        new_shape:           Post-edit shape label from OP-040 relabeler.
        confidence:          Relabeler confidence in [0, 1].
        needs_resegment:     True when rule_class is RECLASSIFY_VIA_SEGMENTER.
        constraint_residual: Mapping {constraint.name: residual_after_projection}.
        method:              Always 'decomposition_first'.
        edit_space:          Always 'coefficient' for this path.
        op_name:             Canonical Tier-2 op name (e.g. 'flatten').
        segment_id:          ID of the edited segment.
        op_id:               UUID4 assigned to this synthesis call.
        validation:          Per-edit validation outcomes; ``None`` when no
                             validator was supplied. ``validation.conformal``
                             holds the VAL-001 BandCheckResult.
    """

    edited_series: np.ndarray
    blob: DecompositionBlob
    new_shape: str
    confidence: float
    needs_resegment: bool
    constraint_residual: dict[str, float]
    method: str
    edit_space: str
    op_name: str
    segment_id: str
    op_id: str
    validation: ValidationResult | None = None


# ---------------------------------------------------------------------------
# Primary entry point
# ---------------------------------------------------------------------------


def synthesize_counterfactual(
    *,
    segment_id: str,
    segment_label: str,
    blob: DecompositionBlob | None,
    op_tier2: Callable[..., Any],
    op_params: dict[str, Any] | None = None,
    constraints: list[Any] | None = None,
    compensation_mode: Literal["naive", "local", "coupled"] = "local",
    segment_mask: np.ndarray | None = None,
    projector: Callable[..., np.ndarray] | None = None,
    event_bus: EventBus | None = None,
    audit_log: AuditLog | None = None,
    validator: ConformalPIDValidator | None = None,
    pre_segment: np.ndarray | None = None,
    probe_model: ProbeModel | None = None,
    probe_sigma: float | None = None,
    probe_method: Literal["linearised", "monte_carlo"] = "linearised",
) -> CFResult:
    """Decomposition-first CF synthesis.

    Never applies raw-signal gradient edits.  All edits are coefficient-level
    mutations on the segment's fitted decomposition blob followed by
    blob.reassemble().

    Reference: HypotheX-TS Formal Definitions §6.

    Args:
        segment_id:       ID of the segment being edited.
        segment_label:    Pre-edit shape label (e.g. 'trend').
        blob:             Fitted DecompositionBlob for the segment.  Must not
                          be None; raises MissingDecompositionError otherwise.
        op_tier2:         Tier-2 callable (e.g. ``raise_lower``, ``flatten``).
                          Must accept (blob, **op_params) and return an object
                          with .values (np.ndarray) and .op_name (str).
        op_params:        Keyword arguments forwarded to op_tier2.
        constraints:      List of Constraint instances to evaluate post-edit.
        compensation_mode: 'naive' | 'local' | 'coupled' (OP-051).
        segment_mask:     Boolean mask (len == len(segment)) for 'local' mode.
        projector:        Callable matching OP-051 project() signature.
                          If None, uses OP-051 project() when available,
                          otherwise falls back to naive (no-op) with a warning.
        event_bus:        EventBus for chip publication; uses default when None.
        audit_log:        AuditLog for chip persistence; uses default when None.
        validator:        Optional ConformalPIDValidator (VAL-001). When
                          supplied together with ``pre_segment``, the
                          coordinator runs ``band_check`` on the pre/post
                          forecasts and attaches the result to
                          ``CFResult.validation.conformal``.
        pre_segment:      Pre-edit segment values (same length as the
                          edited segment) used to compute ``y_pre``. Required
                          when ``validator`` is supplied.
        probe_model:      Optional ProbeModel (VAL-002). When supplied, the
                          coordinator computes the PROBE invalidation rate on
                          ``X_edit`` and attaches the result to
                          ``CFResult.validation.probe_ir``.
        probe_sigma:      Perturbation scale σ for PROBE-IR; falls back to the
                          per-op default in ``TIER2_DEFAULT_SIGMA`` when ``None``.
        probe_method:     'linearised' (default; closed-form Pawelczyk Eq. 5)
                          or 'monte_carlo' (slow-path fallback).

    Returns:
        CFResult with edited series, blob, relabel decision, constraint
        residuals, and metadata.

    Raises:
        MissingDecompositionError: blob is None.
    """
    params: dict[str, Any] = op_params or {}

    # Step 1: guard — blob must be fitted
    if blob is None:
        raise MissingDecompositionError(
            f"Segment '{segment_id}' has no fitted decomposition blob. "
            "Run the decomposition fitter (SEG-019) before CF synthesis."
        )

    # Step 2: coefficient-level edit (never raw-signal L1)
    working_blob = copy.deepcopy(blob)
    tier2_result = op_tier2(working_blob, **params)
    X_edit = np.asarray(tier2_result.values, dtype=np.float64)
    op_name: str = tier2_result.op_name

    # Step 3: constraint projection (delegates to OP-051)
    constraint_residual: dict[str, float] = {}
    if constraints:
        _projector = projector if projector is not None else _get_default_projector()
        for constraint in constraints:
            res_before = float(constraint.residual(X_edit))
            constraint_residual[constraint.name] = res_before
            if not constraint.satisfied(X_edit, aux=params):
                X_edit = _projector(
                    X_edit,
                    constraint,
                    compensation_mode,
                    segment_mask=segment_mask,
                )
                constraint_residual[constraint.name] = float(constraint.residual(X_edit))

    # Step 4: relabel
    # For PRESERVED and DETERMINISTIC the op already carries the authoritative
    # relabeling via its inline rule.  For RECLASSIFY_VIA_SEGMENTER the op
    # returns a confidence-0 stub; invoke the OP-040 classifier on X_edit to
    # get the actual post-edit shape and confidence.
    embedded: RelabelResult = tier2_result.relabel
    if embedded.rule_class == "RECLASSIFY_VIA_SEGMENTER":
        relabel_result = relabel(
            old_shape=segment_label,
            operation=op_name,
            op_params=params,
            edited_series=X_edit,
        )
    else:
        relabel_result = embedded

    # Step 5: emit label chip via OP-041
    op_id = str(uuid.uuid4())
    emit_label_chip(
        segment_id=segment_id,
        op_id=op_id,
        op_name=op_name,
        tier=2,
        old_shape=segment_label,
        relabel_result=relabel_result,
        event_bus=event_bus,
        audit_log=audit_log,
    )

    # Step 6: per-edit validation checks (VAL-001 + VAL-002, both optional)
    conformal_result = None
    if validator is not None:
        if pre_segment is None:
            raise ValueError(
                "synthesize_counterfactual: 'pre_segment' is required when 'validator' is supplied."
            )
        y_pre = float(validator.forecaster.predict(np.asarray(pre_segment, dtype=np.float64)))
        y_post = float(validator.forecaster.predict(X_edit))
        conformal_result = validator.band_check(y_pre, y_post)

    probe_result = None
    if probe_model is not None:
        effective_sigma = probe_sigma if probe_sigma is not None else default_sigma_for_op(op_name)
        probe_result = probe_invalidation_rate(
            probe_model,
            X_edit,
            sigma=effective_sigma,
            method=probe_method,
        )

    validation_result: ValidationResult | None = None
    if conformal_result is not None or probe_result is not None:
        validation_result = ValidationResult(
            conformal=conformal_result,
            probe_ir=probe_result,
        )

    return CFResult(
        edited_series=X_edit,
        blob=working_blob,
        new_shape=relabel_result.new_shape,
        confidence=relabel_result.confidence,
        needs_resegment=relabel_result.needs_resegment,
        constraint_residual=constraint_residual,
        method="decomposition_first",
        edit_space="coefficient",
        op_name=op_name,
        segment_id=segment_id,
        op_id=op_id,
        validation=validation_result,
    )


# ---------------------------------------------------------------------------
# Default projector (OP-051 delegate or naive fallback)
# ---------------------------------------------------------------------------


def _get_default_projector() -> Callable[..., np.ndarray]:
    try:
        from app.services.operations.tier3.compensation import project  # noqa: PLC0415
        return project
    except ImportError:
        logger.warning(
            "OP-051 compensation module not available; using naive projection fallback. "
            "Install OP-051 to enable local/coupled compensation modes."
        )
        return _naive_project


def _naive_project(
    X_edit: np.ndarray,
    constraint: Any,
    compensation_mode: str,
    *,
    segment_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Fallback: report residual but do not project (naive mode behaviour)."""
    return X_edit
