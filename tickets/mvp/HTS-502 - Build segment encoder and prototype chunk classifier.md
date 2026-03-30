## Ticket Header

**Ticket ID:** `HTS-502`  
**Title:** `Build segment encoder and prototype chunk classifier`  
**Status:** `done`  
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

- [x] The encoder produces fixed-size embeddings for candidate segments.
- [x] The prototype classifier returns label probabilities for the active chunk types.
- [x] Embeddings or distances are normalized in a documented way.
- [x] Tests cover inference shape and at least one predictable synthetic or fixture case.
- [x] The classifier output can be serialized into the suggestion contract.

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
- [x] model tests
- [x] lint/static checks
- [x] shape/inference smoke tests

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

- [x] Goal is implemented.
- [x] All acceptance criteria are satisfied.
- [x] Required tests and checks pass.
- [x] No blocking review issues remain.
- [x] Docs/comments are updated if behavior changed.
- [x] Changes are committed with the ticket ID.
- [x] Ticket status is updated to `done`.

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
- [x] No unrelated files were changed.
- [x] No out-of-scope behavior was added.

### Architecture review
- [x] Business logic is not in route handlers.
- [x] Domain logic is not embedded in UI code.
- [x] Layer boundaries remain clean.

### Quality review
- [x] Names match project concepts.
- [x] Error handling is explicit.
- [x] New behavior is covered by tests.
- [x] Logging/audit behavior is preserved where relevant.

### Contract review
- [x] Public interfaces remain compatible, or the change is documented in the ticket.

---

## 12. Commit

### Branch naming
`{t['branch']}`

### Commit message
`{tid}: {t['title'][0].lower()+t['title'][1:]}`

---

## 13. Status Update Block

**Current status:** `done`  
**What changed:** `Added a fixed-length normalized segment encoder, a cosine-similarity prototype classifier over the active chunk labels, and service wiring so provisional segments can carry label proposals, confidence, and labelScores in the existing suggestion contract when support segments are provided.`  
**Checks run:** `pytest -q backend/tests/test_prototype_classifier.py backend/tests/test_boundary_suggestions.py; pytest -q backend/tests; ruff check backend schemas docs model; manual prototype-classifier smoke run on a labeled fixture set`  
**Blockers:** `none`  
**Next step:** `Move to HTS-503 for suggestion API wiring and accept/override flow.`

---

## 14. Completion Note

**Completed on:** `2026-03-30`  
**Summary:** `Implemented a small inspectable segment encoder that resamples segments to a fixed profile, normalizes embeddings with L2 geometry, and classifies provisional segments via cosine-similarity prototypes over the active chunk vocabulary. The suggestion service now emits label proposals, confidence, and probability maps directly inside the existing suggestion payload contract.`  
**Tests passed:** `pytest -q backend/tests/test_prototype_classifier.py backend/tests/test_boundary_suggestions.py; pytest -q backend/tests; ruff check backend schemas docs model; manual smoke run produced a 36-dimensional embedding and predicted 'event' with confidence 0.751818 on a held-out event-shaped segment.`  
**Files changed:** `backend/app/services/suggestion/segment_encoder.py; backend/app/services/suggestion/prototype_classifier.py; backend/app/services/suggestion/__init__.py; backend/app/services/suggestions.py; backend/tests/test_prototype_classifier.py; model/suggestion/segment_encoder.py; model/suggestion/prototype_classifier.py; model/suggestion/__init__.py; schemas/fixtures/suggestion-proposal.sample.json`  
**Follow-up tickets needed:** `none`
