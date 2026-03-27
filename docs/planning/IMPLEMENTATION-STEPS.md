# IMPLEMENTATION-STEPS.md

## Purpose

This document defines how HypotheX-TS should be broken into implementation steps before creating Codex tickets.

Order of work for the project:
1. define Codex rules,
2. define implementation steps,
3. convert steps into tickets,
4. debug after ticketed implementation work is complete.

Implementation steps are the bridge between the product idea and executable Codex tickets.
They must be small enough to ticket, but large enough to preserve architectural intent.

---

## 1. What an Implementation Step Is

An implementation step is a scoped build unit that describes one coherent capability or infrastructure change.

A good implementation step:
- has one primary outcome,
- has clear inputs and outputs,
- maps to one architecture layer or a tightly related cross-layer slice,
- can be split into 1–5 tickets,
- has a clear dependency position,
- can be verified.

An implementation step is not:
- a vague milestone,
- a full epic with many unrelated parts,
- a single tiny code edit,
- a debugging task with no defined target behavior.

---

## 2. Step Design Rules

Every implementation step must:
- describe one meaningful capability,
- state why it is needed,
- identify dependencies,
- define the affected modules,
- define what success looks like,
- define what is explicitly out of scope,
- be narrow enough to convert into focused tickets.

Codex should never receive a broad feature area without it first being refined into implementation steps.

---

## 3. Step Granularity Rules

Use these rules to decide whether a step is the right size.

### Too large
A step is too large if it:
- spans many unrelated modules,
- requires multiple independent user workflows,
- mixes infrastructure, UI, model, and study instrumentation without a single core purpose,
- would likely produce more than 5 tickets,
- cannot be verified without finishing several other incomplete systems.

### Too small
A step is too small if it:
- is just one method or one UI control,
- does not create a testable capability,
- exists only because of implementation detail rather than product structure,
- would produce a ticket with no architectural context.

### Good size
A step is the right size if it can become a small ticket cluster with a shared goal.

---

## 4. Required Fields for Each Step

Each implementation step must include:

### Step ID
Use format:
`STEP-XX`

### Step Title
A short, action-oriented name.

### Objective
2–5 sentences describing the capability being added.

### Why it matters
Explain why the step is needed for the HypotheX-TS product or study flow.

### Dependencies
List prerequisite steps or `none`.

### Affected layers
Mark all that apply:
- frontend
- backend
- API contract
- domain logic
- model/data
- tests
- docs

### Inputs
Describe what the step consumes.
Examples:
- raw series data,
- user boundary edit,
- segment label assignment,
- operation request,
- constraint configuration.

### Outputs
Describe what the step produces.
Examples:
- rendered overlay,
- updated segment state,
- validated operation result,
- warning state,
- audit entry.

### In scope
List concrete deliverables.

### Out of scope
List adjacent work that should not be included.

### Success criteria
List observable conditions that prove the step is complete.

### Verification strategy
State how this step will be verified before or during ticket completion.

### Ticket plan
List the expected tickets needed to implement the step.
Prefer 1–5 planned tickets.

---

## 5. Ordering Rules

Implementation steps should be ordered by dependency and product value.

### Default ordering principle
1. core display and state foundations,
2. direct user editing actions,
3. semantic operations,
4. constraint feedback,
5. audit/logging and export,
6. model assistance,
7. advanced controls,
8. study instrumentation and polish.

### Additional ordering rules
- Build visible, testable product slices early.
- Avoid depending on future model sophistication for the basic interaction loop.
- Defer advanced automation until manual workflows are stable.
- Add uncertainty and projection features after the basic semantic operation loop works.

---

## 6. HypotheX-TS Recommended Step Set

Below is the recommended first-pass implementation decomposition for HypotheX-TS.

---

## STEP-01 — Build the time-series viewer and segmentation overlay

### Objective
Create the base interface that displays a time series and shows segment boundaries and labels as an overlay. This is the visual foundation for all later editing and counterfactual interactions.

### Why it matters
Without a stable viewer and overlay, no semantic interaction is possible.

### Dependencies
none

### Affected layers
- frontend
- tests
- docs

### Inputs
- time-series data
- initial segment list
- segment labels

### Outputs
- rendered chart
- visible segment overlay
- selectable segment display state

### In scope
- chart rendering
- segmentation band or overlay
- label display
- active/selected segment state

### Out of scope
- editing boundaries
- changing labels
- counterfactual operations
- constraint logic

### Success criteria
- a time series is displayed correctly
- segment boundaries are visible
- segment labels are visible
- selecting a segment updates UI state predictably

### Verification strategy
frontend tests plus manual UI verification

### Ticket plan
- viewer scaffold
- overlay rendering
- segment selection state
- viewer tests

---

## STEP-02 — Add manual boundary editing and label assignment

### Objective
Enable the user to manually adjust segment boundaries and assign or change semantic labels. This creates the first editable semantic layer.

### Why it matters
User-defined segmentation is central to HypotheX-TS and must exist before semantic operations or alignment analysis.

### Dependencies
STEP-01

### Affected layers
- frontend
- domain logic
- tests
- docs

### Inputs
- existing segments
- user drag/edit actions
- label choices

### Outputs
- updated segment boundaries
- updated labels
- validated edit state

### In scope
- drag/edit shared boundaries
- edit labels
- basic validation
- local state updates

### Out of scope
- model retraining
- disagreement metrics
- operation simulation
- hard constraint blocking

### Success criteria
- users can move valid boundaries
- users can edit labels
- invalid edits are rejected cleanly
- state remains consistent after edits

### Verification strategy
domain tests, frontend tests, manual drag/edit verification

### Ticket plan
- boundary editing logic
- label editing UI
- validation rules
- edit tests

---

## STEP-03 — Implement semantic operations: split, merge, reclassify

### Objective
Implement the first explicit semantic operations on segments: split, merge, and reclassify. These operations should be user-triggered and state-safe.

### Why it matters
These operations form the core interaction language of HypotheX-TS.

### Dependencies
STEP-02

### Affected layers
- frontend
- domain logic
- tests
- docs

### Inputs
- selected segment or adjacent segments
- chosen operation
- operation parameters

### Outputs
- transformed segmentation state
- operation result message
- audit-ready event payload

### In scope
- split operation
- merge operation
- reclassify operation
- operation validation

### Out of scope
- simulation against model prediction
- few-shot adaptation
- hard constraint projection

### Success criteria
- operations can be triggered from the UI
- valid operations update state correctly
- invalid operations fail safely
- resulting segments remain structurally valid

### Verification strategy
domain operation tests, frontend interaction tests, manual verification

### Ticket plan
- operation palette UI
- split logic
- merge logic
- reclassify logic
- operation tests

---

## STEP-04 — Add simulate intervention and counterfactual preview

### Objective
Allow users to preview how a semantic edit or intervention changes the projected counterfactual state. This is the first counterfactual-specific capability.

### Why it matters
The project is not only about editing segmentation, but about exploring what changes would alter model-relevant structure.

### Dependencies
STEP-03

### Affected layers
- frontend
- backend
- domain logic
- API contract
- tests
- docs

### Inputs
- current segmented state
- selected intervention
- operation parameters

### Outputs
- preview state
- comparison view
- counterfactual result object

### In scope
- intervention request flow
- preview rendering
- comparison between current and projected state

### Out of scope
- uncertainty overlays
- alignment metrics
- full model adaptation

### Success criteria
- users can request a preview
- preview result is visible and understandable
- current state and projected state remain distinguishable

### Verification strategy
API tests, domain tests, UI verification, smoke tests

### Ticket plan
- preview API contract
- intervention computation stub/service
- comparison UI
- preview tests

---

## STEP-05 — Add soft constraint feedback and warning states

### Objective
Surface soft constraints as user-visible warnings during semantic edits and interventions.

### Why it matters
Constraint visibility is one of the project’s key design commitments.

### Dependencies
STEP-03

### Affected layers
- frontend
- backend
- domain logic
- tests
- docs

### Inputs
- proposed edit or operation
- current segment state
- constraint rules

### Outputs
- PASS/WARN status
- warning explanations
- constrained operation feedback

### In scope
- constraint checks for relevant operations
- warning display
- non-blocking feedback

### Out of scope
- hard blocking
- projection to nearest valid state
- uncertainty display

### Success criteria
- warnings appear for soft violations
- valid actions still proceed when warnings are non-blocking
- warning messages are tied to the triggered operation

### Verification strategy
constraint tests, UI tests, manual warning-path verification

### Ticket plan
- constraint evaluation layer
- warning UI
- operation-feedback wiring
- warning tests

---

## STEP-06 — Add audit log and interaction export

### Objective
Record meaningful user actions and make the interaction history inspectable and exportable.

### Why it matters
Auditability is part of the product concept and necessary for user-study analysis.

### Dependencies
STEP-03

### Affected layers
- frontend
- backend
- API contract
- tests
- docs

### Inputs
- user edits
- semantic operations
- warnings and previews

### Outputs
- audit entries
- visible interaction log
- export payload

### In scope
- structured event schema
- log panel or history list
- export function

### Out of scope
- advanced analytics dashboards
- full study metric computation

### Success criteria
- key user actions are logged consistently
- users can inspect prior actions
- logs can be exported in a stable format

### Verification strategy
schema tests, integration tests, manual export verification

### Ticket plan
- audit schema
- log capture wiring
- UI history panel
- export feature
- log tests

---

## STEP-07 — Add disagreement view between user and model segmentation

### Objective
Expose the difference between user-defined segmentation and model-generated segmentation in the interface.

### Why it matters
This supports the project’s mental-model and alignment framing.

### Dependencies
STEP-02

### Affected layers
- frontend
- backend
- domain logic
- tests
- docs

### Inputs
- user segmentation
- model segmentation

### Outputs
- disagreement display
- comparison metrics or summaries

### In scope
- fetch or compute model segmentation view
- render disagreement overlay or side-by-side comparison
- basic difference summary

### Out of scope
- full alignment study analysis
- uncertainty estimation

### Success criteria
- users can see where user and model segmentations differ
- disagreement is represented clearly enough to support inspection

### Verification strategy
UI tests, comparison logic tests, manual inspection

### Ticket plan
- disagreement data model
- comparison rendering
- summary component
- disagreement tests

---

## STEP-08 — Add few-shot model adaptation from user corrections

### Objective
Use user edits and labels as few-shot signals to improve or update model segmentation suggestions.

### Why it matters
This connects user-defined segmentation to adaptive system support.

### Dependencies
STEP-02, STEP-07

### Affected layers
- backend
- model/data
- API contract
- tests
- docs

### Inputs
- corrected boundaries
- corrected labels
- previous segmentation state

### Outputs
- updated model suggestions
- adaptation status
- versioned model response

### In scope
- adaptation request path
- model update mechanism or stub
- updated suggestion flow

### Out of scope
- large-scale retraining pipeline
- production optimization

### Success criteria
- corrected user input can trigger adaptation
- adapted suggestions can be retrieved and displayed
- failures are surfaced explicitly

### Verification strategy
backend tests, model adaptation tests or stubs, API tests

### Ticket plan
- adaptation interface
- model update service
- suggestion refresh path
- adaptation tests

---

## STEP-09 — Add hard constraint blocking and projected valid alternatives

### Objective
For certain invalid operations, prevent execution and optionally project the user toward a valid alternative.

### Why it matters
Hard and soft constraint behavior must remain distinct in both logic and UI.

### Dependencies
STEP-05

### Affected layers
- frontend
- backend
- domain logic
- tests
- docs

### Inputs
- invalid operation proposal
- hard constraint rule set

### Outputs
- FAIL state
- blocking message
- optional projected alternative

### In scope
- hard constraint engine path
- blocking UI state
- projected alternative display if defined

### Out of scope
- uncertainty visualization
- advanced optimization over alternatives

### Success criteria
- hard-invalid actions are blocked reliably
- users see clear reasons for the block
- projected alternatives are distinguishable from accepted actions

### Verification strategy
constraint tests, UI tests, manual failure-path verification

### Ticket plan
- hard constraint logic
- blocking UI
- projected alternative support
- hard-constraint tests

---

## STEP-10 — Add uncertainty overlay and study instrumentation

### Objective
Add uncertainty presentation and the instrumentation required for evaluation and user-study analysis.

### Why it matters
This supports the research layer of the project after the core product loop works.

### Dependencies
STEP-04, STEP-06, STEP-07

### Affected layers
- frontend
- backend
- domain logic
- tests
- docs

### Inputs
- model confidence or uncertainty data
- interaction history
- session state

### Outputs
- uncertainty overlay
- study-ready logs or metrics hooks

### In scope
- uncertainty visualization
- instrumentation hooks
- exportable study fields

### Out of scope
- final statistical analysis notebooks
- paper-writing artifacts

### Success criteria
- uncertainty can be displayed without breaking core workflows
- interaction events needed for evaluation are captured reliably

### Verification strategy
integration tests, UI verification, export validation

### Ticket plan
- uncertainty data plumbing
- uncertainty UI
- study metric hooks
- instrumentation tests

---

## 7. Step-to-Ticket Conversion Rules

When converting implementation steps into tickets:
- each ticket must have one clear deliverable,
- keep tickets independently testable,
- group tightly coupled edits only when necessary,
- separate UI work from domain logic work when possible,
- separate contract work from implementation work when useful,
- create follow-up tickets rather than overloading one ticket.

A step should usually produce:
- one setup ticket,
- one or more capability tickets,
- one verification or polish ticket if needed.

---

## 8. MVP Recommendation

For the first usable HypotheX-TS build, prioritize:
- STEP-01
- STEP-02
- STEP-03
- STEP-05
- STEP-06

This yields a product that can:
- show a time series,
- show segments,
- let the user edit segments,
- let the user perform semantic operations,
- surface soft constraints,
- log interactions.

This is likely enough for early internal validation before model adaptation or advanced projection features.

---

## 9. Usage Rules

- Do not create tickets directly from broad ideas.
- First refine broad ideas into implementation steps.
- Do not start debugging from vague symptoms if the related implementation step is not yet defined.
- Revisit the step list whenever architecture or product scope changes.
- Keep implementation steps stable enough that multiple tickets can refer back to them.

---

## 10. Next Artifacts

After this document, the next project outputs should be:
1. the first MVP ticket set,
2. project-specific verification commands,
3. debugging workflow,
4. milestone map from steps to releases or study phases.
