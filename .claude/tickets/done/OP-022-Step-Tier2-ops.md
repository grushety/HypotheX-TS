# OP-022 — Step Tier-2 ops (6 ops)

**Status:** [x] Done
**Depends on:** SEG-013 (ETM Heaviside coefficients), OP-040 (relabeler)

---

## Goal

Implement the 6 Step-specific Tier-2 ops: `de_jump`, `invert_sign`, `scale_magnitude`, `shift_in_time`, `convert_to_ramp`, `duplicate`. Each edits the ETM Heaviside amplitude at the step epoch directly — no raw-signal manipulation.

**How it fits:** Gated when active shape is `step`. `de_jump` → RECLASSIFY_VIA_SEGMENTER (residual determines post-op shape). `convert_to_ramp` → DETERMINISTIC(transient). `scale_magnitude(α=0)` equivalent to `de_jump`.

---

## Paper references (for `algorithm-auditor`)

- Bevis & Brown (2014) — ETM Eq. 1 Heaviside term.
- Wang, Bock, Genrich, van Dam (2012) "Preprocessing of daily GPS time series through noise analysis with colored noise models" — *JGR* 117 (step epoch corrections).

---

## Pseudocode

```python
def de_jump(blob, t_s):
    blob.coefficients[f'step_at_{t_s}'] = 0.0
    blob.components[f'step_at_{t_s}']   = np.zeros_like(blob.components[f'step_at_{t_s}'])
    return blob.reassemble()                     # → RECLASSIFY

def invert_sign(blob, t_s):
    blob.coefficients[f'step_at_{t_s}'] *= -1
    blob.components[f'step_at_{t_s}']   *= -1
    return blob.reassemble()                     # → step (PRESERVED)

def scale_magnitude(blob, t_s, alpha):
    blob.coefficients[f'step_at_{t_s}'] *= alpha
    blob.components[f'step_at_{t_s}']   *= alpha
    return blob.reassemble()                     # → step, or plateau if α == 0

def shift_in_time(blob, t_s_old, t_s_new, t):
    delta = blob.coefficients.pop(f'step_at_{t_s_old}')
    blob.components.pop(f'step_at_{t_s_old}')
    blob.coefficients[f'step_at_{t_s_new}'] = delta
    blob.components[f'step_at_{t_s_new}']   = delta * (t >= t_s_new).astype(float)
    return blob.reassemble()

def convert_to_ramp(blob, t_s, tau_ramp):
    delta = blob.coefficients.pop(f'step_at_{t_s}')
    blob.components.pop(f'step_at_{t_s}')
    t = blob.components['linear_rate'] / blob.coefficients['linear_rate']   # recover t
    blob.coefficients[f'log_{t_s}_tau{tau_ramp}'] = delta
    blob.components[f'log_{t_s}_tau{tau_ramp}']   = delta * np.log1p(np.maximum(0, (t - t_s) / tau_ramp))
    return blob.reassemble()                     # → DETERMINISTIC(transient)

def duplicate(blob, t_s, delta_t, delta_2, t):
    blob.coefficients[f'step_at_{t_s + delta_t}'] = delta_2
    blob.components[f'step_at_{t_s + delta_t}']   = delta_2 * (t >= t_s + delta_t).astype(float)
    return blob.reassemble()                     # may trigger re-segmentation
```

---

## Acceptance Criteria

- [x] `backend/app/services/operations/tier2/step.py` with all 6 ops
- [x] All ops edit ETM step coefficients directly (asserted by test: raw signal outside the step is byte-identical pre/post)
- [x] `convert_to_ramp` emits OP-040 DETERMINISTIC(transient)
- [x] `duplicate` triggers a re-segmentation hint (two steps within one segment suggest splitting)
- [x] `scale_magnitude(α=0)` and `de_jump` produce bit-identical reassembled signals (asserted)
- [x] Step epoch `t_s` must exist in blob.coefficients (else raise)
- [x] Tests cover each op with synthetic ETM step fixture; coefficient-level edit test; `duplicate` triggers split hint
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-022: Step Tier-2 ops (6 ops)"` ← hook auto-moves this file to `done/` on commit

## Result Report

56 tests in `test_step_ops.py`. Reviewer found 1 blocking issue fixed: `duplicate` raised no error on `delta_t=0`, silently overwriting the original step's amplitude — fixed with a `ValueError` guard. Dead test assertion removed. All 56 tests pass.
