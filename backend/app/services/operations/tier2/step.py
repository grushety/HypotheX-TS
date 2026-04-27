"""Tier-2 step ops: de_jump, invert_sign, scale_magnitude, shift_in_time,
convert_to_ramp, duplicate (OP-022).

All ops work directly on ETM Heaviside coefficients — no raw-signal
manipulation.  The step is identified by its epoch t_s, which maps to the
key ``step_at_{t_s:.6g}`` in blob.coefficients / blob.components.

All mutating ops deepcopy the blob internally; the caller's blob is unchanged.

Relabeling:
  de_jump                    → RECLASSIFY_VIA_SEGMENTER
  invert_sign                → PRESERVED('step')
  scale_magnitude(alpha=0)   → RECLASSIFY_VIA_SEGMENTER  (equivalent to de_jump)
  scale_magnitude(alpha≠0)   → PRESERVED('step')
  shift_in_time              → PRESERVED('step')
  convert_to_ramp            → DETERMINISTIC('transient')
  duplicate                  → RECLASSIFY_VIA_SEGMENTER   (split hint)

References
----------
Bevis, M. & Brown, S. (2014). Trajectory models and reference frames for
    crustal motion geodesy. J. Geodesy 88:283-311. DOI 10.1007/s00190-013-0685-5.
    → ETM Eq. 1 Heaviside term: Δᵢ · H(t − t_s,i).

Wang, W., Bock, Y., Genrich, J. F., & van Dam, T. (2012). Preprocessing of
    daily GPS time series through noise analysis with colored noise models.
    J. Geophys. Res. 117:B01405.
    → Motivation for step epoch correction and de-jump operations.
"""

from __future__ import annotations

import copy
import logging

import numpy as np

from app.models.decomposition import DecompositionBlob
from app.services.operations.tier2.plateau import Tier2OpResult
from app.services.operations.relabeler.relabeler import RelabelResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inline relabeler helpers
# ---------------------------------------------------------------------------


def _preserved(pre_shape: str) -> RelabelResult:
    return RelabelResult(
        new_shape=pre_shape,
        confidence=1.0,
        needs_resegment=False,
        rule_class="PRESERVED",
    )


def _deterministic(target_shape: str) -> RelabelResult:
    return RelabelResult(
        new_shape=target_shape,
        confidence=1.0,
        needs_resegment=False,
        rule_class="DETERMINISTIC",
    )


def _reclassify(pre_shape: str) -> RelabelResult:
    return RelabelResult(
        new_shape=pre_shape,
        confidence=0.0,
        needs_resegment=True,
        rule_class="RECLASSIFY_VIA_SEGMENTER",
    )


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------


def _step_key(t_s: float) -> str:
    """Return the blob key for a Heaviside step at epoch t_s."""
    return f"step_at_{float(t_s):.6g}"


def _log_key(t_s: float, tau: float) -> str:
    """Return the blob key for a log-transient at epoch t_s with timescale tau."""
    return f"log_{float(t_s):.6g}_tau{float(tau):.6g}"


def _require_step(blob: DecompositionBlob, t_s: float) -> str:
    """Return the step key for t_s, raising ValueError if absent."""
    key = _step_key(t_s)
    if key not in blob.coefficients:
        available = [k for k in blob.coefficients if k.startswith("step_at_")]
        raise ValueError(
            f"step op: key '{key}' not found in blob.coefficients. "
            f"Available step keys: {available}."
        )
    return key


# ---------------------------------------------------------------------------
# Heaviside / log-transient helpers
# ---------------------------------------------------------------------------


def _heaviside(t: np.ndarray, t_s: float) -> np.ndarray:
    return (t >= float(t_s)).astype(np.float64)


def _log_transient(t: np.ndarray, t_s: float, tau: float) -> np.ndarray:
    """Normalised logarithmic transient: log1p(max(0, (t - t_s) / tau))."""
    return np.log1p(np.maximum(0.0, (t - float(t_s)) / float(tau)))


# ---------------------------------------------------------------------------
# de_jump
# ---------------------------------------------------------------------------


def de_jump(
    blob: DecompositionBlob,
    t_s: float,
    pre_shape: str = "step",
) -> Tier2OpResult:
    """Remove the step at epoch t_s by zeroing its Heaviside amplitude.

    Equivalent to scale_magnitude(alpha=0): both produce bit-identical values.
    The post-op shape depends on the residual, so the relabeler is invoked.

    Relabeling: RECLASSIFY_VIA_SEGMENTER.

    Reference: Bevis & Brown (2014) Eq. 1 — zero Δᵢ removes the Heaviside term.

    Args:
        blob:      ETM DecompositionBlob containing a step at t_s.
        t_s:       Step epoch (must exist in blob.coefficients).
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with de-jumped values and RECLASSIFY relabeling.

    Raises:
        ValueError: If t_s is not a known step epoch in the blob.
    """
    blob = copy.deepcopy(blob)
    key = _require_step(blob, t_s)
    blob.coefficients[key] = 0.0
    blob.components[key] = np.zeros_like(blob.components[key])
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_reclassify(pre_shape),
        op_name="de_jump",
    )


# ---------------------------------------------------------------------------
# invert_sign
# ---------------------------------------------------------------------------


def invert_sign(
    blob: DecompositionBlob,
    t_s: float,
    pre_shape: str = "step",
) -> Tier2OpResult:
    """Negate the amplitude of the step at epoch t_s.

    Relabeling: PRESERVED('step') — a negated step is still a step.

    Reference: Bevis & Brown (2014) Eq. 1 — Δᵢ → −Δᵢ.

    Args:
        blob:      ETM DecompositionBlob.
        t_s:       Step epoch.
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with sign-inverted values and PRESERVED relabeling.

    Raises:
        ValueError: If t_s is not a known step epoch.
    """
    blob = copy.deepcopy(blob)
    key = _require_step(blob, t_s)
    blob.coefficients[key] = -float(blob.coefficients[key])
    blob.components[key] = -blob.components[key]
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="invert_sign",
    )


# ---------------------------------------------------------------------------
# scale_magnitude
# ---------------------------------------------------------------------------


def scale_magnitude(
    blob: DecompositionBlob,
    t_s: float,
    alpha: float,
    pre_shape: str = "step",
) -> Tier2OpResult:
    """Scale the step amplitude at epoch t_s by alpha.

    alpha=0   → equivalent to de_jump (RECLASSIFY_VIA_SEGMENTER).
    alpha=-1  → equivalent to invert_sign.
    alpha≠0   → PRESERVED('step').

    Reference: Bevis & Brown (2014) Eq. 1 — Δᵢ → alpha · Δᵢ.

    Args:
        blob:      ETM DecompositionBlob.
        t_s:       Step epoch.
        alpha:     Multiplicative scale factor.
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with scaled values and appropriate relabeling.

    Raises:
        ValueError: If t_s is not a known step epoch.
    """
    blob = copy.deepcopy(blob)
    key = _require_step(blob, t_s)
    blob.coefficients[key] = float(blob.coefficients[key]) * float(alpha)
    blob.components[key] = blob.components[key] * float(alpha)
    relabel = _reclassify(pre_shape) if float(alpha) == 0.0 else _preserved(pre_shape)
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=relabel,
        op_name="scale_magnitude",
    )


# ---------------------------------------------------------------------------
# shift_in_time
# ---------------------------------------------------------------------------


def shift_in_time(
    blob: DecompositionBlob,
    t_s_old: float,
    t_s_new: float,
    t: np.ndarray,
    pre_shape: str = "step",
) -> Tier2OpResult:
    """Move the step epoch from t_s_old to t_s_new, preserving amplitude.

    Removes the old Heaviside component and inserts a new one at t_s_new
    with the same amplitude Δ.

    Relabeling: PRESERVED('step') — relocation does not change the shape class.

    Reference: Bevis & Brown (2014) Eq. 1 — step epoch t_s,i re-indexed.

    Args:
        blob:      ETM DecompositionBlob.
        t_s_old:   Current step epoch.
        t_s_new:   New step epoch.
        t:         Time axis for the segment, shape (n,).
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with relocated step values and PRESERVED relabeling.

    Raises:
        ValueError: If t_s_old is not a known step epoch.
    """
    blob = copy.deepcopy(blob)
    key_old = _require_step(blob, t_s_old)
    delta = float(blob.coefficients.pop(key_old))
    blob.components.pop(key_old)

    t_arr = np.asarray(t, dtype=np.float64)
    key_new = _step_key(t_s_new)
    blob.coefficients[key_new] = delta
    blob.components[key_new] = delta * _heaviside(t_arr, t_s_new)

    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="shift_in_time",
    )


# ---------------------------------------------------------------------------
# convert_to_ramp
# ---------------------------------------------------------------------------


def convert_to_ramp(
    blob: DecompositionBlob,
    t_s: float,
    tau_ramp: float,
    t: np.ndarray,
    pre_shape: str = "step",
) -> Tier2OpResult:
    """Replace the Heaviside step with a logarithmic transient (ramp).

    Converts the instantaneous step Δ·H(t−t_s) into a logarithmic
    post-seismic relaxation:
        Δ · log1p(max(0, (t − t_s) / tau_ramp))

    The original step key is removed and replaced with the log-transient key
    ``log_{t_s:.6g}_tau{tau_ramp:.6g}``.

    Relabeling: DETERMINISTIC('transient').

    Reference: Bevis & Brown (2014) Eq. 1 — aⱼ·log(1 + (t−t_r)/τⱼ) transient.

    Args:
        blob:      ETM DecompositionBlob.
        t_s:       Step epoch to convert.
        tau_ramp:  Relaxation timescale (> 0).
        t:         Time axis for the segment, shape (n,).
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with ramp values and DETERMINISTIC('transient').

    Raises:
        ValueError: If t_s is not known or tau_ramp <= 0.
    """
    if float(tau_ramp) <= 0.0:
        raise ValueError(f"convert_to_ramp: tau_ramp must be > 0, got {tau_ramp!r}.")
    blob = copy.deepcopy(blob)
    key_step = _require_step(blob, t_s)
    delta = float(blob.coefficients.pop(key_step))
    blob.components.pop(key_step)

    t_arr = np.asarray(t, dtype=np.float64)
    key_log = _log_key(t_s, tau_ramp)
    blob.coefficients[key_log] = delta
    blob.components[key_log] = delta * _log_transient(t_arr, t_s, tau_ramp)

    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_deterministic("transient"),
        op_name="convert_to_ramp",
    )


# ---------------------------------------------------------------------------
# duplicate
# ---------------------------------------------------------------------------


def duplicate(
    blob: DecompositionBlob,
    t_s: float,
    delta_t: float,
    delta_2: float,
    t: np.ndarray,
    pre_shape: str = "step",
) -> Tier2OpResult:
    """Add a second step at t_s + delta_t with amplitude delta_2.

    The original step is unchanged.  The new step is inserted at
    ``t_s + delta_t`` with key ``step_at_{t_s + delta_t:.6g}``.

    Two steps within a single segment suggest it should be split; the
    relabeling signals RECLASSIFY_VIA_SEGMENTER to prompt re-segmentation.

    Reference: Bevis & Brown (2014) Eq. 1 — additional Heaviside term.

    Args:
        blob:      ETM DecompositionBlob.
        t_s:       Existing step epoch (validated to exist).
        delta_t:   Time offset for the duplicate step.
        delta_2:   Amplitude of the new step.
        t:         Time axis for the segment, shape (n,).
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with two-step values and RECLASSIFY relabeling.

    Raises:
        ValueError: If t_s is not a known step epoch.
    """
    if float(delta_t) == 0.0:
        raise ValueError(
            "duplicate: delta_t must be non-zero; use scale_magnitude to modify the existing step amplitude."
        )
    blob = copy.deepcopy(blob)
    _require_step(blob, t_s)  # validate original step exists

    t_arr = np.asarray(t, dtype=np.float64)
    t_s_new = float(t_s) + float(delta_t)
    key_new = _step_key(t_s_new)
    blob.coefficients[key_new] = float(delta_2)
    blob.components[key_new] = float(delta_2) * _heaviside(t_arr, t_s_new)

    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_reclassify(pre_shape),
        op_name="duplicate",
    )
