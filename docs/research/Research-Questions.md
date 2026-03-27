---
tags: [hypothex-ts, research-questions, hypotheses]
parent: [[HypotheX-TS - Index]]
created: 2026-03-11
updated: 2026-03-11
---

# HypotheX-TS — Research Questions

## Background and Motivation

Time-series CFE methods increasingly use subsequences and structured units (CONFETTI, Glacier, shapelet/motif/discord-based methods), and interactive CF tools for time series exist (projection-based, arXiv 2408.10633). Symbolic/semantic CE spaces exist algorithmically (MASCOTS). Constraints are used in backends (physics-guided, LTL-based).

**The gap that remains:** even when methods use subsequences, those units are **algorithm-defined** and the operations are low-level signal edits. Users reason in **semantic units** — trends, plateaus, transitions, anomalies. This mismatch is particularly acute in time series because temporal dependencies mean low-level perturbations can break semantic integrity and feasibility.

This creates two compounding problems:
1. **Semantic mismatch**: the unit of manipulation (algorithm-defined subsequence or timestep) doesn't match the unit of reasoning (user-defined semantic segment)
2. **Constraint blindness**: existing constraints are backend (physics model, LTL rules); no system exposes them as a user-facing typed operation vocabulary that shapes exploration

Additionally, the risk of **biased and cherry-picked counterfactual selection** (counterfactual disagreement literature) is unaddressed in interactive temporal XAI.

> ~~"These are specifically temporal problems — they have no equivalent in tabular XAI."~~ ← **Removed**: semantic CF frameworks in other modalities exist (KB edit operations, IJCAI 2023). Reframe as "particularly acute in time series."

---

## Core Research Questions

### RQ1 — Mental Model Alignment
> *To what extent does a user's semantic segmentation of a time series diverge from model-proposed segmentation, and what does this divergence reveal about their temporal mental model?*

**Why it matters**: If users and models disagree on segment boundaries or labels, CEs generated in model space won't match the user's conceptual space — making explanation misleading. The counterfactual disagreement literature shows users can cherry-pick CEs consistent with their priors; segmentation divergence may explain *which* CEs get selected.

**Hypothesis H1**: Users produce systematically different segmentations than algorithmic methods, with divergence concentrated at semantically ambiguous boundaries (trend-to-plateau, anomaly onset). Divergence is consistent within users but varies across expertise levels.

**What's needed to publish**: Operational definition of alignment $A(S^U, S^M)$ that is not trivially confounded by boundary tolerance (type agreement + boundary IoU + operation-consistency). Must show alignment predicts at least one downstream outcome (decision accuracy, over-trust, or biased exploration log).

**Connection to HypotheX**: In [[MyPaper - HypotheX]] we showed users explore narrow regions of input space. Here: users may also *segment* narrow regions — focusing on salient events, ignoring slow trends — and their segmentation exposes this.

---

### RQ2 — Typed Operations vs. Raw/Projection Manipulation
> *Does interacting via typed semantic operations reduce interpretational risks and biased exploration compared to raw signal manipulation or projection-based interaction?*

**Why it matters**: Interactive CF tools for time series exist (projection-based), but use point-dragging as primitives. HypotheX-TS tests whether semantic operation typing + validity constraints change *how* users explore and *what* CEs they accept — reducing cherry-picking and anchoring patterns.

**Hypothesis H2**: Users interacting via the typed semantic operation vocabulary exhibit broader exploration patterns, fewer recency-biased queries, lower rates of implausible CE acceptance, and better calibrated trust compared to users with raw signal or projection-based manipulation.

**Comparison baseline**: projection-based interactive CF tool (arXiv 2408.10633) + raw signal manipulation — not just WIT.

---

### RQ3 — Constraint Feedback and Trust Calibration
> *How does constraint feedback (hard vs. soft UI guardrails) affect trust calibration and over/underconfidence in what-if conclusions?*

**Why it matters**: Physics/logic constraints already exist in backends, but are invisible to users. HypotheX-TS makes them user-visible as operation-level feedback. The risk: hard blocking may create *constraint-as-truth* bias (if the system allowed it, it must be realistic).

**Hypothesis H3a**: Hard constraints reduce implausible CE acceptance but increase overconfidence in accepted CEs.

**Hypothesis H3b**: Soft constraints produce better-calibrated trust at the cost of higher implausible acceptance.

---

### RQ4 — Operation-Aware Few-Shot Segmentation (Exploratory / Technical)
> *Can the few-shot segmentation model learn segment boundaries that support feasible typed operations — i.e., converge not just by IoU but by stability of the induced operation space?*

**Reframed from original Claim 3**: Not "few-shot segmentation is novel" (that space is crowded) but a **new problem setting induced by HypotheX-TS**: the segmentation model is trained on both labels and user operation traces, and convergence is measured by operation-validity stability + user satisfaction (Feasibility and Trust are dominant predictors of CF satisfaction).

> Suitable for a technical companion paper or PhD chapter rather than the primary contribution.

---

## Theoretical Claim (overarching)

> **User-defined semantic segmentation is both the interaction layer and a measurement instrument for the user's temporal mental model. Alignment between user and model segmentation predicts interpretation quality and biased exploration patterns.**

This claim goes beyond prior work by making segmentation dual-purpose: it structures the what-if exploration space *and* generates structured evidence about where user mental models diverge from learned model behavior.

---

## Scope decisions (still open)

| Decision | Options | Notes |
|----------|---------|-------|
| ML task | Classification / forecasting / anomaly detection | Forecasting most natural for what-if |
| Domain | Industrial sensor, geoscience, medical | Industrial: accessible, clear physical constraints |
| Baselines | (1) Raw signal manipulation, (2) Projection-based interactive CF (arXiv 2408.10633) | Two baselines now required |

---

## Links
- [[HypotheX-TS - Index]]
- [[HypotheX-TS - Formal Definitions]]
- [[HypotheX-TS - Research Plan]]
- [[HypotheX-TS - Novelty Positioning]]
- [[MyPaper - HypotheX]]
