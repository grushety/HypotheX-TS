# OP-024 — Cycle Tier-2 ops (7 ops)

**Status:** [ ] Done
**Depends on:** SEG-014 (STL/MSTL blob), OP-040 (relabeler)

---

## Goal

Implement the 7 Cycle-specific Tier-2 ops: `deseasonalise_remove`, `amplify_amplitude`, `dampen_amplitude`, `phase_shift`, `change_period`, `change_harmonic_content`, `replace_with_flat`.

**How it fits:** Gated when active shape is `cycle`. `deseasonalise_remove` → RECLASSIFY (residual-dependent). `replace_with_flat` → DETERMINISTIC(plateau). Others preserve cycle.

---

## Paper references (for `algorithm-auditor`)

- Cleveland et al. (1990) — STL seasonal component editing.
- Bandara et al. (2021) — MSTL.
- Oppenheim & Schafer (2010) Ch. 11 — Hilbert transform for phase shift.
- Verhoef (1996) — HANTS harmonic coefficients (amplitude/phase).

---

## Pseudocode

```python
def deseasonalise_remove(blob):
    S = blob.components['seasonal'].copy() if 'seasonal' in blob.components else \
        sum(v for k, v in blob.components.items() if k.startswith('seasonal_'))
    for k in list(blob.components.keys()):
        if k.startswith('seasonal'): blob.components[k] = np.zeros_like(blob.components[k])
    return blob.reassemble()                                       # → RECLASSIFY

def amplify_amplitude(blob, alpha):
    for k in blob.components:
        if k.startswith('seasonal'): blob.components[k] *= alpha
    return blob.reassemble()                                       # → cycle, or plateau at α=0

def dampen_amplitude(blob, alpha):                                 # alpha in (0, 1)
    return amplify_amplitude(blob, alpha)

def phase_shift(blob, delta_phi: float, period: float | None = None):
    from scipy.signal import hilbert
    for k in blob.components:
        if k.startswith('seasonal'):
            analytic = hilbert(blob.components[k])
            blob.components[k] = np.real(analytic * np.exp(1j * delta_phi))
    return blob.reassemble()

def change_period(blob, beta: float):
    new_T = blob.coefficients['period'] * beta
    for k in list(blob.components.keys()):
        if k.startswith('seasonal'):
            original = blob.components[k]
            blob.components[k] = resample_seasonal(original, blob.coefficients['period'], new_T)
    blob.coefficients['period'] = new_T
    return blob.reassemble()

def change_harmonic_content(blob, coeffs_dict: dict[int, tuple[float, float]]):
    """coeffs_dict: {harmonic_k: (a_k, b_k)}"""
    for k, (a_k, b_k) in coeffs_dict.items():
        set_harmonic(blob, k, a_k, b_k)
    return blob.reassemble()

def replace_with_flat(blob):
    for k in list(blob.components.keys()):
        if k.startswith('seasonal'):
            blob.components[k] = np.zeros_like(blob.components[k])
    return blob.reassemble()                                       # → plateau (DETERMINISTIC)
```

---

## Acceptance Criteria

- [ ] `backend/app/services/operations/tier2/cycle.py` with all 7 ops
- [ ] `phase_shift` offers Hilbert analytic rotation (default) and explicit harmonic rotation (fallback for numerical stability)
- [ ] `deseasonalise_remove` emits OP-040 RECLASSIFY (shape depends on residual)
- [ ] `replace_with_flat` emits OP-040 DETERMINISTIC(plateau)
- [ ] `change_period(β=1)` is identity (asserted by test)
- [ ] Works with both STL (single `seasonal`) and MSTL (multiple `seasonal_T`) blobs
- [ ] Boundary-effect documentation for `phase_shift`: Hilbert edge artifacts tapered
- [ ] Tests cover: amplitude scaling; phase shift by π/2; period change by factor 2; harmonic content edit; deseasonalise round-trip; MSTL multi-period handling
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper references: Cleveland 1990 (STL seasonal edit), Oppenheim Ch. 11 (Hilbert transform), Verhoef 1996 (HANTS harmonics). Confirm phase shift preserves amplitude
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "OP-024: Cycle Tier-2 ops (7 ops)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
