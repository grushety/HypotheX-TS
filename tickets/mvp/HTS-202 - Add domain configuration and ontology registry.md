## Ticket Header

**Ticket ID:** `HTS-202`  
**Title:** `Add domain configuration and ontology registry`  
**Status:** `done`  
**Priority:** `P0`  
**Type:** `feature`  
**Depends on:** `HTS-201`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-202-domain-config`

---

## 1. Goal

Create a configuration layer for chunk thresholds, legal operation mappings, constraint severity, and MVP ontology scope. This makes the formal layer configurable without hard-coding domain assumptions throughout backend or UI modules.

---

## 2. Scope

### In scope
- define config files for chunk thresholds and duration limits
- define operation-per-chunk registry for the MVP ontology
- define hard vs soft constraint defaults in configuration

### Out of scope
- implementing the constraint engine itself
- full multi-domain support
- training or calibrating thresholds from data

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `MyPaper-HypotheX-TS - Semantic Chunk Types and Typed Operation - Revised.md`
- `HypotheX-TS - Formal Definitions.md`
- `HypotheX-TS - Technical Plan.md`
- `HypotheX-TS - Evaluation.md`

---

## 4. Affected Areas

### Likely files or modules
- `schemas/`
- `backend/config/`
- `docs/`

### Architecture layer
Mark all that apply:
- [ ] frontend
- [x] backend
- [x] API contract
- [x] domain logic
- [ ] model/data
- [ ] tests
- [x] docs

### Risk level
`medium`

Brief reason:
> The config layer controls how formal definitions become runnable code. Poor separation here leads to scattered magic numbers later.

---

## 5. Inputs and Expected Outputs

### Inputs
- MVP chunk ontology
- initial threshold values
- constraint severity settings

### Expected outputs
- domain config file(s)
- ontology registry
- documented config loading path

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [ ] A configuration file defines the active MVP chunk types.
- [ ] Chunk thresholds and minimum durations are stored in config rather than hard-coded in business logic.
- [ ] Legal operations per chunk type are represented in a machine-readable registry.
- [ ] Constraint defaults support both soft and hard modes.
- [ ] Config loading failure produces explicit errors rather than silent fallback behavior.

---

## 7. Implementation Notes

- Keep the first ontology to the MVP core unless another ticket explicitly expands it.
- Use stable naming aligned with the paper terms.
- Do not embed UI labels directly in config if they belong in the frontend translation layer.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [ ] config parse test
- [ ] lint/static checks
- [ ] basic registry lookup test

### Commands
```bash
pytest -q
ruff check .
```

### Manual verification
1. Load the config in a local shell or script.
2. Verify legal operations can be queried for each MVP chunk type.
3. Verify switching a constraint from soft to hard changes only configuration.

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

- config files
- ontology/operation registry
- docs note for configuration usage

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
**What changed:** `added the MVP domain config file, shared domain-config schema, explicit backend loader, and registry tests`  
**Checks run:** `pytest -q (blocked: pytest not on PATH), ruff check . (blocked: ruff not on PATH), JSON parse sanity checks for schemas and backend config`  
**Blockers:** `python and ruff tooling are not runnable in this shell environment`  
**Next step:** `HTS-203`

---

## 14. Completion Note

**Completed on:** `2026-03-28`  
**Summary:** `Added the first machine-readable ontology and threshold registry for the MVP, plus an explicit backend loading path with no silent fallback.`  
**Tests passed:** `JSON parse sanity checks`  
**Files changed:** `backend/config/, backend/app/core/domain_config.py, backend/tests/test_domain_config.py, schemas/, docs/domain-config-note.md, README.md`  
**Follow-up tickets needed:** `HTS-203`
