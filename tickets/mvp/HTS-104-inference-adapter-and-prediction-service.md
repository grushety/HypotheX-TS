
# HTS-104 — Implement inference adapter and prediction service

    **Ticket ID:** `HTS-104`  
    **Title:** `Implement inference adapter and prediction service`  
    **Status:** `done`  
    **Priority:** `P0`  
    **Type:** `feature`  
    **Depends on:** `HTS-102, HTS-103`  
    **Blocked by:** `none`  
    **Owner:** `Codex`  
    **Branch:** `hts/hts-104-inference-service`

    ---

    ## 1. Goal

    Implement a prediction service that wraps loaded model artifacts behind a unified inference adapter. The service should accept a selected dataset sample and a selected compatible model, execute prediction, and return a normalized prediction response for the rest of the app.

    ---

    ## 2. Scope

    ### In scope
    - inference adapter interface
- family-specific adapters as needed
- prediction service
- normalized prediction response schema
- batch-safe sample selection path

    ### Out of scope
    - counterfactual generation
- segmentation model adaptation
- frontend benchmark picker

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
- `HypotheX-TS - Formal Definitions.md`

    ---

    ## 4. Affected Areas

    ### Likely files or modules
    - backend/app/services/inference.py
- backend/app/schemas/
- backend/tests/

    ### Architecture layer
    - [ ] frontend
    - [x] backend
    - [x] API contract
    - [ ] domain logic
    - [x] model/data
    - [x] tests
    - [x] docs

    ### Risk level
    `high`

    ---

    ## 5. Inputs and Expected Outputs

    ### Inputs
    - loaded model handle
- validated dataset/model pair
- selected sample from dataset split

    ### Expected outputs
    - predicted class
- scores/probabilities if available
- sample metadata for display

    ---

    ## 6. Acceptance Criteria

    - [ ] Prediction service can run inference for at least one supported model family on one compatible dataset.
- [ ] Prediction response uses one normalized schema regardless of model family.
- [ ] Prediction failures are explicit and do not crash the application.
- [ ] Tests cover at least one happy path and one adapter failure path.

    ---

    ## 7. Implementation Notes

    Keep inference logic out of route handlers. If the underlying models use different frameworks or tensor layouts, normalize those differences inside adapters only.

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
    1. Execute one prediction on a real dataset sample with a compatible artifact.
2. Confirm the returned response schema is stable.
3. Force an adapter error and confirm the service reports it cleanly.

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

    - inference service
- adapter interface
- normalized prediction schema
- tests

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
    `hts/hts-104-inference-service`

    ### Commit message
    `HTS-104: implement inference adapter and prediction service`
