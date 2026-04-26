# OP-012 — replace_from_library + DonorEngine interface

**Status:** [ ] Done
**Depends on:** OP-010 (crossfade via scale); UI-008 (donor picker)

---

## Goal

Implement a unified `DonorEngine` protocol and at least three donor backends: **Native Guide** (nearest-unlike-neighbour from training set), **SETS** (shapelet-based composition), **DiscoX** (matrix-profile discord). Optional in follow-up tickets: TimeGAN, ShapeDBA, UserDrawn.

**Why:** `replace_from_library` is the signal-space CF primitive: swap a segment with a realistic donor from another class. This is how Tier-1 reaches the CF-for-classification path without going through decomposition. The DonorEngine interface makes all donor strategies interchangeable via the UI picker (UI-008).

**How it fits:** Tier 1 atom. Called when user clicks "replace with library donor" in UI-005 and picks a backend in UI-008. The selected donor is crossfaded at segment boundaries via OP-010 scale to avoid discontinuity.

---

## Paper references (for `algorithm-auditor`)

- Delaney, Greene, Keane (2021) "Instance-Based Counterfactual Explanations for Time Series Classification" — *ICCBR 2021*. GitHub: `e-delaney/Instance-Based_CFE_TSC`.
- Bahri, Salakka, Anand, Gama (2022) "Shapelet-based Explanations for Time Series" — *AALTD 2022*. GitHub: `omarbahri/SETS`.
- Yeh, Zhu, Ulanova, Begum, Ding, Dau, Silva, Mueen, Keogh (2016) "Matrix Profile I: All Pairs Similarity Joins for Time Series" — *ICDM 2016*. Library: `stumpy`.
- Yoon, Jarrett, van der Schaar (2019) "Time-series Generative Adversarial Networks" — *NeurIPS 2019* (TimeGAN; optional backend).
- Holder, Middlehurst, Bagnall (2023) "ShapeDBA: Generating Effective Time Series Prototypes Using ShapeDTW Barycenter Averaging" — *IDA 2023* (optional backend).

---

## Pseudocode

```python
from typing import Protocol
import numpy as np

class DonorEngine(Protocol):
    def propose_donor(self, target_segment, target_class: str) -> np.ndarray: ...

class NativeGuide:
    def __init__(self, training_set): self.training_set = training_set
    def propose_donor(self, seg, target_class):
        cands = [c for c in self.training_set if c.label == target_class]
        return min(cands, key=lambda c: dtw_distance(seg.X, c.X)).X

class SETSDonor:
    def __init__(self, training_set):
        self.shapelets = discover_shapelets(training_set)
    def propose_donor(self, seg, target_class):
        target_shapelets = [s for s in self.shapelets if s.target_class == target_class]
        return compose_from_shapelets(target_shapelets, template=seg)

class DiscordDonor:
    def __init__(self, training_set_concat):
        self.corpus = training_set_concat
    def propose_donor(self, seg, target_class):
        import stumpy
        mp = stumpy.stump(self.corpus, m=len(seg.X))
        idx = np.argmax(mp[:, 0])                  # max matrix-profile = discord
        return self.corpus[idx : idx + len(seg.X)]

def replace_from_library(X_seg, donor_engine, target_class, crossfade_width=5):
    donor = donor_engine.propose_donor(X_seg, target_class)
    if len(donor) != len(X_seg):
        donor = np.interp(np.linspace(0, len(donor)-1, len(X_seg)),
                          np.arange(len(donor)), donor)
    w = np.ones_like(X_seg)
    w[:crossfade_width]  = np.linspace(0, 1, crossfade_width)
    w[-crossfade_width:] = np.linspace(1, 0, crossfade_width)
    return (1 - w) * X_seg + w * donor
```

---

## Acceptance Criteria

- [ ] `backend/app/services/operations/tier1/replace_from_library.py` with:
  - `DonorEngine` Protocol class
  - `NativeGuide`, `SETSDonor`, `DiscordDonor` concrete implementations
  - `replace_from_library(X_seg, donor_engine, target_class, crossfade_width)` function
- [ ] Crossfade prevents discontinuity at segment boundaries (asserted by unit test: `|X_seg[0] - result[0]| == 0`)
- [ ] Donor picker UI-008 consumes the `DonorEngine` protocol (no backend-specific logic in UI)
- [ ] Each backend uses its cited library (no reimplementation):
  - NativeGuide uses `tslearn.metrics.dtw` or `dtw-python`
  - SETS calls `github.com/omarbahri/SETS` shapelet discovery (vendored if unmaintained)
  - DiscordDonor uses `stumpy.stump`
- [ ] Length mismatch resolved via linear interpolation; documented in docstring
- [ ] Unit tests: for each backend, donor for target class is found and boundary-consistent after crossfade
- [ ] Integration test: full round-trip UI-008 → OP-012 → audit entry emitted
- [ ] `tslearn` and `stumpy` added to `backend/requirements.txt`
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "OP-012: replace_from_library + DonorEngine interface (3 backends)"` ← hook auto-moves this file to `done/` on commit
