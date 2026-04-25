"""Tests for BoundaryProposer (SEG-009): ClaSP / PELT / BOCPD backends."""

from __future__ import annotations

import math
import numpy as np
import pytest

from app.services.suggestion.boundary_proposer import (
    BoundaryCandidate,
    BoundaryProposer,
    BoundaryProposerConfig,
    _bocpd_change_probs,
    _clasp_profile,
    _find_local_maxima,
    _local_shift_score,
    _normalise_input,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

STEP_SERIES = [0.0] * 20 + [4.0] * 20 + [0.5] * 20  # 60 samples, 2 changes


def _step(n_before: int = 20, n_after: int = 20, lo: float = 0.0, hi: float = 4.0) -> list[float]:
    return [lo] * n_before + [hi] * n_after


# ---------------------------------------------------------------------------
# Input normalisation
# ---------------------------------------------------------------------------


def test_normalise_1d():
    arr = _normalise_input([1.0, 2.0, 3.0])
    assert arr.ndim == 1
    assert len(arr) == 3


def test_normalise_2d_channels_first():
    arr = _normalise_input([[1, 2, 3], [4, 5, 6]])
    assert arr.ndim == 1
    assert len(arr) == 3  # averaged channels → shape (3,)


def test_normalise_2d_time_first():
    # shape (T, C) → transpose to (C, T) then average
    arr = _normalise_input([[1.0, 4.0], [2.0, 5.0], [3.0, 6.0]])
    # (3,2) → T=3,C=2 after transpose: (2,3), mean → (3,)
    assert arr.ndim == 1
    assert len(arr) == 3


def test_normalise_list_of_floats():
    arr = _normalise_input(STEP_SERIES)
    assert arr.ndim == 1
    assert len(arr) == 60


# ---------------------------------------------------------------------------
# BoundaryProposer — empty / short input
# ---------------------------------------------------------------------------


def test_propose_empty_returns_empty():
    proposer = BoundaryProposer()
    assert proposer.propose([]) == []


def test_propose_single_sample_returns_empty():
    proposer = BoundaryProposer()
    assert proposer.propose([1.0]) == []


# ---------------------------------------------------------------------------
# Unknown method raises ValueError
# ---------------------------------------------------------------------------


def test_unknown_method_raises():
    proposer = BoundaryProposer()
    with pytest.raises(ValueError, match="Unknown boundary detection method"):
        proposer.propose([1.0] * 30, method="foobar")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PELT backend
# ---------------------------------------------------------------------------


def test_pelt_detects_two_regimes():
    proposer = BoundaryProposer(BoundaryProposerConfig(method="pelt", min_segment_length=5))
    candidates = proposer.propose(STEP_SERIES)
    assert len(candidates) >= 1
    timestamps = {c.timestamp for c in candidates}
    # Expect boundary near 20 and 40
    assert any(abs(t - 20) <= 2 for t in timestamps), f"No boundary near 20: {timestamps}"
    assert any(abs(t - 40) <= 2 for t in timestamps), f"No boundary near 40: {timestamps}"


def test_pelt_returns_sorted_by_timestamp():
    proposer = BoundaryProposer(BoundaryProposerConfig(method="pelt", min_segment_length=5))
    candidates = proposer.propose(STEP_SERIES)
    timestamps = [c.timestamp for c in candidates]
    assert timestamps == sorted(timestamps)


def test_pelt_respects_min_segment_length():
    min_seg = 10
    proposer = BoundaryProposer(BoundaryProposerConfig(method="pelt", min_segment_length=min_seg))
    candidates = proposer.propose(STEP_SERIES)
    n = len(STEP_SERIES)
    for c in candidates:
        assert c.timestamp >= min_seg
        assert c.timestamp <= n - min_seg


def test_pelt_respects_max_cps():
    proposer = BoundaryProposer(BoundaryProposerConfig(method="pelt", min_segment_length=5))
    candidates = proposer.propose(STEP_SERIES, max_cps=1)
    assert len(candidates) <= 1


def test_pelt_method_field():
    proposer = BoundaryProposer(BoundaryProposerConfig(method="pelt", min_segment_length=5))
    candidates = proposer.propose(_step(), method="pelt")
    assert all(c.method == "pelt" for c in candidates)


def test_pelt_score_in_range():
    proposer = BoundaryProposer(BoundaryProposerConfig(method="pelt", min_segment_length=5))
    candidates = proposer.propose(STEP_SERIES)
    for c in candidates:
        assert 0.0 <= c.score <= 1.0


# ---------------------------------------------------------------------------
# BOCPD backend
# ---------------------------------------------------------------------------


def test_bocpd_detects_regime_change():
    # With hazard_rate=1/15, change prob per step is bounded near the hazard rate;
    # use a sensitive threshold (0.05) so BOCPD can trigger.
    proposer = BoundaryProposer(
        BoundaryProposerConfig(
            method="bocpd", min_segment_length=5,
            bocpd_mean_run_length=15.0, bocpd_threshold=0.05,
        )
    )
    candidates = proposer.propose(_step(25, 25))
    timestamps = {c.timestamp for c in candidates}
    assert any(abs(t - 25) <= 7 for t in timestamps), f"No boundary near 25: {timestamps}"


def test_bocpd_returns_sorted():
    proposer = BoundaryProposer(BoundaryProposerConfig(method="bocpd", min_segment_length=5))
    candidates = proposer.propose(STEP_SERIES)
    timestamps = [c.timestamp for c in candidates]
    assert timestamps == sorted(timestamps)


def test_bocpd_hazard_parameterisation():
    # Shorter mean run length → more sensitive to changes
    long_rl = BoundaryProposer(
        BoundaryProposerConfig(method="bocpd", min_segment_length=3, bocpd_mean_run_length=200.0, bocpd_threshold=0.3)
    )
    short_rl = BoundaryProposer(
        BoundaryProposerConfig(method="bocpd", min_segment_length=3, bocpd_mean_run_length=5.0, bocpd_threshold=0.3)
    )
    series = _step(30, 30)
    long_cands = long_rl.propose(series)
    short_cands = short_rl.propose(series)
    # Shorter run length may find false positives, but must find the real change
    long_ts = {c.timestamp for c in long_cands}
    short_ts = {c.timestamp for c in short_cands}
    assert any(abs(t - 30) <= 5 for t in long_ts | short_ts), (
        f"Neither setting detected boundary near 30: long={long_ts}, short={short_ts}"
    )


def test_bocpd_respects_min_segment_length():
    min_seg = 8
    proposer = BoundaryProposer(
        BoundaryProposerConfig(method="bocpd", min_segment_length=min_seg, bocpd_mean_run_length=10.0)
    )
    series = _step(30, 30)
    n = len(series)
    for c in proposer.propose(series):
        assert c.timestamp >= min_seg
        assert c.timestamp <= n - min_seg


def test_bocpd_change_probs_constant_series():
    arr = np.ones(50)
    probs = _bocpd_change_probs(arr, hazard_rate=0.1)
    assert len(probs) == 50
    # Constant series: change probs should be low after warm-up
    assert float(probs[20:].max()) < 0.5


def test_bocpd_change_probs_step():
    arr = np.array([0.0] * 25 + [5.0] * 25)
    probs = _bocpd_change_probs(arr, hazard_rate=0.05)
    # Peak probability should occur at or near the step
    peak = int(np.argmax(probs))
    assert abs(peak - 25) <= 5, f"BOCPD peak at {peak}, expected near 25"


# ---------------------------------------------------------------------------
# ClaSP backend (numpy fallback — no claspy required)
# ---------------------------------------------------------------------------


def test_clasp_numpy_detects_regime_change():
    proposer = BoundaryProposer(
        BoundaryProposerConfig(method="clasp", min_segment_length=5, clasp_window_len=8)
    )
    # Force numpy fallback by temporarily hiding claspy
    import sys
    original = sys.modules.get("claspy")
    sys.modules["claspy"] = None  # type: ignore[assignment]
    try:
        candidates = proposer.propose(STEP_SERIES)
    finally:
        if original is None:
            sys.modules.pop("claspy", None)
        else:
            sys.modules["claspy"] = original

    # Should find at least one boundary somewhere in the series
    assert len(candidates) >= 1


def test_clasp_profile_shape():
    arr = np.array(STEP_SERIES)
    profile = _clasp_profile(arr, window_len=8, k=3)
    assert profile.shape == (len(arr),)
    assert float(profile.min()) >= 0.0
    assert float(profile.max()) <= 1.0


def test_clasp_profile_peak_near_change():
    arr = np.array(_step(30, 30))
    profile = _clasp_profile(arr, window_len=8, k=3)
    peak = int(np.argmax(profile))
    assert abs(peak - 30) <= 10, f"ClaSP profile peak at {peak}, expected near 30"


# ---------------------------------------------------------------------------
# Candidate output format
# ---------------------------------------------------------------------------


def test_candidates_are_frozen_dataclasses():
    proposer = BoundaryProposer(BoundaryProposerConfig(method="pelt", min_segment_length=5))
    candidates = proposer.propose(_step())
    for c in candidates:
        assert isinstance(c, BoundaryCandidate)
        with pytest.raises((AttributeError, TypeError)):
            c.timestamp = 0  # type: ignore[misc]


def test_candidates_timestamps_are_ints():
    proposer = BoundaryProposer(BoundaryProposerConfig(method="pelt", min_segment_length=5))
    for c in proposer.propose(_step()):
        assert isinstance(c.timestamp, int)


# ---------------------------------------------------------------------------
# Local-shift score helper
# ---------------------------------------------------------------------------


def test_local_shift_score_large_at_step():
    arr = np.array(_step(20, 20, lo=0.0, hi=4.0))
    score = _local_shift_score(arr, t=20, window=5)
    assert score > 0.3


def test_local_shift_score_zero_for_flat():
    arr = np.ones(40)
    score = _local_shift_score(arr, t=20, window=5)
    assert score == 0.0
