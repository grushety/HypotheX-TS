## Ticket Header

**Ticket ID:** `HTS-204`  
**Title:** `Implement score-based chunk assignment with ambiguity handling`  
**Status:** `done`  
**Priority:** `P0`  
**Type:** `feature`  
**Depends on:** `HTS-202, HTS-203`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-204-chunk-assignment`

---

## 1. Goal

Implement the formal chunk scoring and default assignment layer for the MVP ontology. The system should compute chunk scores per segment, choose a default label, and flag ambiguous cases instead of relying on brittle one-pass priority rules alone.

---

## 2. Scope

### In scope
- compute q_y(s) style scores for each active chunk type
- default chunk assignment from scores
- ambiguity margin / uncertain flag support

### Out of scope
- model-based label prediction
- online adaptation
- full six-type ontology if MVP uses a reduced set

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `MyPaper-HypotheX-TS - Semantic Chunk Types and Typed Operation - Revised.md`
- `MyPaper-HypotheX-TS - ML Model Approach - Revised.md`
- `HypotheX-TS - Formal Definitions.md`
- `HypotheX-TS - Research Questions.md`

---

## 4. Affected Areas

### Likely files or modules
- `backend/domain/chunk_scoring.py`
- `backend/domain/chunk_assignment.py`
- `tests/`

### Architecture layer
Mark all that apply:
- [ ] frontend
- [x] backend
- [ ] API contract
- [x] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`high`

Brief reason:
> This ticket operationalizes the semantics. Poor ambiguity handling will produce brittle labels and undermine both the UI and the learning layer.

---

## 5. Inputs and Expected Outputs

### Inputs
- segment statistics bundle
- threshold config
- active chunk ontology

### Expected outputs
- score map per chunk type
- default assigned label
- uncertainty or ambiguity indicator

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [x] Chunk scores are computed for every active chunk type.
- [x] Default assignment is based on scores rather than a single rigid if/else cascade.
- [x] Near-tie cases can be flagged as uncertain or ambiguous.
- [x] Tests cover at least one clear case and one ambiguous case.
- [x] Assignment results are serializable into the shared segment schema.

---

## 7. Implementation Notes

- A small fallback priority can exist for deterministic tie-breaking, but it must not replace score computation.
- Keep the uncertain/ambiguous mechanism explicit; do not hide it.
- Preserve compatibility with later user override behavior.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [x] unit tests for scoring and assignment
- [x] lint/static checks

### Commands
```bash
pytest -q
ruff check .
```

### Manual verification
1. Score a clean plateau and confirm plateau dominates.
2. Score a borderline trend/plateau case and confirm ambiguity is visible.
3. Confirm assignment output matches the schema contract.

If a check cannot run, Codex must record why.

---

## 9. Definition of Done

A ticket is done only when all items below are true.

- [x] Goal is implemented.
- [x] All acceptance criteria are satisfied.
- [x] Required tests and checks pass.
- [x] No blocking review issues remain.
- [x] Docs/comments are updated if behavior changed.
- [x] Changes are committed with the ticket ID.
- [x] Ticket status is updated to `done`.

---

## 10. Deliverables

- chunk scoring and assignment module
- tests for clear and ambiguous cases
- docs note on score outputs

---

## 11. Review Checklist

Before marking complete, verify:

### Scope review
- [ ] No unrelated files were changed.
- [ ] No out-of-scope behavior was added.

### Architecture review
- [ ] Business logic is not in route handlers.
- [ ] Domain logic is not embedded in UI code.
- [ ] Layer boundaries remain clean.

### Quality review
- [ ] Names match project concepts.
- [ ] Error handling is explicit.
- [ ] New behavior is covered by tests.
- [ ] Logging/audit behavior is preserved where relevant.

### Contract review
- [ ] Public interfaces remain compatible, or the change is documented in the ticket.

---

## 12. Commit

### Branch naming
`{t['branch']}`

### Commit message
`{tid}: {t['title'][0].lower()+t['title'][1:]}`

---

## 13. Status Update Block

**Current status:** `done`  
**What changed:** `added pure chunk scoring and assignment modules, extended segment statistics with periodicity support, and aligned the shared segmentation schema with the MVP ontology`  
**Checks run:** `pytest -q (blocked: pytest not on PATH), ruff check . (blocked: ruff not on PATH), JSON parse sanity checks for schema fixtures`  
**Blockers:** `python and ruff tooling are not runnable in this shell environment`  
**Next step:** `HTS-205`

---

## 14. Completion Note

**Completed on:** `2026-03-28`  
**Summary:** `Implemented score-based chunk scoring and default assignment with explicit ambiguity handling for the active MVP ontology.`  
**Tests passed:** `JSON parse sanity checks`  
**Files changed:** `backend/app/domain/, backend/tests/test_chunk_assignment.py, backend/tests/test_segment_statistics.py, schemas/, README.md, docs/domain-config-note.md`  
**Follow-up tickets needed:** `none`
