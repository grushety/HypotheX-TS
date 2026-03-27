    # HTS-106 — Add frontend benchmark selector panel

    **Ticket ID:** `HTS-106`  
    **Title:** `Add frontend benchmark selector panel`  
    **Status:** `done`  
    **Priority:** `P1`  
    **Type:** `feature`  
    **Depends on:** `HTS-105`  
    **Blocked by:** `none`  
    **Owner:** `Codex`  
    **Branch:** `hts/hts-106-benchmark-selector`

    ---

    ## 1. Goal

    Add a frontend control panel that lets the user select a supported dataset, a supported model, a split, and a sample index. This panel should use the new backend endpoints and keep selection state centralized.

    ---

    ## 2. Scope

    ### In scope
    - dataset selector UI
- model selector UI
- split and sample selector controls
- selection state store
- loading/error states

    ### Out of scope
    - chart integration of raw samples
- prediction visualization details
- editing/operation controls

    Codex must not implement out-of-scope work under this ticket.

    ---

    ## 3. Context to Read First

    Required:
    - `Rules.txt`
    - `docs/planning/codex_rules_hypothe_x_ts.md`
    - `docs/planning/implementation_steps_hypothe_x_ts.md`
    - this ticket

    Task-specific:
    - `HypotheX-TS - Technical Plan.md`
- `IMPLEMENTATION-STEPS.md` current version

    ---

    ## 4. Affected Areas

    ### Likely files or modules
    - frontend/src/components/
- frontend/src/stores/
- frontend/src/services/api/

    ### Architecture layer
    - [x] frontend
    - [ ] backend
    - [x] API contract
    - [ ] domain logic
    - [ ] model/data
    - [x] tests
    - [x] docs

    ### Risk level
    `medium`

    ---

    ## 5. Inputs and Expected Outputs

    ### Inputs
    - dataset list API
- model list API
- compatibility API

    ### Expected outputs
    - selector panel
- selection state
- compatibility-aware enable/disable behavior

    ---

    ## 6. Acceptance Criteria

    - [ ] User can select one supported dataset and one supported model from backend-provided options.
- [ ] Incompatible pairs are flagged or blocked in the UI.
- [ ] Selection state includes split and sample index.
- [ ] Loading and backend error states are visible.

    ---

    ## 7. Implementation Notes

    Keep API calls in a dedicated frontend service layer. Do not embed backend request logic in presentational components.

    ---

    ## 8. Verification Plan

    ### Required checks
    - [ ] relevant unit tests
    - [ ] relevant integration or smoke tests
    - [ ] lint or static checks if configured
    - [ ] manual verification if behavior is user-visible

    ### Commands
    ```bash
    cd frontend
npm test -- --runInBand

    ```

    ### Manual verification
    1. Open the selector panel.
2. Choose a dataset and model.
3. Confirm incompatible pair behavior is visible.
4. Confirm loading and error states render.

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

    - selector panel component
- state store updates
- API service hooks
- frontend tests

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
    `hts/hts-106-benchmark-selector`

    ### Commit message
    `HTS-106: add frontend benchmark selector panel`
