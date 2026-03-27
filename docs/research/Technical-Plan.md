---
tags: [hypothex-ts, technical, system, architecture]
parent: [[HypotheX-TS - Index]]
created: 2026-03-11
---

# HypotheX-TS — Technical Plan

## System Architecture

Three independent modules with clean API boundaries, so ML backend and UI can be developed and swapped separately.

```
┌─────────────────────┐
│   Data source       │  (any time series + trained black-box model)
└────────┬────────────┘
         │
┌────────▼────────────┐
│  Segmentation Model │  propose_segments / adapt_model / score_uncertainty
└────────┬────────────┘
         │
┌────────▼────────────┐
│  Constraint Engine  │  check_constraints / project_to_feasible
└────────┬────────────┘
         │
┌────────▼────────────┐
│  Operation Engine   │  apply_operations / synthesize_counterfactual
└────────┬────────────┘
         │
┌────────▼────────────┐
│  Interactive UI     │  user interaction + audit log
└─────────────────────┘
```

---

## Module 1 — Segmentation Model

### Role
Proposes initial segmentation; updates from user corrections via few-shot adaptation.

### Recommended architecture: Prototype-based + HSMM smoother

**Why prototype-based?**
- Adapts from very few corrected segments (tens, not thousands)
- Prototypes are interpretable — can be shown to users as "representative patterns"
- Natural fit for the {event, trend, anomaly, other} ontology

**Architecture**:
1. **Encoder**: 1D-TCN or Transformer over fixed-length windows → embedding $z_t \in \mathbb{R}^d$
2. **Class prototypes**: $\mu_y$ = mean embedding of user-labeled support segments for class $y$
3. **Label prediction**: $p(y \mid t) \propto \exp(-\|z_t - \mu_y\|^2 / \tau)$
4. **Smoothing**: HSMM (Hidden Semi-Markov Model) layer on top to prevent rapid label switching and enforce minimum segment duration

**Few-shot update protocol**:
- Every $N$ user operations → update prototypes + fine-tune small classification head
- Encoder weights mostly frozen to prevent catastrophic drift
- Return new model version + delta summary (which segments changed)

**Cold-start proposal**:
- Change-point detection (ClaSP or BOCPD) for boundary candidates
- Baseline dense labeler for initial labels
- Uncertainty overlay shown to user from first interaction

### Minimal API
```python
propose_segments(X, context, priors) -> SegmentationProposal
adapt_model(support_set, budget)     -> model_version_id
score_uncertainty(X, S)              -> u_t, u_seg
```

---

## Module 2 — Constraint Engine

### Role
Validates user operations against physics/domain constraints; projects or blocks invalid edits.

### Constraint types
- **Hard**: operation blocked if violated; system projects to nearest feasible segmentation
- **Soft**: warning shown, operation allowed; violation logged and penalized in counterfactual optimization

### Pseudocode (core logic)
```python
def apply_op_with_constraints(X, S, op, constraints, mode):
    S_candidate = op.apply(X, S)
    violations = check_constraints(X, S_candidate, constraints)

    if not violations:
        return S_candidate, {"status": "PASS"}
    if mode == "SOFT":
        return S_candidate, {"status": "WARN", "violations": violations}

    # HARD: project to feasible
    S_projected = project_to_feasible(X, S_candidate, constraints)
    if check_constraints(X, S_projected, constraints):
        return S, {"status": "FAIL", "violations": violations}  # block
    return S_projected, {"status": "PROJECTED", "violations": violations}
```

### Constraint templates (domain-configurable)

| Constraint | Applies to | Hard or Soft |
|-----------|-----------|-------------|
| Monotonic slope | Trend segments | Soft default |
| Minimum segment duration | All | Hard |
| Label semantic rules (e.g. event can't follow event without other/transition) | All | Soft |
| Conservation law (mass, energy) | Aggregate operations | Soft |
| Causal ordering | Event sub-phases | Hard |

---

## Module 3 — Operation Engine

### Role
Applies user operations deterministically; generates counterfactuals within segments.

### Counterfactual synthesis within a segment

Given segment $s = [b, e]$, target prediction class $c^*$, and constraints $\mathcal{C}$:

```python
def synthesize_counterfactual_segment(X, s, target, constraints, alpha, lambda_):
    X_edit = X[b:e].copy()
    for iteration in range(N):
        loss_task  = task_loss(model.predict(X_edit), target)
        loss_close = ||X_edit - X[b:e]||²
        loss_phys  = sum(penalty(c, X_edit) for c in constraints)
        total = loss_task + alpha * loss_close + lambda_ * loss_phys
        X_edit = gradient_step(X_edit, grad(total))
    return X_edit
```

This is constrained to the **semantic segment** — not the full series — which is the key differentiator from existing CE methods that perturb arbitrary time windows.

---

## UI Components

### Screen A — Multi-scale timeline + label track
- Main time series chart with aligned segmentation band (colored bars per label)
- Minimap overview for long series + brush-zoom
- Boundary handles with uncertainty whiskers

### Screen B — Operation palette
- Buttons: Split | Merge | Reclassify | Align | Simulate intervention
- Constraint status widget per operation: ✅ PASS / ⚠️ WARN / ❌ FAIL
- Hard/soft toggle (global or per-constraint)

### Screen C — Model proposal panel
- Current model segmentation shown alongside user segmentation
- Disagreement highlighted (boundary diff, label diff)
- "Accept model suggestion" / "Override" per segment

### Screen D — Counterfactual view
- Shows original segment vs. synthesized counterfactual segment
- Prediction change displayed
- Constraint violations flagged

### Screen E — Audit log
- Every operation: type, segment, timestamp, constraint outcome, model version
- Undo/redo stack
- Session export for analysis

---

## Technology choices (suggested, not fixed)

| Component | Option |
|-----------|--------|
| Frontend | React + D3.js for time series charts |
| Backend | Python (FastAPI) |
| Segmentation encoder | PyTorch (1D-TCN) |
| Change-point proposals | `ruptures` or ClaSP |
| Constraint engine | Rule-based Python, domain-configurable |
| Logging | SQLite per session → export to JSON |

---

## Implementation priority for minimum viable study

1. ✅ Time series display + segmentation overlay
2. ✅ Manual boundary editing + label assignment
3. ✅ Split / merge / reclassify operations
4. ✅ Simulate intervention (basic gradient-based CE within segment)
5. ✅ Constraint check + WARN display (soft mode first)
6. ✅ Interaction log export
7. 🔲 Few-shot model adaptation (can be simplified: prototype update only)
8. 🔲 Hard constraint blocking + projection
9. 🔲 Uncertainty overlay

---

## Links
- [[HypotheX-TS - Index]]
- [[HypotheX-TS - Formal Definitions]]
- [[HypotheX-TS - Research Plan]]
- [[HypotheX-TS - Evaluation]]
