    # HTS-100 — Define benchmark manifest and path contract

    **Ticket ID:** `HTS-100`  
    **Title:** `Define benchmark manifest and path contract`  
    **Status:** `done`  
    **Priority:** `P0`  
    **Type:** `feature`  
    **Depends on:** `HTS-000`  
    **Blocked by:** `none`  
    **Owner:** `Codex`  
    **Branch:** `hts/hts-100-benchmark-manifest`

    ---

    ## 1. Goal

    Create a canonical manifest and path contract for real benchmark datasets and trained model artifacts. This ticket should establish one source of truth for supported datasets, supported model families, artifact locations, and metadata required for later loading and inference.

    ---

    ## 2. Scope

    ### In scope
    - define manifest schema for datasets and models
- add benchmark root/path constants
- document supported datasets: GunPoint, ECG200, Wafer, BasicMotions
- document supported model families: FCN, MLP, InceptionTime
- add example manifest entries

    ### Out of scope
    - actual dataset download automation
- model training
- frontend dataset picker

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
- `HypotheX-TS - Formal Definitions.md`

    ---

    ## 4. Affected Areas

    ### Likely files or modules
    - benchmarks/
- benchmarks/manifests/
- backend/app/config.py
- backend/app/core/paths.py
- docs/

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
    - agreed benchmark root
- supported dataset/model list
- current repo structure

    ### Expected outputs
    - manifest JSON or YAML files
- centralized path constants
- documentation for artifact layout

    ---

    ## 6. Acceptance Criteria

    - [ ] A canonical benchmark manifest exists under the repo and documents dataset and model artifact locations.
- [ ] Supported datasets include GunPoint, ECG200, Wafer, and BasicMotions.
- [ ] Supported model families include FCN, MLP, and InceptionTime.
- [ ] Backend code can read the manifest through a single path/config module.
- [ ] Docs explain where real datasets and trained weights must be placed.

    ---

    ## 7. Implementation Notes

    Use a stable machine-readable manifest such as `benchmarks/manifests/datasets.json` and `benchmarks/manifests/models.json`. Keep path handling centralized. Do not hardcode dataset-specific paths in route handlers or frontend code.

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
pytest -q

    ```

    ### Manual verification
    1. Inspect the created manifest files.
2. Confirm all supported datasets and model families are listed once.
3. Confirm path constants point to the same benchmark root described in docs.

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

    - benchmark manifest files
- central path/config module
- developer docs for benchmark layout

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
    `hts/hts-100-benchmark-manifest`

    ### Commit message
    `HTS-100: define benchmark manifest and path contract`
