# REWORK-09 — Delta provenance (which edit caused which change)

**Status:** [ ] Done
**Depends on:** REWORK-02

---

## Goal

Link the operation/edit list to the OUTPUT Δ: selecting or hovering an operation
highlights its contribution to the prediction change, so the scientist can read *which
edit caused which movement* — and avoid the causal-misattribution trap ("I changed X
and it moved" ≠ "the model depends on X"). Exposed via the "Δ sources" affordance.

---

## Task 0 — Recon (record in Result Report)

- [ ] Read `backend/app/services/audit_log.py` + `lib/audit/auditEvents` (frontend):
      document how the ordered operation sequence for a session is stored.
- [ ] Confirm predictions can be computed at intermediate session states (needed to
      attribute per-op deltas).

## Algorithm & SOTA justification (pick + document)

Attributing a total prediction change to a sequence of applied operations is a
**feature-attribution-over-operations** problem. Recommended:

1. **Primary — leave-one-out / ordered marginal contribution.** For each op, compute
   the prediction with vs. without that op (re-applying the rest in order); the
   difference is its contribution. Cheap, exact for the realized path, easy to explain.
   Caveat to document: order-dependent and ignores interactions.
2. **Higher-fidelity (opt-in) — Shapley value over operations.** Average marginal
   contribution across operation orderings (or a sampled approximation, à la
   KernelSHAP). Handles interactions/correlated edits — directly the
   causal-misattribution concern. Cost grows with op count → cap N or sample.

Default to leave-one-out; offer Shapley when op count is small. State the order-
dependence caveat in the UI tooltip.

## Backend (new)

- [ ] New service `delta_provenance` taking the ordered op list + sample + model,
      returning per-op contribution to the prediction Δ (per class for classification).
- [ ] New thin route `POST /api/operations/provenance`.
- [ ] Reuse `PredictionService`; no new model code.

## Acceptance Criteria

- [ ] "Δ sources" in OUTPUT/EVIDENCE reveals per-op contributions.
- [ ] Selecting/hovering an op highlights its contribution segment in the Δ block
      (and ideally its region on the canvas).
- [ ] Contributions reconcile to the total Δ (leave-one-out residual shown if any).
- [ ] Method + order-dependence caveat surfaced in tooltip and Result Report.
- [ ] Handles the single-op case trivially and the no-op case (empty) gracefully.

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "REWORK-09: delta provenance"`

## Result Report
<!-- attribution method + caveat, reconciliation check, files touched -->
