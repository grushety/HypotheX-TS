"""Tests for split tier-0 operation (OP-002)."""
import pytest
from app.services.operations.tier0.edit_boundary import InvalidEdit, Segment
from app.services.operations.tier0.split import split


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_seg(sid, label, b, e, *, confidence=None, scope=None, provenance="model"):
    return Segment(
        segment_id=sid,
        label=label,
        start_index=b,
        end_index=e,
        provenance=provenance,
        confidence=confidence,
        scope=scope,
    )


def three_segs():
    return [
        make_seg("s1", "trend", 0, 9),
        make_seg("s2", "plateau", 10, 29),
        make_seg("s3", "trend", 30, 39),
    ]


# ---------------------------------------------------------------------------
# Valid splits
# ---------------------------------------------------------------------------


def test_split_replaces_target_with_two_halves():
    segs = three_segs()
    result = split(segs, k=1, t_star=19)

    assert len(result) == 4
    assert result[1].segment_id == "s2-a"
    assert result[2].segment_id == "s2-b"


def test_left_half_boundaries():
    segs = three_segs()
    result = split(segs, k=1, t_star=19)

    assert result[1].start_index == 10
    assert result[1].end_index == 19


def test_right_half_boundaries():
    segs = three_segs()
    result = split(segs, k=1, t_star=19)

    assert result[2].start_index == 20
    assert result[2].end_index == 29


def test_halves_are_contiguous():
    segs = three_segs()
    result = split(segs, k=1, t_star=19)

    assert result[1].end_index + 1 == result[2].start_index


def test_surrounding_segments_unchanged():
    segs = three_segs()
    result = split(segs, k=1, t_star=19)

    assert result[0].segment_id == "s1"
    assert result[0].start_index == 0
    assert result[0].end_index == 9
    assert result[3].segment_id == "s3"
    assert result[3].start_index == 30
    assert result[3].end_index == 39


def test_halves_inherit_parent_label():
    segs = three_segs()
    result = split(segs, k=1, t_star=19)

    assert result[1].label == "plateau"
    assert result[2].label == "plateau"


def test_halves_provenance_set_to_user():
    segs = three_segs()
    result = split(segs, k=1, t_star=19)

    assert result[1].provenance == "user"
    assert result[2].provenance == "user"


def test_halves_inherit_parent_confidence():
    segs = [make_seg("s1", "trend", 0, 19, confidence=0.85)]
    result = split(segs, k=0, t_star=9)

    assert result[0].confidence == 0.85
    assert result[1].confidence == 0.85


def test_halves_inherit_parent_scope():
    segs = [make_seg("s1", "trend", 0, 19, scope="local")]
    result = split(segs, k=0, t_star=9)

    assert result[0].scope == "local"
    assert result[1].scope == "local"


def test_both_halves_marked_decomposition_dirty():
    segs = three_segs()
    result = split(segs, k=1, t_star=19)

    assert result[1].decomposition_dirty is True
    assert result[2].decomposition_dirty is True


def test_unchanged_segments_not_dirty():
    segs = three_segs()
    result = split(segs, k=1, t_star=19)

    assert result[0].decomposition_dirty is False
    assert result[3].decomposition_dirty is False


# ---------------------------------------------------------------------------
# Boundary split — t_star at b+1 and e-1 (L_min satisfied)
# ---------------------------------------------------------------------------


def test_split_at_b_plus_one_succeeds_when_l_min_satisfied():
    # segment [0,9] length 10; split at 1 → left=[0,1] len=2, right=[2,9] len=8
    segs = [make_seg("s1", "trend", 0, 9)]
    result = split(segs, k=0, t_star=1)

    assert result[0].end_index == 1
    assert result[1].start_index == 2


def test_split_at_e_minus_one_violates_l_min_for_right_half():
    # segment [0,9] split at e-1=8 → right=[9,9] len=1 < L_min=2
    segs = [make_seg("s1", "trend", 0, 9)]
    with pytest.raises(InvalidEdit, match="s1-b"):
        split(segs, k=0, t_star=8)


def test_split_at_e_minus_one_always_violates_l_min_2():
    # right half length = end - t_star = end - (end-1) = 1 < L_min=2 regardless of length
    segs = [make_seg("s1", "trend", 0, 19)]
    with pytest.raises(InvalidEdit, match="s1-b"):
        split(segs, k=0, t_star=18)


def test_split_near_end_succeeds_when_both_halves_above_l_min():
    # segment [0,9] split at 7 → left=[0,7] len=8, right=[8,9] len=2
    segs = [make_seg("s1", "trend", 0, 9)]
    result = split(segs, k=0, t_star=7)

    assert result[0].length == 8
    assert result[1].length == 2


# ---------------------------------------------------------------------------
# Invalid split — t_star outside bounds
# ---------------------------------------------------------------------------


def test_t_star_at_start_index_raises():
    segs = [make_seg("s1", "trend", 0, 9)]
    with pytest.raises(InvalidEdit, match="not strictly inside"):
        split(segs, k=0, t_star=0)


def test_t_star_at_end_index_raises():
    segs = [make_seg("s1", "trend", 0, 9)]
    with pytest.raises(InvalidEdit, match="not strictly inside"):
        split(segs, k=0, t_star=9)


def test_t_star_before_segment_raises():
    segs = [make_seg("s1", "trend", 5, 15)]
    with pytest.raises(InvalidEdit, match="not strictly inside"):
        split(segs, k=0, t_star=3)


def test_t_star_after_segment_raises():
    segs = [make_seg("s1", "trend", 5, 15)]
    with pytest.raises(InvalidEdit, match="not strictly inside"):
        split(segs, k=0, t_star=20)


# ---------------------------------------------------------------------------
# L_min violations
# ---------------------------------------------------------------------------


def test_l_min_violation_on_left_half_raises():
    # split at b+1 on a segment that would make left half length 1
    segs = [make_seg("s1", "trend", 5, 14)]  # length 10
    # t_star=5 is not strictly inside (equals start), so use t_star=6
    # left=[5,6] len=2 OK, right=[7,14] len=8 OK — should succeed
    result = split(segs, k=0, t_star=6)
    assert result[0].length == 2

    # Now trigger left violation: t_star can't be b (= start) — already blocked
    # Use a 3-sample segment: [5,7]; t_star must be 6 → left=[5,6] len=2, right=[7,7] len=1 → fail
    segs2 = [make_seg("s2", "trend", 5, 7)]
    with pytest.raises(InvalidEdit, match="s2-b"):
        split(segs2, k=0, t_star=6)


def test_l_min_violation_on_right_half_raises():
    segs = [make_seg("s1", "trend", 0, 4)]  # length 5
    # t_star=3 → left=[0,3] len=4, right=[4,4] len=1 < L_min=2
    with pytest.raises(InvalidEdit, match="s1-b"):
        split(segs, k=0, t_star=3)


def test_event_l_min_violation_raises():
    # eventMinLength=3; split so one half has length 2
    segs = [make_seg("s1", "event", 0, 7)]  # length 8
    # t_star=1 → left=[0,1] len=2 < L_min=3
    with pytest.raises(InvalidEdit, match="s1-a"):
        split(segs, k=0, t_star=1)


def test_l_min_violation_does_not_mutate_originals():
    segs = [make_seg("s1", "trend", 0, 4)]
    with pytest.raises(InvalidEdit):
        split(segs, k=0, t_star=3)

    assert segs[0].end_index == 4
    assert segs[0].decomposition_dirty is False


# ---------------------------------------------------------------------------
# Split on first / last segment
# ---------------------------------------------------------------------------


def test_split_first_segment():
    segs = three_segs()
    result = split(segs, k=0, t_star=4)

    assert len(result) == 4
    assert result[0].segment_id == "s1-a"
    assert result[0].end_index == 4
    assert result[1].segment_id == "s1-b"
    assert result[1].start_index == 5
    assert result[2].segment_id == "s2"


def test_split_last_segment():
    segs = three_segs()
    result = split(segs, k=2, t_star=34)

    assert len(result) == 4
    assert result[2].segment_id == "s3-a"
    assert result[2].end_index == 34
    assert result[3].segment_id == "s3-b"
    assert result[3].start_index == 35
