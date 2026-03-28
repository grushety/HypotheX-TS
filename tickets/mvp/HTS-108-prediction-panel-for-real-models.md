    # HTS-108 — Add prediction panel for real models

    **Ticket ID:** `HTS-108`  
    **Title:** `Add prediction panel for real models`  
    **Status:** `done`  
    **Priority:** `P1`  
    **Type:** `feature`  
    **Depends on:** `HTS-104, HTS-105, HTS-106, HTS-107`  
    **Blocked by:** `none`  
    **Owner:** `Codex`  
    **Branch:** `hts/hts-108-prediction-panel`

    ---

    ## 1. Goal

    Add a frontend prediction panel that requests inference for the selected real dataset sample and selected compatible model, then displays the returned prediction and confidence information if available.

    ---

    ## 2. Scope

    ### In scope
    - prediction request flow
- prediction panel UI
- request state and errors
- model/sample summary display

    ### Out of scope
    - counterfactual preview
- comparison of multiple models at once
- advanced probability calibration views

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
- `HypotheX-TS - Research Plan.md`

    ---

    ## 4. Affected Areas

    ### Likely files or modules
    - frontend/src/components/
- frontend/src/services/api/
- frontend/src/stores/
- frontend/tests/

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
    - selection state
- prediction API endpoint

    ### Expected outputs
    - prediction panel with normalized real-model output

    ---

    ## 6. Acceptance Criteria

    - [ ] User can request prediction for the selected sample/model pair.
- [ ] Prediction panel renders predicted class and any available score information from the normalized response.
- [ ] Loading and error states are explicit.
- [ ] Frontend tests cover success and failure rendering paths.

    ---

    ## 7. Implementation Notes

    The panel should depend only on the normalized prediction schema, not on family-specific model details.

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
    1. Request prediction for a compatible pair.
2. Inspect success state.
3. Force an error and inspect the UI error state.

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

    - prediction panel component
- API integration
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
    `hts/hts-108-prediction-panel`

    ### Commit message
    `HTS-108: add prediction panel for real models`
