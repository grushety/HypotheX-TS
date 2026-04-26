# UI-013 — Predicted new-label chip

**Status:** [ ] Done
**Depends on:** OP-040 (relabeler), OP-041 (label chip emission)

---

## Goal

After every Tier-1/2/3 op, show a chip above the edited segment predicting the new shape label with confidence and rule class (`PRESERVED` / `DETERMINISTIC` / `RECLASSIFY`). User can Accept (default after 5 s), Override (opens shape picker), or Undo.

**Why:** The chip is the UI contract for OP-040's relabel semantics. It is how users learn that ops change shape labels (or don't), and how they correct RECLASSIFY cases where the classifier is wrong.

---

## Acceptance Criteria

- [ ] `frontend/src/components/relabel/PredictedLabelChip.vue` appears ~200 ms after an op completes, anchored above the edited segment in the timeline
- [ ] Content: `{old_shape} → {new_shape}  ({confidence}%)  [rule_class]` + 3 buttons: Accept / Override / Undo
- [ ] RECLASSIFY with confidence < 70 % → orange border + auto-focus "Override" button
- [ ] Auto-accept timer: 5 s by default; user setting `accept_timer_seconds` in config; countdown visible in progress ring
- [ ] "Accept" fires API call to confirm the new label
- [ ] "Override" opens `ShapePicker.vue` dropdown with 7 shape primitives; selection sends a label-correction event
- [ ] "Undo" reverts the last op (delegates to the global undo stack shared with UI-015)
- [ ] Chip dismisses on accept / override / undo / auto-accept-timer
- [ ] Subscribes to `label_chip` event bus topic (from OP-041)
- [ ] Fixture tests: PRESERVED → chip shows old=new; DETERMINISTIC → shows target; RECLASSIFY low-confidence → orange border, Override focused; timer auto-accept fires; Undo reverts op
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "UI-013: predicted new-label chip with accept/override/undo"` ← hook auto-moves this file to `done/` on commit
