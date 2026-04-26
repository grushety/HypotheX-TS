# UI-017 — Gap indicator and missing-data gating

**Status:** [ ] Done
**Depends on:** SEG-023 (cloud_gap semantic label)

---

## Goal

Visually indicate data gaps on the timeline and disable ops that cannot run on gap-heavy segments, with opt-in gap-fill via Tier-1 `suppress`.

**Why:** FFT-based Cycle ops and decomposition fits silently produce garbage on gap-heavy series. The UI must make gaps visible and block dense-data-requiring ops until the user explicitly fills them.

---

## Acceptance Criteria

- [ ] Gap regions rendered as hatched / dashed pattern in the timeline, distinct from normal segment fills
- [ ] A segment labelled `noise` with `semantic_label=cloud_gap` (from SEG-023) shows a gap icon on its chip
- [ ] Gating rule: ops requiring dense data (OP-024 `change_period`, `phase_shift`; SEG-013 ETM harmonics; SEG-014 STL) disabled when the segment's missingness ratio > 30 %
- [ ] Disabled button tooltip: "Not available: segment has {pct}% missing data. Fill via Tier-1 suppress first."
- [ ] Gap-fill available as Tier-1 `suppress` with strategy picker (linear / spline / climatology per UI-005)
- [ ] After fill, the filled segment is marked with a `filled=true` metadata flag and a subtle badge "filled (linear)"; dense-data ops become enabled
- [ ] Missingness-threshold configurable via `gap.dense_ops_threshold_pct` user setting (default 30)
- [ ] Fixture tests: synthetic series with artificial gaps → hatched render; FFT Cycle op disabled with correct tooltip; suppress(linear) fills → FFT op enabled; filled badge visible
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "UI-017: gap indicator + missing-data gating for dense-data ops"` ← hook auto-moves this file to `done/` on commit
