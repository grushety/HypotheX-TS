# OP-023 — Spike Tier-2 ops (6 ops)

**Status:** [x] Done
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

(see implementation in spike.py)

---

## Acceptance Criteria

- [x] `backend/app/services/operations/tier2/spike.py` with all 6 ops
- [x] `remove` supports Hampel (default) or Chen SG upper-envelope
- [x] `smear_to_transient` emits OP-040 DETERMINISTIC(transient)
- [x] `clip_cap` winsorizes (replaces above-cap with cap), does not zero out
- [x] `amplify` uses Gaussian window around peak; widening_sigma controls shape retention
- [x] `remove` emits OP-040 RECLASSIFY (residual drives post-op shape)
- [x] Tests cover each op on synthetic spike (z=5σ within plateau); Hampel vs SG comparison; widening preservation in amplify
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-023: Spike Tier-2 ops (6 ops)"` ← hook auto-moves this file to `done/` on commit

## Result Report

63 tests in `test_spike_ops.py`. Reviewer found 1 blocking issue fixed: `shift_time` raised a tier1 taper_width error on near-single-sample spike segments (n < 6) — fixed by capping `taper_width=max(1, min(5, n-1))`. Two test fixture bugs also fixed: widening_sigma test needed non-zero baseline; smear_to_transient pre_shape test corrected to assert DETERMINISTIC always outputs 'transient'. All 63 tests pass.
