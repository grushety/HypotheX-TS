# OP-011 — Tier 1 time atoms: time_shift, reverse_time, resample

**Status:** [x] Done
**Depends on:** —

---

## Goal

Implement the three Tier-1 time-axis atoms. Each is label-agnostic and operates on the raw values of the segment (time-axis manipulation does not have a clean decomposition-coefficient analogue).

**Why:** Time-axis manipulation is needed for Cycle `phase_shift`, Step `shift_in_time`, Transient `shift_time` and many other Tier-2 ops. Implementing the atoms once in Tier 1 and composing into Tier 2 keeps the per-shape op code small.

**How it fits:** Called from UI-005 directly as Tier-1 ops, and also used as primitives by OP-022 (Step), OP-023 (Spike), OP-024 (Cycle), OP-025 (Transient).

---

## Paper references (for `algorithm-auditor`)

- Savitzky & Golay (1964) "Smoothing and differentiation of data by simplified least squares procedures" — *Anal. Chem.* 36(8):1627–1639 (resample with SG filter).
- Oppenheim & Schafer (2010) "Discrete-Time Signal Processing" 3rd ed., Ch. 4 (anti-aliasing for decimation).

---

## Pseudocode

```python
def time_shift(X_seg, delta_t: int, taper_width: int = 5):
    if delta_t == 0:
        return X_seg.copy()
    shifted = np.roll(X_seg, delta_t)
    # Taper wrap-around edges to avoid spurious discontinuity
    w = np.linspace(0, 1, taper_width)
    if delta_t > 0:
        shifted[:taper_width] = w * shifted[:taper_width] + (1 - w) * shifted[taper_width]
    else:
        shifted[-taper_width:] = (1 - w) * shifted[-taper_width:] + w * shifted[-taper_width - 1]
    return shifted

def reverse_time(X_seg):
    return X_seg[::-1].copy()

def resample(X_seg, new_dt: float, old_dt: float = 1.0,
             method: Literal['sg', 'linear', 'antialiased'] = 'antialiased'):
    ratio = old_dt / new_dt
    if method == 'antialiased':
        from scipy.signal import decimate, resample_poly
        # Apply low-pass BEFORE subsampling (Oppenheim Ch. 4)
        if ratio < 1:                               # down-sampling
            q = int(round(1 / ratio))
            return decimate(X_seg, q, ftype='fir', zero_phase=True)
        return resample_poly(X_seg, up=int(round(ratio)), down=1)
    elif method == 'sg':
        from scipy.signal import savgol_filter
        smoothed = savgol_filter(X_seg, window_length=11, polyorder=3)
        return np.interp(np.arange(0, len(X_seg), 1 / ratio), np.arange(len(X_seg)), smoothed)
    elif method == 'linear':
        return np.interp(np.arange(0, len(X_seg), 1 / ratio), np.arange(len(X_seg)), X_seg)
```

---

## Acceptance Criteria

- [x] `backend/app/services/operations/tier1/time.py` with `time_shift`, `reverse_time`, `resample`
- [x] `time_shift` preserves series length; edges tapered (taper_width configurable, default 5)
- [x] `reverse_time` is involutive: `reverse_time(reverse_time(X)) == X`
- [x] `resample` supports SG, linear, and antialiased decimation
- [x] Antialiased decimation applies low-pass filter BEFORE subsampling (verified by unit test on synthetic signal with high-frequency component above Nyquist)
- [x] Unit tests assert no aliasing artefacts on test signal `sin(2π·0.4·t)` decimated by 2
- [x] Invalid inputs (negative `new_dt`, unknown method) raise `ValueError`
- [x] Tests cover: time_shift roll + taper; reverse involution; resample ratio < 1 (downsample) and > 1 (upsample); anti-aliasing test; unknown method rejection
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-011: Tier-1 time atoms (time_shift/reverse_time/resample)"` ← hook auto-moves this file to `done/` on commit

## Result Report

`time_shift`, `reverse_time`, `resample` implemented in `backend/app/services/operations/tier1/time.py`. All return `TimeOpResult(values, op_name, relabel=PRESERVED, tier=1)`. `time_shift` uses `np.roll` + configurable linear taper on the wrap-around edge. `reverse_time` is `arr[::-1].copy()` — involutive by construction. `resample` dispatches to three back-ends: `antialiased` (scipy `decimate` FIR LPF before downsampling, `resample_poly` for upsampling), `sg` (Savitzky-Golay smooth + `np.interp`), `linear` (raw `np.interp`). Anti-aliasing test verifies that `sin(2π·0.4·t)` decimated 2× loses >10× energy vs linear path. 35 tests; all pass.
