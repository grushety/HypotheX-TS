# HypotheX-TS — Implementation Plan

## Purpose

This document translates the current HypotheX-TS design into an implementation plan. It is intentionally one level above engineering tickets: it defines phases, workstreams, dependencies, deliverables, risks, and exit criteria, but does not yet decompose work into individual tasks.

The plan preserves the current project core:

- user-defined semantic segmentation
- typed operations over semantic chunks
- explicit constraint feedback
- a lightweight suggestion model that assists rather than replaces the user

It also follows the current project framing in which formalization comes first, then a minimal prototype, then technical and user evaluation.

## Guiding implementation principles

1. **Build the interaction layer before optimizing the model.** The primary contribution is the semantic interaction design, not raw segmentation accuracy.
2. **Keep the first model simple and auditable.** Use a suggestion model that is easy to inspect and debug. Avoid large end-to-end architectures in the MVP.
3. **Separate formal semantics from learned estimation.** Chunk definitions, operation legality, and constraint checks should exist independently of the learned model.
4. **Treat the model as assistive infrastructure.** The user remains authoritative over boundaries and labels.
5. **Instrument everything from the start.** The system should produce usable logs for both debugging and later user-study analysis.

## Implementation scope for the first complete prototype

The first full prototype should support:

- univariate or small multivariate time series input
- semantic chunk labels for the MVP ontology
- manual boundary editing and reclassification
- split and merge operations
- a small typed operation palette
- soft and hard constraint feedback
- model proposals for chunk boundaries and labels
- interaction logging
- exportable session data
- evaluation scripts for segmentation quality and interaction behavior

The first prototype should **not** aim to solve:

- universal cross-domain segmentation
- full operation-aware learning
- large-scale online model retraining
- perfect counterfactual generation for every domain
- full domain-physics integration beyond a small set of configurable constraints

## Recommended MVP ontology and operation scope

### Semantic chunk types for MVP

Use the four-type core ontology first:

- `trend`
- `plateau`
- `spike`
- `event`

Treat `transition` and `periodic` as deferred extensions unless the pilot data shows they are essential from the start.

This reduces class overlap and lowers annotation noise while preserving the semantic interaction idea.

### MVP operation palette

Support only the operations needed to make the interaction paradigm real:

- `EditBoundary`
- `Split`
- `Merge`
- `Reclassify`
- `ShiftLevel` (plateau)
- `ChangeSlope` (trend)
- `ScaleSpike` / `SuppressSpike` (spike)
- `ShiftEvent` / `RemoveEvent` (event)

All other operations can remain in the formal document but should be marked as phase-2 extensions.

## High-level architecture to implement

Implement the system as four layers:

1. **Formal layer**
   - chunk predicates
   - operation legality table
   - constraint definitions
   - annotation schema

2. **Suggestion layer**
   - boundary proposal
   - chunk scoring/classification
   - uncertainty output
   - lightweight prototype adaptation

3. **Interaction layer**
   - time-series visualization
   - segmentation editing
   - operation palette
   - model-vs-user comparison
   - constraint feedback

4. **Evaluation layer**
   - technical metrics
   - interaction logs
   - replay / analysis scripts
   - user-study-ready telemetry

## Phase 0 — Project setup and alignment

### Goal

Establish a stable implementation foundation before building modules.

### Workstreams

#### 0.1 Repository structure
Set up a monorepo or clearly linked frontend/backend structure.

Recommended layout:

- `frontend/`
- `backend/`
- `model/`
- `evaluation/`
- `data/`
- `schemas/`
- `docs/`

#### 0.2 Shared schemas
Define shared JSON schemas for:

- time series input
- semantic segments
- operations
- constraints
- audit logs
- exported sessions

#### 0.3 Configuration system
Add domain-configurable YAML or JSON files for:

- chunk thresholds
- legal operations per chunk
- hard vs soft constraints
- duration limits
- model parameters

#### 0.4 Development environment
Set up:

- Python environment for backend/model
- React frontend scaffold
- linting / formatting
- local run scripts
- seed datasets and sample sessions

### Deliverables

- running frontend + backend shells
- shared schema definitions
- config files for one starter domain
- local development instructions

### Exit criteria

- a sample series can be loaded end to end
- frontend and backend exchange a mock segmentation
- schemas are stable enough to build against

## Phase 1 — Formal layer implementation

### Goal

Implement the semantic and operational core without depending on learning.

### Workstreams

#### 1.1 Chunk scoring utilities
Implement segment statistics:

- mean
- variance
- linear slope
- sign consistency
- residual-to-line
- context contrast
- peak score

Wrap them as reusable functions over any segment `[b, e]`.

#### 1.2 Chunk scoring and default assignment
Implement score functions `q_y(s)` for each active chunk type.

Use:

- score-based assignment
- ambiguity margin
- optional `uncertain` state for near ties

Avoid brittle hard priority as the only logic.

#### 1.3 Operation legality table
Encode legal operations per chunk type in a machine-readable registry.

Example:

- trend → `ChangeSlope`, `EditBoundary`, `Split`, `Merge`
- plateau → `ShiftLevel`, `EditBoundary`, `Merge`
- spike → `ScaleSpike`, `SuppressSpike`
- event → `ShiftEvent`, `RemoveEvent`

#### 1.4 Constraint library
Implement a first constraint set:

- minimum segment duration
- monotonic trend constraint
- plateau stability constraint
- label compatibility rules

Each constraint should expose:

- `check()`
- `severity` (hard or soft)
- violation description
- optional projection or repair hint

#### 1.5 Annotation schema
Define the canonical segment record:

```json
{
  "start": 10,
  "end": 35,
  "chunk_type": "plateau",
  "confidence": 0.86,
  "provenance": "model",
  "stats": {
    "slope": 0.01,
    "variance": 0.12,
    "peak_score": 0.4
  }
}
```

### Deliverables

- reusable chunk-scoring module
- legality registry
- constraint engine v1
- stable annotation schema

### Exit criteria

- any series can be segmented manually and validated against legality/constraints without a learned model
- all typed operations can be checked against chunk type and constraints

## Phase 2 — Backend interaction core

### Goal

Make the system usable before model assistance becomes sophisticated.

### Workstreams

#### 2.1 Segmentation state manager
Implement backend data structures for:

- segmentation state
- undo / redo
- edit history
- operation application
- validation responses

#### 2.2 Operation engine
Implement deterministic operations over segments and signals.

For MVP, each operation should:

- transform `X` and/or `S`
- return updated state
- invoke constraint engine
- write audit entry

#### 2.3 Constraint feedback API
Create a unified backend response structure:

```json
{
  "status": "WARN",
  "violations": [
    {
      "constraint": "minimum_duration",
      "severity": "hard",
      "message": "Segment would become shorter than 5 steps."
    }
  ]
}
```

#### 2.4 Session logging
Log:

- timestamp
- operation type
- before/after segment boundaries
- constraint result
- model suggestion accepted or overridden
- confidence values

### Deliverables

- working operation engine
- constraint feedback API
- persistent session log format

### Exit criteria

- a user can edit segmentation and receive valid constraint feedback without any learned model
- every interaction is logged cleanly

## Phase 3 — Frontend prototype

### Goal

Build the first usable interactive interface.

### Workstreams

#### 3.1 Time-series viewer
Implement:

- primary chart
- zoom / pan
- minimap
- segment overlay band
- boundary handles

#### 3.2 Segmentation editing UI
Support:

- click/select segment
- drag boundaries
- split at cursor
- merge adjacent segments
- relabel segment

#### 3.3 Operation palette
Show only valid operations for the selected chunk.

If an operation is invalid:

- disable it
- or allow click and show explanatory warning

#### 3.4 Model-vs-user comparison panel
Show:

- model proposal
- current user segmentation
- disagreement highlights
- confidence or uncertainty markers

#### 3.5 Audit and session export
Provide a session panel with:

- chronological action list
- operation outcomes
- download session JSON

### Deliverables

- usable end-to-end MVP UI
- manual semantic segmentation workflow
- typed operation workflow

### Exit criteria

- internal users can complete a semantic editing session without developer intervention
- session export is readable and complete

## Phase 4 — Suggestion model v1

### Goal

Add lightweight, stable model assistance without overcomplicating the architecture.

### Recommended MVP model

Use:

- boundary proposal: ClaSP or equivalent change-point proposal
- segment encoder: small 1D TCN
- chunk classifier: prototype-based head
- adaptation: prototype updates only

Do **not** implement full online fine-tuning or full HSMM first.

### Workstreams

#### 4.1 Boundary proposal integration
Integrate ClaSP or another conservative boundary proposer.

Output:

- candidate boundaries
- boundary confidence or score

#### 4.2 Segment encoder
Implement a small TCN that maps each candidate segment to an embedding.

Important implementation choices:

- fixed-length resampling or attention pooling
- channel normalization
- support for short and long segments

#### 4.3 Prototype classifier
Implement normalized embeddings and cosine or temperature-scaled distance.

Add:

- class prototypes
- confidence estimates
- uncertainty flag for ambiguous segments

#### 4.4 Prototype update strategy
Use:

- confidence-gated updates
- capped memory buffer per class
- periodic recomputation of prototypes

Do not let every correction shift the model immediately.

#### 4.5 Suggestion API
Model outputs should include:

- candidate boundaries
- proposed segments
- label probabilities
- confidence scores
- uncertainty flags

### Deliverables

- model-assisted segmentation proposal
- prototype update pipeline
- suggestion API linked into UI

### Exit criteria

- system proposes usable initial segmentation on at least one target dataset
- user can accept / reject / edit suggestions
- model remains stable over several correction cycles

## Phase 5 — Duration and consistency stabilization

### Goal

Add only the minimum stabilization required after observing failure modes.

### Recommended order

#### 5.1 First add a rule-based duration smoother
Use simple rules:

- merge too-short segments
- suppress isolated jitter segments
- apply class-specific minimum lengths

This should precede a full HSMM.

#### 5.2 Add consistency regularization only if needed
If classifier predictions are unstable under mild variation, add a consistency loss.

#### 5.3 Add full HSMM only if justified
Only introduce an HSMM if:

- label flickering remains significant
- duration heuristics are clearly insufficient
- ablation shows measurable gain

### Deliverables

- duration rule module
- optional consistency training
- decision memo on whether HSMM is warranted

### Exit criteria

- over-segmentation reduced to acceptable level
- stabilization approach chosen based on evidence, not assumption

## Phase 6 — Constraint-aware model refinement

### Goal

Tighten integration between the suggestion model and the legality/constraint layer.

### Workstreams

#### 6.1 Constraint violation metrics
Track for every model proposal:

- violation count
- violation magnitude
- chunk-type-specific invalidity frequency

#### 6.2 Constraint-aware training signal
Add a lightweight penalty if model predictions systematically produce invalid chunk proposals or illegal operation affordances.

This can be as simple as:

- penalty on duration-invalid segments
- penalty on trend labels violating monotonicity
- penalty on plateau labels with high slope

#### 6.3 Operation-aware evaluation
Measure whether model proposals support valid operations without immediate correction.

This is the first concrete step toward your longer-term operation-aware learning claim.

### Deliverables

- violation-aware evaluation scripts
- optional constraint-aware loss term
- report of proposal validity before and after refinement

### Exit criteria

- model proposals are not only accurate, but operationally usable

## Phase 7 — Technical evaluation harness

### Goal

Create a reproducible technical evaluation pipeline before the user study.

### Workstreams

#### 7.1 Dataset preparation
Select one primary domain and one secondary benchmark.

Recommended strategy:

- one semantically clean dataset for pilot development
- one public benchmark for technical reporting

#### 7.2 Evaluation metrics
Implement:

- Segment IoU
- Boundary F1
- Covering
- WARI / SMS
- over-segmentation rate
- prototype drift
- constraint violation rate
- corrections-to-convergence

#### 7.3 Baselines
Prepare at least:

- rule-based segmentation without model adaptation
- model proposal without typed interaction
- simplified raw manipulation baseline for user study planning

#### 7.4 Ablation scripts
Test:

- without prototype updates
- without duration smoothing
- without constraint feedback
- with 4-class vs 6-class ontology

### Deliverables

- reproducible evaluation scripts
- dataset splits
- baseline outputs
- ablation tables

### Exit criteria

- technical results can be regenerated from one command or notebook pipeline
- you can compare components, not just demo them

## Phase 8 — Pilot user-study readiness

### Goal

Prepare the system for internal pilot use before the formal study.

### Workstreams

#### 8.1 Task design
Prepare a small set of what-if tasks with known expected outcomes.

#### 8.2 UI friction test
Run 3–5 internal pilot sessions to detect:

- confusing chunk labels
- invalid operation wording
- unclear constraint messages
- missing undo / rollback support

#### 8.3 Logging validation
Ensure all user actions needed for later analysis are captured.

#### 8.4 Study condition freezing
Freeze the first study conditions:

- baseline raw manipulation
- HypotheX-TS soft constraints
- HypotheX-TS hard constraints

### Deliverables

- pilot protocol
- revised UI labels/messages
- verified log schema for study analysis

### Exit criteria

- pilot users can complete tasks
- logs support the planned interpretation and bias analyses

## Cross-cutting workstreams

These run throughout the phases.

### A. Documentation
Maintain:

- architecture diagrams
- API definitions
- data schemas
- model cards for each version
- reproducibility notes

### B. Data governance
Track:

- data provenance
- label provenance
- manual corrections
- train/validation/test separation

### C. Reproducibility
Each model or rule-set revision should be versioned with:

- config
- code hash
- dataset version
- metric summary

### D. Error review
Create a recurring review loop for:

- ambiguous chunk assignments
- repeated invalid operations
- unstable prototype drift
- user override hotspots

## Suggested implementation order

If you want the smartest low-risk sequence, implement in this order:

1. repository + schemas
2. chunk scoring + legality rules
3. constraint engine
4. operation engine
5. UI for manual segmentation and typed operations
6. logging and export
7. boundary proposal integration
8. TCN encoder + prototype classifier
9. suggestion UI + accept/override flow
10. duration stabilization
11. technical evaluation scripts
12. pilot-study preparation

This order keeps the project valuable even if the learned model underperforms early.

## Definition of success for the first full prototype

The first full prototype is successful if all of the following are true:

1. a user can load a time series and inspect a model proposal
2. the user can edit boundaries and chunk labels
3. the interface exposes typed operations conditioned on chunk type
4. the system gives soft or hard constraint feedback for those operations
5. the model proposal improves the starting point relative to no suggestion
6. all interactions are logged for later analysis
7. technical evaluation can quantify segmentation quality and operational validity

If those conditions are met, the system is already strong enough for a pilot study and for the main CHI/IUI-oriented contribution.

## Main implementation risks and mitigation

### Risk 1 — Chunk ontology confusion
**Mitigation:** start with 4 chunk types, not 6.

### Risk 2 — Model instability
**Mitigation:** prototype-only adaptation first; freeze encoder online.

### Risk 3 — Overengineering too early
**Mitigation:** delay HSMM, online fine-tuning, and operation-aware learning until ablation justifies them.

### Risk 4 — Weak evaluation story
**Mitigation:** build technical evaluation scripts before user study.

### Risk 5 — Interface–model mismatch
**Mitigation:** build manual semantic editing workflow first, then add model assistance.

## What should not be turned into tickets yet

Do not decompose into tickets yet:

- full operation-aware learning
- multi-domain generalization
- large-scale hyperparameter search
- full symbolic CE subspace proofs
- advanced constraint projection algorithms
- every chunk subtype from the formal ontology

These belong after the first usable system exists.

## Immediate next planning artifact after this document

The next document should be a **ticket architecture map**, not individual tickets yet.
That map should group future tickets into epics such as:

- schemas and config
- formal chunk engine
- constraint engine
- operation engine
- frontend interaction
- suggestion model
- evaluation pipeline
- pilot study preparation

That will let you create tickets later without losing the system-level logic.

