# REWORK-11 — Shoebox: pin mechanism + modal export

**Status:** [ ] Done
**Depends on:** REWORK-02, REWORK-06

---

## Goal

Add the evidence-collection "shoebox": a lightweight one-click **pin** on any
Output/Evidence result (capturing it *with provenance*), and a **modal** to review,
annotate, reorder, and **export** the collection report-ready for the paper pipeline.
The shoebox is a latent fourth zone — reached by icon, never a standing panel.

---

## Task 0 — Recon (record in Result Report)

- [ ] Read the audit export path (HTS-103 / `audit/AuditLogPanel.vue`, CSV/JSON export)
      to reuse the export format rather than inventing a new one.
- [ ] Confirm what provenance fields are available to attach to a pin (sample id,
      ordered op list, model id, prediction snapshot, plausibility snapshot).

## Backend verification

- [ ] Pinned-item provenance is assembled from REAL session state (audit log + current
      prediction/uncertainty/plausibility), not re-fabricated. If session persistence
      is needed across reloads, document whether it's client-only or backend-stored;
      prefer reusing existing audit/session storage.

## Acceptance Criteria

- [ ] **Pin (lightweight):** a pin affordance on any result card in OUTPUT and
      EVIDENCE (prediction, Δ, min-flip result, plausibility snapshot, cohort
      aggregate). One click captures it WITH provenance auto-attached. Quick
      confirmation; does NOT open the modal.
- [ ] **Shoebox modal (heavyweight):** top-bar icon with count badge; opens a modal of
      collected items as reorderable cards, each with an editable note, plus a free-
      notes area.
- [ ] **Export:** report-ready output (figures/values/provenance) reusing the existing
      audit export format (CSV/JSON; markdown if cheap) — feeds the paper pipeline.
- [ ] Three primary zones visually unchanged.
- [ ] Mobile: pin = tap action; shoebox = bottom-sheet.
- [ ] Empty shoebox state handled.

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "REWORK-11: shoebox pin + export"`

## Result Report
<!-- provenance fields, export format reused, persistence decision, files touched -->
