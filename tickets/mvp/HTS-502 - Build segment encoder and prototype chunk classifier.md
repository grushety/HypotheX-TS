## Ticket Header

**Ticket ID:** `HTS-502`  
**Title:** `Build segment encoder and prototype chunk classifier`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-203, HTS-204, HTS-501`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-502-prototype-classifier`

---

## 1. Goal

Implement the first assistive chunk-label suggestion model using a small segment encoder and prototype-based classifier. The objective is not state-of-the-art accuracy, but stable, inspectable label proposals aligned with the semantic chunk ontology.

---

## 2. Scope

### In scope
- segment encoder for candidate segments
- normalized embedding output
- prototype-based chunk classification with confidence scores

### Out of scope
- full online fine-tuning
- HSMM integration
- operation-aware learning

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `MyPaper-HypotheX-TS - ML Model Approach - Revised.md`
- `MyPaper-HypotheX-TS - Semantic Chunk Types and Typed Operation - Revised.md`
- `HypotheX-TS - Technical Plan.md`

---

## 4. Affected Areas

### Likely files or modules
- `model/`
- `backend/services/suggestion/`
- `tests/`

### Architecture layer
Mark all that apply:
- [ ] frontend
- [x] backend
- [x] API contract
- [ ] domain logic
- [x] model/data
- [x] tests
- [ ] docs

### Risk level
`high`

Brief reason:
> This is the first learned component and can easily become unstable if embeddings or prototypes are poorly normalized.

---

## 5. Inputs and Expected Outputs

### Inputs
- candidate segments
- segment features
- prototype support set

### Expected outputs
- embedding per segment
- label probabilities
- confidence or uncertainty signal

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [ ] The encoder produces fixed-size embeddings for candidate segments.
- [ ] The prototype classifier returns label probabilities for the active chunk types.
- [ ] Embeddings or distances are normalized in a documented way.
- [ ] Tests cover inference shape and at least one predictable synthetic or fixture case.
- [ ] The classifier output can be serialized into the suggestion contract.

---

## 7. Implementation Notes

- Keep the model small and inspectable.
- Prefer cosine or normalized-distance behavior over raw unstable Euclidean magnitudes.
- Do not add online fine-tuning under this ticket.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [ ] model tests
- [ ] lint/static checks
- [ ] shape/inference smoke tests

### Commands
```bash
pytest -q
ruff check .
```

### Manual verification
1. Run inference on a small labeled fixture set.
2. Inspect embeddings and probabilities.
3. Confirm at least clear prototype cases behave sensibly.

If a check cannot run, Codex must record why.

---

## 9. Definition of Done

A ticket is done only when all items below are true.

- [ ] Goal is implemented.
- [ ] All acceptance criteria are satisfied.
- [ ] Required tests and checks pass.
- [ ] No blocking review issues remain.
- [ ] Docs/comments are updated if behavior changed.
- [ ] Changes are committed with the ticket ID.
- [ ] Ticket status is updated to `done`.

---

## 10. Deliverables

- encoder module
- prototype classifier module
- tests
- basic inference wiring

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

**Current status:** `todo`  
**What changed:** `none yet`  
**Checks run:** `none yet`  
**Blockers:** `none`  
**Next step:** `{t['status_next']}`

---

## 14. Completion Note

**Completed on:** `<date>`  
**Summary:** `<brief summary of implemented result>`  
**Tests passed:** `<list>`  
**Files changed:** `<list or summary>`  
**Follow-up tickets needed:** `<IDs or none>`
