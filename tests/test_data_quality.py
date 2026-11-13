"""Spike rejection and clip detection (ticket 06) on hand-made frames.

``find_clipped`` and ``reject_spikes`` are the two steps ``analyse`` runs
before anything else; the frame-level behaviour is tested through ``analyse``
in test_analyse.py.
"""

import numpy as np
import pytest

from denoisifier._data_quality import find_clipped, reject_spikes


def _smooth(shape=(64, 80), base=0.0):
    """A noise-free lit spot with gentle structure: no pixel stands out from
    its column neighbours."""
    rows, cols = shape
    y, x = np.mgrid[0:rows, 0:cols].astype(float)
    spot = np.exp(-0.5 * (((y - rows / 2) / (rows / 4)) ** 2 + ((x - cols / 2) / (cols / 4)) ** 2))
    return base + 100.0 * spot * (1 + 0.3 * np.cos(2 * np.pi * x / 7))


# --- find_clipped -------------------------------------------------------------


def test_a_plateau_at_the_maximum_is_clipped():
    frame = _smooth()
    level = 0.9 * frame.max()
    clipped = np.minimum(frame, level)
    assert np.array_equal(find_clipped(clipped, None), frame >= level)


def test_a_maximum_shared_by_too_few_pixels_is_not_a_plateau():
    frame = _smooth()
    frame[10, 10:13] = frame.max() + 5.0  # three pixels tie at the maximum
    assert not find_clipped(frame, None).any()
    frame[11, 10] = frame.max()  # a fourth
    assert find_clipped(frame, None).sum() == 4


def test_a_constant_frame_is_not_clipped():
    assert not find_clipped(np.full((64, 64), 7.0), None).any()


def test_a_constant_offset_keeps_the_plateau():
    clipped = np.minimum(_smooth(), 80.0)
    expected = find_clipped(clipped, None)
    assert expected.any()
    for shifted in (clipped + 1000.0, clipped - 40.0):
        assert np.array_equal(find_clipped(shifted, None), expected)


def test_a_clip_level_overrides_detection():
    frame = np.minimum(_smooth(), 80.0)
    assert np.array_equal(find_clipped(frame, 60.0), frame >= 60.0)
    assert not find_clipped(frame, np.inf).any()


# --- reject_spikes ------------------------------------------------------------


def test_a_smooth_frame_has_no_spikes():
    frame = _smooth()
    work, spikes = reject_spikes(frame)
    assert not spikes.any()
    assert np.array_equal(work, frame)


def test_bright_single_pixels_and_streaks_are_rejected():
    frame = _smooth()
    excess = 3 * frame.max()
    hits = np.zeros(frame.shape, dtype=bool)
    hits[30, 40] = True  # single pixel
    hits[20:23, 20] = True  # vertical streak of 3
    hits[45, 50:53] = True  # horizontal streak of 3
    hits[[10, 11, 12], [60, 61, 62]] = True  # diagonal streak of 3
    spiked = frame + excess * hits
    before = spiked.copy()
    work, spikes = reject_spikes(spiked)
    assert np.array_equal(spikes, hits)
    assert np.array_equal(spiked, before)  # the input is never modified
    assert np.array_equal(work[~hits], frame[~hits])
    # Each rejected pixel takes a value from its own column, near the true one.
    assert np.all(np.abs(work[hits] - frame[hits]) < 0.2 * frame.max())


@pytest.mark.parametrize("row", [0, 1, 2, 61, 62, 63])
def test_vertical_streaks_at_the_top_and_bottom_edges_are_rejected(row):
    frame = _smooth(base=50.0)
    hits = np.zeros(frame.shape, dtype=bool)
    start = min(row, frame.shape[0] - 3)
    hits[start : start + 3, 40] = True
    _, spikes = reject_spikes(frame + 3 * frame.max() * hits)
    assert np.array_equal(spikes, hits)


def test_saturated_spikes_are_still_spikes():
    """Every pixel is tested, clipped or not: spikes cut off at a clip level
    of twice the scene's maximum still stand out from their columns."""
    frame = _smooth()
    hits = np.zeros(frame.shape, dtype=bool)
    hits[[5, 10, 50, 58], [5, 70, 12, 60]] = True
    level = 2 * frame.max()
    clipped = np.minimum(frame + 5 * frame.max() * hits, level)
    assert np.array_equal(find_clipped(clipped, None), hits)  # they form the plateau
    _, spikes = reject_spikes(clipped)
    assert np.array_equal(spikes, hits)


def test_a_baseline_offset_does_not_change_the_spikes():
    frame = _smooth()
    hits = np.zeros(frame.shape, dtype=bool)
    hits[30, 40] = hits[20:22, 20] = True
    spiked = frame + 3 * frame.max() * hits
    _, expected = reject_spikes(spiked)
    for shifted in (spiked + 1000.0, spiked - frame.max()):
        assert np.array_equal(reject_spikes(shifted)[1], expected)


def test_excess_below_the_scale_of_the_frame_is_not_a_spike():
    """The floor: a pixel must exceed its column neighbours by the frame's
    peak-over-baseline scale, so a narrow bright feature of the scene stays."""
    frame = _smooth()
    frame[30, 40] += 0.5 * frame.max()
    _, spikes = reject_spikes(frame)
    assert not spikes.any()
