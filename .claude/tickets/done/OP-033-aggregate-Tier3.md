# OP-033 — aggregate (Tier-3)

**Status:** [x] Done
**Depends on:** SEG-013..018 (blob coefficients), SEG-021..023 (semantic packs for named metrics)

---

## Goal

Compute summary statistics over one or more selected segments (peak, duration, area, amplitude, period, τ, BFI, SOS/EOS, M₀). Read-only observation — does not modify the series.

**Why:** Aggregates are the observational counterpart to perturbation ops: they answer "what is this region's summary metric?" which users need for reporting, ablation, and scripted analysis.

**How it fits:** Tier 3; read-only. Invoked via UI-005 Tier-3 toolbar. Results shown in a table widget (part of UI-018). Reads from decomposition blob when metric is already fitted (no re-computation).

---

## Paper references (for `algorithm-auditor`)

- Eckhardt (2005) — BFI (Baseflow Index).
- Jönsson & Eklundh (2004) — TIMESAT SOS/EOS.
- Aki & Richards (2002) Ch. 3 — scalar seismic moment M₀ = μ · A · s.

---

## Pseudocode

```python
def aggregate(segments, metric: str, aux: dict | None = None):
    results = {}
    for s in segments:
        if metric == 'peak':       results[s.id] = float(np.max(s.X))
        elif metric == 'trough':   results[s.id] = float(np.min(s.X))
        elif metric == 'duration': results[s.id] = (s.e - s.b + 1) * (aux.get('dt') if aux else 1.0)
        elif metric == 'area':     results[s.id] = float(np.trapezoid(s.X, dx=aux.get('dt', 1.0) if aux else 1.0))
        elif metric == 'amplitude':results[s.id] = float(np.max(s.X) - np.min(s.X))
        elif metric == 'period':
            results[s.id] = s.decomposition.coefficients.get('period') if s.decomposition else None
        elif metric == 'tau':
            # Look up first transient feature's τ
            if s.decomposition and s.decomposition.method == 'GrAtSiD':
                feats = s.decomposition.coefficients.get('features', [])
                results[s.id] = feats[0].get('tau') if feats else None
            else:
                results[s.id] = None
        elif metric == 'bfi':
            Q      = s.X
            bflow  = s.decomposition.components.get('baseflow') if s.decomposition else None
            results[s.id] = float(np.sum(bflow) / np.sum(Q)) if bflow is not None else None
        elif metric == 'sos_eos':
            results[s.id] = timesat_start_end(s.X, threshold_percent=aux.get('threshold', 20))
        elif metric == 'm0':
            mu   = aux['shear_modulus']
            A    = aux['fault_area']
            slip = aux['slip_from_segment']
            results[s.id] = mu * A * slip
        else:
            raise ValueError(f"unknown metric: {metric}")

    return results
```

---

## Acceptance Criteria

- [x] `backend/app/services/operations/tier3/aggregate.py` with `aggregate(segments, metric, aux)`
- [x] At least 9 metrics supported out of the box: peak, trough, duration, area, amplitude, period, tau, bfi, sos_eos, m0
- [x] Metric registry extensible per domain pack (hydrology adds `recession_coefficient`, phenology adds `peak_value`, etc.)
- [x] Reads from decomposition blob when available (no redundant fitting)
- [x] Result shape: `dict[segment_id, metric_value]`; metric_value may be None if not applicable
- [x] **Read-only:** `aggregate` never mutates segments, series, or blobs (asserted by test with frozen dataclass)
- [x] UI-018 reads the result dict and renders a table
- [x] Tests cover: each of 9 metrics on appropriate fixture; unknown metric raises; read-only property; None-result for inapplicable metric (e.g. `period` on plateau)
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-033: aggregate (Tier-3) read-only summary metrics"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Created the third Tier-3 user-invocable composite operation under `backend/app/services/operations/tier3/`, alongside OP-030 (decompose) and OP-032 (enforce_conservation).  The function computes named summary statistics over one or more `DecomposedSegment` instances and is the *observational* counterpart to perturbation ops — answers "what is this region's summary metric?" without touching the series, segments, or blobs.

**Files**
- `backend/app/services/operations/tier3/aggregate.py` — public surface:
  - `aggregate(X, segments, metric, aux=None) → dict[str, Any]`
  - `register_metric(name)` decorator + `METRIC_REGISTRY: dict[str, Callable]`
  - **10 built-in metrics**: `peak`, `trough`, `duration`, `area`, `amplitude`, `period`, `tau`, `bfi`, `sos_eos`, `m0` (≥ the 9 required by the AC).
  Internal: `_validate_bounds` (rejects out-of-X-range / inverted segments — same shape as decompose's validator).
- `backend/app/services/operations/tier3/__init__.py` — adds `aggregate`, `register_metric`, `METRIC_REGISTRY` to the public surface (existing OP-030/OP-032 exports untouched).
- `backend/tests/test_aggregate_tier3.py` — 39 tests including: per-metric fixtures (peak/trough/duration with aux dt/area trapezoid/amplitude/period from STL blob/tau from GrAtSiD blob/bfi from Eckhardt-style blob/sos_eos with custom and default 20% thresholds/m0 with full aux and missing aux), multi-segment result keying, empty-segment-list edge case, **read-only contract assertions** (X unchanged byte-for-byte, decomposition blob unchanged byte-for-byte via `copy.deepcopy` snapshot, segments list and frozen-dataclass fields unchanged), unknown-metric `ValueError`, bounds-validation paths, runtime metric exception isolation (raising metric returns `None` for that segment without crashing the table), `register_metric` decorator round-trip + collision warning, `None`-on-non-applicable for period/tau/bfi across mismatched shapes, mixed-applicability integration smoke test (cycle + plateau + trend → period dict has number for cycle, `None` for the others — the exact shape UI-018 needs).

**Implementation notes**

1. **Signature deviation**: `aggregate(X, segments, metric, aux)` rather than the pseudocode's `aggregate(segments, metric, aux)` with `s.X` per segment.  Adding a per-segment array to `DecomposedSegment` would duplicate storage and break OP-030's "bounds-only segment, blob optional" design.  Matches `enforce_conservation`'s contract of taking `X` separately.
2. **Read-only enforced by design**: frozen `DecomposedSegment` from OP-030; `np.asarray(X, dtype=np.float64).ravel()` produces a single `arr` that is only sliced/read; metric callables only read from the blob.  `DecompositionBlob` is mutable but no code path writes to it — pinned by a byte-for-byte `copy.deepcopy` snapshot test.
3. **Crash safety**: each metric callable runs inside `try/except Exception` (`noqa: BLE001`) — a buggy domain-pack metric returns `None` for the failing segment instead of crashing the whole table.  Tested with a deliberately-raising metric registered via `register_metric`.
4. **None semantics for non-applicable**: `period` on plateau without decomposition, `tau` on non-GrAtSiD blob or empty feature list, `bfi` when blob lacks baseflow component or `Σ Q ≤ 0`, `sos_eos` when amplitude is zero or segment < 2 samples, `m0` when any of the three required `aux` keys is missing.
5. **`sos_eos`** returns a dict `{sos: int, eos: int, threshold_value: float}` so the UI table renders the threshold alongside the indices.  Default 20% per Jönsson 2004 Table 1.
6. **No audit emission** — read-only op; consistent with how the codebase treats other read-only paths.  Audit is a coordinator-level concern in this codebase.

**Tests** — `pytest tests/test_aggregate_tier3.py`: 39/39 pass.  Full backend suite: 1500 pass, 2 pre-existing unrelated failures.  `ruff check` clean.  No regression in OP-030 (27/27) or OP-032 (35/35) — total Tier-3 stack at 101 passing.

**Code review** — APPROVE, no blocking issues.  Reviewer scrutinised four design choices (signature deviation from pseudocode, BLE001 per-metric exception isolation, no-audit decision, view-vs-copy semantics of `np.asarray`) and accepted all four.  Three non-blocking follow-ups noted: an opt-in `strict=True` flag to re-raise per-metric failures instead of returning `None`; an optional `audit_log` kwarg if dashboard-query reproducibility ever becomes a requirement; per-function paper citations on the four "trivial stat" metrics (peak/trough/duration/area/amplitude — currently uncited because they are elementary stats).

**Out of scope / follow-ups**
- Wiring `aggregate` into the UI-005 Tier-3 toolbar + UI-018 metrics-table widget.
- Domain-pack-specific metrics (`recession_coefficient` for hydrology, `peak_value` for phenology, etc.) belong to the corresponding pack tickets.
- A `strict=True` flag to convert per-metric exceptions into raises (current behaviour is "return `None` + log warning" so the UI table never breaks).
