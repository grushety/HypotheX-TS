# CODEX_RULES.md

## Purpose
These rules define how Codex should work on HypotheX-TS.

Project goal: convert the HypotheX-TS idea into a ready-to-use app with Codex.
Workflow order:
1. define Codex rules,
2. refine implementation steps,
3. create tickets from the template,
4. debug only after implementation work is ticketed and completed.

Codex must optimize for correctness, traceability, small scoped changes, and verifiable progress.

---

## 1. Operating Principles

- Work ticket-first. Do not start implementation without a ticket.
- Work on one ticket at a time.
- Do not make unsolicited changes outside the active ticket.
- Prefer the smallest change that satisfies the ticket.
- Preserve working code unless the ticket explicitly requires changing it.
- Never guess hidden requirements when project documents can answer them.
- When scope expands beyond the current ticket, stop and report the boundary.
- When a requested change would require touching many unrelated files, split the work into new implementation steps or tickets.

---

## 2. Required Order of Work

For every feature or fix, Codex must follow this order:

1. Read the active ticket.
2. Read the relevant project context documents.
3. Confirm scope boundaries from the ticket.
4. Implement only what is in scope.
5. Run the required verification steps.
6. Record any issues that block completion.
7. Mark the ticket done only when Definition of Done is fully satisfied.

Codex must not jump directly from idea to code without the context and ticket layers.

---

## 3. Context Loading Rules

Before editing code, Codex must read the minimum relevant context.

### Always read first
- `Rules.txt`
- active ticket file
- `TICKET-TEMPLATE.md`
- project architecture or implementation notes relevant to the task

### Read before backend work
- technical plan sections for backend modules
- formal definitions relevant to the touched module
- backend patterns / backend conventions document if present

### Read before frontend work
- technical plan sections for UI components and user flows
- frontend patterns / frontend conventions document if present

### Read before domain logic work
- formal definitions for segmentation, operations, and constraints
- project notes that define semantic labels, operation behavior, and constraint behavior

### Read before model or data work
- technical plan for segmentation model, constraint engine, and operation engine
- any status-tracking or mock-removal document if the project uses one

If context is missing or contradictory, Codex should not invent policy. It should surface the conflict in the ticket notes.

---

## 4. Architecture Rules

HypotheX-TS should be implemented as separate modules with clean API boundaries.

Minimum architecture:
- segmentation model
- constraint engine
- operation engine
- interactive UI
- audit/logging layer

Codex must preserve module boundaries.

### Backend rules
- Keep route or API handlers thin.
- Put business logic in services or domain modules, not in handlers.
- Use typed, explicit input and output contracts where practical.
- Keep file paths and storage access consistent across the backend.
- Avoid hidden coupling between segmentation, constraints, and UI code.

### Frontend rules
- UI components should not contain backend business logic.
- Prefer a dedicated API layer between UI state and backend requests.
- Keep visualization logic separate from domain logic.
- The interface should reflect the operation-centered design of HypotheX-TS: split, merge, reclassify, align, simulate intervention, and audit logging.

### Domain rules
- The segment is the core interaction unit.
- Operations act on semantic segments, not arbitrary raw slices, unless a ticket explicitly defines a lower-level editing feature.
- Constraints must be represented explicitly as statuses such as PASS, WARN, FAIL, or PROJECTED, not only hidden backend checks.
- Hard and soft constraint behavior must remain distinguishable in both logic and UI.

---

## 5. Scope Control Rules

- Touch only files required for the current ticket.
- Do not rewrite unrelated code during a feature implementation.
- Do not rename, move, or delete files unless the ticket explicitly requires it.
- Do not delete tests without explicit approval in the ticket.
- Do not refactor stable code opportunistically.
- If a fix requires changing more than the expected scope, stop and note the dependency.
- If a caller also needs to change, prefer a separate follow-up ticket unless the active ticket explicitly includes both sides.

For larger refactors, create a checkpoint commit before structural changes.

---

## 6. Implementation Style Rules

- Prefer small, reversible edits.
- Add or update docstrings and comments where the contract is not obvious.
- Use clear names that match project concepts: segment, boundary, operation, constraint, proposal, audit log, model version.
- Keep functions compact and single-purpose where practical.
- Avoid duplicating logic across modules.
- Prefer explicit errors over silent fallbacks.
- Prefer deterministic behavior in domain logic and tests.

Codex should optimize for maintainability over cleverness.

---

## 7. Testing and Verification Rules

After any code change, Codex must run verification appropriate to the scope.

### Minimum rule
Always run tests after changes.

### Backend changes
Run backend unit tests relevant to the changed module.
If the change affects APIs, services, models, or integration flow, run the project smoke or integration test sequence.

### Frontend changes
Run frontend unit tests relevant to the changed components, stores, or API layer.
Run end-to-end checks when the ticket changes interactive workflows.

### API changes
Validate response shape against the defined API contract.

### New behavior
Add or update tests for:
- happy path,
- error path,
- edge cases,
- constraint behavior where applicable.

### Verification gate
A ticket is not complete if required tests fail, are skipped without reason, or the integration contract is broken.

---

## 8. Ticket Workflow Rules

All implementation work must be tracked as ticket files.

Each ticket should contain at least:
- ticket ID and title,
- status,
- dependencies,
- goal,
- acceptance criteria,
- definition of done.

Codex must use the ticket to constrain work.

### Ticket execution rules
- Do not begin coding without an active ticket.
- Complete the active ticket before starting another.
- Update ticket status only after verification succeeds.
- Use the ticket ID in commit messages.
- If blocked, record the blocker clearly instead of partially marking the ticket done.

### Recommended completion sequence
1. implement,
2. run tests,
3. run review checks,
4. commit,
5. update ticket status to done.

---

## 9. Review Passes

Before a ticket is considered complete, Codex should perform these review passes when relevant.

### Contract review
Check that APIs, payloads, and returned structures match the current project contract.

### Refactor guard review
Check for:
- business logic in handlers,
- oversized functions,
- duplicated logic,
- missing type information where the codebase expects it,
- missing public documentation,
- direct network calls in the wrong layer.

### Test review
Confirm tests cover intended behavior and do not rely on hidden side effects.

### Documentation review
If the ticket changes behavior visible to future developers, update the relevant docs, comments, or notes.

---

## 10. Git and Change Management Rules

- Use one branch per ticket when working in git.
- Never commit directly to main.
- Run tests before commit.
- Use a checkpoint commit before large refactors.
- Commit message format should include the ticket ID.

Suggested format:
`TICKET-X: short description`

Do not create noisy commits for unfinished or unverified work unless the ticket explicitly requests a checkpoint.

---

## 11. HypotheX-TS Product Rules

Codex must preserve the core product shape of HypotheX-TS.

### Core interaction model
The app centers on:
- time series display,
- segmentation overlay,
- manual boundary editing,
- label assignment,
- semantic operations,
- constraint feedback,
- counterfactual exploration,
- disagreement view between user and model segmentation,
- audit log.

### Priority order for MVP
Default implementation order should follow the current minimum viable study path unless a ticket overrides it:
1. time series display and segmentation overlay,
2. manual boundary editing and label assignment,
3. split, merge, reclassify,
4. simulate intervention,
5. soft constraint check and warning display,
6. interaction log export,
7. few-shot model adaptation,
8. hard constraint blocking and projection,
9. uncertainty overlay.

### Domain integrity rules
- Segment labels and operations should match the project’s formal definitions.
- Constraint behavior must stay domain-configurable.
- Counterfactual synthesis should remain segment-bounded unless a ticket explicitly expands scope.
- Auditability is a product feature, not an optional extra.

---

## 12. What Codex Must Avoid

- starting implementation without a ticket,
- doing multiple tickets at once,
- broad refactors without a checkpoint,
- hidden architectural rewrites,
- changing unrelated files for convenience,
- deleting tests or files without explicit authorization,
- embedding domain logic in UI handlers,
- embedding business logic in route handlers,
- bypassing verification because a change looks small,
- marking a ticket done while tests are failing.

---

## 13. Definition of Done for Codex Work

A ticket is done only when all of the following are true:

- the ticket goal is implemented,
- acceptance criteria are satisfied,
- required tests pass,
- required review checks have no blocking issues,
- any necessary documentation updates are made,
- the change is committed with the ticket ID,
- the ticket status is updated to done.

If any item is incomplete, the ticket remains open.

---

## 14. Default Escalation Rules

Codex should stop and report instead of pushing through when:
- required context documents are missing,
- ticket scope is ambiguous,
- implementation requires touching unrelated stable modules,
- tests fail and the root cause is outside ticket scope,
- the project architecture in code conflicts with the written project plan,
- a requested change would violate the core HypotheX-TS interaction model.

When stopping, Codex should report:
- what blocked progress,
- which files or modules are affected,
- whether the blocker should become a new ticket.

---

## 15. Recommended Next Artifacts

After this rules file, the project should define:
1. implementation-step format,
2. Codex-adapted ticket template,
3. first MVP ticket set,
4. debugging workflow.

This ordering should be preserved unless the project owner explicitly changes it.