# OP-031 — align / warp (Tier-3)

**Status:** [x] Done
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

- [x] `backend/app/services/operations/tier3/align_warp.py` with `align_warp(segments, reference_seg, method, warping_band)`
- [x] Three methods selectable: DTW (default), soft-DTW, ShapeDBA
- [x] Warping band constrains DTW by Sakoe-Chiba radius = `warping_band × len(segment)` (default 10 %)
- [x] Compatibility:
  - Cycle, Spike, Transient → ✓ (no warning)
  - Plateau, Trend → ✓ with `approx` warning in audit entry
  - Noise → raises `IncompatibleOp`
- [x] Alignment preserves segment length (target length = reference segment length; edges padded/trimmed as needed)
- [ ] UI-009 populates `reference_seg`, `method`, `warping_band` from pickers — *out of scope for this backend ticket; function signature is ready for UI-009 to wire in*
- [x] Tests cover: DTW alignment on synthetic shifted cycle; soft-DTW differentiability smoke test; ShapeDBA barycenter; noise rejection; plateau/trend warning; band constraint respected
- [x] `tslearn` added to `backend/requirements.txt` — *already at `tslearn>=0.6` from OP-012*
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-031: align/warp Tier-3 (DTW/soft-DTW/ShapeDBA)"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Created `backend/app/services/operations/tier3/align_warp.py` exposing `align_warp(segments, reference_seg, method, warping_band, *, soft_dtw_gamma, event_bus, audit_log) → (list[AlignableSegment], AlignWarpAudit)`. Three methods: hard DTW (`tslearn.metrics.dtw_path` with Sakoe-Chiba radius `int(round(warping_band * len(seg)))`, then `_collapse_path_to_reference` averages segment values per reference index), soft-DTW (`tslearn.metrics.soft_dtw_alignment` row-normalised into soft warp weights with a degenerate-row fallback to nearest-neighbour resampling), and ShapeDBA (`tslearn.barycenters.softdtw_barycenter` of `[ref, seg]` initialised at the reference so output length always matches). All three paths are length-preserving against the reference; tested explicitly across all three methods.

Frozen dataclasses `AlignableSegment` (segment_id / label / values + `with_values` helper) and `AlignWarpAudit` follow the existing `decompose.py` pattern. `IncompatibleOp(ValueError)` lives in this module since no shared exception class existed for "shape label refuses this op". Compatibility table mirrors the ticket: cycle/spike/transient pass cleanly; plateau/trend run but are listed in `audit.approx_segment_ids`; noise raises `IncompatibleOp`. The reference segment is also subjected to the compatibility check — aligning *to* white noise would be just as meaningless as warping noise, and the test suite pins this. Unknown labels are treated as approx and recorded in the audit (deliberate fall-through; would mask typos like "cyle" but matches the ticket's open-vocabulary intent).

Audit emission via DI'd `event_bus` + `audit_log` (defaults from `app.services.events`); audit `extra` carries per-segment costs and the soft_dtw_gamma (None for hard DTW). No `LabelChip` is emitted because alignment doesn't change shape labels — consistent with how OP-030 decompose handles audit. `tslearn>=0.6` was already in `backend/requirements.txt` from OP-012, so no new dependency lands here.

19 new tests in `test_align_warp_tier3.py`: DTW phase-shift correctness (post-warp L2 < pre-warp L2 against the reference), length preservation across all three methods including length asymmetric inputs, soft-DTW + ShapeDBA smoke, noise refusal on both segment AND reference, plateau/trend marked approx, compatible shapes not flagged, band validation (rejects 0/negative/>1), narrow-vs-wide-band produces different warps, unknown method raises `ValueError`, audit emission via `EventBus.subscribe`, empty-segments still emits audit, zero-length reference rejected, `with_values` returns a fresh frozen instance, and frozen-dataclass non-mutation of input segment list across calls. Full backend suite goes from 1852 → 1871 (+19), zero regressions in the other 1852.

**Code-reviewer findings:** APPROVE, 0 blocking. Three non-blocking nits left for future work: (1) the `max(1, …)` floor on the Sakoe-Chiba radius silently overrides `warping_band` for very short segments and the audit doesn't record the *effective* radius; (2) empty `seg.values` (non-reference) silently substitutes a zero-vector with NaN cost rather than rejecting symmetrically with the empty-reference check; (3) `_warp_shapedba` calls `soft_dtw_alignment` a second time just to compute the audit cost — would be cheaper via the scalar `soft_dtw` form for long segments. None of these affect correctness; addressing them would be a small follow-up cleanup ticket if the data ever hits the regimes that surface the issues.
