    # HTS-105 — Add benchmark dataset and model API endpoints

    **Ticket ID:** `HTS-105`  
    **Title:** `Add benchmark dataset and model API endpoints`  
    **Status:** `done`  
    **Priority:** `P0`  
    **Type:** `feature`  
    **Depends on:** `HTS-101, HTS-102, HTS-103, HTS-104`  
    **Blocked by:** `none`  
    **Owner:** `Codex`  
    **Branch:** `hts/hts-105-benchmark-api`

    ---

    ## 1. Goal

    Expose backend API endpoints for listing available datasets, listing available models, validating a dataset/model pair, and fetching a prediction for a selected sample. These endpoints form the app-facing contract for loading real benchmark assets.

    ---

    ## 2. Scope

    ### In scope
    - dataset list endpoint
- model list endpoint
- compatibility endpoint
- sample prediction endpoint
- response schemas and tests

    ### Out of scope
    - frontend state management
- chart rendering
- counterfactual preview

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
- `HypotheX-TS - Evaluation.md`

    ---

    ## 4. Affected Areas

    ### Likely files or modules
    - backend/app/routes/
- backend/app/schemas/
- backend/tests/

    ### Architecture layer
    - [ ] frontend
    - [x] backend
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
    - dataset and model registry services
- compatibility validator
- prediction service

    ### Expected outputs
    - HTTP endpoints for dataset/model discovery and prediction

    ---

    ## 6. Acceptance Criteria

    - [ ] Backend exposes endpoints for listing datasets and models.
- [ ] Backend exposes an endpoint to validate a selected dataset/model pair.
- [ ] Backend exposes an endpoint to fetch prediction output for a selected sample.
- [ ] Response schemas are documented and tested.
- [ ] Route handlers stay thin and call service-layer code.

    ---

    ## 7. Implementation Notes

    Use stable JSON response shapes. Prefer explicit query/path parameters over hidden global state. Do not let endpoints read files directly; always go through services.

    ---

    ## 8. Verification Plan

    ### Required checks
    - [ ] relevant unit tests
    - [ ] relevant integration or smoke tests
    - [ ] lint or static checks if configured
    - [ ] manual verification if behavior is user-visible

    ### Commands
    ```bash
    cd backend
pytest -q backend/tests

    ```

    ### Manual verification
    1. Call the dataset list endpoint.
2. Call the model list endpoint.
3. Validate one compatible and one incompatible pair.
4. Request a prediction for one real sample and inspect the response.

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

    - benchmark API routes
- response schemas
- endpoint tests

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
    `hts/hts-105-benchmark-api`

    ### Commit message
    `HTS-105: add benchmark dataset and model API endpoints`
