    # HTS-110 — Document real dataset and model asset workflow

    **Ticket ID:** `HTS-110`  
    **Title:** `Document real dataset and model asset workflow`  
    **Status:** `done`  
    **Priority:** `P2`  
    **Type:** `docs`  
    **Depends on:** `HTS-109`  
    **Blocked by:** `none`  
    **Owner:** `Codex`  
    **Branch:** `hts/hts-110-real-asset-runbook`

    ---

    ## 1. Goal

    Document how real benchmark datasets and model artifacts should be placed, validated, and used inside the app. The runbook should make it easy for Codex and human developers to reproduce the integration setup without guessing paths.

    ---

    ## 2. Scope

    ### In scope
    - benchmark asset placement docs
- supported dataset/model matrix
- setup and validation commands
- known failure modes and fixes

    ### Out of scope
    - new code features
- training guide beyond short references
- paper-writing content

    Codex must not implement out-of-scope work under this ticket.

    ---

    ## 3. Context to Read First

    Required:
    - `Rules.txt`
    - `docs/planning/codex_rules_hypothe_x_ts.md`
    - `docs/planning/implementation_steps_hypothe_x_ts.md`
    - this ticket

    Task-specific:
    - `HypotheX-TS - Evaluation.md`
- `HypotheX-TS - References.md`
- `Rules.txt`

    ---

    ## 4. Affected Areas

    ### Likely files or modules
    - README.md
- benchmarks/README.md
- docs/

    ### Architecture layer
    - [ ] frontend
    - [ ] backend
    - [ ] API contract
    - [ ] domain logic
    - [ ] model/data
    - [x] tests
    - [x] docs

    ### Risk level
    `low`

    ---

    ## 5. Inputs and Expected Outputs

    ### Inputs
    - current manifests, services, and smoke tests

    ### Expected outputs
    - developer-readable runbook for real assets

    ---

    ## 6. Acceptance Criteria

    - [ ] Docs state the supported datasets and model families clearly.
- [ ] Docs specify canonical folder locations for datasets, manifests, and model artifacts.
- [ ] Docs include validation and smoke-test commands.
- [ ] Docs include at least three common failure cases and their likely fixes.

    ---

    ## 7. Implementation Notes

    Keep docs operational. The goal is reproducible setup, not literature discussion.

    ---

    ## 8. Verification Plan

    ### Required checks
    - [ ] relevant unit tests
    - [ ] relevant integration or smoke tests
    - [ ] lint or static checks if configured
    - [ ] manual verification if behavior is user-visible

    ### Commands
    ```bash
    pytest -q || true

    ```

    ### Manual verification
    1. Read the runbook top to bottom.
2. Confirm a new developer could find the expected folders and commands.
3. Confirm the supported dataset/model matrix matches the manifests.

    ---

    ## 9. Definition of Done

    - [ ] Goal is implemented.
    - [ ] All acceptance criteria are satisfied.
    - [ ] Required tests and checks pass.
    - [ ] No blocking review issues remain.
    - [ ] Docs/comments are updated if behavior changed.
    - [ ] Changes are committed with the ticket ID.
    - [ ] Ticket status is updated to `done`.

    ---

    ## 10. Deliverables

    - runbook docs
- updated README
- supported matrix table

    ---

    ## 11. Review Checklist

    ### Scope review
    - [ ] No unrelated files were changed.
    - [ ] No out-of-scope behavior was added.

    ### Architecture review
    - [ ] Layer boundaries remain clean.
    - [ ] Data loading is not duplicated across modules.
    - [ ] Model artifact handling is centralized.

    ### Quality review
    - [ ] Names match project concepts.
    - [ ] Error handling is explicit.
    - [ ] New behavior is covered by tests.

    ### Contract review
    - [ ] Public interfaces remain compatible, or the change is documented.

    ---

    ## 12. Commit

    ### Branch naming
    `hts/hts-110-real-asset-runbook`

    ### Commit message
    `HTS-110: document real dataset and model asset workflow`
