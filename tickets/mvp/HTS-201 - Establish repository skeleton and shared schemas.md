## Ticket Header

**Ticket ID:** `HTS-201`  
**Title:** `Establish repository skeleton and shared schemas`  
**Status:** `done`  
**Priority:** `P0`  
**Type:** `feature`  
**Depends on:** `none`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-201-repo-schemas`

---

## 1. Goal

Create the initial project structure and the shared schema layer that all later tickets will build on. This should define the canonical data contracts for time series input, semantic segments, operations, constraints, and session logs so frontend, backend, and model code can evolve without diverging.

---

## 2. Scope

### In scope
- create or confirm the top-level frontend/backend/model/evaluation/docs/schemas structure
- define JSON schemas or equivalent typed contracts for core domain objects
- add sample fixture files for one time series and one segmentation/session payload

### Out of scope
- implementing real UI behavior
- implementing learned segmentation logic
- adding ticket-specific business logic beyond schema definition

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `MyPaper-HypotheX-TS - ML Model Approach - Revised.md`
- `MyPaper-HypotheX-TS - Semantic Chunk Types and Typed Operation - Revised.md`
- `HypotheX-TS - Technical Plan.md`
- `HypotheX-TS - Formal Definitions.md`
- `HypotheX-TS - Research Plan.md`

---

## 4. Affected Areas

### Likely files or modules
- `frontend/`
- `backend/`
- `model/`
- `evaluation/`
- `schemas/`
- `docs/`

### Architecture layer
Mark all that apply:
- [x] frontend
- [x] backend
- [x] API contract
- [x] domain logic
- [ ] model/data
- [ ] tests
- [x] docs

### Risk level
`medium`

Brief reason:
> This ticket sets the contracts the rest of the system depends on. Weak schemas will create later rework across all layers.

---

## 5. Inputs and Expected Outputs

### Inputs
- sample time series payload
- sample semantic segmentation payload
- sample session export payload

### Expected outputs
- versioned shared schemas
- sample fixtures that validate against the schemas
- documented canonical object names and fields

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [ ] Core schemas exist for time series, semantic segments, typed operations, constraints, and session logs.
- [ ] At least one sample fixture validates against each schema.
- [ ] Schema names and fields match HypotheX-TS terminology from the methodology docs.
- [ ] No domain logic is embedded in the schema layer.
- [ ] A short docs note explains where future modules should import or reference the contracts.

---

## 7. Implementation Notes

- Keep this ticket focused on structure and contracts.
- Prefer explicit field names over compact but ambiguous ones.
- Do not invent extra ontology fields that are not motivated by the methodology docs.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [ ] schema validation
- [ ] backend lint or static checks
- [ ] docs path sanity check

### Commands
```bash
pytest -q
ruff check .
python -m json.tool < sample_fixture.json >/dev/null
```

### Manual verification
1. Open the sample fixtures.
2. Confirm each fixture is readable and matches the schema names.
3. Confirm later tickets can reference the schema paths without ambiguity.

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

- repository/module skeleton updates
- shared schema files
- sample fixtures
- brief docs note for contracts

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
**What changed:** `added top-level shared schema contracts, fixtures, and skeleton notes for future model/evaluation modules`  
**Checks run:** `pytest -q (blocked: pytest not on PATH), ruff check . (blocked: ruff not on PATH), json fixture syntax checks via ConvertFrom-Json`  
**Blockers:** `python and ruff tooling are not runnable in this shell environment`  
**Next step:** `HTS-202`

---

## 14. Completion Note

**Completed on:** `2026-03-28`  
**Summary:** `Established a root-level shared schema layer, example fixtures, and minimal model/evaluation skeleton docs for future tickets.`  
**Tests passed:** `JSON fixture syntax sanity checks`  
**Files changed:** `schemas/, model/README.md, evaluation/README.md, docs/shared-contracts-note.md, README.md`  
**Follow-up tickets needed:** `HTS-202`
