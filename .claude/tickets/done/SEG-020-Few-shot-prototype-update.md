# SEG-020 — Few-shot prototype update from user corrections

**Status:** [x] Done
**Depends on:** SEG-011 (prototype classifier)

---

## Goal

Maintain a per-class bounded-memory support buffer that accumulates accepted user corrections. Every `N` accepted corrections, recompute prototypes, compute drift, and expose the drift metric to the UI (UI-002). Implements the online few-shot adaptation loop without unbounded memory growth or catastrophic drift.

**Why:** Without a bounded buffer, prototypes would be dominated by early (often noisy) corrections or drift uncontrollably over a long session. Without a drift metric, the user and the classifier have no signal when adaptation is going off the rails.

**How it fits:** Sits between `BoundarySuggestionService.accept_correction()` and `SEG-011.fit_prototypes()`. Called after every accepted correction; triggers a prototype recompute every `N_update` corrections (configurable, default 5). Drift metric surfaced by UI-002 alongside uncertainty overlay.

---

## Paper references (for `algorithm-auditor`)

- Snell, Swersky, Zemel (2017) "Prototypical Networks for Few-shot Learning" — *NeurIPS 2017* (prototype update rule).
- Wang, Yao, Kwok, Ni (2020) "Generalizing from a Few Examples: A Survey on Few-Shot Learning" — *ACM Computing Surveys* 53(3):63 (buffer and memory strategies).

---

## Pseudocode

```python
class SupportBuffer:
    def __init__(self, cap_per_class: int = 50, drift_threshold: float = 0.3,
                 n_update: int = 5, confidence_gate: float = 0.7):
        self.buffers: dict[str, deque[SupportSegment]] = {
            y: deque(maxlen=cap_per_class) for y in Y_SHAPE
        }
        self.drift_threshold = drift_threshold
        self.n_update = n_update
        self.confidence_gate = confidence_gate
        self.total_accepted = 0
        self.prototypes: dict[str, np.ndarray] = {}
        self.prev_prototypes: dict[str, np.ndarray] = {}

    def accept_correction(self, segment_X, label, confidence, classifier):
        if confidence < self.confidence_gate:
            return AcceptResult(accepted=False, reason='below_confidence_gate')

        self.buffers[label].append(SupportSegment(X=segment_X, label=label))
        self.total_accepted += 1

        if self.total_accepted % self.n_update == 0:
            self.prev_prototypes = deepcopy(self.prototypes)
            classifier.fit_prototypes(self._flatten_buffers())
            self.prototypes = classifier.prototypes
            drift = self._compute_max_drift()
            return AcceptResult(accepted=True, prototypes_updated=True, drift=drift)
        return AcceptResult(accepted=True, prototypes_updated=False)

    def _compute_max_drift(self) -> float:
        if not self.prev_prototypes:
            return 0.0
        return max(
            np.linalg.norm(self.prototypes[y] - self.prev_prototypes[y])
            for y in self.prototypes if y in self.prev_prototypes
        )
```

---

## Acceptance Criteria

- [x] `backend/app/services/suggestion/support_buffer.py` with:
  - `SupportBuffer` class as above
  - `AcceptResult` frozen dataclass: `accepted`, `reason`, `prototypes_updated`, `drift`
  - Bounded memory per class (default 50, configurable via `SupportBufferConfig`)
- [x] Confidence gate enforced at `accept_correction`; sub-threshold corrections logged but not buffered
- [x] Prototype recompute triggered every `n_update` accepted corrections (default 5)
- [x] Drift metric = `max_y ‖μ_y^new − μ_y^old‖` over classes present in both versions
- [x] Drift exceeding `drift_threshold` logs a warning and emits a drift event consumed by UI-002
- [x] Non-destructive: `prev_prototypes` retained so UI can offer rollback
- [x] Encoder weights frozen online (MVP assumption; documented in docstring)
- [x] Buffer state serializable to/from JSON for session persistence
- [x] Tests cover: confidence gating, buffer cap enforcement (FIFO eviction), trigger frequency, drift computation, rollback via `prev_prototypes`, JSON round-trip
- [x] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "SEG-020: few-shot support buffer with drift tracking"` ← hook auto-moves this file to `done/` on commit

## Result Report

`SupportBuffer` added at `backend/app/services/suggestion/support_buffer.py`. Maintains per-class `deque(maxlen=cap_per_class)` buffers for all 7 shape primitives. `accept_correction()` gates on confidence and label validity, then appends to the deque (FIFO eviction automatic via `deque.maxlen`) and increments `total_accepted`. Every `n_update` accepted corrections it calls `classifier.fit_prototypes(all_support)` and computes drift as `max_y ‖μ_y^new − μ_y^old‖₂`; drift > `drift_threshold` emits a `logging.WARNING`. `prev_prototypes` property exposes a copy of pre-update prototypes for rollback. `to_dict()`/`from_dict()` serialise buffer segments and config; prototype vectors are not persisted (recomputed from segments). 28 new tests; all pass. Exported from `suggestion/__init__.py`.
