# OP-033 — aggregate (Tier-3)

**Status:** [ ] Done
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

- [ ] `backend/app/services/operations/tier3/aggregate.py` with `aggregate(segments, metric, aux)`
- [ ] At least 9 metrics supported out of the box: peak, trough, duration, area, amplitude, period, tau, bfi, sos_eos, m0
- [ ] Metric registry extensible per domain pack (hydrology adds `recession_coefficient`, phenology adds `peak_value`, etc.)
- [ ] Reads from decomposition blob when available (no redundant fitting)
- [ ] Result shape: `dict[segment_id, metric_value]`; metric_value may be None if not applicable
- [ ] **Read-only:** `aggregate` never mutates segments, series, or blobs (asserted by test with frozen dataclass)
- [ ] UI-018 reads the result dict and renders a table
- [ ] Tests cover: each of 9 metrics on appropriate fixture; unknown metric raises; read-only property; None-result for inapplicable metric (e.g. `period` on plateau)
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "OP-033: aggregate (Tier-3) read-only summary metrics"` ← hook auto-moves this file to `done/` on commit
