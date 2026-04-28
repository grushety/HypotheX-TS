"""Tier-2 transient ops: remove, amplify, dampen, shift_time, change_duration,
change_decay_constant, replace_shape, duplicate, convert_to_step (OP-025).

Dispatches by blob.method:
  'ETM'     — edits log/exp transient keys in blob.coefficients/components.
  'GrAtSiD' — edits blob.coefficients['features'] list (full SEG-018 format),
              or falls back to the stub's single Gaussian transient.

feature_id:
  ETM:              string key, e.g. 'log_60_tau20' or 'exp_60_tau20'.
  GrAtSiD features: integer index into blob.coefficients['features'].
  GrAtSiD stub:     string 'transient' (single Gaussian transient component).

All mutating ops deepcopy the blob internally; the caller's blob is unchanged.

Relabeling:
  remove                → RECLASSIFY_VIA_SEGMENTER
  amplify               → PRESERVED('transient')
  dampen                → PRESERVED('transient')
  shift_time            → PRESERVED('transient')
  change_duration       → PRESERVED('transient')
  change_decay_constant → PRESERVED('transient')
  replace_shape         → PRESERVED('transient')
  duplicate             → RECLASSIFY_VIA_SEGMENTER  (split hint)
  convert_to_step       → DETERMINISTIC('step')

References
----------
Bevis, M. & Brown, S. (2014). Trajectory models and reference frames for
    crustal motion geodesy. J. Geodesy 88:283-311.
    DOI 10.1007/s00190-013-0685-5.
    → ETM log/exp basis: log(1+(t-t_r)/τ), exp(-(t-t_r)/τ); Eq. 1.

Bedford, J. & Bevis, M. (2018). Greedy automatic signal decomposition and its
    application to daily GPS time series. J. Geophys. Res. Solid Earth 123.
    DOI 10.1029/2017JB014987.
    → GrAtSiD feature list: {type, t_ref, tau, amplitude}.
"""

from __future__ import annotations

import copy
import logging
from typing import Literal

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
# ETM key helpers
# ---------------------------------------------------------------------------


def _parse_etm_transient_key(key: str) -> dict:
    """Parse ETM transient key into {type, t_ref, tau}.

    Key format (from ETM fitter, Bevis & Brown 2014):
      'log_{t_ref:.6g}_tau{tau:.6g}'
      'exp_{t_ref:.6g}_tau{tau:.6g}'
    """
    if key.startswith("log_"):
        basis, rest = "log", key[4:]
    elif key.startswith("exp_"):
        basis, rest = "exp", key[4:]
    else:
        raise ValueError(f"Not an ETM transient key: '{key}'")
    idx = rest.rfind("_tau")
    if idx < 0:
        raise ValueError(f"Cannot parse '_tau' separator from ETM key: '{key}'")
    return {"type": basis, "t_ref": float(rest[:idx]), "tau": float(rest[idx + 4:])}


def _etm_transient_key(basis: str, t_ref: float, tau: float) -> str:
    return f"{basis}_{float(t_ref):.6g}_tau{float(tau):.6g}"


def _etm_basis_values(
    t: np.ndarray, t_ref: float, tau: float, basis: str
) -> np.ndarray:
    """Compute unnormalised ETM basis vector (without amplitude scaling).

    Reference: Bevis & Brown (2014) Eq. 1 — log1p and exp transient terms.
    """
    pos = np.maximum(0.0, (t - float(t_ref)) / float(tau))
    if basis == "log":
        return np.log1p(pos)
    if basis == "exp":
        return np.exp(-pos)
    raise ValueError(f"Unknown ETM transient basis: '{basis}'")


def _require_etm_transient(blob: DecompositionBlob, feature_id: str) -> str:
    """Return feature_id if valid ETM transient key, else raise ValueError."""
    if not (feature_id.startswith("log_") or feature_id.startswith("exp_")):
        raise ValueError(
            f"transient op: '{feature_id}' is not an ETM transient key "
            "(must start with 'log_' or 'exp_')."
        )
    if feature_id not in blob.coefficients:
        avail = [k for k in blob.coefficients if k.startswith(("log_", "exp_"))]
        raise ValueError(
            f"transient op: '{feature_id}' not found in blob.coefficients. "
            f"Available transient keys: {avail}."
        )
    return feature_id


# ---------------------------------------------------------------------------
# GrAtSiD feature helpers
# ---------------------------------------------------------------------------


def _gratsid_feature(blob: DecompositionBlob, feature_id) -> dict:
    """Return the GrAtSiD feature dict for feature_id.

    feature_id: int index into blob.coefficients['features'], or 'transient'
    for the stub's single Gaussian transient.
    """
    if "features" in blob.coefficients:
        idx = int(feature_id)
        features = blob.coefficients["features"]
        if not (0 <= idx < len(features)):
            raise ValueError(
                f"GrAtSiD: feature index {idx} out of range [0, {len(features) - 1}]."
            )
        return features[idx]
    # Stub fallback: construct synthetic feature dict from stub coefficients
    if feature_id != "transient":
        raise ValueError(
            f"GrAtSiD stub: feature_id must be 'transient' or int index; got '{feature_id}'. "
            "Full GrAtSiD (SEG-018) not yet available."
        )
    comp = blob.components.get("transient", np.zeros(1))
    peak_idx = int(blob.coefficients.get("peak_index", np.argmax(np.abs(comp))))
    amplitude = float(comp[peak_idx]) if len(comp) > peak_idx else 0.0
    return {
        "type": "gaussian",
        "t_ref": float(peak_idx),
        "tau": float(blob.coefficients.get("sigma", 1.0)),
        "amplitude": amplitude,
    }


def _gratsid_compute_component(feature: dict, t: np.ndarray) -> np.ndarray:
    """Compute transient component array from a GrAtSiD feature dict.

    Reference: Bedford & Bevis (2018) — GrAtSiD feature parameterisation.
    """
    t_ref = float(feature["t_ref"])
    tau = float(feature["tau"])
    amplitude = float(feature["amplitude"])
    ftype = feature.get("type", "gaussian")
    if ftype == "gaussian":
        return amplitude * np.exp(-0.5 * ((t - t_ref) / tau) ** 2)
    pos = np.maximum(0.0, (t - t_ref) / tau)
    if ftype == "log":
        return amplitude * np.log1p(pos)
    if ftype == "exp":
        return amplitude * np.exp(-pos)
    logger.warning("GrAtSiD: unknown feature type '%s'; using Gaussian.", ftype)
    return amplitude * np.exp(-0.5 * ((t - t_ref) / tau) ** 2)


def _gratsid_update_stub_component(blob: DecompositionBlob, feature: dict, t: np.ndarray) -> None:
    """Recompute stub transient component in-place from feature dict."""
    blob.components["transient"] = _gratsid_compute_component(feature, t)
    blob.coefficients["peak_index"] = float(feature["t_ref"])
    blob.coefficients["sigma"] = float(feature["tau"])


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


def remove(
    blob: DecompositionBlob,
    feature_id,
    pre_shape: str = "transient",
    t: np.ndarray | None = None,
) -> Tier2OpResult:
    """Remove a transient feature from the segment.

    ETM: deletes the transient coefficient and component at feature_id.
    GrAtSiD (features list): removes the feature from the features list and
    recomputes components['transient'] as the sum of remaining features.
    Requires t when using the full GrAtSiD features format.
    GrAtSiD (stub): zeros components['transient'].

    Relabeling: RECLASSIFY_VIA_SEGMENTER — the post-removal shape depends on
    the remaining signal.

    Reference: Bevis & Brown (2014) Eq. 1 — removing a transient term.

    Args:
        blob:       ETM or GrAtSiD DecompositionBlob.
        feature_id: ETM key string or GrAtSiD feature index / 'transient'.
        pre_shape:  Shape label before the edit.
        t:          Time axis (n,); required for GrAtSiD full-features format.

    Returns:
        Tier2OpResult with de-transient-ed values and RECLASSIFY relabeling.
    """
    blob = copy.deepcopy(blob)
    if blob.method == "ETM":
        _require_etm_transient(blob, str(feature_id))
        del blob.coefficients[str(feature_id)]
        blob.components.pop(str(feature_id), None)
    elif blob.method == "GrAtSiD":
        if "features" in blob.coefficients:
            if t is None:
                raise ValueError(
                    "remove: t (time axis) is required when blob.method='GrAtSiD' "
                    "with full features list (SEG-018 format)."
                )
            _gratsid_feature(blob, feature_id)  # validates bounds, raises ValueError if OOB
            idx = int(feature_id)
            blob.coefficients["features"].pop(idx)
            t_arr = np.asarray(t, dtype=np.float64)
            remaining = blob.coefficients["features"]
            blob.components["transient"] = (
                np.sum([_gratsid_compute_component(f, t_arr) for f in remaining], axis=0)
                if remaining
                else np.zeros(len(t_arr))
            )
        else:
            if feature_id != "transient":
                raise ValueError(
                    f"GrAtSiD stub: feature_id must be 'transient' or int index; got '{feature_id}'. "
                    "Full GrAtSiD (SEG-018) not yet available."
                )
            blob.components["transient"] = np.zeros_like(
                blob.components.get("transient", np.zeros(1))
            )
    else:
        raise ValueError(f"remove: unsupported blob method '{blob.method}'.")
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_reclassify(pre_shape),
        op_name="remove",
    )


# ---------------------------------------------------------------------------
# amplify
# ---------------------------------------------------------------------------


def amplify(
    blob: DecompositionBlob,
    feature_id,
    alpha: float,
    pre_shape: str = "transient",
    t: np.ndarray | None = None,
) -> Tier2OpResult:
    """Scale the transient feature amplitude by alpha.

    ETM: multiplies both the coefficient and the component array.
    GrAtSiD (features list): multiplies feature['amplitude'] and recomputes
    components['transient'] as the sum of all features' contributions.
    Requires t when using the full GrAtSiD features format.
    GrAtSiD (stub): scales components['transient'] directly (no t needed).

    Reference: Bevis & Brown (2014) Eq. 1 — scaling the transient amplitude.

    Args:
        blob:       ETM or GrAtSiD DecompositionBlob.
        feature_id: ETM key string or GrAtSiD feature index / 'transient'.
        alpha:      Amplitude scale factor.
        pre_shape:  Shape label before the edit.
        t:          Time axis (n,); required for GrAtSiD full-features format.

    Returns:
        Tier2OpResult with scaled values and PRESERVED('transient').
    """
    blob = copy.deepcopy(blob)
    if blob.method == "ETM":
        key = _require_etm_transient(blob, str(feature_id))
        blob.coefficients[key] = float(blob.coefficients[key]) * float(alpha)
        if key in blob.components:
            blob.components[key] = blob.components[key] * float(alpha)
    elif blob.method == "GrAtSiD":
        if "features" in blob.coefficients:
            if t is None:
                raise ValueError(
                    "amplify: t (time axis) is required when blob.method='GrAtSiD' "
                    "with full features list (SEG-018 format)."
                )
            t_arr = np.asarray(t, dtype=np.float64)
            feat = _gratsid_feature(blob, feature_id)
            feat["amplitude"] = float(feat["amplitude"]) * float(alpha)
            blob.components["transient"] = np.sum(
                [_gratsid_compute_component(f, t_arr) for f in blob.coefficients["features"]],
                axis=0,
            )
        else:
            blob.components["transient"] = (
                blob.components.get("transient", np.zeros(1)) * float(alpha)
            )
    else:
        raise ValueError(f"amplify: unsupported blob method '{blob.method}'.")
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="amplify",
    )


# ---------------------------------------------------------------------------
# dampen
# ---------------------------------------------------------------------------


def dampen(
    blob: DecompositionBlob,
    feature_id,
    alpha: float,
    pre_shape: str = "transient",
    t: np.ndarray | None = None,
) -> Tier2OpResult:
    """Reduce the transient feature amplitude by alpha ∈ (0, 1].

    Validated wrapper around amplify for the dampening use-case.

    Reference: Bevis & Brown (2014) Eq. 1 — scaling the transient amplitude.

    Args:
        blob:       ETM or GrAtSiD DecompositionBlob.
        feature_id: ETM key string or GrAtSiD feature index / 'transient'.
        alpha:      Dampening factor in (0, 1].
        pre_shape:  Shape label before the edit.
        t:          Time axis (n,); forwarded to amplify for GrAtSiD full-features.

    Returns:
        Tier2OpResult with dampened values and PRESERVED('transient').

    Raises:
        ValueError: If alpha is not in (0, 1].
    """
    if not (0.0 < float(alpha) <= 1.0):
        raise ValueError(
            f"dampen: alpha must be in (0, 1], got {alpha!r}. "
            "Use amplify(alpha=0) to remove the feature."
        )
    result = amplify(blob, feature_id, float(alpha), pre_shape=pre_shape, t=t)
    return Tier2OpResult(
        values=result.values,
        relabel=_preserved(pre_shape),
        op_name="dampen",
    )


# ---------------------------------------------------------------------------
# shift_time
# ---------------------------------------------------------------------------


def shift_time(
    blob: DecompositionBlob,
    feature_id,
    delta_t: float,
    t: np.ndarray,
    pre_shape: str = "transient",
) -> Tier2OpResult:
    """Move the transient reference time by delta_t, recomputing the component.

    ETM: renames the key (new t_ref = old t_ref + delta_t) and recomputes
    the log/exp component on the new time axis.
    GrAtSiD: updates feature['t_ref'] and recomputes the component.

    Reference: Bevis & Brown (2014) Eq. 1 — t_r,j re-indexed.

    Args:
        blob:       ETM or GrAtSiD DecompositionBlob.
        feature_id: ETM key string or GrAtSiD feature index / 'transient'.
        delta_t:    Time shift (positive → later, negative → earlier).
        t:          Time axis for the segment, shape (n,).
        pre_shape:  Shape label before the edit.

    Returns:
        Tier2OpResult with shifted transient values and PRESERVED('transient').
    """
    blob = copy.deepcopy(blob)
    t_arr = np.asarray(t, dtype=np.float64)
    if blob.method == "ETM":
        key = _require_etm_transient(blob, str(feature_id))
        info = _parse_etm_transient_key(key)
        amplitude = float(blob.coefficients.pop(key))
        blob.components.pop(key, None)
        info["t_ref"] += float(delta_t)
        new_key = _etm_transient_key(info["type"], info["t_ref"], info["tau"])
        blob.coefficients[new_key] = amplitude
        blob.components[new_key] = amplitude * _etm_basis_values(
            t_arr, info["t_ref"], info["tau"], info["type"]
        )
    elif blob.method == "GrAtSiD":
        feat = _gratsid_feature(blob, feature_id)
        feat["t_ref"] = float(feat["t_ref"]) + float(delta_t)
        if "features" in blob.coefficients:
            blob.components["transient"] = np.sum(
                [_gratsid_compute_component(f, t_arr) for f in blob.coefficients["features"]],
                axis=0,
            )
        else:
            _gratsid_update_stub_component(blob, feat, t_arr)
    else:
        raise ValueError(f"shift_time: unsupported blob method '{blob.method}'.")
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="shift_time",
    )


# ---------------------------------------------------------------------------
# change_duration
# ---------------------------------------------------------------------------


def change_duration(
    blob: DecompositionBlob,
    feature_id,
    s: float,
    t: np.ndarray,
    pre_shape: str = "transient",
) -> Tier2OpResult:
    """Scale the transient duration (timescale τ) by factor s.

    ETM: renames the key (new τ = old τ × s) and recomputes the component.
    GrAtSiD: updates feature['tau'] (or feature['duration_scale'] if present).

    Reference: Bevis & Brown (2014) Eq. 1 — τ controls the log/exp decay width.

    Args:
        blob:       ETM or GrAtSiD DecompositionBlob.
        feature_id: ETM key string or GrAtSiD feature index / 'transient'.
        s:          Scale factor for τ (> 0).
        t:          Time axis for the segment, shape (n,).
        pre_shape:  Shape label before the edit.

    Returns:
        Tier2OpResult with reshaped transient values and PRESERVED('transient').

    Raises:
        ValueError: If s <= 0.
    """
    if float(s) <= 0.0:
        raise ValueError(f"change_duration: s must be > 0, got {s!r}.")
    blob = copy.deepcopy(blob)
    t_arr = np.asarray(t, dtype=np.float64)
    if blob.method == "ETM":
        key = _require_etm_transient(blob, str(feature_id))
        info = _parse_etm_transient_key(key)
        amplitude = float(blob.coefficients.pop(key))
        blob.components.pop(key, None)
        info["tau"] = max(1e-12, float(info["tau"]) * float(s))
        new_key = _etm_transient_key(info["type"], info["t_ref"], info["tau"])
        blob.coefficients[new_key] = amplitude
        blob.components[new_key] = amplitude * _etm_basis_values(
            t_arr, info["t_ref"], info["tau"], info["type"]
        )
    elif blob.method == "GrAtSiD":
        feat = _gratsid_feature(blob, feature_id)
        if "duration_scale" in feat:
            feat["duration_scale"] = float(s)
        else:
            feat["tau"] = max(1e-12, float(feat["tau"]) * float(s))
        if "features" in blob.coefficients:
            blob.components["transient"] = np.sum(
                [_gratsid_compute_component(f, t_arr) for f in blob.coefficients["features"]],
                axis=0,
            )
        else:
            _gratsid_update_stub_component(blob, feat, t_arr)
    else:
        raise ValueError(f"change_duration: unsupported blob method '{blob.method}'.")
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="change_duration",
    )


# ---------------------------------------------------------------------------
# change_decay_constant
# ---------------------------------------------------------------------------


def change_decay_constant(
    blob: DecompositionBlob,
    feature_id,
    beta: float,
    t: np.ndarray,
    pre_shape: str = "transient",
) -> Tier2OpResult:
    """Scale the decay constant τ of the transient feature by beta.

    Equivalent to change_duration(s=beta) for ETM blobs.  For GrAtSiD blobs,
    always updates feature['tau'] directly (bypasses duration_scale).

    Reference: Bevis & Brown (2014) Eq. 1 — τ parameterises the decay rate.

    Args:
        blob:       ETM or GrAtSiD DecompositionBlob.
        feature_id: ETM key string or GrAtSiD feature index / 'transient'.
        beta:       Scale factor for τ (> 0).
        t:          Time axis for the segment, shape (n,).
        pre_shape:  Shape label before the edit.

    Returns:
        Tier2OpResult with rescaled decay values and PRESERVED('transient').

    Raises:
        ValueError: If beta <= 0.
    """
    if float(beta) <= 0.0:
        raise ValueError(f"change_decay_constant: beta must be > 0, got {beta!r}.")
    blob = copy.deepcopy(blob)
    t_arr = np.asarray(t, dtype=np.float64)
    if blob.method == "ETM":
        key = _require_etm_transient(blob, str(feature_id))
        info = _parse_etm_transient_key(key)
        amplitude = float(blob.coefficients.pop(key))
        blob.components.pop(key, None)
        info["tau"] = max(1e-12, float(info["tau"]) * float(beta))
        new_key = _etm_transient_key(info["type"], info["t_ref"], info["tau"])
        blob.coefficients[new_key] = amplitude
        blob.components[new_key] = amplitude * _etm_basis_values(
            t_arr, info["t_ref"], info["tau"], info["type"]
        )
    elif blob.method == "GrAtSiD":
        feat = _gratsid_feature(blob, feature_id)
        feat["tau"] = max(1e-12, float(feat["tau"]) * float(beta))
        if "features" in blob.coefficients:
            blob.components["transient"] = np.sum(
                [_gratsid_compute_component(f, t_arr) for f in blob.coefficients["features"]],
                axis=0,
            )
        else:
            _gratsid_update_stub_component(blob, feat, t_arr)
    else:
        raise ValueError(f"change_decay_constant: unsupported blob method '{blob.method}'.")
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="change_decay_constant",
    )


# ---------------------------------------------------------------------------
# replace_shape
# ---------------------------------------------------------------------------


def replace_shape(
    blob: DecompositionBlob,
    feature_id,
    new_basis: Literal["log", "exp", "both"],
    t: np.ndarray,
    pre_shape: str = "transient",
) -> Tier2OpResult:
    """Replace the transient basis (log/exp/both), refitting amplitude to preserve energy.

    The new amplitude is found via OLS minimising ||amplitude × new_basis(t) − old_component||².
    For new_basis='both', two separate log and exp keys are inserted with OLS amplitudes.

    Reference: Bevis & Brown (2014) Eq. 1 — log/exp basis alternatives.

    Args:
        blob:       ETM DecompositionBlob (GrAtSiD updates feature type).
        feature_id: ETM key string or GrAtSiD feature index / 'transient'.
        new_basis:  'log', 'exp', or 'both'.
        t:          Time axis for the segment, shape (n,).
        pre_shape:  Shape label before the edit.

    Returns:
        Tier2OpResult with re-fitted transient values and PRESERVED('transient').

    Raises:
        ValueError: If new_basis is invalid.
    """
    if new_basis not in ("log", "exp", "both"):
        raise ValueError(
            f"replace_shape: new_basis must be 'log', 'exp', or 'both'; got '{new_basis}'."
        )
    blob = copy.deepcopy(blob)
    t_arr = np.asarray(t, dtype=np.float64)

    if blob.method == "ETM":
        key = _require_etm_transient(blob, str(feature_id))
        info = _parse_etm_transient_key(key)
        old_component = blob.components.pop(key)
        blob.coefficients.pop(key)
        t_ref, tau = info["t_ref"], info["tau"]
        pos = np.maximum(0.0, (t_arr - t_ref) / tau)

        if new_basis in ("log", "exp"):
            basis_vec = np.log1p(pos) if new_basis == "log" else np.exp(-pos)
            denom = float(np.dot(basis_vec, basis_vec)) + 1e-12
            a = float(np.dot(old_component, basis_vec)) / denom
            new_key = _etm_transient_key(new_basis, t_ref, tau)
            blob.coefficients[new_key] = a
            blob.components[new_key] = a * basis_vec
        else:  # 'both'
            log_vec = np.log1p(pos)
            exp_vec = np.exp(-pos)
            A = np.column_stack([log_vec, exp_vec])
            coeff, _, _, _ = np.linalg.lstsq(A, old_component, rcond=None)
            a_log, a_exp = float(coeff[0]), float(coeff[1])
            log_key = _etm_transient_key("log", t_ref, tau)
            exp_key = _etm_transient_key("exp", t_ref, tau)
            blob.coefficients[log_key] = a_log
            blob.components[log_key] = a_log * log_vec
            blob.coefficients[exp_key] = a_exp
            blob.components[exp_key] = a_exp * exp_vec

    elif blob.method == "GrAtSiD":
        if new_basis == "both":
            raise ValueError(
                "replace_shape: new_basis='both' is not supported for GrAtSiD blobs. "
                "GrAtSiD features are single-type; use two separate features instead."
            )
        feat = _gratsid_feature(blob, feature_id)
        feat["type"] = new_basis
        old_component = blob.components.get("transient", np.zeros_like(t_arr))
        # Compute unit basis vector (amplitude=1) to avoid divide-by-amplitude issues
        unit_feat = {**feat, "amplitude": 1.0}
        basis_vec = _gratsid_compute_component(unit_feat, t_arr)
        denom = float(np.dot(basis_vec, basis_vec)) + 1e-12
        a = float(np.dot(old_component, basis_vec)) / denom
        feat["amplitude"] = a
        if "features" in blob.coefficients:
            blob.components["transient"] = np.sum(
                [_gratsid_compute_component(f, t_arr) for f in blob.coefficients["features"]],
                axis=0,
            )
        else:
            _gratsid_update_stub_component(blob, feat, t_arr)
    else:
        raise ValueError(f"replace_shape: unsupported blob method '{blob.method}'.")

    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="replace_shape",
    )


# ---------------------------------------------------------------------------
# duplicate
# ---------------------------------------------------------------------------


def duplicate(
    blob: DecompositionBlob,
    feature_id,
    delta_t: float,
    t: np.ndarray,
    pre_shape: str = "transient",
) -> Tier2OpResult:
    """Add a second transient feature at t_ref + delta_t with the same parameters.

    Two transients within one segment suggest a split; RECLASSIFY_VIA_SEGMENTER
    is signalled to prompt re-segmentation.

    Reference: Bevis & Brown (2014) Eq. 1 — additional transient term.

    Args:
        blob:       ETM or GrAtSiD DecompositionBlob.
        feature_id: ETM key string or GrAtSiD feature index / 'transient'.
        delta_t:    Time offset for the duplicate transient.
        t:          Time axis for the segment, shape (n,).
        pre_shape:  Shape label before the edit.

    Returns:
        Tier2OpResult with two-transient values and RECLASSIFY relabeling.

    Raises:
        ValueError: If delta_t == 0.
    """
    if float(delta_t) == 0.0:
        raise ValueError("duplicate: delta_t must be non-zero.")
    blob = copy.deepcopy(blob)
    t_arr = np.asarray(t, dtype=np.float64)
    if blob.method == "ETM":
        key = _require_etm_transient(blob, str(feature_id))
        info = _parse_etm_transient_key(key)
        amplitude = float(blob.coefficients[key])
        new_t_ref = info["t_ref"] + float(delta_t)
        new_key = _etm_transient_key(info["type"], new_t_ref, info["tau"])
        blob.coefficients[new_key] = amplitude
        blob.components[new_key] = amplitude * _etm_basis_values(
            t_arr, new_t_ref, info["tau"], info["type"]
        )
    elif blob.method == "GrAtSiD":
        feat = _gratsid_feature(blob, feature_id)
        new_feat = {**feat, "t_ref": float(feat["t_ref"]) + float(delta_t)}
        if "features" in blob.coefficients:
            blob.coefficients["features"].append(new_feat)
            blob.components["transient"] = np.sum(
                [_gratsid_compute_component(f, t_arr) for f in blob.coefficients["features"]],
                axis=0,
            )
        else:
            logger.warning(
                "duplicate: GrAtSiD stub does not support multiple features; "
                "adding second transient component."
            )
            new_comp = _gratsid_compute_component(new_feat, t_arr)
            blob.components["transient_2"] = new_comp
    else:
        raise ValueError(f"duplicate: unsupported blob method '{blob.method}'.")
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_reclassify(pre_shape),
        op_name="duplicate",
    )


# ---------------------------------------------------------------------------
# convert_to_step
# ---------------------------------------------------------------------------


def convert_to_step(
    blob: DecompositionBlob,
    feature_id,
    t: np.ndarray,
    pre_shape: str = "transient",
) -> Tier2OpResult:
    """Replace the transient with a Heaviside step at the same reference time.

    The transient is removed and replaced by a step_at_{t_ref} key with the
    same amplitude, using the ETM Heaviside convention (Bevis & Brown 2014).

    Relabeling: DETERMINISTIC('step').

    Reference: Bevis & Brown (2014) Eq. 1 — Δᵢ·H(t − t_s,i) step term.

    Args:
        blob:       ETM or GrAtSiD DecompositionBlob.
        feature_id: ETM key string or GrAtSiD feature index / 'transient'.
        t:          Time axis for the segment, shape (n,).
        pre_shape:  Shape label before the edit.

    Returns:
        Tier2OpResult with step-converted values and DETERMINISTIC('step').
    """
    blob = copy.deepcopy(blob)
    t_arr = np.asarray(t, dtype=np.float64)
    if blob.method == "ETM":
        key = _require_etm_transient(blob, str(feature_id))
        info = _parse_etm_transient_key(key)
        amplitude = float(blob.coefficients.pop(key))
        blob.components.pop(key, None)
        t_ref = info["t_ref"]
    elif blob.method == "GrAtSiD":
        feat = _gratsid_feature(blob, feature_id)
        t_ref = float(feat["t_ref"])
        amplitude = float(feat["amplitude"])
        if "features" in blob.coefficients:
            blob.coefficients["features"].pop(int(feature_id))
        else:
            blob.components["transient"] = np.zeros_like(
                blob.components.get("transient", np.zeros(len(t_arr)))
            )
    else:
        raise ValueError(f"convert_to_step: unsupported blob method '{blob.method}'.")

    step_key = f"step_at_{float(t_ref):.6g}"
    blob.coefficients[step_key] = amplitude
    blob.components[step_key] = amplitude * (t_arr >= float(t_ref)).astype(np.float64)

    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_deterministic("step"),
        op_name="convert_to_step",
    )
