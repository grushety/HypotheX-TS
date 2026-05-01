"""Tests for the OP-031 align_warp Tier-3 operation."""
from __future__ import annotations

import warnings

import numpy as np
import pytest

from app.services.events import AuditLog, EventBus
from app.services.operations.tier3 import (
    ALIGN_METHODS,
    DEFAULT_WARPING_BAND,
    AlignableSegment,
    AlignWarpAudit,
    IncompatibleOp,
    align_warp,
)

# tslearn warns about an h5py-optional install on import; that is unrelated
# to alignment correctness.
warnings.filterwarnings("ignore", message="h5py not installed")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _isolated_bus() -> tuple[EventBus, AuditLog]:
    return EventBus(), AuditLog()


def _sine(n: int, period: float = 12.0, phase: float = 0.0) -> np.ndarray:
    t = np.arange(n, dtype=np.float64)
    return np.sin(2 * np.pi * t / period + phase)


def _seg(seg_id: str, label: str, values: np.ndarray) -> AlignableSegment:
    return AlignableSegment(segment_id=seg_id, label=label, values=values)


# ---------------------------------------------------------------------------
# DTW path — the AC's primary correctness case
# ---------------------------------------------------------------------------


def test_dtw_aligns_phase_shifted_cycle_to_reference():
    """A cycle that is phase-shifted by ~π/3 should warp closer to its
    in-phase reference than it was before alignment.  (We don't expect a
    perfect match because the segment is a different length than the
    reference; we just need the post-warp series to be measurably closer.)"""
    ref = _sine(40, period=20.0, phase=0.0)
    shifted = _sine(50, period=25.0, phase=np.pi / 3)
    bus, log = _isolated_bus()

    aligned, audit = align_warp(
        [_seg("s1", "cycle", shifted)],
        _seg("ref", "cycle", ref),
        method="dtw",
        warping_band=0.2,
        event_bus=bus,
        audit_log=log,
    )

    assert len(aligned) == 1
    out = aligned[0]
    # Length is preserved against the reference, not the original segment.
    assert out.length == len(ref)
    assert out.segment_id == "s1"
    assert out.label == "cycle"

    # Pre-alignment: compare on a shared index range
    naive_l2 = float(np.linalg.norm(ref - shifted[: len(ref)]))
    aligned_l2 = float(np.linalg.norm(ref - out.values))
    assert aligned_l2 < naive_l2, (
        f"DTW alignment did not reduce L2 distance: pre={naive_l2:.3f}, "
        f"post={aligned_l2:.3f}"
    )

    # Audit was emitted on the isolated bus + log
    assert len(log.records) == 1
    rec = log.records[0]
    assert isinstance(rec, AlignWarpAudit)
    assert rec.method == "dtw"
    assert rec.tier == 3
    assert rec.reference_id == "ref"
    assert rec.segment_ids == ("s1",)
    assert rec.warping_band == pytest.approx(0.2)


def test_dtw_preserves_length_to_reference_for_each_segment():
    ref = _sine(30)
    shorter = _sine(15)
    longer = _sine(60)
    bus, log = _isolated_bus()

    aligned, _ = align_warp(
        [_seg("a", "cycle", shorter), _seg("b", "cycle", longer)],
        _seg("ref", "cycle", ref),
        method="dtw",
        event_bus=bus,
        audit_log=log,
    )
    assert all(s.length == len(ref) for s in aligned)


# ---------------------------------------------------------------------------
# Soft-DTW + ShapeDBA smoke tests
# ---------------------------------------------------------------------------


def test_soft_dtw_smoke_runs_and_preserves_length():
    """Soft-DTW path must run end-to-end and produce a finite, length-equal
    warp.  Differentiability itself is provided by tslearn's implementation;
    here we just verify we wire it correctly."""
    ref = _sine(25, period=10.0)
    seg = _sine(35, period=12.0, phase=0.5)
    bus, log = _isolated_bus()

    aligned, audit = align_warp(
        [_seg("s1", "cycle", seg)],
        _seg("ref", "cycle", ref),
        method="soft_dtw",
        soft_dtw_gamma=0.1,
        event_bus=bus,
        audit_log=log,
    )
    assert aligned[0].length == len(ref)
    assert np.isfinite(aligned[0].values).all()
    assert audit.method == "soft_dtw"
    assert audit.extra["soft_dtw_gamma"] == pytest.approx(0.1)


def test_shapedba_barycenter_length_matches_reference():
    ref = _sine(20)
    seg = _sine(28, phase=0.3)
    bus, log = _isolated_bus()
    aligned, audit = align_warp(
        [_seg("s1", "cycle", seg)],
        _seg("ref", "cycle", ref),
        method="shapedba",
        event_bus=bus,
        audit_log=log,
    )
    assert aligned[0].length == len(ref)
    assert audit.method == "shapedba"


# ---------------------------------------------------------------------------
# Compatibility table (cycle/spike/transient ✓, plateau/trend approx,
# noise refused)
# ---------------------------------------------------------------------------


def test_noise_segment_raises_incompatible_op():
    ref = _sine(20)
    bus, log = _isolated_bus()
    with pytest.raises(IncompatibleOp, match="noise"):
        align_warp(
            [_seg("noise-1", "noise", _sine(20))],
            _seg("ref", "cycle", ref),
            event_bus=bus,
            audit_log=log,
        )
    # Audit must NOT be emitted on a refusal — the op never completes.
    assert len(log.records) == 0


def test_noise_reference_also_raises_incompatible_op():
    """The reference segment is not exempt from the compatibility check —
    aligning *to* white noise has no meaningful interpretation either."""
    bus, log = _isolated_bus()
    with pytest.raises(IncompatibleOp):
        align_warp(
            [_seg("s1", "cycle", _sine(20))],
            _seg("noise-ref", "noise", _sine(20)),
            event_bus=bus,
            audit_log=log,
        )


def test_plateau_segment_marked_approx_in_audit():
    ref = _sine(25)
    plateau = np.full(30, 1.5, dtype=np.float64)
    bus, log = _isolated_bus()

    aligned, audit = align_warp(
        [_seg("flat", "plateau", plateau)],
        _seg("ref", "cycle", ref),
        event_bus=bus,
        audit_log=log,
    )
    assert audit.approx_segment_ids == ("flat",)
    assert aligned[0].length == len(ref)


def test_trend_segment_marked_approx_in_audit():
    ref = _sine(25)
    trend = np.linspace(0, 5, 30)
    bus, log = _isolated_bus()

    _, audit = align_warp(
        [_seg("rising", "trend", trend)],
        _seg("ref", "cycle", ref),
        event_bus=bus,
        audit_log=log,
    )
    assert audit.approx_segment_ids == ("rising",)


def test_cycle_spike_transient_not_flagged_as_approx():
    ref = _sine(20)
    bus, log = _isolated_bus()

    _, audit = align_warp(
        [
            _seg("cy", "cycle", _sine(22)),
            _seg("sp", "spike", _sine(22)),
            _seg("tr", "transient", _sine(22)),
        ],
        _seg("ref", "cycle", ref),
        event_bus=bus,
        audit_log=log,
    )
    assert audit.approx_segment_ids == ()


# ---------------------------------------------------------------------------
# Band constraint
# ---------------------------------------------------------------------------


def test_warping_band_invalid_values_rejected():
    bus, log = _isolated_bus()
    args = (
        [_seg("s1", "cycle", _sine(20))],
        _seg("ref", "cycle", _sine(20)),
    )
    for bad in (0.0, -0.1, 1.5, 2.0):
        with pytest.raises(ValueError, match="warping_band"):
            align_warp(*args, warping_band=bad, event_bus=bus, audit_log=log)


def test_warping_band_default_recorded_in_audit():
    bus, log = _isolated_bus()
    _, audit = align_warp(
        [_seg("s1", "cycle", _sine(20))],
        _seg("ref", "cycle", _sine(20)),
        event_bus=bus,
        audit_log=log,
    )
    assert audit.warping_band == pytest.approx(DEFAULT_WARPING_BAND)


def test_narrow_band_constrains_dtw_path_more_than_wide_band():
    """With a narrow band, the DTW path must stay closer to the diagonal,
    so a heavily phase-shifted segment will warp differently than under a
    wide band.  We assert the two outputs are measurably different."""
    ref = _sine(40, period=12.0)
    shifted = _sine(40, period=12.0, phase=np.pi)
    bus, log = _isolated_bus()

    out_narrow, _ = align_warp(
        [_seg("s1", "cycle", shifted)],
        _seg("ref", "cycle", ref),
        warping_band=0.05,
        event_bus=bus,
        audit_log=log,
    )
    out_wide, _ = align_warp(
        [_seg("s1", "cycle", shifted)],
        _seg("ref", "cycle", ref),
        warping_band=0.9,
        event_bus=bus,
        audit_log=log,
    )
    diff = float(np.linalg.norm(out_narrow[0].values - out_wide[0].values))
    assert diff > 1e-6, "Narrow vs wide band produced byte-identical warps"


# ---------------------------------------------------------------------------
# Method validation
# ---------------------------------------------------------------------------


def test_unknown_method_raises_value_error():
    bus, log = _isolated_bus()
    with pytest.raises(ValueError, match="unknown method"):
        align_warp(
            [_seg("s1", "cycle", _sine(20))],
            _seg("ref", "cycle", _sine(20)),
            method="bogus",  # type: ignore[arg-type]
            event_bus=bus,
            audit_log=log,
        )


def test_all_three_documented_methods_run():
    ref = _sine(20)
    seg = _sine(22, phase=0.4)
    bus, log = _isolated_bus()
    for method in ALIGN_METHODS:
        out, audit = align_warp(
            [_seg("s1", "cycle", seg)],
            _seg("ref", "cycle", ref),
            method=method,
            event_bus=bus,
            audit_log=log,
        )
        assert out[0].length == len(ref), method
        assert audit.method == method


# ---------------------------------------------------------------------------
# Audit emission + event bus
# ---------------------------------------------------------------------------


def test_audit_published_on_event_bus():
    received: list[AlignWarpAudit] = []
    bus, log = _isolated_bus()
    bus.subscribe("align_warp", lambda payload: received.append(payload))

    align_warp(
        [_seg("s1", "cycle", _sine(20))],
        _seg("ref", "cycle", _sine(20)),
        event_bus=bus,
        audit_log=log,
    )
    assert len(received) == 1
    assert received[0].op_name == "align_warp"
    assert received[0].tier == 3


def test_empty_segments_still_emits_audit_with_no_segment_ids():
    bus, log = _isolated_bus()
    out, audit = align_warp(
        [],
        _seg("ref", "cycle", _sine(20)),
        event_bus=bus,
        audit_log=log,
    )
    assert out == []
    assert audit.segment_ids == ()
    assert audit.reference_id == "ref"
    assert len(log.records) == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_zero_length_reference_raises():
    bus, log = _isolated_bus()
    with pytest.raises(ValueError, match="zero length"):
        align_warp(
            [_seg("s1", "cycle", _sine(20))],
            _seg("ref", "cycle", np.array([], dtype=np.float64)),
            event_bus=bus,
            audit_log=log,
        )


def test_with_values_returns_new_alignable_segment():
    s = _seg("s1", "cycle", _sine(20))
    new = s.with_values(np.zeros(20))
    assert new is not s
    assert new.segment_id == "s1"
    assert new.label == "cycle"
    np.testing.assert_array_equal(new.values, np.zeros(20))


def test_input_segment_list_not_mutated():
    """Frozen-dataclass contract: callers should be able to reuse the
    same segment list across calls and see no in-place changes."""
    seg = _seg("s1", "cycle", _sine(20))
    seg_list = [seg]
    bus, log = _isolated_bus()

    align_warp(
        seg_list,
        _seg("ref", "cycle", _sine(15)),
        event_bus=bus,
        audit_log=log,
    )
    assert seg_list[0] is seg
    assert seg_list[0].length == 20  # unchanged
