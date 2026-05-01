"""GrAtSiD — Greedy Automatic Signal Decomposition (SEG-018).

Iterative basis-pursuit fitter for transient features in geodetic-style
time series.  At each step the residual is projected onto a grid of
(``type``, ``t_ref``, ``τ``) basis functions; the best-scoring projection
is added as a feature and its contribution is subtracted before the next
iteration.

References
----------
- Bedford, J. & Bevis, M. (2018) "Greedy Automatic Signal Decomposition
  and Its Application to Daily GPS Time Series" — *J. Geophys. Res.
  Solid Earth* 123(8):6901–6919.  DOI 10.1029/2017JB014765.
- Klos, A., Olivares, G., Teferle, F.N., Hunegnaw, A., Bogusz, J. (2018)
  "On the combined effect of periodic signals and colored noise on
  velocity uncertainties" — *GPS Solutions* 22:1.

Output contract
---------------
``DecompositionBlob`` with:

  ``method``       — ``'GrAtSiD'``
  ``components``   — ``{'skeleton', 'transient', 'residual'}``
  ``coefficients`` — ``{'features': list[{type, t_ref, tau, amplitude}],
                         'n_features': int,
                         'skeleton': {'slope', 'intercept', ...}}``
  ``residual``     — final residual array (also in ``components['residual']``)

The feature dict shape mirrors what
``backend/app/services/operations/tier2/transient.py::_gratsid_feature``
already reads, so OP-025 transient ops (amplify / shift_time /
change_decay_constant / replace_shape / convert_to_step / ...) can edit
GrAtSiD output directly.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


DEFAULT_BASIS_TYPES: tuple[str, ...] = ("log", "exp", "step")
DEFAULT_MAX_FEATURES: int = 30
DEFAULT_RESIDUAL_THRESHOLD: float = 0.05
DEFAULT_CANDIDATE_TOP_K: int = 20

# Bedford 2018 §3: avoid duplicate basis selections.  Two features in the
# same (type, t_ref, τ) family are considered duplicates when their τ values
# agree to ±10 % and their t_ref values are within ``DUP_T_REF_GAP_FRAC``
# of segment length.
DUP_TAU_REL_TOL: float = 0.10
DUP_T_REF_GAP_FRAC: float = 0.05

# Numerical floor for the OLS projection denominator.
_EPS = 1e-12


def _default_tau_grid() -> np.ndarray:
    """Default τ grid: log-spaced 1 → 1000 days, 20 points."""
    return np.logspace(0, 3, 20)


# ---------------------------------------------------------------------------
# Basis functions — formulas matched to the OP-025 transient reader
# ``_gratsid_compute_component`` in services/operations/tier2/transient.py.
# Keep these two in lockstep: a feature emitted here must reassemble
# bit-identically when read back through that path.
# ---------------------------------------------------------------------------


def basis(
    btype: str,
    t_ref: float,
    tau: float,
    t: np.ndarray,
) -> np.ndarray:
    """Evaluate a single basis function at every sample in ``t``.

    Supported types:
      ``log``   amplitude·log(1 + max(0, (t − t_ref)/τ))
      ``exp``   amplitude·exp(−max(0, (t − t_ref)/τ))
                — value 1 before t_ref, decaying after (matches OP-025).
      ``step``  Heaviside H(t − t_ref).  τ is ignored but kept in the
                feature dict for uniform schema.

    Returns an array shape == ``t.shape`` with unit amplitude.  The
    greedy loop scales by the OLS-projected amplitude.
    """
    arr = np.asarray(t, dtype=np.float64)
    if btype == "step":
        return (arr >= t_ref).astype(np.float64)
    safe_tau = max(float(tau), _EPS)
    pos = np.maximum(0.0, (arr - t_ref) / safe_tau)
    if btype == "log":
        return np.log1p(pos)
    if btype == "exp":
        return np.exp(-pos)
    raise ValueError(
        f"GrAtSiD basis: unknown type {btype!r}; "
        f"expected one of 'log', 'exp', 'step'."
    )


# ---------------------------------------------------------------------------
# Candidate t_ref selection — top-k residual energy + segment-start anchor
# ---------------------------------------------------------------------------


def candidate_t_refs(
    residual: np.ndarray,
    t: np.ndarray,
    top_k: int = DEFAULT_CANDIDATE_TOP_K,
    min_spacing: int = 1,
) -> list[float]:
    """Return candidate t_ref values likely to be transient onsets.

    Onsets of log / exp / step bases sit at *kinks* in the residual —
    points where the derivative changes sharply — not at the points of
    largest ``|residual|`` (a monotone log climbs to its asymptote far
    from its onset).  Candidates are therefore ranked by the absolute
    discrete derivative ``|Δresidual|``, then deduplicated by a minimum
    spacing, with the segment endpoints always included so step features
    at the boundary are reachable.

    Args:
        residual:    Current residual array, shape (n,).
        t:           Time axis (same length as residual).
        top_k:       Maximum number of candidates after deduplication.
        min_spacing: Minimum index gap between accepted candidates.

    Returns:
        Sorted list of ``t`` values.
    """
    n = len(residual)
    if n == 0:
        return []
    if n == 1:
        return [float(t[0])]

    # Discrete derivative magnitude — onset detector.  Pad to length n so
    # index alignment with ``t`` is preserved.
    diff = np.abs(np.diff(residual))
    score = np.concatenate([diff, [diff[-1]]])

    order = np.argsort(-score)  # descending
    spacing = max(1, min_spacing)
    chosen: list[int] = []
    for idx in order:
        if any(abs(idx - c) < spacing for c in chosen):
            continue
        chosen.append(int(idx))
        if len(chosen) >= top_k:
            break
    # Always allow features at the segment boundaries.
    for endpoint in (0, n - 1):
        if endpoint not in chosen:
            chosen.append(endpoint)
    chosen.sort()
    return [float(t[i]) for i in chosen]


# ---------------------------------------------------------------------------
# Skeleton fit — OLS linear (+ optional seasonal at a known period)
# ---------------------------------------------------------------------------


def _fit_skeleton(
    X: np.ndarray,
    t: np.ndarray,
    seasonal_period: float | None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Fit a linear (+ optional seasonal) skeleton.

    The skeleton absorbs the structured background that the greedy loop
    should *not* explain with transients.  When ``seasonal_period`` is
    None (the default), a pure linear fit is performed — leaving all
    remaining structure for the basis loop to chase.

    Returns ``(skeleton_array, coefficients_dict)``.
    """
    n = len(X)
    if n == 0:
        return np.array([], dtype=np.float64), {"slope": 0.0, "intercept": 0.0}

    cols = [np.ones_like(t), t.astype(np.float64)]
    labels = ["intercept", "slope"]

    if seasonal_period is not None and seasonal_period > 0:
        omega = 2.0 * np.pi / float(seasonal_period)
        cols.extend([np.sin(omega * t), np.cos(omega * t)])
        labels.extend(["sin_seasonal", "cos_seasonal"])

    A = np.stack(cols, axis=1)
    coeffs, *_ = np.linalg.lstsq(A, X, rcond=None)
    skeleton = A @ coeffs
    coeff_dict: dict[str, Any] = {labels[i]: float(coeffs[i]) for i in range(len(labels))}
    if seasonal_period is not None:
        coeff_dict["seasonal_period"] = float(seasonal_period)
    return skeleton, coeff_dict


# ---------------------------------------------------------------------------
# Duplicate suppression
# ---------------------------------------------------------------------------


def _is_duplicate(
    candidate: dict[str, Any],
    existing: list[dict[str, Any]],
    n_samples: int,
) -> bool:
    """Test whether ``candidate`` duplicates an already-selected feature.

    Two features are considered duplicates iff they share ``type``, their
    ``t_ref`` values are within ``DUP_T_REF_GAP_FRAC × n_samples``, AND
    (for non-step types) their τ values agree to ``DUP_TAU_REL_TOL``.
    Step features ignore τ entirely.
    """
    t_gap = max(1.0, DUP_T_REF_GAP_FRAC * float(n_samples))
    for feat in existing:
        if feat["type"] != candidate["type"]:
            continue
        if abs(feat["t_ref"] - candidate["t_ref"]) > t_gap:
            continue
        if candidate["type"] == "step":
            return True
        if abs(feat["tau"]) < _EPS:
            continue
        if abs(candidate["tau"] / feat["tau"] - 1.0) <= DUP_TAU_REL_TOL:
            return True
    return False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


@register_fitter("GrAtSiD")
def fit_gratsid(
    X: np.ndarray,
    t: np.ndarray | None = None,
    *,
    basis_types: Sequence[str] = DEFAULT_BASIS_TYPES,
    tau_grid: Sequence[float] | None = None,
    max_features: int = DEFAULT_MAX_FEATURES,
    residual_threshold: float = DEFAULT_RESIDUAL_THRESHOLD,
    candidate_top_k: int = DEFAULT_CANDIDATE_TOP_K,
    pre_skeleton: np.ndarray | None = None,
    seasonal_period: float | None = None,
    **_kwargs: Any,
) -> DecompositionBlob:
    """Greedy basis-pursuit fit for overlapping transients.

    Bedford & Bevis (2018) Algorithm 1.  Iteratively selects the basis
    function that best explains the current residual, subject to a
    duplicate-suppression rule (Bedford §3) and a stopping criterion
    on either ``max_features`` or relative residual reduction.

    Args:
        X:                  Segment values, shape ``(n,)``.
        t:                  Time axis; defaults to ``np.arange(n)``.
        basis_types:        Subset of ``('log', 'exp', 'step')`` to search.
        tau_grid:           τ values to try; default ``np.logspace(0, 3, 20)``.
        max_features:       Hard cap on the number of features extracted.
        residual_threshold: Stop when the best-scoring basis explains less
                            than this fraction of the current residual norm.
        candidate_top_k:    Number of high-energy t_ref candidates per iter.
        pre_skeleton:       Pre-computed skeleton array (e.g. ETM output);
                            when given, GrAtSiD skips its internal linear fit
                            and works directly on ``X − pre_skeleton``.
        seasonal_period:    Optional seasonal period for the internal
                            skeleton fit; ignored when ``pre_skeleton`` is
                            supplied.

    Returns:
        :class:`DecompositionBlob` with ``method='GrAtSiD'``.

    Raises:
        ValueError: ``X`` is multi-dimensional, ``residual_threshold`` is
                    not in (0, 1], or ``basis_types`` contains an unknown
                    type.
    """
    # ---- input validation ------------------------------------------------
    arr = np.asarray(X, dtype=np.float64)
    if arr.ndim > 1:
        if arr.ndim == 2 and arr.shape[1] == 1:
            arr = arr.ravel()
        else:
            raise ValueError(
                f"GrAtSiD: expected 1-D input; got shape {arr.shape}."
            )
    if not (0 < residual_threshold <= 1):
        raise ValueError(
            f"GrAtSiD: residual_threshold must lie in (0, 1]; got {residual_threshold!r}."
        )
    for bt in basis_types:
        if bt not in {"log", "exp", "step"}:
            raise ValueError(
                f"GrAtSiD: unknown basis type {bt!r}; expected 'log', 'exp', or 'step'."
            )

    n = len(arr)
    if n == 0:
        return DecompositionBlob(
            method="GrAtSiD",
            components={
                "skeleton": np.array([], dtype=np.float64),
                "transient": np.array([], dtype=np.float64),
                "residual": np.array([], dtype=np.float64),
            },
            coefficients={"features": [], "n_features": 0, "skeleton": {}},
            residual=np.array([], dtype=np.float64),
            fit_metadata={
                "rmse": 0.0,
                "rank": 0,
                "n_params": 0,
                "convergence": True,
                "version": "1.0",
                "iterations": 0,
            },
        )

    if t is None:
        t_axis = np.arange(n, dtype=np.float64)
    else:
        t_axis = np.asarray(t, dtype=np.float64).ravel()
        if len(t_axis) != n:
            raise ValueError(
                f"GrAtSiD: t length {len(t_axis)} does not match X length {n}."
            )

    grid = np.asarray(tau_grid if tau_grid is not None else _default_tau_grid(), dtype=np.float64)

    # ---- skeleton fit (or use the supplied one) --------------------------
    if pre_skeleton is not None:
        skeleton = np.asarray(pre_skeleton, dtype=np.float64).ravel()
        if len(skeleton) != n:
            raise ValueError(
                f"GrAtSiD: pre_skeleton length {len(skeleton)} does not match X length {n}."
            )
        skeleton_coeffs: dict[str, Any] = {"source": "pre_skeleton"}
    else:
        skeleton, skeleton_coeffs = _fit_skeleton(arr, t_axis, seasonal_period)

    residual = arr - skeleton
    initial_residual_norm = float(np.linalg.norm(residual))

    # ---- greedy loop -----------------------------------------------------
    features: list[dict[str, Any]] = []
    iterations = 0
    converged = True

    while len(features) < max_features:
        iterations += 1
        residual_norm = float(np.linalg.norm(residual))
        if residual_norm < _EPS:
            break

        candidates = candidate_t_refs(
            residual, t_axis, top_k=candidate_top_k, min_spacing=max(1, n // 50)
        )

        best_score = 0.0
        best_feature: dict[str, Any] | None = None
        best_basis_arr: np.ndarray | None = None

        for btype in basis_types:
            tau_iter = (1.0,) if btype == "step" else grid
            for t_ref in candidates:
                for tau in tau_iter:
                    b = basis(btype, t_ref, float(tau), t_axis)
                    bb = float(np.dot(b, b))
                    if bb < _EPS:
                        continue
                    amplitude = float(np.dot(b, residual) / bb)
                    score = abs(amplitude) * float(np.sqrt(bb))
                    if score <= best_score:
                        continue
                    feat = {
                        "type": btype,
                        "t_ref": float(t_ref),
                        "tau": float(tau),
                        "amplitude": amplitude,
                    }
                    if _is_duplicate(feat, features, n):
                        continue
                    best_score = score
                    best_feature = feat
                    best_basis_arr = b

        if best_feature is None or best_basis_arr is None:
            converged = True
            break

        # Stopping rule: best projection explains too little of the residual
        if residual_norm > 0 and best_score / residual_norm < residual_threshold:
            converged = True
            break

        features.append(best_feature)
        residual = residual - best_feature["amplitude"] * best_basis_arr

    if len(features) >= max_features:
        # Hit the hard cap — the residual may still carry signal.
        converged = False

    # ---- final OLS refinement pass --------------------------------------
    # Greedy projection underestimates feature amplitudes when bases overlap
    # (e.g. compounded steps).  Bedford 2018 Algorithm 1 closes the loop with
    # a single least-squares solve over all selected features against the
    # original signal-minus-skeleton.
    if features:
        design = np.stack(
            [basis(f["type"], f["t_ref"], f["tau"], t_axis) for f in features],
            axis=1,
        )
        target = arr - skeleton
        refined, *_ = np.linalg.lstsq(design, target, rcond=None)
        for i, feat in enumerate(features):
            feat["amplitude"] = float(refined[i])

    # ---- reassemble outputs ----------------------------------------------
    transient = np.zeros_like(arr)
    for feat in features:
        transient = transient + feat["amplitude"] * basis(
            feat["type"], feat["t_ref"], feat["tau"], t_axis
        )

    residual_final = arr - skeleton - transient
    rmse = float(np.sqrt(np.mean(residual_final ** 2)))
    explained = (
        1.0 - float(np.linalg.norm(residual_final)) / initial_residual_norm
        if initial_residual_norm > _EPS
        else 1.0
    )

    return DecompositionBlob(
        method="GrAtSiD",
        components={
            "skeleton": skeleton,
            "transient": transient,
            "residual": residual_final,
        },
        coefficients={
            "features": features,
            "n_features": len(features),
            "skeleton": skeleton_coeffs,
        },
        residual=residual_final,
        fit_metadata={
            "rmse": rmse,
            "rank": len(features),
            "n_params": 4 * len(features) + len(skeleton_coeffs),
            "convergence": bool(converged),
            "version": "1.0",
            "iterations": iterations,
            "explained_fraction": float(explained),
        },
    )
