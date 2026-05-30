# REWORK-04 — Evidence zone default view (declutter)

**Status:** [ ] Done
**Depends on:** REWORK-01

---

## Goal

Assemble the EVIDENCE zone so its *default* (collapsed) state is calm and glanceable:
only the plausibility gauges, the "Model sees this" fidelity strip, and the probe
toggles. Heavy detail (Guardrails breakdown, Audit log, Layers, Model) moves behind
carets or into the shoebox modal. Prevent EVIDENCE from becoming the new dumping
ground the editor once was.

---

## Task 0 — Recon (record in Result Report)

- [ ] Inventory existing EVIDENCE-family components: `plausibility/`,
      `guardrails/GuardrailsSidebar.vue`, `audit/AuditLogPanel.vue`, semantic/layers,
      model-comparison. Map each to default-visible vs. behind-caret.
- [ ] Confirm the plausibility components already consume backend
      `ynn_plausibility` / `native_guide` / `validity_rate` outputs.

## Backend verification

- [ ] Plausibility gauges are backed by real services (no mock values): Validity rate
      (VAL-012 `validity_rate.py`), Proximity & Sparsity (VAL-004 `native_guide.py`),
      Plausibility (VAL-003 `ynn_plausibility.py`). Confirm each gauge maps to a real
      field; document the mapping.

## Acceptance Criteria

- [ ] EVIDENCE default view shows ONLY: 4 plausibility gauges (Validity / Proximity /
      Sparsity / Plausibility), the fidelity strip (REWORK-05 slot), and probe toggles
      (Saliency / Δ-sources / Min-flip).
- [ ] Guardrails detail, Audit log, Layers, Model are collapsed behind carets/tabs and
      reachable without leaving the zone.
- [ ] Gauges are flat/muted (no accent color — that's reserved for OUTPUT).
- [ ] Zone scrolls internally; never causes page scroll.
- [ ] No gauge shows a hardcoded/placeholder number — each is wired to its service.

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "REWORK-04: evidence zone default view"`

## Result Report
<!-- gauge→service mapping table, default-vs-caret map, files touched -->
