# VAL-012 — Validity rate (session-level)

**Status:** [ ] Done
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

- [ ] `backend/app/services/validation/validity_rate.py` with `ValidityRateTracker` and `ValidityRateResult` dataclass
- [ ] Subscribes to `cf_result` event bus topic; updates counters incrementally
- [ ] Per-tier and per-shape breakdown (drives "you've struggled with cycle ops — try…" tips)
- [ ] Rolling 7-day trend computed for long-running researchers (confirmation-bias canary)
- [ ] Surfaces in Guardrails sidebar (VAL-014); rate < 0.3 over last 10 edits triggers tip "low CF success rate; consider alternative shape primitive or larger amplitude" (VAL-020)
- [ ] Latency: O(1) per event (incremental counters)
- [ ] Tests: empty tracker → rate=0; one valid edit → rate=1; mixed valid/invalid → correct rate; per-tier breakdown sums to total; rolling trend correctly excludes events older than 7 days
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "VAL-012: validity rate (session-level)"` ← hook auto-moves this file to `done/` on commit
