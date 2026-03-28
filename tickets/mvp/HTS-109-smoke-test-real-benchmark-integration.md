    # HTS-109 — Add smoke tests for real benchmark integration

    **Ticket ID:** `HTS-109`  
    **Title:** `Add smoke tests for real benchmark integration`  
    **Status:** `done`  
    **Priority:** `P1`  
    **Type:** `test`  
    **Depends on:** `HTS-105, HTS-107, HTS-108`  
    **Blocked by:** `none`  
    **Owner:** `Codex`  
    **Branch:** `hts/hts-109-smoke-real-integration`

    ---

    ## 1. Goal

    Add an integration smoke test path that proves the app can load real benchmark metadata, fetch a real sample, validate a dataset/model pair, and return a prediction end-to-end.

    ---

    ## 2. Scope

    ### In scope
    - backend smoke path for real assets
- optional frontend integration test if current stack supports it
- document expected fixture or artifact prerequisites

    ### Out of scope
    - full model retraining
- performance benchmarking
- user-study instrumentation

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
- `HypotheX-TS - Research Plan.md`

    ---

    ## 4. Affected Areas

    ### Likely files or modules
    - backend/tests/
- frontend/tests/
- docs/

    ### Architecture layer
    - [x] frontend
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
    - real benchmark fixture data and at least one real model artifact

    ### Expected outputs
    - repeatable smoke test that exercises the full asset-loading path

    ---

    ## 6. Acceptance Criteria

    - [ ] A repeatable smoke test exists for at least one univariate dataset/model pair.
- [ ] A repeatable smoke test exists for at least one multivariate dataset/model pair or an explicit deferred note is documented if artifacts are not yet available.
- [ ] Smoke test setup requirements are documented.
- [ ] Failures identify which stage broke: registry, validation, sample load, or prediction.

    ---

    ## 7. Implementation Notes

    Keep smoke tests focused on system readiness, not exhaustive model quality. Use the smallest viable real artifacts for repeatability.

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
cd ../frontend
npm test -- --runInBand

    ```

    ### Manual verification
    1. Run the documented smoke flow with a univariate pair.
2. Run the multivariate smoke flow if artifacts exist.
3. Confirm failure messages localize the broken stage.

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

    - smoke tests
- smoke setup docs
- artifact prerequisite notes

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
    `hts/hts-109-smoke-real-integration`

    ### Commit message
    `HTS-109: add smoke tests for real benchmark integration`
