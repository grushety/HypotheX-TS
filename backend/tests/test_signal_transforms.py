import numpy as np
import pytest

from app.domain.signal_transforms import (
    SignalTransformError,
    change_slope,
    remove_event,
    scale_spike,
    shift_event,
    shift_level,
    suppress_spike,
)


def test_shift_level_changes_only_selected_plateau_region():
    series = np.asarray([0.0, 0.0, 1.0, 1.0, 1.0, 0.0], dtype=np.float64)

    edited = shift_level(series, 2, 4, delta=0.5)

    assert edited.tolist() == [0.0, 0.0, 1.5, 1.5, 1.5, 0.0]


def test_change_slope_preserves_unaffected_regions_and_mean_centers_ramp():
    series = np.asarray([0.0, 1.0, 1.0, 1.0, 1.0, 5.0], dtype=np.float64)

    edited = change_slope(series, 1, 4, slope_delta=0.2)

    assert edited[0] == pytest.approx(0.0)
    assert edited[5] == pytest.approx(5.0)
    assert edited[1:5].tolist() == pytest.approx([0.7, 0.9, 1.1, 1.3])


def test_scale_spike_scales_segment_around_local_mean_only():
    series = np.asarray([0.0, 0.0, 0.0, 5.0, 0.0, 0.0, 0.0], dtype=np.float64)

    edited = scale_spike(series, 2, 4, scale_factor=0.5)

    assert edited.tolist() == pytest.approx([0.0, 0.0, 0.8333333333, 3.3333333333, 0.8333333333, 0.0, 0.0])


def test_suppress_spike_flattens_segment_to_local_mean():
    series = np.asarray([0.0, 0.0, 0.0, 5.0, 0.0, 0.0, 0.0], dtype=np.float64)

    edited = suppress_spike(series, 2, 4)

    assert edited.tolist() == pytest.approx([0.0, 0.0, 1.6666666667, 1.6666666667, 1.6666666667, 0.0, 0.0])


def test_shift_event_retimes_values_within_segment_only():
    series = np.asarray([10.0, 1.0, 2.0, 3.0, 4.0, 20.0], dtype=np.float64)

    edited = shift_event(series, 1, 4, offset=1)

    assert edited.tolist() == pytest.approx([10.0, 1.0, 1.0, 2.0, 3.0, 20.0])


def test_remove_event_interpolates_between_neighbors():
    series = np.asarray([0.0, 10.0, 10.0, 10.0, 20.0], dtype=np.float64)

    edited = remove_event(series, 1, 3)

    assert edited.tolist() == pytest.approx([0.0, 5.0, 10.0, 15.0, 20.0])


def test_remove_event_requires_context_for_full_series_segment():
    series = np.asarray([1.0, 2.0, 3.0], dtype=np.float64)

    with pytest.raises(SignalTransformError, match="spans the entire series"):
        remove_event(series, 0, 2)
