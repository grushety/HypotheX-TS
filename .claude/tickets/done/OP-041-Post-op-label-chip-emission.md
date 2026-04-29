# OP-041 — Post-op label chip emission

**Status:** [x] Done
**Depends on:** OP-040 (relabeler)

---

## Goal

After every Tier-1/2/3 operation completes, emit a `LabelChip` event describing `(old_shape, new_shape, confidence, op_id, rule_class)`. Consumed by UI-013 (predicted new-label chip) and written to the audit log via UI-015.

**Why:** Without a uniform event, each op would have to know how to update the UI and audit log itself. The chip event is the contract that decouples op implementation from UI rendering.

**How it fits:** Called at the tail of every OP-010..033 invocation. Event bus is a simple in-process pub/sub; UI-013 subscribes and renders; audit log appends.

---

## Paper references

N/A (event plumbing).

---

## Pseudocode

```python
from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass(frozen=True)
class LabelChip:
    chip_id: str              = field(default_factory=lambda: str(uuid.uuid4()))
    segment_id: str           = ...
    op_id: str                = ...
    op_name: str              = ...
    tier: int                 = ...
    old_shape: str            = ...
    new_shape: str            = ...
    confidence: float         = ...
    rule_class: Literal['PRESERVED', 'DETERMINISTIC', 'RECLASSIFY_VIA_SEGMENTER'] = ...
    timestamp: str            = field(default_factory=lambda: datetime.utcnow().isoformat())

def emit_label_chip(op_result: OpResult, relabel_result: RelabelResult):
    if op_result.tier == 0 and op_result.op_name == 'edit_boundary':
        return                                  # boundary-only edits do not emit a chip

    chip = LabelChip(
        segment_id=op_result.segment_id,
        op_id=op_result.op_id,
        op_name=op_result.op_name,
        tier=op_result.tier,
        old_shape=op_result.pre.label,
        new_shape=relabel_result.new_shape,
        confidence=relabel_result.confidence,
        rule_class=relabel_result.rule_class,
    )
    event_bus.publish('label_chip', chip)
    audit_log.append(chip)
    return chip
```

---

## Acceptance Criteria

- [x] `backend/app/services/operations/relabeler/label_chip.py` with `LabelChip` dataclass and `emit_label_chip()`
- [x] Event bus (simple in-process pub/sub) in `backend/app/services/events.py`; UI-013 subscribes
- [x] Chip emitted for every Tier-1/2/3 op that passes through OP-040 (exactly one chip per op)
- [x] Chip NOT emitted for pure Tier-0 boundary edits (edit_boundary); IS emitted for split/merge (they change shape possibilities)
- [x] Persisted in audit log with all 10 fields (id, segment, op_id, op_name, tier, pre, post, confidence, rule, timestamp)
- [x] Order-preserving delivery: subscribers receive chips in emission order (FIFO)
- [x] Tests cover: chip emitted for each op type; not emitted for edit_boundary; all 10 fields populated; subscriber receives event; FIFO order
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-041: post-op label chip emission + event bus"` ← hook auto-moves this file to `done/` on commit
