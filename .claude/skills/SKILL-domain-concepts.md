# HypotheX-TS — Domain Concepts Skill

Load this skill before any work involving segmentation, operations, constraints, scoring, or audit logging.

---

## 1. Core Principle

The **segment** is the fundamental interaction unit. Operations act on semantic segments, not raw timestep slices. Constraints are evaluated at segment granularity. The audit log records every operation on a segment.

---

## 2. Time Series

A time series is `X = (x_t)_{t=1}^{T}`, univariate or multivariate, `x_t ∈ ℝ^d`.

---

## 3. Semantic Segmentation

A segmentation of `X` is a partition into `K` contiguous non-overlapping segments:

```
S = {(b_k, e_k, y_k)}_{k=1}^{K}
```

Invariants that must always hold:
- `b_1 = 1`, `e_K = T` (full coverage)
- `e_k < b_{k+1}` for all k (non-overlapping, contiguous)
- `y_k ∈ {event, trend, anomaly, other}` (valid label set)

Optional per-segment attributes:
- `c_k` — model confidence score (float, 0–1)
- `σ_{b_k}, σ_{e_k}` — boundary uncertainty
- `provenance` — `"user"` | `"model"` | `"imported"`

### Segment label semantics

| Label | Operational definition |
|---|---|
| `event` | Bounded interval where a domain event predicate holds. Rare, transient. Cannot directly follow another `event` without an intervening `other` or `trend`. |
| `trend` | Monotone directional movement. Smoothed signal `x̃` has sign-consistent slope across the segment. |
| `anomaly` | Local deviation from expected baseline beyond threshold `τ`. `‖X_{b:e} − f(X_{b:e})‖ > τ`. |
| `other` | Background / noise / unmodeled regime. Ideally subtyped in domain-specific extensions. |

### Naming rule
The canonical term is **segment** everywhere. `chunk` is a legacy name present in `chunk_scoring.py`, `ChunkScores`, and `operationsByChunk`. Do not introduce new uses of `chunk`. When editing files that use `chunk`, prefer renaming in the same ticket if scope allows.

---

## 4. Operation Catalog

An operation transforms a segmentation:

```
op: (X, S, φ) → (S', Δ)
```

Where `φ` contains parameters and constraint specs, and `Δ` is the audit record.

| Operation | What it does | Constraint-sensitive |
|---|---|---|
| `edit_boundary` | Move `b_k` or `e_k` | Minimum duration |
| `split` | Divide segment `k` at point `t*` into two | Minimum duration on both halves |
| `merge` | Combine adjacent segments `k, k+1` | Label compatibility |
| `reclassify` | Change `y_k` to `y'_k` | Label compatibility with neighbours |
| `align_warp` | Re-time segment to match a template | Causal ordering |
| `aggregate` | Roll up to regime level | Conservation laws |
| `enforce_conservation` | Adjust attributes to satisfy physical constraint | Always hard |
| `simulate_intervention` | Counterfactual what-if within segment | Physics model |
| `synthesize_counterfactual` | Generate plausible alternative segment toward target class | Segment-bounded |

**Counterfactual synthesis is always segment-bounded.** The gradient-based loop operates on `X[b:e]` only, never across segment boundaries, unless a ticket explicitly expands scope.

---

## 5. Constraint System

### Modes
- **Hard constraint**: operation is blocked or projected to nearest feasible state if violated
- **Soft constraint**: violation is allowed but generates a warning and an audit entry with penalty

### Status enum
Every constraint evaluation returns one of exactly four values:

```
PASS       — no violation
WARN       — soft violation; operation proceeds; logged
FAIL       — hard violation; operation blocked
PROJECTED  — hard violation; operation was projected to nearest valid state
```

Do not use `ALLOW`, `DENY`, `"soft"`, `"hard"` as status values. Those describe constraint *mode*, not constraint *outcome*.

### Implemented constraint types

| Constraint | Applies to | Default mode |
|---|---|---|
| Minimum segment duration | All segments | Hard |
| Monotonic trend consistency | Trend segments | Soft |
| Plateau stability | Other/plateau segments | Soft |
| Label compatibility | Adjacent segment pairs | Soft (event+event is a known check) |

### Constraint templates (formal)

**Monotonic slope** (soft, trend segments):
```
sign(x̃_{t+1} − x̃_t) = σ  ∀t ∈ [b_k, e_k]
```
where `x̃` is the smoothed signal and `σ ∈ {+1, −1}` is the segment's dominant direction.

**Conservation** (soft, aggregate operations):
```
ΔS_s ≈ P_s − ET_s − Q_s,  |ε_s| ≤ τ
```

**Causal order** (hard, event sub-phases):
```
b_P < b_S  and plausible separation bounds hold
```

### Domain config
Constraint thresholds are loaded from `backend/config/mvp-domain-config.json`. Key fields include `slopeAbsMin`, `varianceMax`, `minSegmentDuration`. See `docs/domain-config-note.md` for rationale. `load_domain_config()` must be cached with `@functools.lru_cache(maxsize=1)` — it is called by every constraint function.

---

## 6. Segment Statistics

Computed in `backend/app/domain/stats.py`. All statistics are computed on a single segment `[b_k, e_k]`.

| Statistic | Description | Computed on |
|---|---|---|
| `slope` | Linear trend slope | Smoothed signal `x̃` |
| `variance` | Signal variance | Raw `X[b:e]` |
| `sign_consistency` | Fraction of steps with consistent slope sign | Smoothed `x̃` |
| `residual` | Mean absolute deviation from linear fit | Raw `X[b:e]` |
| `peak` | Max absolute value in segment | Raw `X[b:e]` |
| `periodicity` | Dominant frequency energy ratio | Raw `X[b:e]` |
| `context_contrast` | Difference in mean from neighbouring segments | Raw `X[b:e]` vs neighbours |

**Important**: `slope` and `sign_consistency` are always computed on the smoothed signal `x̃`, not raw `X`. `_smooth_series` uses convolution with mode `"same"` (preserves segment length). The `if window_size < 1` guard in `stats.py:269` is currently unreachable dead code — the `<= 1` early-return guard on the preceding line already handles this.

---

## 7. Chunk Scoring → Segment Labels

Implemented in `backend/app/domain/chunk_scoring.py` (legacy name). Maps `SegmentStatistics` to one of 6 internal ontology scores, then to the 4 user-visible labels.

The 4 user-visible labels (`event`, `trend`, `anomaly`, `other`) are what the UI exposes. The 6-score internal ontology is a backend implementation detail.

---

## 8. Audit Log Schema

**AuditSession** — one per user session:
- `id` — integer PK
- `session_key` — string, human-facing identifier
- `created_at` — timestamp

**AuditEvent** — one per user operation:
- `id` — integer PK
- `session_id` — FK to AuditSession
- `event_type` — operation name (e.g. `"split"`, `"reclassify"`)
- `segment_index` — which segment was affected
- `payload` — JSON blob (operation parameters, constraint outcome, model version)
- `constraint_status` — one of `PASS | WARN | FAIL | PROJECTED`
- `created_at` — timestamp

Every user operation must produce an AuditEvent. This is a product requirement, not optional.

The `POST /api/audit/sessions/<id>/suggestions/decision` endpoint records whether the user accepted or overrode a model suggestion. Valid values for the `decision` field: `{"accepted", "overridden"}` — validate against this whitelist.

---

## 9. Mental Model Alignment

**Not yet implemented** — planned for STEP-07 (disagreement view) and later study instrumentation.

Concept: alignment `A(S^U, S^M)` is a structured divergence between user segmentation `S^U` and model-proposed segmentation `S^M`. Components:
- Boundary F1 disagreement at tolerance δ
- Label disagreement rate
- Operation-consistency (do proposed operations remain valid under both segmentations?)

When implementing the disagreement view, do not invent a custom alignment measure — consult `research-algorithms` skill and the formal definitions in Obsidian first.

---

## 10. Few-Shot Adaptation Protocol

**Partially implemented** — prototype classifier exists in `services/suggestion/`.

Protocol:
1. Every N user operations → update class prototypes `μ_y = mean(embeddings of support segments for class y)`
2. Encoder weights are mostly frozen — only the classification head updates
3. HSMM smoother layer sits on top to prevent rapid label switching and enforce minimum segment duration
4. Each adaptation produces a new `model_version_id` logged in the audit trail

When modifying the suggestion service or prototype classifier, read `research-algorithms` skill first.
