# OP-023 — Spike Tier-2 ops (6 ops)

**Status:** [ ] Done
**Depends on:** OP-010 (scale), OP-011 (shift_time), OP-013 (suppress as remove primitive), OP-040 (relabeler)

---

## Goal

Implement the 6 Spike-specific Tier-2 ops: `remove` (Hampel/Chen-SG), `clip_cap` (winsorize), `amplify`, `smear_to_transient` (Ricker convolution), `duplicate`, `shift_time`.

**How it fits:** Gated when active shape is `spike`. `remove` → RECLASSIFY (residual determines new shape). `smear_to_transient` → DETERMINISTIC(transient). Others preserve spike.

---

## Paper references (for `algorithm-auditor`)

- Hampel (1974) "The influence curve and its role in robust estimation" — *JASA* 69(346):383–393 (Hampel filter).
- Chen, Jönsson, Tamura, Gu, Matsushita, Eklundh (2004) "A simple method for reconstructing a high-quality NDVI time series data set based on the Savitzky–Golay filter" — *Remote Sensing of Environment* 91(3–4):332–344 (SG upper-envelope).
- Ricker (1943) "Further developments in the wavelet theory of seismogram structure" — *BSSA* 33(3):197–228 (Ricker wavelet).

---

## Pseudocode

```python
def remove(X_seg, method: Literal['hampel', 'chen_sg'] = 'hampel'):
    if method == 'hampel':
        return hampel_filter(X_seg, window=7, n_sigma=3)
    elif method == 'chen_sg':
        return chen_upper_envelope_sg(X_seg)

def clip_cap(X_seg, quantile: float = 0.99):
    cap = np.quantile(X_seg, quantile)
    return np.minimum(X_seg, cap)                 # winsorize

def amplify(X_seg, t_peak: int, alpha: float, widening_sigma: float = 2.0):
    w = np.exp(-0.5 * ((np.arange(len(X_seg)) - t_peak) / widening_sigma) ** 2)
    return X_seg + w * (alpha - 1) * X_seg

def smear_to_transient(X_seg, sigma_new: float):
    from scipy.signal import ricker
    kernel = ricker(max(5, int(6 * sigma_new)), sigma_new)
    kernel /= np.sum(kernel)                      # normalize
    from scipy.signal import convolve
    return convolve(X_seg, kernel, mode='same')   # → transient (DETERMINISTIC)

def duplicate(X_seg, t_new: int, alpha: float):
    delta = np.zeros_like(X_seg)
    t_peak = np.argmax(np.abs(X_seg))
    delta[t_new] = alpha * X_seg[t_peak]
    return X_seg + delta                          # multi-spike (may trigger split)

def shift_time(X_seg, delta_t: int):
    from backend.app.services.operations.tier1.time import time_shift
    return time_shift(X_seg, delta_t)
```

---

## Acceptance Criteria

- [ ] `backend/app/services/operations/tier2/spike.py` with all 6 ops
- [ ] `remove` supports Hampel (default) or Chen SG upper-envelope
- [ ] `smear_to_transient` emits OP-040 DETERMINISTIC(transient)
- [ ] `clip_cap` winsorizes (replaces above-cap with cap), does not zero out
- [ ] `amplify` uses Gaussian window around peak; widening_sigma controls shape retention
- [ ] `remove` emits OP-040 RECLASSIFY (residual drives post-op shape)
- [ ] Tests cover each op on synthetic spike (z=5σ within plateau); Hampel vs SG comparison; widening preservation in amplify
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper references: Hampel 1974 (filter formula), Chen 2004 (SG upper-envelope for NDVI). Confirm window and n_sigma defaults match published recommendations
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "OP-023: Spike Tier-2 ops (6 ops)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
