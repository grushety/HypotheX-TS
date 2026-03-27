
# HTS-102 — Implement model registry and artifact loader

    **Ticket ID:** `HTS-102`  
    **Title:** `Implement model registry and artifact loader`  
    **Status:** `done`  
    **Priority:** `P0`  
    **Type:** `feature`  
    **Depends on:** `HTS-100`  
    **Blocked by:** `none`  
    **Owner:** `Codex`  
    **Branch:** `hts/hts-102-model-registry`

    ---

    ## 1. Goal

    Implement a backend model registry that can enumerate supported trained models and load their artifacts for inference. The registry should treat FCN, MLP, and InceptionTime as first-class model families and should not assume a single checkpoint format without validation.

    ---

    ## 2. Scope

    ### In scope
    - model registry service
- artifact discovery via manifest
- support FCN, MLP, InceptionTime
- artifact validation before load
- centralized error handling

    ### Out of scope
    - training pipelines
- frontend model selector
- dataset-to-model compatibility logic beyond basic manifest checks

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
    - backend/app/services/models.py
- backend/app/schemas/
- backend/tests/
- benchmarks/models/

    ### Architecture layer
    - [ ] frontend
    - [x] backend
    - [ ] API contract
    - [ ] domain logic
    - [x] model/data
    - [x] tests
    - [x] docs

    ### Risk level
    `high`

    ---

    ## 5. Inputs and Expected Outputs

    ### Inputs
    - model manifests
- trained artifact folders
- model family metadata

    ### Expected outputs
    - model registry
- loaded model handles
- standardized model descriptor objects

    ---

    ## 6. Acceptance Criteria

    - [ ] Backend can enumerate supported model artifacts from the manifest.
- [ ] Model descriptors include family, dataset, artifact path, input shape expectations, and label-space info if available.
- [ ] Artifact loading fails fast with explicit errors when paths or required files are missing.
- [ ] Unit tests cover at least one successful artifact resolution path and one failure path.
- [ ] No route handler directly accesses model artifact files.

    ---

    ## 7. Implementation Notes

    Separate registry/discovery from actual inference execution. If artifact formats differ by family, isolate that behind adapters. Do not assume all three model families share the same checkpoint layout.

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
    1. Inspect the listed model registry output.
2. Resolve one FCN artifact and one InceptionTime artifact.
3. Confirm malformed artifact metadata produces a readable failure.

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

    - model registry service
- artifact loader/adapters
- tests for registry resolution and failure modes

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
    `hts/hts-102-model-registry`

    ### Commit message
    `HTS-102: implement model registry and artifact loader`
