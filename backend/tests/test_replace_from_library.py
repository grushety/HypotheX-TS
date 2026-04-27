"""Tests for replace_from_library + DonorEngine backends (OP-012)."""

import math

import numpy as np
import pytest

from app.services.operations.tier1.replace_from_library import (
    DiscordDonor,
    DonorCandidate,
    DonorEngine,
    DonorEngineError,
    LibraryOpResult,
    NativeGuide,
    replace_from_library,
    SETSDonor,
)

tslearn = pytest.importorskip("tslearn", reason="tslearn not installed")
stumpy = pytest.importorskip("stumpy", reason="stumpy not installed")


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _seg(n: int = 20, val: float = 0.5) -> np.ndarray:
    return np.full(n, val)


def _trend(n: int = 20) -> list[float]:
    return [i / (n - 1) for i in range(n)]


def _plateau(n: int = 20) -> list[float]:
    return [0.5] * n


def _cycle(n: int = 20) -> list[float]:
    return [math.sin(2 * math.pi * i / 6) for i in range(n)]


def _candidates(n_per_class: int = 5, length: int = 20) -> list[DonorCandidate]:
    cands = []
    for _ in range(n_per_class):
        cands.append(DonorCandidate(label="trend", values=tuple(_trend(length))))
        cands.append(DonorCandidate(label="plateau", values=tuple(_plateau(length))))
        cands.append(DonorCandidate(label="cycle", values=tuple(_cycle(length))))
    return cands


# ---------------------------------------------------------------------------
# DonorCandidate
# ---------------------------------------------------------------------------


def test_donor_candidate_is_frozen():
    c = DonorCandidate(label="trend", values=(1.0, 2.0))
    with pytest.raises((AttributeError, TypeError)):
        c.label = "plateau"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DonorEngine protocol
# ---------------------------------------------------------------------------


def test_native_guide_satisfies_protocol():
    ng = NativeGuide(_candidates())
    assert isinstance(ng, DonorEngine)


def test_sets_donor_satisfies_protocol():
    sd = SETSDonor(_candidates())
    assert isinstance(sd, DonorEngine)


def test_discord_donor_satisfies_protocol():
    corpus = np.random.default_rng(0).standard_normal(200)
    dd = DiscordDonor(corpus)
    assert isinstance(dd, DonorEngine)


# ---------------------------------------------------------------------------
# replace_from_library — crossfade boundary
# ---------------------------------------------------------------------------


class _FixedDonor:
    backend_name = "fixed"

    def __init__(self, donor: np.ndarray) -> None:
        self._donor = donor

    def propose_donor(self, target_segment: np.ndarray, target_class: str) -> np.ndarray:
        return self._donor.copy()


def test_crossfade_first_sample_equals_original():
    X = np.linspace(0.0, 1.0, 30)
    donor_val = np.full(30, 5.0)
    engine = _FixedDonor(donor_val)
    result = replace_from_library(X, engine, "any", crossfade_width=5)
    assert math.isclose(result.values[0], X[0], abs_tol=1e-12)


def test_crossfade_last_sample_equals_original():
    X = np.linspace(0.0, 1.0, 30)
    donor_val = np.full(30, 5.0)
    engine = _FixedDonor(donor_val)
    result = replace_from_library(X, engine, "any", crossfade_width=5)
    assert math.isclose(result.values[-1], X[-1], abs_tol=1e-12)


def test_crossfade_middle_equals_donor():
    X = np.zeros(30)
    donor_val = np.full(30, 9.0)
    engine = _FixedDonor(donor_val)
    result = replace_from_library(X, engine, "any", crossfade_width=5)
    mid = result.values[5:25]
    assert np.allclose(mid, 9.0, atol=1e-12)


def test_crossfade_zero_width_returns_pure_donor():
    X = np.zeros(20)
    donor_val = np.full(20, 7.0)
    engine = _FixedDonor(donor_val)
    result = replace_from_library(X, engine, "any", crossfade_width=0)
    assert np.allclose(result.values, 7.0)


def test_result_has_same_length_as_input():
    X = np.ones(25)
    engine = _FixedDonor(np.zeros(25))
    result = replace_from_library(X, engine, "any", crossfade_width=4)
    assert len(result.values) == 25


# ---------------------------------------------------------------------------
# replace_from_library — length mismatch via interpolation
# ---------------------------------------------------------------------------


def test_donor_length_mismatch_shorter_is_interpolated():
    X = np.ones(30)
    short_donor = np.linspace(0.0, 1.0, 15)
    engine = _FixedDonor(short_donor)
    result = replace_from_library(X, engine, "any", crossfade_width=0)
    assert len(result.values) == 30


def test_donor_length_mismatch_longer_is_interpolated():
    X = np.ones(20)
    long_donor = np.linspace(0.0, 1.0, 40)
    engine = _FixedDonor(long_donor)
    result = replace_from_library(X, engine, "any", crossfade_width=0)
    assert len(result.values) == 20


# ---------------------------------------------------------------------------
# replace_from_library — error handling
# ---------------------------------------------------------------------------


def test_negative_crossfade_raises():
    with pytest.raises(ValueError, match="crossfade_width"):
        replace_from_library(np.ones(20), _FixedDonor(np.ones(20)), "any", crossfade_width=-1)


def test_crossfade_too_large_raises():
    with pytest.raises(ValueError, match="crossfade_width"):
        replace_from_library(np.ones(10), _FixedDonor(np.ones(10)), "any", crossfade_width=5)


# ---------------------------------------------------------------------------
# replace_from_library — relabel
# ---------------------------------------------------------------------------


def test_relabel_is_reclassify_via_segmenter():
    result = replace_from_library(np.ones(20), _FixedDonor(np.ones(20)), "trend", crossfade_width=0)
    assert result.relabel.rule_class == "RECLASSIFY_VIA_SEGMENTER"
    assert result.relabel.needs_resegment is True


def test_result_type_and_metadata():
    result = replace_from_library(np.ones(20), _FixedDonor(np.ones(20)), "trend", crossfade_width=0)
    assert isinstance(result, LibraryOpResult)
    assert result.op_name == "replace_from_library"
    assert result.tier == 1
    assert result.backend == "fixed"


# ---------------------------------------------------------------------------
# NativeGuide
# ---------------------------------------------------------------------------


def test_native_guide_backend_name():
    ng = NativeGuide(_candidates())
    assert ng.backend_name == "NativeGuide"


def test_native_guide_returns_correct_class():
    cands = _candidates(n_per_class=3, length=20)
    ng = NativeGuide(cands)
    query = np.array(_trend(20))
    donor = ng.propose_donor(query, "trend")
    assert len(donor) == 20


def test_native_guide_dtw_selects_closest():
    """NativeGuide should return the plateau candidate (close match) not cycle."""
    plateau_cand = DonorCandidate(label="plateau", values=tuple(_plateau(20)))
    cycle_cand = DonorCandidate(label="plateau", values=tuple(_cycle(20)))
    query = np.array(_plateau(20))
    ng = NativeGuide([plateau_cand, cycle_cand])
    donor = ng.propose_donor(query, "plateau")
    assert np.allclose(donor, np.array(_plateau(20)), atol=1e-10)


def test_native_guide_raises_for_unknown_class():
    ng = NativeGuide(_candidates())
    with pytest.raises(DonorEngineError, match="no training candidates"):
        ng.propose_donor(np.ones(20), "spike")


def test_native_guide_empty_candidates_raises():
    with pytest.raises(DonorEngineError):
        NativeGuide([])


def test_native_guide_result_in_replace_from_library():
    cands = _candidates(n_per_class=3)
    ng = NativeGuide(cands)
    X = np.array(_plateau(20))
    result = replace_from_library(X, ng, "cycle", crossfade_width=3)
    assert isinstance(result, LibraryOpResult)
    assert result.backend == "NativeGuide"
    assert math.isclose(result.values[0], X[0], abs_tol=1e-12)
    assert math.isclose(result.values[-1], X[-1], abs_tol=1e-12)


# ---------------------------------------------------------------------------
# SETSDonor (vendored, no external lib required)
# ---------------------------------------------------------------------------


def test_sets_donor_backend_name():
    sd = SETSDonor(_candidates())
    assert sd.backend_name == "SETSDonor"


def test_sets_donor_discovers_known_classes():
    sd = SETSDonor(_candidates())
    known = set(sd._shapelets.keys())
    assert "trend" in known
    assert "plateau" in known
    assert "cycle" in known


def test_sets_donor_returns_correct_length():
    sd = SETSDonor(_candidates(length=20))
    query = np.array(_trend(20))
    donor = sd.propose_donor(query, "trend")
    assert len(donor) == 20


def test_sets_donor_returns_correct_length_when_query_differs():
    sd = SETSDonor(_candidates(length=20))
    query = np.array(_trend(30))
    donor = sd.propose_donor(query, "plateau")
    assert len(donor) == 30


def test_sets_donor_raises_for_unknown_class():
    sd = SETSDonor(_candidates())
    with pytest.raises(DonorEngineError, match="no shapelet discovered"):
        sd.propose_donor(np.ones(20), "noise")


def test_sets_donor_empty_candidates_raises():
    with pytest.raises(DonorEngineError):
        SETSDonor([])


def test_sets_donor_result_boundary_consistent():
    sd = SETSDonor(_candidates())
    X = np.array(_cycle(20))
    result = replace_from_library(X, sd, "trend", crossfade_width=3)
    assert math.isclose(result.values[0], X[0], abs_tol=1e-12)
    assert math.isclose(result.values[-1], X[-1], abs_tol=1e-12)


def test_sets_donor_custom_shapelet_length():
    sd = SETSDonor(_candidates(length=30), shapelet_length=8)
    donor = sd.propose_donor(np.ones(30), "plateau")
    assert len(donor) == 30


# ---------------------------------------------------------------------------
# DiscordDonor
# ---------------------------------------------------------------------------


def test_discord_donor_backend_name():
    corpus = np.random.default_rng(0).standard_normal(200)
    dd = DiscordDonor(corpus)
    assert dd.backend_name == "DiscordDonor"


def test_discord_donor_returns_correct_length():
    rng = np.random.default_rng(42)
    corpus = rng.standard_normal(200)
    dd = DiscordDonor(corpus)
    query = np.ones(20)
    donor = dd.propose_donor(query, "any_class")
    assert len(donor) == 20


def test_discord_donor_invalid_corpus_raises():
    with pytest.raises(DonorEngineError):
        DiscordDonor(np.array([1.0, 2.0]))


def test_discord_donor_segment_too_large_raises():
    corpus = np.random.default_rng(0).standard_normal(30)
    dd = DiscordDonor(corpus)
    with pytest.raises(DonorEngineError, match="too large"):
        dd.propose_donor(np.ones(20), "any")


def test_discord_donor_boundary_consistent():
    rng = np.random.default_rng(7)
    corpus = rng.standard_normal(300)
    dd = DiscordDonor(corpus)
    X = np.array(_trend(20))
    result = replace_from_library(X, dd, "any", crossfade_width=4)
    assert math.isclose(result.values[0], X[0], abs_tol=1e-12)
    assert math.isclose(result.values[-1], X[-1], abs_tol=1e-12)


def test_discord_donor_result_in_replace_from_library():
    rng = np.random.default_rng(99)
    corpus = rng.standard_normal(400)
    dd = DiscordDonor(corpus)
    X = np.ones(25)
    result = replace_from_library(X, dd, "discord", crossfade_width=5)
    assert isinstance(result, LibraryOpResult)
    assert result.backend == "DiscordDonor"
    assert len(result.values) == 25
