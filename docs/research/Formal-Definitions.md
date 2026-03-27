---
tags: [hypothex-ts, formal, definitions, time-series]
parent: [[HypotheX-TS - Index]]
created: 2026-03-11
---

# HypotheX-TS — Formal Definitions

## 1. Time Series

Let $X = (x_t)_{t=1}^{T}$ be a univariate or multivariate time series, where $x_t \in \mathbb{R}^d$.

---

## 2. Semantic Segmentation

A **semantic segmentation** of $X$ is a partition into $K$ contiguous, non-overlapping segments:

$$S = \{(b_k, e_k, y_k)\}_{k=1}^{K}$$

such that:
1. $1 = b_1 \leq e_1 < b_2 \leq \ldots < b_K \leq e_K = T$ (contiguity + full coverage)
2. Each segment $k$ has label $y_k \in \mathcal{Y} = \{\text{event}, \text{trend}, \text{anomaly}, \text{other}\}$
3. Each segment optionally has attributes: confidence $c_k$, boundary uncertainty $\sigma_{b_k}, \sigma_{e_k}$, and provenance (user / model / imported)

### Segment semantics (operational predicates)

| Label | Operational definition |
|-------|----------------------|
| **Event** | Bounded interval where a domain event predicate holds: $P_\text{event}(X_{b:e}; \theta) = \text{true}$. Typically rare, interval-defined, transient. |
| **Trend** | Interval where a low-frequency component dominates with sign-consistent slope on smoothed signal $\tilde{x}$: $\text{sign}(\tilde{x}_{t+1} - \tilde{x}_t) = \sigma \; \forall t \in s$. |
| **Anomaly** | Interval where behavior deviates from an expected baseline model $f$ beyond threshold: $\|X_{b:e} - f(X_{b:e})\| > \tau$. |
| **Other** | Background / noise / gap / unmodeled regime. Ideally subtyped, not a catch-all. |

Domain-specific refinements are supported via a mapping $m_d: \mathcal{Y}_d \to \mathcal{Y}$ (e.g., "coseismic step" → event).

---

## 3. Operation

An **operation** is a function:

$$\text{op}: (X, S, \phi) \mapsto (S', \Delta)$$

where $\phi$ includes domain parameters and constraint specifications, $S'$ is the modified segmentation, and $\Delta$ is the audit record.

### Operation catalog

| Operation | What it does | Physics-sensitive |
|-----------|-------------|------------------|
| **Edit boundary** | Move $b_k$ or $e_k$ | Optional (snap rules) |
| **Split** | Divide segment $k$ at point $t^*$ into two | Optional (min duration) |
| **Merge** | Combine adjacent segments $k, k+1$ | Optional (label compatibility) |
| **Reclassify** | Change $y_k$ to $y'_k$ | Optional (semantic rules) |
| **Align / warp** | Re-time segment to match template | Often (order constraints) |
| **Aggregate** | Roll up segments to regime-level | Often (mass/energy budgets) |
| **Enforce conservation** | Adjust attributes to satisfy physical constraint | Yes |
| **Simulate intervention** | Counterfactual "what if" within segment | Yes (physics model) |
| **Synthesize counterfactual** | Generate plausible alternative segment meeting target | Yes |

---

## 4. Constraint Types

**Hard constraint**: $g(S', X) = 0$ or $g \leq 0$. Operation is blocked or projected if violated.

**Soft constraint (prior)**: violation is penalized in optimization: $\lambda \cdot \max(0, g)$.

### Example constraint templates

**Monotonic trend**: For a trend segment $s$, enforce sign-consistent slope:
$$\text{sign}(\tilde{x}_{t+1} - \tilde{x}_t) = \sigma \quad \forall t \in s$$

**Conservation (e.g. mass balance)**:
$$\Delta S_s \approx P_s - ET_s - Q_s, \quad |\epsilon_s| \leq \tau$$

**Causal order (e.g. event phases)**:
$$b_{P} < b_{S} \quad \text{and plausible separation bounds hold}$$

---

## 5. Few-Shot Segmentation Model

Let $\mathcal{M}_\theta$ be a segmentation model that:
- Takes $X$ and a support set of user-labeled segments as input
- Outputs: per-step label distribution $p(y \mid t, X)$, boundary uncertainty $u_t$, per-segment confidence $c_k$
- Updates prototypes from $N$ user operations (not thousands of labels)

### Minimal API

```
propose_segments(X, context, priors)   → SegmentationProposal
apply_operations(S, ops)               → S'
adapt_model(support_set, budget)       → model_version
score_uncertainty(X, S)                → u_t, u_seg
check_constraints(X, S, constraints)   → violations
```

---

## 6. Mental Model Alignment

**User segmentation** $S^U$ = partition produced by the user interactively.

**Model segmentation** $S^M$ = partition proposed by $\mathcal{M}_\theta$.

**Mental model–model alignment** $A(S^U, S^M)$: a structured divergence measure between user and model segmentation, capturing boundary disagreement, label disagreement, and operation type patterns.

> Formal definition of $A$ is an open research question — see [[HypotheX-TS - Research Questions]].

---

## Links
- [[HypotheX-TS - Index]]
- [[HypotheX-TS - Research Questions]]
- [[HypotheX-TS - Technical Plan]]
