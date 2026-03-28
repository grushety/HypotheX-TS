    # HTS-107 — Load real dataset samples into the viewer

    **Ticket ID:** `HTS-107`  
    **Title:** `Load real dataset samples into the viewer`  
    **Status:** `done`  
    **Priority:** `P1`  
    **Type:** `feature`  
    **Depends on:** `HTS-105, HTS-106`  
    **Blocked by:** `none`  
    **Owner:** `Codex`  
    **Branch:** `hts/hts-107-viewer-real-data`

    ---

    ## 1. Goal

    Connect the viewer to real dataset samples from the benchmark backend instead of placeholder or mock data. The viewer should render the selected sample with metadata and remain compatible with existing segmentation overlay behavior.

    ---

    ## 2. Scope

    ### In scope
    - viewer data fetch from selected dataset sample
- support univariate and multivariate sample formatting
- sample metadata display
- preserve existing viewer interactions

    ### Out of scope
    - prediction display
- semantic editing changes
- counterfactual previews

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
    - frontend/src/views/
- frontend/src/components/
- frontend/src/services/api/
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
    - selected dataset/split/sample state
- backend sample data endpoint if needed

    ### Expected outputs
    - viewer renders real benchmark sample data
- sample metadata visible in UI

    ---

    ## 6. Acceptance Criteria

    - [ ] Viewer renders a real selected sample from a supported dataset.
- [ ] Viewer handles both univariate and multivariate sample shapes without crashing.
- [ ] Existing selection or overlay behavior is not broken by the new data source.
- [ ] Frontend tests cover at least one render path with real-shaped sample data.

    ---

    ## 7. Implementation Notes

    If the existing API does not yet expose raw sample values, add only the minimum required endpoint contract in a coordinated way with backend tickets or as a follow-up. Do not regress current viewer interactions.

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
    1. Select GunPoint and render one sample.
2. Select BasicMotions and confirm the viewer handles multivariate shape.
3. Verify existing viewer controls still work.

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

    - viewer integration with real data
- frontend tests
- sample metadata display

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
    `hts/hts-107-viewer-real-data`

    ### Commit message
    `HTS-107: load real dataset samples into the viewer`
