# OP-031 — align / warp (Tier-3)

**Status:** [ ] Done
**Depends on:** OP-011 (resample primitive), UI-009 (reference picker + band slider)

---

## Goal

Align one or more segments to a reference segment via DTW, soft-DTW, or ShapeDBA barycenter averaging. Compatible with Cycle, Spike, Transient shapes; Plateau/Trend get an `approx` warning; Noise blocks.

**Why:** Align/warp is a first-class Tier-3 operation in HypotheX-TS: "make this wave look like that wave." No existing interactive CF tool exposes this at the UI surface (typically backend distance-metric only).

**How it fits:** Tier 3; UI-009 picks reference + warping band + method. OP-031 applies the chosen alignment. Result replaces segment values (time-axis warp is not a decomposition edit).

---

## Paper references (for `algorithm-auditor`)

- Sakoe & Chiba (1978) "Dynamic programming algorithm optimization for spoken word recognition" — *IEEE ASSP* 26(1):43–49 (DTW with band constraint).
- Cuturi & Blondel (2017) "Soft-DTW: a differentiable loss function for time-series" — *ICML 2017*. arXiv 1703.01541.
- Petitjean, Ketterlin, Gançarski (2011) "A global averaging method for Dynamic Time Warping, with applications to clustering" — *Pattern Recognition* 44(3):678–693 (DBA).
- Holder, Middlehurst, Bagnall (2023) "ShapeDBA" — *IDA 2023*.
- Library: `tslearn.metrics.dtw`, `tslearn.barycenters.softdtw_barycenter`.

---

## Pseudocode

```python
def align_warp(segments, reference_seg, method: Literal['dtw', 'soft_dtw', 'shapedba'] = 'dtw',
               warping_band: float = 0.1):
    import tslearn.metrics
    import tslearn.barycenters

    aligned = []
    for s in segments:
        if s.label == 'noise':
            raise IncompatibleOp(f"align_warp not applicable to noise segments (id={s.id})")
        if s.label in ('plateau', 'trend'):
            log_warning(f"align_warp on {s.label} segment is approximate")

        if method == 'dtw':
            path, cost = tslearn.metrics.dtw_path(reference_seg.X, s.X,
                                                   sakoe_chiba_radius=int(warping_band * len(s.X)))
            s_aligned = warp_by_path(s.X, path, target_length=len(reference_seg.X))
        elif method == 'soft_dtw':
            s_aligned = softdtw_align(s.X, reference_seg.X, gamma=0.1)
        elif method == 'shapedba':
            barycenter = tslearn.barycenters.softdtw_barycenter([reference_seg.X, s.X])
            s_aligned = barycenter

        aligned.append(s.with_values(s_aligned))

    return aligned
```

---

## Acceptance Criteria

- [ ] `backend/app/services/operations/tier3/align_warp.py` with `align_warp(segments, reference_seg, method, warping_band)`
- [ ] Three methods selectable: DTW (default), soft-DTW, ShapeDBA
- [ ] Warping band constrains DTW by Sakoe-Chiba radius = `warping_band × len(segment)` (default 10 %)
- [ ] Compatibility:
  - Cycle, Spike, Transient → ✓ (no warning)
  - Plateau, Trend → ✓ with `approx` warning in audit entry
  - Noise → raises `IncompatibleOp`
- [ ] Alignment preserves segment length (target length = reference segment length; edges padded/trimmed as needed)
- [ ] UI-009 populates `reference_seg`, `method`, `warping_band` from pickers
- [ ] Tests cover: DTW alignment on synthetic shifted cycle; soft-DTW differentiability smoke test; ShapeDBA barycenter; noise rejection; plateau/trend warning; band constraint respected
- [ ] `tslearn` added to `backend/requirements.txt`
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper references: Sakoe 1978 (DTW band), Cuturi 2017 (soft-DTW γ), Petitjean 2011 (DBA), Holder 2023 (ShapeDBA). Confirm tslearn calls match paper parameter semantics
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "OP-031: align/warp Tier-3 (DTW/soft-DTW/ShapeDBA)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
