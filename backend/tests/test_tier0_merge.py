"""Tests for merge tier-0 operation (OP-003)."""
import numpy as np
import pytest

from app.services.operations.relabeler.relabeler import RelabelResult
from app.services.operations.tier0.edit_boundary import InvalidEdit, Segment
from app.services.operations.tier0.merge import merge


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


def flat_series(n: int, value: float = 1.0) -> np.ndarray:
    return np.full(n, value)


def relabeler_returning(shape: str, confidence: float = 0.9):
    """Stub relabeler that always returns the given shape."""
    def _relabeler(*, old_shape, operation, op_params, edited_series):
        return RelabelResult(
            new_shape=shape,
            confidence=confidence,
            needs_resegment=True,
            rule_class="RECLASSIFY_VIA_SEGMENTER",
        )
    return _relabeler


def capturing_relabeler():
    """Stub that records every call; returns 'plateau' with confidence 0.85."""
    calls = []

    def _relabeler(*, old_shape, operation, op_params, edited_series):
        calls.append(
            dict(
                old_shape=old_shape,
                operation=operation,
                op_params=dict(op_params or {}),
                series_length=len(edited_series),
            )
        )
        return RelabelResult(
            new_shape="plateau",
            confidence=0.85,
            needs_resegment=True,
            rule_class="RECLASSIFY_VIA_SEGMENTER",
        )

    _relabeler.calls = calls
    return _relabeler


def three_segs():
    return [
        make_seg("s1", "trend", 0, 9),
        make_seg("s2", "plateau", 10, 19),
        make_seg("s3", "trend", 20, 29),
    ]


# ---------------------------------------------------------------------------
# Successful merges
# ---------------------------------------------------------------------------


def test_merge_reduces_segment_count_by_one():
    segs = three_segs()
    X = flat_series(30)
    result = merge(segs, k=0, X=X, relabeler=relabeler_returning("plateau"))

    assert len(result) == 2


def test_merged_segment_spans_full_range():
    segs = three_segs()
    X = flat_series(30)
    result = merge(segs, k=0, X=X, relabeler=relabeler_returning("plateau"))

    assert result[0].start_index == 0
    assert result[0].end_index == 19


def test_merged_segment_id_combines_both_parents():
    segs = three_segs()
    X = flat_series(30)
    result = merge(segs, k=0, X=X, relabeler=relabeler_returning("plateau"))

    assert result[0].segment_id == "s1+s2"


def test_merged_segment_label_comes_from_relabeler():
    segs = three_segs()
    X = flat_series(30)
    result = merge(segs, k=0, X=X, relabeler=relabeler_returning("trend"))

    assert result[0].label == "trend"


def test_merged_segment_confidence_comes_from_relabeler():
    segs = three_segs()
    X = flat_series(30)
    result = merge(segs, k=0, X=X, relabeler=relabeler_returning("plateau", confidence=0.77))

    assert result[0].confidence == pytest.approx(0.77)


def test_merged_segment_provenance_is_user():
    segs = three_segs()
    X = flat_series(30)
    result = merge(segs, k=0, X=X, relabeler=relabeler_returning("plateau"))

    assert result[0].provenance == "user"


def test_merged_segment_decomposition_dirty():
    segs = three_segs()
    X = flat_series(30)
    result = merge(segs, k=0, X=X, relabeler=relabeler_returning("plateau"))

    assert result[0].decomposition_dirty is True


def test_surrounding_segments_unchanged():
    segs = three_segs()
    X = flat_series(30)
    result = merge(segs, k=0, X=X, relabeler=relabeler_returning("plateau"))

    assert result[1].segment_id == "s3"
    assert result[1].start_index == 20
    assert result[1].end_index == 29


def test_merge_two_plateaus_yields_plateau():
    segs = [
        make_seg("s1", "plateau", 0, 9),
        make_seg("s2", "plateau", 10, 19),
    ]
    X = flat_series(20)
    result = merge(segs, k=0, X=X, relabeler=relabeler_returning("plateau"))

    assert result[0].label == "plateau"


def test_merge_trend_and_plateau_uses_relabeler_not_majority():
    """Relabeler decides the label; merge never does simple majority-vote."""
    segs = [
        make_seg("s1", "trend", 0, 9),
        make_seg("s2", "plateau", 10, 19),
    ]
    X = flat_series(20)
    # Relabeler says "cycle" — must be honoured regardless of source labels
    result = merge(segs, k=0, X=X, relabeler=relabeler_returning("cycle"))

    assert result[0].label == "cycle"


# ---------------------------------------------------------------------------
# Scope inheritance
# ---------------------------------------------------------------------------


def test_scope_inherited_from_left_segment():
    segs = [
        make_seg("s1", "plateau", 0, 9, scope="local"),
        make_seg("s2", "trend", 10, 19, scope="global"),
    ]
    X = flat_series(20)
    result = merge(segs, k=0, X=X, relabeler=relabeler_returning("plateau"))

    assert result[0].scope == "local"


def test_scope_none_when_left_has_no_scope():
    segs = [
        make_seg("s1", "plateau", 0, 9, scope=None),
        make_seg("s2", "trend", 10, 19, scope="global"),
    ]
    X = flat_series(20)
    result = merge(segs, k=0, X=X, relabeler=relabeler_returning("plateau"))

    assert result[0].scope is None


# ---------------------------------------------------------------------------
# Relabeler receives correct arguments
# ---------------------------------------------------------------------------


def test_relabeler_called_with_left_label_as_old_shape():
    rel = capturing_relabeler()
    segs = [
        make_seg("s1", "trend", 0, 9),
        make_seg("s2", "plateau", 10, 19),
    ]
    merge(segs, k=0, X=flat_series(20), relabeler=rel)

    assert rel.calls[0]["old_shape"] == "trend"


def test_relabeler_called_with_operation_merge():
    rel = capturing_relabeler()
    segs = [
        make_seg("s1", "trend", 0, 9),
        make_seg("s2", "plateau", 10, 19),
    ]
    merge(segs, k=0, X=flat_series(20), relabeler=rel)

    assert rel.calls[0]["operation"] == "merge"


def test_relabeler_called_with_right_label_in_op_params():
    rel = capturing_relabeler()
    segs = [
        make_seg("s1", "trend", 0, 9),
        make_seg("s2", "plateau", 10, 19),
    ]
    merge(segs, k=0, X=flat_series(20), relabeler=rel)

    assert rel.calls[0]["op_params"]["neighbour_label"] == "plateau"


def test_relabeler_receives_merged_series_length():
    rel = capturing_relabeler()
    segs = [
        make_seg("s1", "trend", 0, 9),   # 10 samples
        make_seg("s2", "plateau", 10, 19),  # 10 samples
    ]
    merge(segs, k=0, X=flat_series(20), relabeler=rel)

    assert rel.calls[0]["series_length"] == 20


def test_relabeler_called_exactly_once():
    rel = capturing_relabeler()
    segs = [
        make_seg("s1", "trend", 0, 9),
        make_seg("s2", "plateau", 10, 19),
    ]
    merge(segs, k=0, X=flat_series(20), relabeler=rel)

    assert len(rel.calls) == 1


# ---------------------------------------------------------------------------
# Invalid k — raises InvalidEdit
# ---------------------------------------------------------------------------


def test_k_at_last_index_raises():
    segs = three_segs()
    X = flat_series(30)
    with pytest.raises(InvalidEdit, match="no right neighbour"):
        merge(segs, k=2, X=X, relabeler=relabeler_returning("trend"))


def test_k_negative_raises():
    segs = three_segs()
    X = flat_series(30)
    with pytest.raises(InvalidEdit, match="out of range"):
        merge(segs, k=-1, X=X, relabeler=relabeler_returning("trend"))


def test_k_beyond_list_raises():
    segs = three_segs()
    X = flat_series(30)
    with pytest.raises(InvalidEdit, match="out of range"):
        merge(segs, k=10, X=X, relabeler=relabeler_returning("trend"))


def test_single_segment_list_raises():
    segs = [make_seg("s1", "plateau", 0, 9)]
    X = flat_series(10)
    with pytest.raises(InvalidEdit):
        merge(segs, k=0, X=X, relabeler=relabeler_returning("plateau"))


# ---------------------------------------------------------------------------
# No mutation on failure
# ---------------------------------------------------------------------------


def test_original_list_not_mutated_on_invalid_k():
    segs = three_segs()
    X = flat_series(30)
    with pytest.raises(InvalidEdit):
        merge(segs, k=2, X=X, relabeler=relabeler_returning("trend"))

    assert len(segs) == 3
    assert segs[2].segment_id == "s3"


# ---------------------------------------------------------------------------
# Merge at first and last positions
# ---------------------------------------------------------------------------


def test_merge_first_two_segments():
    segs = three_segs()
    X = flat_series(30)
    result = merge(segs, k=0, X=X, relabeler=relabeler_returning("plateau"))

    assert len(result) == 2
    assert result[0].start_index == 0
    assert result[0].end_index == 19
    assert result[1].segment_id == "s3"


def test_merge_last_two_segments():
    segs = three_segs()
    X = flat_series(30)
    result = merge(segs, k=1, X=X, relabeler=relabeler_returning("plateau"))

    assert len(result) == 2
    assert result[0].segment_id == "s1"
    assert result[1].start_index == 10
    assert result[1].end_index == 29
