# OP-050 — CF synthesis coordinator (decomposition-first)

**Status:** [x] Done
**Depends on:** SEG-013..018 (fitters), OP-020..026 (Tier-2 ops), OP-040 (relabeler), OP-051 (compensation), OP-032 (conservation)

---

## Goal

Orchestrate the decomposition-first counterfactual synthesis loop: given a target prediction class and a chosen Tier-2 op, produce the edited series via **coefficient-level edit on the segment's decomposition blob** (not via pointwise L1 perturbation). This is the algorithmic core of HypotheX-TS's strongest novelty claim (score 5/5 per [[_project HypotheX-TS/HypotheX-TS - Originality Assessment]]).

**Why:** Every TS-CF method in the verified 2020–2026 literature operates in one of {raw-signal L1, shapelet/subsequence, autoencoder latent, NUN instance, symbolic/SAX} spaces. Decomposition-coefficient-edit is the 7th empty category in the Schlegel & Seidl 2026 taxonomy — HypotheX-TS claims it. OP-050 is the component that enforces this architectural property.

**How it fits:** Central coordinator. Called by UI when user commits a Tier-2 op with parameters (amplitude, phase, τ, etc.). Delegates the actual edit to the specific OP-020..026 function, then projects via OP-051 if constraints are violated, then calls OP-040 for relabel.

---

## Paper references (for `algorithm-auditor`)

- Architecture: [[_project HypotheX-TS/HypotheX-TS - Formal Definitions]] §6.
- Baseline comparators (for benchmarking, not for implementation): Wachter, Mittelstadt, Russell (2017) "Counterfactual Explanations without Opening the Black Box" (wCF); Delaney, Greene, Keane (2021) Native Guide; Mothilal, Sharma, Tan (2020) DiCE.

---

## Pseudocode

```python
def synthesize_counterfactual(
    X, segment, target_class, op_tier2,
    op_params: dict, constraints: list[Constraint],
    compensation_mode: Literal['naive', 'local', 'coupled'] = 'local',
) -> CFResult:
    """
    Decomposition-first CF synthesis. Never applies raw-signal gradient edits.
    """
    assert segment.decomposition is not None, \
        f"segment {segment.id} missing decomposition blob; fit via OP-030 first"

    # 1. Coefficient-level edit on fitted decomposition
    blob = copy.deepcopy(segment.decomposition)
    X_edit = op_tier2.apply(blob, **op_params)

    # 2. Constraint projection (delegates to OP-051)
    from backend.app.services.operations.tier3.compensation import project
    for constraint in constraints:
        if not constraint.satisfied(X_edit, aux=op_params):
            X_edit = project(X_edit, constraint, compensation_mode)

    # 3. Relabel (delegates to OP-040)
    from backend.app.services.operations.relabeler import relabel
    relabel_result = relabel(
        old_shape=segment.label,
        operation=op_tier2.name,
        op_params=op_params,
        edited_series=X_edit,
    )

    # 4. Audit + return
    return CFResult(
        edited_series=X_edit,
        blob=blob,
        new_shape=relabel_result.new_shape,
        confidence=relabel_result.confidence,
        needs_resegment=relabel_result.resegment_needed,
        constraint_residual={c.name: c.residual(X_edit) for c in constraints},
        method='decomposition_first',
        edit_space='coefficient',        # NEVER 'raw_signal_gradient'
    )
```

---

## Acceptance Criteria

- [x] `backend/app/services/operations/cf_coordinator.py` with `synthesize_counterfactual()` and `CFResult` dataclass
- [x] **Architectural property:** no Tier-2 op path mutates `X` pointwise at the raw-signal level — asserted by a grep test in CI (`tests/test_architecture.py` greps for forbidden patterns like `X[i] += ` outside Tier-1 atoms)
- [x] Fails fast with clear error if segment has no decomposition blob (prompts user/UI to run OP-030 first)
- [x] Signal-space CF (via Tier-1 `replace_from_library`) is an explicit separate code path, not automatic fallback
- [x] Constraint projection delegates to OP-051; residual exposed in `CFResult` and surfaced to UI-010 budget bar
- [x] Relabel invoked on every result; `CFResult.new_shape` populated
- [x] `CFResult.edit_space` field is always literally `'coefficient'` for decomposition-first path (used by paper-benchmark comparator)
- [x] Unit test: CF synthesis on plateau segment with `raise_lower(delta=+5)` → reassembled signal = original + 5 exactly (coefficient-level, no residual drift)
- [x] Integration test: full round-trip UI → OP-050 → edited series + audit log entry + label chip + constraint badge
- [x] Tests cover: missing-blob error; constraint projection triggered; relabel invoked; `edit_space == 'coefficient'` invariant; comparison ablation vs a pointwise-L1 baseline on fixture (decomposition-first produces smaller L∞ off-segment error)
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-050: CF synthesis coordinator (decomposition-first architecture)"` ← hook auto-moves this file to `done/` on commit
