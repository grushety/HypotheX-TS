# OP-040 — Relabeler rule table (3 classes)

**Status:** [ ] Done
**Depends on:** SEG-008 (classifier for RECLASSIFY path); consumed by all Tier-1/2/3 ops

---

## Goal

Implement the 3-class relabeling rule table from [[HypotheX-TS - Operation Vocabulary Research]] §6: `PRESERVED`, `DETERMINISTIC(target)`, `RECLASSIFY_VIA_SEGMENTER`. Reclassify is NOT a primitive op — it is the derived post-op step triggered after any Tier-1/2/3 edit.

**Why:** Consistent relabel rules prevent the ambiguity of "what shape is this after I edited it?" that would otherwise force Tier-2 ops to re-invent label logic per op. The rule table centralizes the decision; each op calls `relabel()` once, gets back `(new_shape, confidence, resegment_needed)`.

**How it fits:** Called by every Tier-1/2/3 op after it finishes its edit. OP-041 wraps OP-040's result in a UI event for UI-013 (predicted new-label chip).

---

## Paper references

Design ticket; references [[HypotheX-TS - Operation Vocabulary Research]] §6.

---

## Pseudocode

```python
RULE_TABLE = {
    # (old_shape, op_name, param_predicate?) → (rule_class, target_or_None)
    ('plateau', 'raise_lower', None):            ('PRESERVED', None),
    ('plateau', 'invert', None):                 ('PRESERVED', None),
    ('plateau', 'replace_with_trend', None):     ('DETERMINISTIC', 'trend'),
    ('plateau', 'replace_with_cycle', None):     ('DETERMINISTIC', 'cycle'),
    ('plateau', 'tilt_detrend', None):           ('PRESERVED', None),

    ('trend', 'flatten', None):                  ('DETERMINISTIC', 'plateau'),
    ('trend', 'reverse_direction', None):        ('PRESERVED', None),
    ('trend', 'change_slope', 'alpha=0'):        ('DETERMINISTIC', 'plateau'),
    ('trend', 'change_slope', None):             ('PRESERVED', None),
    ('trend', 'linearise', None):                ('PRESERVED', None),
    ('trend', 'extrapolate', None):              ('PRESERVED', None),
    ('trend', 'add_acceleration', None):         ('PRESERVED', None),

    ('step', 'de_jump', None):                   ('RECLASSIFY_VIA_SEGMENTER', None),
    ('step', 'invert_sign', None):               ('PRESERVED', None),
    ('step', 'scale_magnitude', 'alpha=0'):      ('DETERMINISTIC', 'plateau'),
    ('step', 'scale_magnitude', None):           ('PRESERVED', None),
    ('step', 'shift_in_time', None):             ('PRESERVED', None),
    ('step', 'convert_to_ramp', None):           ('DETERMINISTIC', 'transient'),
    ('step', 'duplicate', None):                 ('RECLASSIFY_VIA_SEGMENTER', None),

    ('spike', 'remove', None):                   ('RECLASSIFY_VIA_SEGMENTER', None),
    ('spike', 'clip_cap', None):                 ('PRESERVED', None),
    ('spike', 'amplify', None):                  ('PRESERVED', None),
    ('spike', 'smear_to_transient', None):       ('DETERMINISTIC', 'transient'),
    ('spike', 'duplicate', None):                ('RECLASSIFY_VIA_SEGMENTER', None),
    ('spike', 'shift_time', None):               ('PRESERVED', None),

    ('cycle', 'deseasonalise_remove', None):     ('RECLASSIFY_VIA_SEGMENTER', None),
    ('cycle', 'amplify_amplitude', 'alpha=0'):   ('DETERMINISTIC', 'plateau'),
    ('cycle', 'amplify_amplitude', None):        ('PRESERVED', None),
    ('cycle', 'dampen_amplitude', None):         ('PRESERVED', None),
    ('cycle', 'phase_shift', None):              ('PRESERVED', None),
    ('cycle', 'change_period', None):            ('PRESERVED', None),
    ('cycle', 'change_harmonic_content', None):  ('PRESERVED', None),
    ('cycle', 'replace_with_flat', None):        ('DETERMINISTIC', 'plateau'),

    ('transient', 'remove', None):               ('RECLASSIFY_VIA_SEGMENTER', None),
    ('transient', 'amplify', None):              ('PRESERVED', None),
    ('transient', 'dampen', 'alpha=0'):          ('DETERMINISTIC', 'plateau'),
    ('transient', 'dampen', None):               ('PRESERVED', None),
    ('transient', 'shift_time', None):           ('PRESERVED', None),
    ('transient', 'change_duration', None):      ('PRESERVED', None),
    ('transient', 'change_decay_constant', None):('PRESERVED', None),
    ('transient', 'replace_shape', None):        ('PRESERVED', None),
    ('transient', 'duplicate', None):            ('PRESERVED', None),
    ('transient', 'convert_to_step', None):      ('DETERMINISTIC', 'step'),

    ('noise', 'suppress_denoise', None):         ('RECLASSIFY_VIA_SEGMENTER', None),
    ('noise', 'amplify', None):                  ('PRESERVED', None),
    ('noise', 'change_color', None):             ('PRESERVED', None),
    ('noise', 'inject_synthetic', None):         ('PRESERVED', None),
    ('noise', 'whiten', None):                   ('PRESERVED', None),

    # Tier 0
    ('*', 'edit_boundary', None):                ('PRESERVED', None),
    ('*', 'split', None):                        ('RECLASSIFY_VIA_SEGMENTER', None),
    ('*', 'merge', None):                        ('RECLASSIFY_VIA_SEGMENTER', None),
}

def relabel(old_shape, operation, op_params, edited_series, classifier=None):
    key = (old_shape, operation, _param_predicate(op_params))
    rule = RULE_TABLE.get(key) or RULE_TABLE.get((old_shape, operation, None)) or \
           RULE_TABLE.get(('*', operation, None))
    if rule is None:
        raise UnknownRule(f"no relabel rule for ({old_shape}, {operation})")
    rule_class, target = rule
    if rule_class == 'PRESERVED':
        return RelabelResult(new_shape=old_shape, confidence=1.0,
                             resegment_needed=False, rule_class='PRESERVED')
    elif rule_class == 'DETERMINISTIC':
        return RelabelResult(new_shape=target, confidence=1.0,
                             resegment_needed=False, rule_class='DETERMINISTIC')
    elif rule_class == 'RECLASSIFY_VIA_SEGMENTER':
        shape_label = classifier.classify_shape(edited_series)
        return RelabelResult(new_shape=shape_label.label, confidence=shape_label.confidence,
                             resegment_needed=True, rule_class='RECLASSIFY_VIA_SEGMENTER')
```

---

## Acceptance Criteria

- [ ] `backend/app/services/operations/relabeler/rule_table.py` with complete `RULE_TABLE` (≥ 48 entries covering all Tier-1/2 ops plus Tier-0)
- [ ] `backend/app/services/operations/relabeler/relabeler.py` with `relabel()` and `RelabelResult` dataclass
- [ ] Amplitude-threshold-crossing cases (e.g. `alpha=0`) handled via `_param_predicate()` lookup that falls back to `None` key if no specific predicate matches
- [ ] `RECLASSIFY_VIA_SEGMENTER` path invokes SEG-008 classifier and returns `confidence` from classifier output
- [ ] Never silently relabels: every relabel returns a `RelabelResult` with explicit `rule_class` field
- [ ] Every rule in the table verified against [[HypotheX-TS - Operation Vocabulary Research]] §6 (no rules invented locally)
- [ ] Tests cover: every (old_shape, operation) pair returns an expected rule; `alpha=0` predicate dispatch; wildcard (`*`) for Tier-0; unknown rule raises
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "OP-040: relabeler rule table (3 classes, ≥48 entries)"` ← hook auto-moves this file to `done/` on commit
