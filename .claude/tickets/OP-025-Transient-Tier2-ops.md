# OP-025 — Transient Tier-2 ops (9 ops)

**Status:** [ ] Done
**Depends on:** SEG-013 (ETM log/exp basis), SEG-018 (GrAtSiD features), OP-040 (relabeler)

---

## Goal

Implement the 9 Transient-specific Tier-2 ops: `remove`, `amplify`, `dampen`, `shift_time`, `change_duration`, `change_decay_constant`, `replace_shape`, `duplicate`, `convert_to_step`.

**How it fits:** Gated when active shape is `transient`. `remove` → RECLASSIFY. `convert_to_step` → DETERMINISTIC(step). Others preserve transient. All ops edit GrAtSiD feature list or ETM log/exp coefficients directly.

---

## Paper references (for `algorithm-auditor`)

- Bevis & Brown (2014) — ETM log/exp basis definitions.
- Bedford & Bevis (2018) — GrAtSiD feature parameterization.

---

## Pseudocode

```python
def _get_feature(blob, feature_id):
    if blob.method == 'GrAtSiD':
        return blob.coefficients['features'][feature_id]
    # ETM: feature_id is e.g. 'log_60_tau20'
    return blob.coefficients[feature_id]

def remove(blob, feature_id):
    if blob.method == 'GrAtSiD':
        del blob.coefficients['features'][feature_id]
    else:
        del blob.coefficients[feature_id]
        del blob.components[feature_id]
    return blob.reassemble()                   # → RECLASSIFY

def amplify(blob, feature_id, alpha):
    f = _get_feature(blob, feature_id)
    f['amplitude'] *= alpha if isinstance(f, dict) else None
    if blob.method == 'ETM': blob.coefficients[feature_id] *= alpha
    return blob.reassemble()

def dampen(blob, feature_id, alpha):           # alpha in (0, 1)
    return amplify(blob, feature_id, alpha)

def shift_time(blob, feature_id, delta_t):
    f = _get_feature(blob, feature_id)
    if blob.method == 'GrAtSiD': f['t_ref'] += delta_t
    return recompute_component(blob, feature_id).reassemble()

def change_duration(blob, feature_id, s):
    # s: scale factor on feature width
    f = _get_feature(blob, feature_id)
    if 'duration_scale' in f: f['duration_scale'] = s
    else: f['tau'] *= s                         # ETM log/exp basis
    return recompute_component(blob, feature_id).reassemble()

def change_decay_constant(blob, feature_id, beta):
    f = _get_feature(blob, feature_id)
    f['tau'] *= beta
    return recompute_component(blob, feature_id).reassemble()

def replace_shape(blob, feature_id, new_basis: Literal['log', 'exp', 'both']):
    f = _get_feature(blob, feature_id)
    f['type'] = new_basis
    return refit_feature_amplitude(blob, feature_id).reassemble()

def duplicate(blob, feature_id, delta_t):
    f = _get_feature(blob, feature_id)
    new_f = {**f, 't_ref': f['t_ref'] + delta_t}
    if blob.method == 'GrAtSiD':
        blob.coefficients['features'].append(new_f)
    return blob.reassemble()

def convert_to_step(blob, feature_id):
    f = _get_feature(blob, feature_id)
    t_ref = f['t_ref']
    amplitude = f['amplitude']
    # τ → 0, move to steps dict
    if blob.method == 'GrAtSiD':
        blob.coefficients['features'].remove(f)
    blob.coefficients[f'step_at_{t_ref}'] = amplitude
    return blob.reassemble()                   # → DETERMINISTIC(step)
```

---

## Acceptance Criteria

- [ ] `backend/app/services/operations/tier2/transient.py` with all 9 ops
- [ ] All ops edit transient features in blob; no pointwise raw-signal mutation (asserted by test: raw signal before/after feature's t_ref window is byte-identical for non-overlapping features)
- [ ] `convert_to_step` emits OP-040 DETERMINISTIC(step)
- [ ] `remove` emits OP-040 RECLASSIFY
- [ ] Works with both ETM log/exp coefficients (SEG-013) and GrAtSiD feature list (SEG-018); dispatcher by `blob.method`
- [ ] Unit tests with synthetic `log(1 + (t − 60)/20) × amplitude=5` fixture: each edit recovers expected coefficient within 5 %
- [ ] `replace_shape` re-fits amplitude to preserve energy when basis changes
- [ ] Tests cover: each op; ETM vs GrAtSiD dispatch; `duplicate` adds a second feature; `convert_to_step` removes from features + adds to steps
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper references: Bevis 2014 (log/exp basis), Bedford & Bevis 2018 (GrAtSiD feature params). Confirm editing primitives match paper feature semantics
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "OP-025: Transient Tier-2 ops (9 ops)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
