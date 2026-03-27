    # HTS-101 — Implement backend dataset registry and loader

    **Ticket ID:** `HTS-101`  
    **Title:** `Implement backend dataset registry and loader`  
    **Status:** `done`  
    **Priority:** `P0`  
    **Type:** `feature`  
    **Depends on:** `HTS-100`  
    **Blocked by:** `none`  
    **Owner:** `Codex`  
    **Branch:** `hts/hts-101-dataset-registry`

    ---

    ## 1. Goal

    Implement a backend dataset registry that can enumerate supported datasets and load normalized train/test arrays plus metadata from the benchmark root. The loader should support univariate and multivariate datasets without leaking archive-specific logic into the rest of the application.

    ---

    ## 2. Scope

    ### In scope
    - dataset registry service
- load metadata and processed arrays
- support GunPoint, ECG200, Wafer, BasicMotions
- normalize returned dataset descriptor objects
- graceful errors for missing files

    ### Out of scope
    - frontend controls
- model inference
- on-the-fly dataset preprocessing

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
- `HypotheX-TS - Technical Plan.md`

    ---

    ## 4. Affected Areas

    ### Likely files or modules
    - backend/app/services/datasets.py
- backend/app/schemas/
- backend/tests/
- benchmarks/datasets/

    ### Architecture layer
    - [ ] frontend
    - [x] backend
    - [ ] API contract
    - [ ] domain logic
    - [x] model/data
    - [x] tests
    - [x] docs

    ### Risk level
    `medium`

    ---

    ## 5. Inputs and Expected Outputs

    ### Inputs
    - dataset manifests
- processed arrays under benchmarks/datasets/<name>/processed
- dataset metadata

    ### Expected outputs
    - dataset registry API/service object
- loaded numpy arrays or equivalent backend tensors
- standardized dataset summary objects

    ---

    ## 6. Acceptance Criteria

    - [ ] Backend can enumerate all supported datasets from the manifest.
- [ ] Backend can load processed arrays for GunPoint, ECG200, Wafer, and BasicMotions.
- [ ] Returned metadata distinguishes univariate vs. multivariate datasets.
- [ ] Missing or malformed dataset artifacts raise explicit, readable errors.
- [ ] Unit tests cover at least one univariate and one multivariate load path.

    ---

    ## 7. Implementation Notes

    Prefer a service layer plus typed response objects. Keep archive/raw layout concerns out of higher-level application code. The loader should expose split sizes, shape information, class labels if available, and dataset-level notes.

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
    1. Load one univariate dataset through the registry.
2. Load BasicMotions through the registry.
3. Temporarily point to a missing dataset path and confirm the error is explicit.

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

    - dataset registry service
- loader tests
- dataset summary schema

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
    `hts/hts-101-dataset-registry`

    ### Commit message
    `HTS-101: implement backend dataset registry and loader`
