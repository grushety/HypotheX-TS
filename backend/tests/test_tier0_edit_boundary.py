"""Tests for edit_boundary tier-0 operation (OP-001)."""
import pytest
from app.services.operations.tier0.edit_boundary import (
    InvalidEdit,
    Segment,
    edit_boundary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_segs(*specs):
    """Build a contiguous list of Segments from (seg_id, label, start, end) tuples."""
    return [
        Segment(segment_id=sid, label=lbl, start_index=b, end_index=e)
        for sid, lbl, b, e in specs
    ]


# ---------------------------------------------------------------------------
# Successful edits
# ---------------------------------------------------------------------------


def test_successful_mid_segment_edit_updates_target_boundaries():
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "plateau", 10, 19),
        ("s3", "trend", 20, 29),
    )
    result = edit_boundary(segs, k=1, delta_b=2, delta_e=-2)

    assert result[1].start_index == 12
    assert result[1].end_index == 17


def test_successful_edit_propagates_to_left_neighbour():
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "plateau", 10, 19),
        ("s3", "trend", 20, 29),
    )
    result = edit_boundary(segs, k=1, delta_b=2, delta_e=-2)

    assert result[0].end_index == 11  # new_b - 1 == 12 - 1


def test_successful_edit_propagates_to_right_neighbour():
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "plateau", 10, 19),
        ("s3", "trend", 20, 29),
    )
    result = edit_boundary(segs, k=1, delta_b=2, delta_e=-2)

    assert result[2].start_index == 18  # new_e + 1 == 17 + 1


def test_propagation_preserves_contiguity_invariant():
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "plateau", 10, 19),
        ("s3", "trend", 20, 29),
    )
    result = edit_boundary(segs, k=1, delta_b=-3, delta_e=3)

    assert result[0].end_index + 1 == result[1].start_index
    assert result[1].end_index + 1 == result[2].start_index


def test_all_affected_segments_marked_dirty():
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "plateau", 10, 19),
        ("s3", "trend", 20, 29),
    )
    result = edit_boundary(segs, k=1, delta_b=1, delta_e=-1)

    assert result[0].decomposition_dirty is True
    assert result[1].decomposition_dirty is True
    assert result[2].decomposition_dirty is True


def test_unaffected_segments_remain_clean():
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "plateau", 10, 19),
        ("s3", "trend", 20, 29),
        ("s4", "event", 30, 39),
    )
    result = edit_boundary(segs, k=1, delta_b=1, delta_e=-1)

    assert result[3].decomposition_dirty is False


def test_original_list_not_mutated_on_success():
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "plateau", 10, 19),
        ("s3", "trend", 20, 29),
    )
    edit_boundary(segs, k=1, delta_b=1, delta_e=-1)

    assert segs[0].end_index == 9
    assert segs[1].start_index == 10
    assert segs[1].end_index == 19
    assert segs[2].start_index == 20


# ---------------------------------------------------------------------------
# L_min violation (transaction rollback)
# ---------------------------------------------------------------------------


def test_l_min_violation_on_target_raises_invalid_edit():
    # seg-2 is length 2 (= minimumSegmentLength); shrinking by 1 should fail.
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "trend", 10, 11),  # length 2
        ("s3", "trend", 12, 20),
    )
    with pytest.raises(InvalidEdit, match="s2"):
        edit_boundary(segs, k=1, delta_b=0, delta_e=-1)


def test_l_min_violation_on_left_neighbour_raises_invalid_edit():
    segs = make_segs(
        ("s1", "trend", 0, 1),  # length 2 (exactly at minimum)
        ("s2", "plateau", 2, 10),
        ("s3", "trend", 11, 20),
    )
    with pytest.raises(InvalidEdit, match="s1"):
        # Moving s2's start left (delta_b=-1) shrinks s1 below L_min=2.
        edit_boundary(segs, k=1, delta_b=-1, delta_e=0)


def test_l_min_violation_does_not_mutate_originals():
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "trend", 10, 11),
        ("s3", "trend", 12, 20),
    )
    with pytest.raises(InvalidEdit):
        edit_boundary(segs, k=1, delta_b=0, delta_e=-1)

    # Frozen dataclass — originals are unchanged.
    assert segs[1].end_index == 11
    assert segs[1].decomposition_dirty is False


def test_event_l_min_enforced():
    # eventMinLength = 3; reducing length below 3 must be rejected.
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "event", 10, 12),  # length 3
        ("s3", "trend", 13, 20),
    )
    with pytest.raises(InvalidEdit):
        edit_boundary(segs, k=1, delta_b=1, delta_e=0)


def test_periodic_l_min_enforced():
    # periodicMinLength = 6; length 6 is at minimum; shrinking should fail.
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "periodic", 10, 15),  # length 6
        ("s3", "trend", 16, 25),
    )
    with pytest.raises(InvalidEdit):
        edit_boundary(segs, k=1, delta_b=1, delta_e=0)


# ---------------------------------------------------------------------------
# Edge cases: first and last segment
# ---------------------------------------------------------------------------


def test_first_segment_edge_no_left_propagation():
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "plateau", 10, 19),
    )
    result = edit_boundary(segs, k=0, delta_b=0, delta_e=2)

    assert result[0].end_index == 11
    assert result[1].start_index == 12
    assert len(result) == 2


def test_last_segment_edge_no_right_propagation():
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "plateau", 10, 19),
    )
    result = edit_boundary(segs, k=1, delta_b=-2, delta_e=0)

    assert result[1].start_index == 8
    assert result[0].end_index == 7
    assert len(result) == 2


def test_first_segment_only_target_and_right_neighbour_dirty():
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "plateau", 10, 19),
    )
    result = edit_boundary(segs, k=0, delta_b=0, delta_e=-2)

    assert result[0].decomposition_dirty is True
    assert result[1].decomposition_dirty is True


def test_last_segment_only_target_and_left_neighbour_dirty():
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "plateau", 10, 19),
    )
    result = edit_boundary(segs, k=1, delta_b=2, delta_e=0)

    assert result[0].decomposition_dirty is True
    assert result[1].decomposition_dirty is True


def test_negative_start_index_raises_invalid_edit():
    segs = make_segs(
        ("s1", "trend", 0, 9),
        ("s2", "plateau", 10, 19),
    )
    with pytest.raises(InvalidEdit, match="start_index"):
        edit_boundary(segs, k=0, delta_b=-1, delta_e=0)


def test_inverted_boundaries_raises_invalid_edit():
    segs = make_segs(("s1", "trend", 5, 5))
    with pytest.raises(InvalidEdit, match="inverted"):
        edit_boundary(segs, k=0, delta_b=2, delta_e=0)


def test_single_segment_no_neighbours():
    segs = make_segs(("s1", "trend", 0, 9))
    result = edit_boundary(segs, k=0, delta_b=2, delta_e=-2)

    assert result[0].start_index == 2
    assert result[0].end_index == 7
    assert result[0].decomposition_dirty is True
    assert len(result) == 1
