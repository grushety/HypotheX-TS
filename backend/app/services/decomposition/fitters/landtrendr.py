"""LandTrendr fitter — Kennedy, Yang & Cohen (2010).

Vertex-based piecewise-linear trajectory segmentation for non-periodic
remote-sensing time series (NDVI, NBR, EVI).  Identifies a small set of
breakpoint vertices that define a continuous broken-line approximation of
the trajectory, with per-segment slopes and intercepts available as
editable coefficients for OP-021 (Trend ops) and OP-022 (disturbance /
recovery edits).

Algorithm outline (Kennedy 2010 §2.2):

1. **Candidate generation** — start from the two endpoints, then
   iteratively add the time index whose residual against the current
   piecewise-linear fit is largest (greedy SSE-reducing selection),
   until ``2 · max_vertices`` candidates exist or no residual remains.
2. **Subset selection** — starting from the full candidate set,
   iteratively drop the interior vertex whose removal least increases
   SSE.  Record the (k, vertices, SSE) triple at every step.
3. **Penalised pick** — among truncations with k ≤ max_vertices, choose
   the one minimising ``SSE + penalty_per_vertex · k``.

Vertex *Y* values are jointly fitted by ordinary least squares against a
linear B-spline (tent) basis with knots at the chosen X positions, so
the resulting trajectory is continuous at every vertex (no jumps) — this
matches Kennedy 2010 §2.4.

Backward compatibility: the existing OP-021 trend ops read the legacy
``slope_1 / slope_2 / intercept_1 / intercept_2 / breakpoint`` keys (the
2-segment LandTrendr stub schema).  This fitter therefore emits BOTH the
new generalised schema (``vertices``, ``slopes``, ``intercepts``,
``recovery``) and the legacy keys derived from the first / last segments
plus the first internal vertex, keeping OP-021 working unchanged for the
common 2-segment case and degrading gracefully for k > 3 vertices.

References
----------
Kennedy, R., Yang, Z., & Cohen, W. (2010).
    Detecting trends in forest disturbance and recovery using yearly
    Landsat time series: 1. LandTrendr — Temporal segmentation
    algorithms.  *Remote Sensing of Environment* 114(12):2897–2910.
    DOI 10.1016/j.rse.2010.07.008.
    → §2.2 candidate generation; §2.4 vertex Y-value fit; §2.5 penalty.

Kennedy, R. et al. (2018).
    Implementation of the LandTrendr algorithm on Google Earth Engine.
    *Remote Sensing* 10(5):691.
    → Reference implementation; default penalty values.
"""
from __future__ import annotations

import logging

import numpy as np

from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import register_fitter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers — design matrix and OLS fit
# ---------------------------------------------------------------------------


def _build_design_matrix(t: np.ndarray, vx: np.ndarray) -> np.ndarray:
    """Linear B-spline (tent) basis over knots ``vx`` evaluated at ``t``.

    Returns ``A`` of shape ``(n, k)`` with ``A[j, i]`` equal to the weight of
    vertex ``i`` at sample time ``t[j]``.  Inside ``[vx_i, vx_{i+1}]`` the
    function is the linear blend between ``vy_i`` and ``vy_{i+1}``;
    outside the knot range the boundary vertex carries weight 1 (so the
    fit clamps to the endpoint vertex Y value).
    """
    n = len(t)
    k = len(vx)
    A = np.zeros((n, k), dtype=np.float64)
    for j in range(n):
        ti = float(t[j])
        if ti <= vx[0]:
            A[j, 0] = 1.0
            continue
        if ti >= vx[-1]:
            A[j, -1] = 1.0
            continue
        for i in range(k - 1):
            if vx[i] <= ti <= vx[i + 1]:
                span = float(vx[i + 1] - vx[i])
                if span <= 0.0:
                    A[j, i] = 1.0
                    break
                w_right = (ti - vx[i]) / span
                A[j, i] = 1.0 - w_right
                A[j, i + 1] = w_right
                break
    return A


def _fit_vertices(
    X: np.ndarray, t: np.ndarray, vx: list[float]
) -> tuple[np.ndarray, np.ndarray, float]:
    """Anchored OLS-fit of vertex Y values for given vertex X positions.

    Per Kennedy 2010 §2.4: the endpoint vertex Y values are *anchored* to the
    observed data (``vy[0] = X[t≈vx[0]]``, ``vy[-1] = X[t≈vx[-1]]``) and only
    the interior vertex Y values are fitted by OLS — this guarantees the
    fitted trajectory passes through the boundary observations exactly, so
    that the candidate-generation residual is not dominated by endpoint
    behaviour.  For ``k=2`` (endpoints only) the fit is a direct line
    between the two boundary observations.
    """
    vx_arr = np.asarray(vx, dtype=np.float64)
    k = len(vx_arr)
    n = len(t)

    if k == 0:
        return np.zeros(0), np.zeros(n), 0.0

    A = _build_design_matrix(t, vx_arr)

    if k == 1:
        vy_val = float(X[int(np.argmin(np.abs(t - vx_arr[0])))])
        vy = np.array([vy_val])
        trend = np.full(n, vy_val, dtype=np.float64)
        sse = float(np.sum((X - trend) ** 2))
        return vy, trend, sse

    idx_left = int(np.argmin(np.abs(t - vx_arr[0])))
    idx_right = int(np.argmin(np.abs(t - vx_arr[-1])))
    vy_left = float(X[idx_left])
    vy_right = float(X[idx_right])

    if k == 2:
        vy = np.array([vy_left, vy_right])
    else:
        boundary = vy_left * A[:, 0] + vy_right * A[:, -1]
        target = X - boundary
        vy_interior, *_ = np.linalg.lstsq(A[:, 1:-1], target, rcond=None)
        vy = np.concatenate([[vy_left], vy_interior, [vy_right]])

    trend = A @ vy
    sse = float(np.sum((X - trend) ** 2))
    return vy, trend, sse


# ---------------------------------------------------------------------------
# Step 1 — candidate vertex generation (Kennedy 2010 §2.2)
# ---------------------------------------------------------------------------


def find_candidate_vertices(
    X: np.ndarray,
    t: np.ndarray | None = None,
    max_candidates: int = 12,
) -> list[float]:
    """Iterative SSE-reducing candidate-vertex selection.

    Starts from the two endpoints and repeatedly inserts the sample whose
    residual against the *current* OLS piecewise-linear fit is largest,
    until ``max_candidates`` vertices exist or no residual remains.

    Args:
        X:               Trajectory values, shape (n,).
        t:               Time index; defaults to ``np.arange(n)``.
        max_candidates:  Cap on candidate count; floored at 2.

    Returns:
        Sorted list of candidate vertex X positions (floats).
    """
    arr = np.asarray(X, dtype=np.float64).ravel()
    n = len(arr)
    if n == 0:
        return []
    if t is None:
        t_arr = np.arange(n, dtype=np.float64)
    else:
        t_arr = np.asarray(t, dtype=np.float64).ravel()
        if len(t_arr) != n:
            raise ValueError(
                f"find_candidate_vertices: t length {len(t_arr)} ≠ X length {n}."
            )
    if n < 2:
        return [float(t_arr[0])]

    cap = max(2, int(max_candidates))
    cap = min(cap, n)
    vx_positions: list[float] = [float(t_arr[0]), float(t_arr[-1])]

    while len(vx_positions) < cap:
        _, trend, _ = _fit_vertices(arr, t_arr, vx_positions)
        residual_abs = np.abs(arr - trend)

        # Mask out positions already at a vertex so we never pick a duplicate.
        for vx in vx_positions:
            idx = int(np.argmin(np.abs(t_arr - vx)))
            residual_abs[idx] = -1.0

        if float(residual_abs.max()) < 1e-12:
            break  # current fit is already exact

        best_idx = int(np.argmax(residual_abs))
        vx_positions.append(float(t_arr[best_idx]))
        vx_positions.sort()

    return vx_positions


# ---------------------------------------------------------------------------
# Step 1b — public per-vertex linear fit (helper for callers / tests)
# ---------------------------------------------------------------------------


def fit_piecewise_linear(
    X: np.ndarray,
    t: np.ndarray,
    vertices: list[float],
) -> tuple[list[tuple[float, float]], np.ndarray]:
    """OLS-fit a continuous piecewise-linear trajectory at given vertex positions.

    Args:
        X:        Trajectory values, shape (n,).
        t:        Time index, shape (n,).
        vertices: Sorted list of vertex X positions (≥ 2 entries).

    Returns:
        ``(vertex_pairs, trend)`` where ``vertex_pairs`` is a list of
        ``(vx, vy)`` tuples and ``trend`` is the fitted (n,) array.

    Raises:
        ValueError: ``vertices`` has fewer than 2 entries.
    """
    if len(vertices) < 2:
        raise ValueError(
            f"fit_piecewise_linear: need at least 2 vertices, got {len(vertices)}."
        )
    arr = np.asarray(X, dtype=np.float64).ravel()
    t_arr = np.asarray(t, dtype=np.float64).ravel()
    vx = sorted(float(v) for v in vertices)
    vy, trend, _ = _fit_vertices(arr, t_arr, vx)
    return list(zip(vx, vy.tolist())), trend


# ---------------------------------------------------------------------------
# Step 2 — iterative pruning to (k, vertices, sse) traces
# ---------------------------------------------------------------------------


def _prune_iteratively(
    X: np.ndarray,
    t: np.ndarray,
    candidates: list[float],
) -> list[tuple[int, list[float], np.ndarray, np.ndarray, float]]:
    """Iteratively drop the interior vertex whose removal least increases SSE.

    Returns a list of ``(k, vx_list, vy, trend, sse)`` snapshots from the full
    candidate set down to k = 2 (endpoints only).  Used by the penalised
    selector below.
    """
    history: list[tuple[int, list[float], np.ndarray, np.ndarray, float]] = []
    current = list(candidates)

    while len(current) >= 2:
        vy, trend, sse = _fit_vertices(X, t, current)
        history.append((len(current), list(current), vy, trend, sse))

        if len(current) == 2:
            break

        best_drop_sse = np.inf
        best_drop_idx = 1
        for drop_idx in range(1, len(current) - 1):
            trial = current[:drop_idx] + current[drop_idx + 1 :]
            _, _, sse_w = _fit_vertices(X, t, trial)
            if sse_w < best_drop_sse:
                best_drop_sse = sse_w
                best_drop_idx = drop_idx
        current.pop(best_drop_idx)

    return history


# ---------------------------------------------------------------------------
# Recovery flag (Kennedy 2010 §3.2)
# ---------------------------------------------------------------------------


def _recovery_flags(
    vertices: list[tuple[float, float]],
    slopes: list[float],
    threshold: float,
) -> list[bool]:
    """Tag a segment as ``recovery=True`` when it has positive slope and follows
    a negative-slope segment whose absolute Y drop exceeds ``threshold``.

    Implements the disturbance → recovery transition rule used by the
    remote-sensing semantic pack (SEG-023).
    """
    n_seg = len(slopes)
    flags = [False] * n_seg
    for i in range(1, n_seg):
        prev_slope = slopes[i - 1]
        curr_slope = slopes[i]
        delta_y_prev = vertices[i][1] - vertices[i - 1][1]
        if (
            prev_slope < 0.0
            and curr_slope > 0.0
            and abs(delta_y_prev) > float(threshold)
        ):
            flags[i] = True
    return flags


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


@register_fitter("LandTrendr")
def fit_landtrendr(
    X: np.ndarray,
    t: np.ndarray | None = None,
    max_vertices: int = 6,
    recovery_threshold: float = 0.25,
    penalty_per_vertex: float = 0.1,
    **_kwargs,
) -> DecompositionBlob:
    """Fit a LandTrendr (Kennedy 2010) piecewise-linear trajectory.

    Identifies up to ``max_vertices`` knot points and emits a continuous
    piecewise-linear approximation; per-segment slopes and intercepts are
    stored as editable coefficients.

    Args:
        X:                  Trajectory values, shape (n,).
        t:                  Time index; defaults to ``np.arange(n)``.
        max_vertices:       Cap on the chosen vertex count (≥ 2);
                            default 6 per Kennedy 2010 §2.5.
        recovery_threshold: Absolute Y drop above which a positive-slope
                            segment following a negative-slope segment is
                            tagged ``recovery=True``.  NDVI default 0.25.
        penalty_per_vertex: Penalty weight in ``SSE + λ·k``; default 0.1
                            per Kennedy 2018 EE implementation.

    Returns:
        :class:`DecompositionBlob` with ``method='LandTrendr'``,
        components ``{'trend', 'residual'}`` and coefficients

        * ``vertices``  — list of ``(vx, vy)`` tuples (new schema)
        * ``slopes``    — per-segment OLS slope (new schema)
        * ``intercepts``— per-segment OLS intercept (new schema)
        * ``recovery``  — per-segment ``bool`` recovery flag
        * ``slope_1``, ``slope_2``, ``intercept_1``, ``intercept_2``,
          ``breakpoint``  — legacy 2-segment schema kept for OP-021
          backward compatibility

    Raises:
        ValueError: ``X`` is multivariate, ``t`` length mismatches ``X``,
                    or ``max_vertices < 2``.
    """
    arr = np.asarray(X, dtype=np.float64)
    if arr.ndim > 1 and (arr.ndim != 2 or arr.shape[1] != 1):
        raise ValueError(
            f"fit_landtrendr expects 1-D input; got shape {arr.shape}. "
            "Multi-channel LandTrendr is not implemented."
        )
    arr = arr.ravel()
    n = len(arr)
    if int(max_vertices) < 2:
        raise ValueError(
            f"fit_landtrendr: max_vertices must be ≥ 2; got {max_vertices!r}."
        )

    if t is None:
        t_arr = np.arange(n, dtype=np.float64)
    else:
        t_arr = np.asarray(t, dtype=np.float64).ravel()
        if len(t_arr) != n:
            raise ValueError(
                f"fit_landtrendr: t length {len(t_arr)} ≠ X length {n}."
            )

    # Trivial cases ---------------------------------------------------------
    if n == 0:
        return _empty_blob(max_vertices, recovery_threshold, penalty_per_vertex)
    if n == 1:
        return _single_point_blob(
            arr, t_arr, max_vertices, recovery_threshold, penalty_per_vertex
        )

    # Step 1 — candidate vertices ------------------------------------------
    n_candidates = min(int(max_vertices) * 2, n)
    candidates = find_candidate_vertices(arr, t_arr, max_candidates=n_candidates)

    # Step 2 — iterative pruning history -----------------------------------
    history = _prune_iteratively(arr, t_arr, candidates)

    # Step 3 — choose best k via penalised SSE -----------------------------
    eligible = [h for h in history if h[0] <= int(max_vertices)]
    if not eligible:
        # candidates was tiny → use the smallest available (k=2 or k=3)
        eligible = history
    best_k, best_vx, best_vy, best_trend, best_sse = min(
        eligible,
        key=lambda h: h[4] + float(penalty_per_vertex) * h[0],
    )

    vertex_pairs: list[tuple[float, float]] = list(
        zip(best_vx, [float(v) for v in best_vy])
    )

    # Per-segment slopes / intercepts --------------------------------------
    slopes: list[float] = []
    intercepts: list[float] = []
    for (vx_a, vy_a), (vx_b, vy_b) in zip(vertex_pairs[:-1], vertex_pairs[1:]):
        span = vx_b - vx_a
        slope = (vy_b - vy_a) / span if span > 0.0 else 0.0
        intercept = vy_a - slope * vx_a
        slopes.append(float(slope))
        intercepts.append(float(intercept))

    recovery = _recovery_flags(vertex_pairs, slopes, recovery_threshold)
    residual = arr - best_trend

    # Legacy schema for OP-021 backward compatibility ----------------------
    legacy = _legacy_segment_keys(vertex_pairs, slopes, intercepts)

    coefficients: dict = {
        "vertices": [(float(vx), float(vy)) for vx, vy in vertex_pairs],
        "slopes": slopes,
        "intercepts": intercepts,
        "recovery": recovery,
        "max_vertices": int(max_vertices),
        "recovery_threshold": float(recovery_threshold),
        "penalty_per_vertex": float(penalty_per_vertex),
    }
    coefficients.update(legacy)

    return DecompositionBlob(
        method="LandTrendr",
        components={
            "trend": best_trend,
            "residual": residual,
        },
        coefficients=coefficients,
        residual=residual,
        fit_metadata={
            "rmse": float(np.sqrt(np.mean(residual ** 2))) if n > 0 else 0.0,
            "rank": min(best_k, n),
            "n_params": int(best_k),
            "convergence": True,
            "version": "1.0",
            "n_vertices": int(best_k),
            "sse": float(best_sse),
        },
    )


# ---------------------------------------------------------------------------
# Edge-case blob constructors and legacy schema helper
# ---------------------------------------------------------------------------


def _empty_blob(
    max_vertices: int,
    recovery_threshold: float,
    penalty_per_vertex: float,
) -> DecompositionBlob:
    empty = np.zeros(0, dtype=np.float64)
    return DecompositionBlob(
        method="LandTrendr",
        components={"trend": empty, "residual": empty},
        coefficients={
            "vertices": [],
            "slopes": [],
            "intercepts": [],
            "recovery": [],
            "max_vertices": int(max_vertices),
            "recovery_threshold": float(recovery_threshold),
            "penalty_per_vertex": float(penalty_per_vertex),
            "slope_1": 0.0,
            "intercept_1": 0.0,
            "slope_2": 0.0,
            "intercept_2": 0.0,
            "breakpoint": None,
        },
        residual=empty,
        fit_metadata={
            "rmse": 0.0,
            "rank": 0,
            "n_params": 0,
            "convergence": True,
            "version": "1.0",
            "n_vertices": 0,
            "sse": 0.0,
        },
    )


def _single_point_blob(
    arr: np.ndarray,
    t_arr: np.ndarray,
    max_vertices: int,
    recovery_threshold: float,
    penalty_per_vertex: float,
) -> DecompositionBlob:
    trend = arr.copy()
    residual = np.zeros_like(arr)
    vy = float(arr[0])
    vx = float(t_arr[0])
    return DecompositionBlob(
        method="LandTrendr",
        components={"trend": trend, "residual": residual},
        coefficients={
            "vertices": [(vx, vy)],
            "slopes": [],
            "intercepts": [],
            "recovery": [],
            "max_vertices": int(max_vertices),
            "recovery_threshold": float(recovery_threshold),
            "penalty_per_vertex": float(penalty_per_vertex),
            "slope_1": 0.0,
            "intercept_1": vy,
            "slope_2": 0.0,
            "intercept_2": vy,
            "breakpoint": None,
        },
        residual=residual,
        fit_metadata={
            "rmse": 0.0,
            "rank": 1,
            "n_params": 1,
            "convergence": True,
            "version": "1.0",
            "n_vertices": 1,
            "sse": 0.0,
        },
    )


def _legacy_segment_keys(
    vertices: list[tuple[float, float]],
    slopes: list[float],
    intercepts: list[float],
) -> dict:
    """Pull the first / last segment's slope-intercept and the first internal
    vertex into the legacy 2-segment schema consumed by OP-021.

    For a multi-vertex fit the legacy ``slope_1`` / ``slope_2`` describe the
    first and last segment respectively; the legacy ``breakpoint`` is the X
    position of the first internal vertex (``None`` for a single-segment
    fit, which has no internal vertex).
    """
    if not slopes:
        return {
            "slope_1": 0.0,
            "intercept_1": 0.0,
            "slope_2": 0.0,
            "intercept_2": 0.0,
            "breakpoint": None,
        }
    return {
        "slope_1": float(slopes[0]),
        "intercept_1": float(intercepts[0]),
        "slope_2": float(slopes[-1]),
        "intercept_2": float(intercepts[-1]),
        "breakpoint": int(vertices[1][0]) if len(vertices) >= 3 else None,
    }
