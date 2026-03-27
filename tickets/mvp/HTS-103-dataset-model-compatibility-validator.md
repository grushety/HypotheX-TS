    # HTS-103 — Add dataset model compatibility validator

    **Ticket ID:** `HTS-103`  
    **Title:** `Add dataset model compatibility validator`  
    **Status:** `done`  
    **Priority:** `P1`  
    **Type:** `feature`  
    **Depends on:** `HTS-101, HTS-102`  
    **Blocked by:** `none`  
    **Owner:** `Codex`  
    **Branch:** `hts/hts-103-compatibility-validator`

    ---

    ## 1. Goal

    Add a compatibility validator that checks whether a chosen dataset and model artifact can be used together before inference. The validator should prevent shape mismatches and unsupported pairings from reaching runtime prediction paths.

    ---

    ## 2. Scope

    ### In scope
    - compatibility validator service
- shape and channel checks
- manifest-level dataset-family pairing validation
- readable validation messages

    ### Out of scope
    - frontend picker UI
- actual prediction endpoint
- automatic repair of invalid artifacts

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
- `HypotheX-TS - Formal Definitions.md`

    ---

    ## 4. Affected Areas

    ### Likely files or modules
    - backend/app/services/compatibility.py
- backend/tests/

    ### Architecture layer
    - [ ] frontend
    - [x] backend
    - [ ] API contract
    - [x] domain logic
    - [x] model/data
    - [x] tests
    - [x] docs

    ### Risk level
    `medium`

    ---

    ## 5. Inputs and Expected Outputs

    ### Inputs
    - dataset summary objects
- model descriptor objects

    ### Expected outputs
    - compatibility result object
- validation errors or pass result

    ---

    ## 6. Acceptance Criteria

    - [ ] Validator rejects dataset/model pairs with incompatible input shapes or unsupported dataset names.
- [ ] Validator distinguishes univariate and multivariate expectations.
- [ ] Validation messages are explicit enough for UI display or logs.
- [ ] Unit tests cover valid and invalid pairings.

    ---

    ## 7. Implementation Notes

    This validator should run before model loading or inference requests are accepted. Keep it reusable from APIs and smoke tests.

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
    1. Run validator for GunPoint with a compatible model artifact.
2. Run validator for BasicMotions with an intentionally incompatible univariate artifact.
3. Confirm error output names the mismatch clearly.

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

    - compatibility validator
- tests for valid and invalid pairings

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
    `hts/hts-103-compatibility-validator`

    ### Commit message
    `HTS-103: add dataset model compatibility validator`
