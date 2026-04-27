"""Tier-1 amplitude atoms: scale, offset, mute_zero (OP-010).

Three label-agnostic amplitude operations applicable to any segment shape.
When a DecompositionBlob is present the op edits the appropriate component
or coefficient in-place and reassembles via blob.reassemble().  When no blob
is present, or when the blob method is unrecognised, the op falls back to
direct arithmetic on the raw values with a WARNING log.

Relabeling rules (inline; OP-040 full rule table is a separate ticket):
  scale(α=0)  → DETERMINISTIC('plateau')   — any shape collapses
  scale(α≠0)  → PRESERVED
  offset(δ)   → PRESERVED
  mute_zero   → DETERMINISTIC('plateau')   — constant fill = plateau

Source: HypotheX-TS Operation Vocabulary Research §3.1–§3.4.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.models.decomposition import DecompositionBlob
from app.services.operations.relabeler.relabeler import RelabelResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class AmplitudeOpResult:
    """Result of a Tier-1 amplitude operation.

    Attributes:
        values:   Edited segment values (numpy array, same shape as input).
        relabel:  Relabeling decision from the inline OP-040 rule application.
        op_name:  Operation name for audit emission (OP-041).
        tier:     Always 1 for amplitude atoms.
    """

    values: np.ndarray
    relabel: RelabelResult
    op_name: str
    tier: int = 1


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


def _deterministic(target: str) -> RelabelResult:
    return RelabelResult(
        new_shape=target,
        confidence=1.0,
        needs_resegment=False,
        rule_class="DETERMINISTIC",
    )


# ---------------------------------------------------------------------------
# Blob-aware component selectors
# ---------------------------------------------------------------------------


def _scale_blob_components(blob: DecompositionBlob, alpha: float) -> None:
    """Scale the amplitude-bearing component(s) of blob in-place by alpha.

    Dispatch by blob.method:
      Constant — scales the 'trend' component (the constant level).
      ETM      — scales sin_*/cos_* harmonic components and their coefficients.
      STL      — scales the 'seasonal' component.
      MSTL     — scales all 'seasonal_*' components.
      Other    — no-op; caller falls back to raw-value arithmetic.
    """
    method = blob.method
    if method == "Constant":
        if "trend" in blob.components:
            blob.components["trend"] = blob.components["trend"] * alpha
    elif method == "ETM":
        for key in list(blob.components):
            if key.startswith("sin_") or key.startswith("cos_"):
                blob.components[key] = blob.components[key] * alpha
        for key in list(blob.coefficients):
            if key.startswith("sin_") or key.startswith("cos_"):
                blob.coefficients[key] = float(blob.coefficients[key]) * alpha
    elif method == "STL":
        if "seasonal" in blob.components:
            blob.components["seasonal"] = blob.components["seasonal"] * alpha
    elif method == "MSTL":
        for key in list(blob.components):
            if key.startswith("seasonal_"):
                blob.components[key] = blob.components[key] * alpha
    else:
        raise _UnrecognisedMethod(method)


def _offset_blob(blob: DecompositionBlob, delta: float) -> None:
    """Shift the constant-level component of blob in-place by delta.

    Dispatch by blob.method:
      Constant — shifts 'trend' component and 'level' coefficient.
      ETM      — shifts 'x0' component and coefficient.
      STL      — shifts the 'trend' component.
      MSTL     — shifts the 'trend' component.
      Other    — no-op; caller falls back to raw-value arithmetic.
    """
    method = blob.method
    if method == "Constant":
        if "trend" in blob.components:
            blob.components["trend"] = blob.components["trend"] + delta
        if "level" in blob.coefficients:
            blob.coefficients["level"] = float(blob.coefficients["level"]) + delta
    elif method == "ETM":
        if "x0" in blob.components:
            blob.components["x0"] = blob.components["x0"] + delta
        if "x0" in blob.coefficients:
            blob.coefficients["x0"] = float(blob.coefficients["x0"]) + delta
    elif method in ("STL", "MSTL"):
        if "trend" in blob.components:
            blob.components["trend"] = blob.components["trend"] + delta
    else:
        raise _UnrecognisedMethod(method)


class _UnrecognisedMethod(Exception):
    """Signals that the blob method has no explicit dispatch rule."""


# ---------------------------------------------------------------------------
# Public ops
# ---------------------------------------------------------------------------


def scale(
    X_seg: np.ndarray,
    blob: DecompositionBlob | None,
    alpha: float,
    pivot: Literal["mean", "min", "zero"] = "mean",
    pre_shape: str = "unknown",
) -> AmplitudeOpResult:
    """Scale a segment's amplitude around a pivot by factor alpha.

    When a blob is present, scales the amplitude-bearing component(s) in-place
    (ignoring the pivot — the component centre serves as the implicit pivot).
    When blob is absent, applies pivot-based scaling to raw values:
        X_out = pivot_value + alpha * (X_seg - pivot_value)

    Pivot options: 'mean' (default), 'min', 'zero'.

    Relabeling (inline OP-040 rule):
      alpha=0  → DETERMINISTIC('plateau')
      alpha≠0  → PRESERVED

    Args:
        X_seg:     Segment signal, shape (n,).
        blob:      DecompositionBlob mutated in-place; None for raw-value path.
        alpha:     Scale factor.
        pivot:     Reference point for raw-value path.
        pre_shape: Shape label before the edit, for relabeling.

    Returns:
        AmplitudeOpResult with edited values and relabel decision.

    Raises:
        ValueError: Unknown pivot value.
    """
    arr = np.asarray(X_seg, dtype=np.float64)

    if blob is not None:
        try:
            _scale_blob_components(blob, alpha)
            values = blob.reassemble()
        except _UnrecognisedMethod as exc:
            logger.warning(
                "scale: unrecognised blob method '%s'; falling back to raw-value edit.", exc
            )
            values = _scale_raw(arr, alpha, pivot)
    else:
        values = _scale_raw(arr, alpha, pivot)

    relabel = _deterministic("plateau") if alpha == 0.0 else _preserved(pre_shape)
    return AmplitudeOpResult(values=values, relabel=relabel, op_name="scale")


def offset(
    X_seg: np.ndarray,
    blob: DecompositionBlob | None,
    delta: float,
    pre_shape: str = "unknown",
) -> AmplitudeOpResult:
    """Shift the level of a segment by a constant delta.

    When a blob is present, shifts the constant-level component in-place
    (Constant: 'level'; ETM: 'x0'; STL/MSTL: 'trend').
    When blob is absent, adds delta to all values.

    Relabeling (inline OP-040 rule): PRESERVED — level shift does not change shape.

    Args:
        X_seg:     Segment signal, shape (n,).
        blob:      DecompositionBlob mutated in-place; None for raw-value path.
        delta:     Additive shift applied to the constant-level component.
        pre_shape: Shape label before the edit, for relabeling.

    Returns:
        AmplitudeOpResult with edited values and relabel decision.
    """
    arr = np.asarray(X_seg, dtype=np.float64)

    if blob is not None:
        try:
            _offset_blob(blob, delta)
            values = blob.reassemble()
        except _UnrecognisedMethod as exc:
            logger.warning(
                "offset: unrecognised blob method '%s'; falling back to raw-value edit.", exc
            )
            values = arr + delta
    else:
        values = arr + delta

    return AmplitudeOpResult(values=values, relabel=_preserved(pre_shape), op_name="offset")


def mute_zero(
    X_seg: np.ndarray,
    blob: DecompositionBlob | None,
    fill: Literal["zero", "global_mean"] = "zero",
    mu_global: float | None = None,
    pre_shape: str = "unknown",
) -> AmplitudeOpResult:
    """Replace segment values with zeros or a constant fill value.

    When fill='global_mean', mu_global must be provided.
    When a blob is present, its components and coefficients are replaced
    with a degenerate single-component blob that reassembles to the fill value.

    Relabeling (inline OP-040 rule): DETERMINISTIC('plateau') for both fill
    modes — a constant signal is always a plateau.

    Args:
        X_seg:     Segment signal, shape (n,).
        blob:      DecompositionBlob mutated in-place; None for raw-value path.
        fill:      'zero' to fill with 0.0; 'global_mean' to fill with mu_global.
        mu_global: Required when fill='global_mean'.
        pre_shape: Shape label before the edit (for relabeling record).

    Returns:
        AmplitudeOpResult with edited values and relabel decision.

    Raises:
        ValueError: fill='global_mean' but mu_global is None.
    """
    arr = np.asarray(X_seg, dtype=np.float64)

    if fill == "global_mean":
        if mu_global is None:
            raise ValueError("mute_zero: mu_global must be provided when fill='global_mean'.")
        fill_value = float(mu_global)
    elif fill == "zero":
        fill_value = 0.0
    else:
        raise ValueError(f"mute_zero: unknown fill mode '{fill}'. Choose 'zero' or 'global_mean'.")

    out = np.full(arr.shape, fill_value, dtype=np.float64)

    if blob is not None:
        blob.components = {"muted": out.copy()}
        blob.coefficients = {"fill": fill, "fill_value": fill_value}

    return AmplitudeOpResult(
        values=out,
        relabel=_deterministic("plateau"),
        op_name="mute_zero",
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _scale_raw(arr: np.ndarray, alpha: float, pivot: str) -> np.ndarray:
    pivot_options = {
        "mean": float(np.mean(arr)),
        "min": float(np.min(arr)),
        "zero": 0.0,
    }
    if pivot not in pivot_options:
        raise ValueError(
            f"scale: unknown pivot '{pivot}'. Valid options: {sorted(pivot_options)}."
        )
    p = pivot_options[pivot]
    return p + alpha * (arr - p)
