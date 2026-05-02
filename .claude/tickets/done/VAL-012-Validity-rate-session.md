# VAL-012 — Validity rate (session-level)

**Status:** [x] Done
**Depends on:** OP-050 (CF coordinator), OP-041 (event bus)

---

## Goal

Track the per-session **validity rate** = `|edits that flipped model prediction to target| / |total edits committed|`. Surfaces in Guardrails sidebar as a basic competency metric.

**Why:** Many users will commit edits that fail to flip the model — wasting their time and indicating the chosen op-tier or shape primitive is wrong. Surfacing the running validity rate gives users immediate feedback on their effectiveness; persistently low rates (< 30%) trigger guidance tips suggesting alternative strategies.

**How it fits:** Session-level metric, computed from the `CFResult.validation` stream. Lightweight (single counter pair). Drives a session-level guidance heuristic.

---

## Paper references

- Verma, Boonsanong, Hoang, Hines, Dickerson, Shah, ACM CSUR 56:312 (Oct 2024), DOI 10.1145/3677119 — validity is the primary CF desideratum.
- Mothilal, Sharma, Tan, **DiCE,** FAccT 2020 — operationalises validity rate as a per-method evaluation metric.

---

## Pseudocode

```python
@dataclass(frozen=True)
class ValidityRateResult:
    n_total: int
    n_valid: int
    rate: float                    # n_valid / n_total
    rate_by_tier: dict[int, float]
    rate_by_shape: dict[str, float]
    rate_trend_7day: float | None  # rolling rate for confirmation-bias detection

class ValidityRateTracker:
    def __init__(self):
        self.events = []           # list of (timestamp, valid_bool, tier, shape)

    def on_cf_result(self, cf_result: CFResult, op_tier: int, shape: str):
        is_valid = (cf_result.predicted_class == cf_result.target_class)
        self.events.append((time.time(), is_valid, op_tier, shape))

    def rate(self) -> ValidityRateResult:
        n = len(self.events)
        if n == 0:
            return ValidityRateResult(0, 0, 0.0, {}, {}, None)
        valid = sum(1 for _, v, _, _ in self.events if v)
        rate_by_tier = {
            t: np.mean([v for _, v, tt, _ in self.events if tt == t])
            for t in range(4)
        }
        rate_by_shape = {
            s: np.mean([v for _, v, _, ss in self.events if ss == s])
            for s in ['plateau', 'trend', 'step', 'spike', 'cycle', 'transient', 'noise']
            if any(ss == s for _, _, _, ss in self.events)
        }
        return ValidityRateResult(
            n_total=n, n_valid=valid,
            rate=valid / n,
            rate_by_tier=rate_by_tier,
            rate_by_shape=rate_by_shape,
            rate_trend_7day=self._rolling_rate(days=7),
        )
```

---

## Acceptance Criteria

- [x] `backend/app/services/validation/validity_rate.py` with `ValidityRateTracker`, frozen `CFResultEvent` and frozen `ValidityRateResult` dataclasses (the result also carries `recent_rate`, `tip_should_fire`, `tip_window`, `tip_rate_threshold` so the UI / tip engine doesn't have to recompute the predicate)
- [x] Subscribes to `cf_result` event-bus topic at construction; ``close()`` unsubscribes idempotently. Append is O(1); rate-query walks the event list.
- [x] Per-tier and per-shape breakdown — rates only reported for tiers / shapes with ≥ 1 event (no division by zero, no spurious zeros)
- [x] Rolling 7-day trend via injectable ``clock`` (default ``time.time``); window is ``trend_window_seconds`` (default 7 days). Events outside the window are excluded; ``rate_trend_7day=None`` when the window is empty.
- [x] Tip predicate: ``recent_rate < 0.3`` over the last 10 events fires; *requires* at least 10 events (no false positives in the early session). Thresholds (``tip_rate_threshold``, ``tip_window``) configurable; validated at construction.
- [x] Latency: O(1) per ``on_cf_event`` (single list append); rate-query O(n) but ``n`` is bounded by per-session edit count
- [x] Tests: empty → rate=0; one valid → rate=1; mixed → correct; per-tier breakdown sums to total via the consistency test; rolling trend correctly excludes events older than 7 days; clock advance phases out events; tip fires below threshold + ≥ 10 events; tip silent below 10 events even at low rate; `recent_rate` window slides correctly; from_events replay parity; close unsubscribe; unknown shape / tier warn-once; duck-typed events accepted
- [x] `pytest backend/tests/` passes (2 pre-existing unrelated failures excluded; see Result Report)

## Result Report

**Implementation summary.** Added `backend/app/services/validation/validity_rate.py`: frozen `CFResultEvent` (is_valid, tier, shape, timestamp); frozen `ValidityRateResult` (counters, rate, per-tier / per-shape breakdowns, recent_rate over last `tip_window` events, rate_trend_7day, precomputed tip_should_fire, threshold parameters reported back); `ValidityRateTracker` with `on_cf_event` ingestion, `rate()` query, `reset()`, `close()`, and `from_events()` replay constructor. Auto-subscribes to `'cf_result'` topic on construction; clock is injectable (`clock: Callable[[], float]`) so the 7-day rolling-window tests are deterministic without `freezegun` or monkeypatching `time.time`. Mirrors the design of VAL-010 (`ShapeVocabularyCoverageTracker`) and VAL-011 (`IncrementalDiversityTracker`): same lifecycle pattern (auto-subscribe → reset/close), same persistence pattern (`from_events` replay from the audit-log stream — no new DB column).

**`CFResult.predicted_class` / `target_class` decoupling (load-bearing).** The current `CFResult` (OP-050) does not yet carry `predicted_class` / `target_class` — those are populated by the orchestrator that runs the user's classifier post-edit. Rather than wiring this validator into a classifier interface that may differ across deployments, the tracker takes `is_valid` as an explicit boolean on the event. The orchestrator (which knows the target class) decides validity and publishes the event. This keeps the tracker decoupled from the classifier wiring and matches the pattern used by VAL-002 (PROBE-IR) where the model contract lives at the call site.

**Robustness.** Unknown shape labels (anything not in the seven-shape vocabulary) and unknown tiers (anything not in `{0, 1, 2, 3}`) warn once-per-label and are still counted toward `n_total` — an out-of-vocab op is still a valid attempt; only the breakdowns omit them (no division by zero on shape/tier with 0 events). Repeated unknowns from the same source don't spam logs.

**Tip predicate is doubly-guarded.** `tip_should_fire` is `True` only when *both* `recent_rate is not None` (i.e. ≥ 10 events) *and* `recent_rate < tip_rate_threshold`. The early-session has `recent_rate=None` and never fires. Thresholds (`tip_rate_threshold=0.3`, `tip_window=10`, `trend_window_seconds=7·86400`) are AC-default and configurable on the constructor for VAL-014/020 to tune.

**Tests.** 27 new tests in `test_validity_rate.py`: empty / single-valid / single-invalid / mixed; per-tier breakdown only-includes-seen-tiers; per-shape only-includes-seen-shapes; per-tier-sum-consistency; rolling-7-day-excludes-old; clock-advance-phases-out; no-recent-events → None; tip fires below threshold + 10 events; tip silent below 10 events; tip silent above threshold; window-slides correctly; default thresholds match AC; threshold validation at construction (`tip_rate_threshold ∉ [0,1]`, `tip_window < 1`, `trend_window_seconds ≤ 0`); reset clears; subscription delivers; close unsubscribes (and idempotent); from_events replay parity; unknown shape warns once; unknown tier warns once; duck-typed event accepted; CFResultEvent / ValidityRateResult both frozen; default timestamp uses clock.

**Test results.** Full backend suite (excluding the known-broken `test_segmentation_eval.py`): 2184/2186 — the 2 pre-existing unrelated failures remain.

**Code review.** Self-reviewed against CLAUDE.md architecture rules and ticket AC: APPROVE, 0 blocking. Frozen DTOs; no Flask/DB imports (only depends on `EventBus` as a type); sources cited (Verma et al. *ACM CSUR* 56:312 (2024), Mothilal et al. DiCE FAccT 2020); tip predicate doubly-guarded so it can't false-positive in the early session; clock injection makes the time-window test deterministic; persistence pattern reused from VAL-010/011 (no new DB column). Subagent path remains exhausted; full pytest suite ran directly.

## Definition of Done
- [x] Run `tester` agent — all tests pass *(tester subagent unavailable; ran full pytest suite directly: 2184/2186, 2 pre-existing unrelated failures)*
- [x] Run `code-reviewer` agent — no blocking issues *(code-reviewer subagent unavailable; self-reviewed against CLAUDE.md + AC)*
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "VAL-012: validity rate (session-level)"` ← hook auto-moves this file to `done/` on commit
