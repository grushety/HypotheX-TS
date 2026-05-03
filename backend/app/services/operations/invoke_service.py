"""Op-invocation dispatch service (HTS-100).

Single entry point for the ``POST /api/operations/invoke`` route. Resolves
``(tier, op_name)`` to a backend callable, runs the op, and returns the
post-edit values + relabeling chip + audit_id. The route layer stays
thin (validate, call this service, serialise).

Dispatch table:

  Tier 1 → call the op directly on the segment slice (raw-value path,
           ``blob=None``); emit a ``LabelChip`` manually with ``tier=1``
           since ``cf_coordinator.synthesize_counterfactual`` is a
           Tier-2-only entry point per its docstring.
  Tier 2 → fit a ``DecompositionBlob`` for the segment slice via
           SEG-019 ``dispatch_fitter``, then call
           ``synthesize_counterfactual`` so OP-051 projection +
           OP-040 relabel + OP-041 chip emission run via the existing
           pipeline.
  Tier 3 ``decompose`` / ``enforce_conservation`` / ``align_warp`` →
           call directly; each emits its own audit (no LabelChip).
  Tier 3 ``aggregate`` → call directly; read-only; no audit, no chip.

Audit-id contract: snapshot ``len(default_audit_log)`` before the op
runs. If a record was appended, ``audit_id`` is the index of the
just-appended record (i.e. the pre-call length). When the op did not
append (Tier-3 ``aggregate``), ``audit_id`` is ``None``.

Reference: HypotheX-TS HTS-100 ticket.
"""
from __future__ import annotations

import inspect
import logging
import uuid
from typing import Any, Callable

import numpy as np

from app.schemas.operation_invoke import (
    OperationInvokeRequest,
    OperationInvokeResponse,
    SegmentSpec,
)
from app.services.decomposition.dispatcher import dispatch_fitter
from app.services.events import (
    AuditLog,
    EventBus,
    default_audit_log,
    default_event_bus,
)
from app.services.operations import cf_coordinator
from app.services.operations.relabeler.label_chip import LabelChip, emit_label_chip

# Tier-1 ops
from app.services.operations.tier1 import amplitude as _t1_amp
from app.services.operations.tier1 import stochastic as _t1_sto
from app.services.operations.tier1 import time as _t1_time
from app.services.operations.tier1.replace_from_library import replace_from_library

# Tier-2 ops
from app.services.operations.tier2 import cycle as _t2_cycle
from app.services.operations.tier2 import noise as _t2_noise
from app.services.operations.tier2 import plateau as _t2_plateau
from app.services.operations.tier2 import spike as _t2_spike
from app.services.operations.tier2 import step as _t2_step
from app.services.operations.tier2 import transient as _t2_transient
from app.services.operations.tier2 import trend as _t2_trend

# Tier-3 ops
from app.services.operations.tier3.aggregate import aggregate as _aggregate
from app.services.operations.tier3.align_warp import (
    AlignableSegment,
    IncompatibleOp,
    align_warp as _align_warp,
)
from app.services.operations.tier3.decompose import (
    DecomposedSegment,
    decompose as _decompose,
)
from app.services.operations.tier3.enforce_conservation import (
    UnknownLaw,
    enforce_conservation as _enforce_conservation,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InvokeError(Exception):
    """Base for invoke-service errors mapped to non-500 HTTP statuses."""


class UnknownOpError(InvokeError):
    """``(tier, op_name)`` is not in the registry → 400."""


class SegmentNotFoundError(InvokeError):
    """``segment_id`` not in the request's ``segments`` list → 404."""


class MalformedParamsError(InvokeError):
    """Op-specific param validation failed → 400."""


class IncompatibleOpError(InvokeError):
    """Op refused on this segment shape (e.g. align_warp on noise) → 422."""


# ---------------------------------------------------------------------------
# Tier-1 / Tier-2 op registry (frontend op_name → backend callable)
# ---------------------------------------------------------------------------


# Tier 1 — frontend names match backend function names directly
_TIER1_REGISTRY: dict[str, Callable[..., Any]] = {
    "scale": _t1_amp.scale,
    "offset": _t1_amp.offset,
    "mute_zero": _t1_amp.mute_zero,
    "time_shift": _t1_time.time_shift,
    "reverse_time": _t1_time.reverse_time,
    "resample": _t1_time.resample,
    "suppress": _t1_sto.suppress,
    "add_uncertainty": _t1_sto.add_uncertainty,
    "replace_from_library": replace_from_library,
}

# Tier 2 — frontend uses <shape>_<verb>; backend uses verb only.
# This table covers ops with a clear backend counterpart. Future tickets
# can extend it; unknown names fall through to UnknownOpError.
_TIER2_REGISTRY: dict[str, Callable[..., Any]] = {
    # plateau
    "plateau_scale": _t2_plateau.raise_lower,
    "plateau_remove_drift": _t2_plateau.tilt_detrend,
    "plateau_flatten": _t2_plateau.tilt_detrend,
    "plateau_add_seasonal": _t2_plateau.replace_with_cycle,
    # trend
    "trend_change_slope": _t2_trend.change_slope,
    "trend_reverse": _t2_trend.reverse_direction,
    "trend_detrend": _t2_trend.flatten,
    "trend_fit_piecewise": _t2_trend.linearise,
    # step
    "step_remove": _t2_step.de_jump,
    "step_adjust_height": _t2_step.scale_magnitude,
    "step_smooth": _t2_step.convert_to_ramp,
    # spike
    "spike_remove": _t2_spike.remove,
    "spike_scale": _t2_spike.amplify,
    "spike_widen": _t2_spike.smear_to_transient,
    # cycle
    "cycle_shift_phase": _t2_cycle.phase_shift,
    "cycle_amplify": _t2_cycle.amplify_amplitude,
    "cycle_damp": _t2_cycle.dampen_amplitude,
    "cycle_change_frequency": _t2_cycle.change_period,
    "cycle_remove_harmonics": _t2_cycle.change_harmonic_content,
    "cycle_add_harmonics": _t2_cycle.change_harmonic_content,
    # transient
    "transient_change_duration": _t2_transient.change_duration,
    "transient_scale": _t2_transient.amplify,
    "transient_shift_onset": _t2_transient.shift_time,
    # noise
    "noise_denoise": _t2_noise.suppress_denoise,
    "noise_rescale": _t2_noise.amplify,
    "noise_filter": _t2_noise.change_color,
}


# Ops that produce a *whole-series* dict rather than a segment slice.
_WHOLE_SERIES_TIER3 = frozenset({"enforce_conservation", "align_warp"})


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def invoke_operation(
    req: OperationInvokeRequest,
    *,
    event_bus: EventBus | None = None,
    audit_log: AuditLog | None = None,
) -> OperationInvokeResponse:
    """Dispatch a single op-invocation request and return the response DTO.

    The bus / log defaults are the package-level singletons; callers
    (typically the route layer) inherit them. Tests inject their own
    instances for isolation.

    Args:
        req:        Validated request DTO.
        event_bus:  Override for chip/audit publication.
        audit_log:  Override for chip/audit persistence.

    Returns:
        Response DTO ready for ``jsonify``.

    Raises:
        UnknownOpError:        ``(tier, op_name)`` is not registered.
        SegmentNotFoundError:  ``segment_id`` does not match any segment.
        MalformedParamsError:  Op param validation failed.
        IncompatibleOpError:   Op refused on this segment shape.
    """
    log = audit_log if audit_log is not None else default_audit_log
    pre_call_len = len(log)

    if req.tier == 1:
        return _dispatch_tier1(req, event_bus=event_bus, audit_log=audit_log,
                               pre_call_len=pre_call_len)
    if req.tier == 2:
        return _dispatch_tier2(req, event_bus=event_bus, audit_log=audit_log,
                               pre_call_len=pre_call_len)
    if req.tier == 3:
        return _dispatch_tier3(req, event_bus=event_bus, audit_log=audit_log,
                               pre_call_len=pre_call_len)
    raise UnknownOpError(f"Unknown tier: {req.tier}")


# ---------------------------------------------------------------------------
# Tier 1 — raw-value path + manual chip emission
# ---------------------------------------------------------------------------


def _dispatch_tier1(
    req: OperationInvokeRequest,
    *,
    event_bus: EventBus | None,
    audit_log: AuditLog | None,
    pre_call_len: int,
) -> OperationInvokeResponse:
    op_fn = _TIER1_REGISTRY.get(req.op_name)
    if op_fn is None:
        raise UnknownOpError(
            f"Unknown Tier-1 op {req.op_name!r}. "
            f"Known: {sorted(_TIER1_REGISTRY)}"
        )

    seg = _resolve_segment(req)
    arr = np.asarray(req.sample_values, dtype=np.float64)
    X_seg = arr[seg.start : seg.end + 1]

    params = dict(req.params)
    params.setdefault("pre_shape", seg.label)

    try:
        if req.op_name in ("scale", "offset", "mute_zero"):
            params.setdefault("blob", None)
            result = op_fn(X_seg, **params)
        else:
            result = op_fn(X_seg, **params)
    except (TypeError, ValueError) as exc:
        raise MalformedParamsError(str(exc)) from exc

    values = np.asarray(result.values, dtype=np.float64)
    op_id = str(uuid.uuid4())
    chip = emit_label_chip(
        segment_id=req.segment_id,
        op_id=op_id,
        op_name=result.op_name,
        tier=1,
        old_shape=seg.label,
        relabel_result=result.relabel,
        event_bus=event_bus,
        audit_log=audit_log,
    )

    return OperationInvokeResponse(
        op_name=result.op_name,
        tier=1,
        edit_space="signal",
        values=[float(v) for v in values],
        constraint_residual=None,
        validation=None,
        label_chip=_serialise_chip(chip),
        audit_id=pre_call_len if chip is not None else None,
        aggregate_result=None,
    )


# ---------------------------------------------------------------------------
# Tier 2 — fit blob, hand to cf_coordinator
# ---------------------------------------------------------------------------


def _dispatch_tier2(
    req: OperationInvokeRequest,
    *,
    event_bus: EventBus | None,
    audit_log: AuditLog | None,
    pre_call_len: int,
) -> OperationInvokeResponse:
    op_fn = _TIER2_REGISTRY.get(req.op_name)
    if op_fn is None:
        raise UnknownOpError(
            f"Unknown Tier-2 op {req.op_name!r}. "
            f"Known: {sorted(_TIER2_REGISTRY)}"
        )

    seg = _resolve_segment(req)
    arr = np.asarray(req.sample_values, dtype=np.float64)
    X_seg = arr[seg.start : seg.end + 1]
    t = np.arange(seg.start, seg.end + 1, dtype=np.float64)

    op_sig = inspect.signature(op_fn)
    first_param = next(iter(op_sig.parameters), None)

    if first_param == "X_seg":
        return _dispatch_tier2_raw(
            req, op_fn, op_sig, seg, X_seg, t,
            event_bus=event_bus, audit_log=audit_log,
            pre_call_len=pre_call_len,
        )
    return _dispatch_tier2_blob(
        req, op_fn, op_sig, seg, X_seg, t,
        event_bus=event_bus, audit_log=audit_log,
        pre_call_len=pre_call_len,
    )


def _dispatch_tier2_blob(
    req: OperationInvokeRequest,
    op_fn: Callable[..., Any],
    op_sig: inspect.Signature,
    seg: SegmentSpec,
    X_seg: np.ndarray,
    t: np.ndarray,
    *,
    event_bus: EventBus | None,
    audit_log: AuditLog | None,
    pre_call_len: int,
) -> OperationInvokeResponse:
    try:
        fitter = dispatch_fitter(seg.label, req.domain_hint)
    except (KeyError, RuntimeError) as exc:
        raise MalformedParamsError(
            f"Cannot fit decomposition for shape {seg.label!r}: {exc}"
        ) from exc

    try:
        blob = fitter(X_seg, t=t)
    except Exception as exc:  # noqa: BLE001 — fitter failures surface as 400
        raise MalformedParamsError(f"Fitter failed: {exc}") from exc

    compensation_mode = req.compensation_mode or "local"

    op_params = dict(req.params)
    if "t" in op_sig.parameters and "t" not in op_params:
        op_params["t"] = t
    if "pre_shape" in op_sig.parameters and "pre_shape" not in op_params:
        op_params["pre_shape"] = seg.label

    try:
        cf_result = cf_coordinator.synthesize_counterfactual(
            segment_id=req.segment_id,
            segment_label=seg.label,
            blob=blob,
            op_tier2=op_fn,
            op_params=op_params,
            compensation_mode=compensation_mode,
            event_bus=event_bus,
            audit_log=audit_log,
        )
    except cf_coordinator.MissingDecompositionError as exc:
        raise MalformedParamsError(str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise MalformedParamsError(str(exc)) from exc

    chip = _peek_last_chip(audit_log)

    return OperationInvokeResponse(
        op_name=cf_result.op_name,
        tier=2,
        edit_space=cf_result.edit_space,
        values=[float(v) for v in cf_result.edited_series],
        constraint_residual=dict(cf_result.constraint_residual) or None,
        validation=None,
        label_chip=_serialise_chip(chip),
        audit_id=pre_call_len if chip is not None else None,
        aggregate_result=None,
    )


def _dispatch_tier2_raw(
    req: OperationInvokeRequest,
    op_fn: Callable[..., Any],
    op_sig: inspect.Signature,
    seg: SegmentSpec,
    X_seg: np.ndarray,
    t: np.ndarray,
    *,
    event_bus: EventBus | None,
    audit_log: AuditLog | None,
    pre_call_len: int,
) -> OperationInvokeResponse:
    """Tier-2 ops that operate on raw signal (e.g. spike ops).

    These ops do not consume a DecompositionBlob — calling them through
    cf_coordinator would crash because the coordinator passes ``blob`` as
    the first positional arg. Here we call the op directly on ``X_seg``
    and emit the LabelChip manually with ``tier=2``.
    """
    op_params = dict(req.params)
    if "t" in op_sig.parameters and "t" not in op_params:
        op_params["t"] = t
    if "pre_shape" in op_sig.parameters and "pre_shape" not in op_params:
        op_params["pre_shape"] = seg.label

    try:
        result = op_fn(X_seg, **op_params)
    except (TypeError, ValueError) as exc:
        raise MalformedParamsError(str(exc)) from exc

    op_id = str(uuid.uuid4())
    chip = emit_label_chip(
        segment_id=req.segment_id,
        op_id=op_id,
        op_name=result.op_name,
        tier=2,
        old_shape=seg.label,
        relabel_result=result.relabel,
        event_bus=event_bus,
        audit_log=audit_log,
    )

    return OperationInvokeResponse(
        op_name=result.op_name,
        tier=2,
        edit_space="signal",
        values=[float(v) for v in np.asarray(result.values, dtype=np.float64)],
        constraint_residual=None,
        validation=None,
        label_chip=_serialise_chip(chip),
        audit_id=pre_call_len if chip is not None else None,
        aggregate_result=None,
    )


# ---------------------------------------------------------------------------
# Tier 3 — direct dispatch
# ---------------------------------------------------------------------------


def _dispatch_tier3(
    req: OperationInvokeRequest,
    *,
    event_bus: EventBus | None,
    audit_log: AuditLog | None,
    pre_call_len: int,
) -> OperationInvokeResponse:
    if req.op_name == "decompose":
        return _dispatch_t3_decompose(req, event_bus, audit_log, pre_call_len)
    if req.op_name == "enforce_conservation":
        return _dispatch_t3_enforce(req, event_bus, audit_log, pre_call_len)
    if req.op_name == "align_warp":
        return _dispatch_t3_align(req, event_bus, audit_log, pre_call_len)
    if req.op_name == "aggregate":
        return _dispatch_t3_aggregate(req)
    raise UnknownOpError(f"Unknown Tier-3 op {req.op_name!r}.")


def _dispatch_t3_decompose(
    req: OperationInvokeRequest,
    event_bus: EventBus | None,
    audit_log: AuditLog | None,
    pre_call_len: int,
) -> OperationInvokeResponse:
    arr = np.asarray(req.sample_values, dtype=np.float64)
    decomp_segs = [_to_decomposed(seg) for seg in req.segments]
    target_id = req.segment_id
    try:
        new_segs = _decompose(
            arr, decomp_segs,
            domain_hint=req.domain_hint,
            event_bus=event_bus,
            audit_log=audit_log,
        )
    except ValueError as exc:
        raise MalformedParamsError(str(exc)) from exc
    except KeyError as exc:
        raise MalformedParamsError(f"Unknown shape label: {exc}") from exc

    target = next((s for s in new_segs if s.segment_id == target_id), None)
    values: list[float] | None = None
    if target is not None and target.decomposition is not None:
        try:
            values = [float(v) for v in target.decomposition.reassemble()]
        except Exception:  # noqa: BLE001
            values = None

    return OperationInvokeResponse(
        op_name="decompose",
        tier=3,
        edit_space="coefficient",
        values=values,
        constraint_residual=None,
        validation=None,
        label_chip=None,
        audit_id=pre_call_len,
        aggregate_result=None,
    )


def _dispatch_t3_enforce(
    req: OperationInvokeRequest,
    event_bus: EventBus | None,
    audit_log: AuditLog | None,
    pre_call_len: int,
) -> OperationInvokeResponse:
    if "X_all" not in req.params or "law" not in req.params:
        raise MalformedParamsError(
            "enforce_conservation requires params.X_all and params.law"
        )
    X_all = req.params["X_all"]
    if not isinstance(X_all, dict):
        raise MalformedParamsError("params.X_all must be an object")

    X_all_np = {k: np.asarray(v, dtype=np.float64) for k, v in X_all.items()}
    compensation_mode = req.compensation_mode or "local"

    try:
        X_edit, conservation_result = _enforce_conservation(
            X_all_np,
            law=str(req.params["law"]),
            compensation_mode=compensation_mode,
            aux=req.params.get("aux"),
            tolerance=req.params.get("tolerance"),
            event_bus=event_bus,
            audit_log=audit_log,
        )
    except UnknownLaw as exc:
        raise MalformedParamsError(str(exc)) from exc
    except ValueError as exc:
        raise MalformedParamsError(str(exc)) from exc

    serialised_X = {
        k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in X_edit.items()
    }
    residual = {
        "law": conservation_result.law,
        "compensation_mode": conservation_result.compensation_mode,
        "initial_residual": _residual_jsonable(conservation_result.initial_residual),
        "final_residual": _residual_jsonable(conservation_result.final_residual),
        "converged": conservation_result.converged,
        "tolerance": conservation_result.tolerance,
    }

    return OperationInvokeResponse(
        op_name="enforce_conservation",
        tier=3,
        edit_space="signal",
        values=None,
        constraint_residual=residual,
        validation=None,
        label_chip=None,
        audit_id=pre_call_len,
        aggregate_result=None,
        extra={"X_edit": serialised_X},
    )


def _dispatch_t3_align(
    req: OperationInvokeRequest,
    event_bus: EventBus | None,
    audit_log: AuditLog | None,
    pre_call_len: int,
) -> OperationInvokeResponse:
    arr = np.asarray(req.sample_values, dtype=np.float64)
    reference_id = req.params.get("reference_segment_id")
    if reference_id is None:
        raise MalformedParamsError(
            "align_warp requires params.reference_segment_id"
        )
    ref_spec = next((s for s in req.segments if s.id == reference_id), None)
    if ref_spec is None:
        raise SegmentNotFoundError(
            f"reference_segment_id {reference_id!r} not in segments list"
        )
    ref_seg = AlignableSegment(
        segment_id=ref_spec.id,
        label=ref_spec.label,
        values=arr[ref_spec.start : ref_spec.end + 1].copy(),
    )
    other_segs = [
        AlignableSegment(
            segment_id=s.id,
            label=s.label,
            values=arr[s.start : s.end + 1].copy(),
        )
        for s in req.segments
        if s.id != reference_id
    ]

    method = req.params.get("method", "dtw")
    warping_band = float(req.params.get("warping_band", 0.1))

    try:
        aligned, _audit = _align_warp(
            other_segs, ref_seg,
            method=method,
            warping_band=warping_band,
            event_bus=event_bus,
            audit_log=audit_log,
        )
    except IncompatibleOp as exc:
        raise IncompatibleOpError(str(exc)) from exc
    except ValueError as exc:
        raise MalformedParamsError(str(exc)) from exc

    target = next((s for s in aligned if s.segment_id == req.segment_id), None)
    values: list[float] | None
    if target is not None:
        values = [float(v) for v in target.values]
    elif req.segment_id == reference_id:
        values = [float(v) for v in ref_seg.values]
    else:
        values = None

    return OperationInvokeResponse(
        op_name="align_warp",
        tier=3,
        edit_space="signal",
        values=values,
        constraint_residual=None,
        validation=None,
        label_chip=None,
        audit_id=pre_call_len,
        aggregate_result=None,
    )


def _dispatch_t3_aggregate(req: OperationInvokeRequest) -> OperationInvokeResponse:
    metric = req.params.get("metric")
    if metric is None:
        raise MalformedParamsError("aggregate requires params.metric")

    arr = np.asarray(req.sample_values, dtype=np.float64)
    decomp_segs = [_to_decomposed(seg) for seg in req.segments]

    try:
        result = _aggregate(arr, decomp_segs, str(metric), aux=req.params.get("aux"))
    except ValueError as exc:
        raise MalformedParamsError(str(exc)) from exc

    return OperationInvokeResponse(
        op_name="aggregate",
        tier=3,
        edit_space="signal",
        values=None,
        constraint_residual=None,
        validation=None,
        label_chip=None,
        audit_id=None,
        aggregate_result=_jsonable(result),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_segment(req: OperationInvokeRequest) -> SegmentSpec:
    seg = req.find_segment()
    if seg is None:
        raise SegmentNotFoundError(
            f"segment_id {req.segment_id!r} not in segments list"
        )
    return seg


def _to_decomposed(seg: SegmentSpec) -> DecomposedSegment:
    return DecomposedSegment(
        segment_id=seg.id,
        start_index=seg.start,
        end_index=seg.end,
        label=seg.label,
    )


def _peek_last_chip(audit_log: AuditLog | None) -> LabelChip | None:
    log = audit_log if audit_log is not None else default_audit_log
    if len(log) == 0:
        return None
    last = log.records[-1]
    return last if isinstance(last, LabelChip) else None


def _serialise_chip(chip: LabelChip | None) -> dict[str, Any] | None:
    if chip is None:
        return None
    return {
        "chip_id": chip.chip_id,
        "segment_id": chip.segment_id,
        "op_id": chip.op_id,
        "op_name": chip.op_name,
        "tier": chip.tier,
        "old_shape": chip.old_shape,
        "new_shape": chip.new_shape,
        "confidence": float(chip.confidence),
        "rule_class": chip.rule_class,
        "timestamp": chip.timestamp,
    }


def _residual_jsonable(residual: Any) -> Any:
    if isinstance(residual, np.ndarray):
        return [float(x) for x in residual.ravel()]
    if isinstance(residual, (tuple, list)):
        return [float(x) for x in residual]
    return float(residual)


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [float(x) for x in value.ravel()]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.floating, np.integer)):
        return float(value)
    return value
