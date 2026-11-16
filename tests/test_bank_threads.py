"""The bank's threads across Periods (ticket 13 slice 4): the result does not depend on the thread
count, and the private thread knob refuses bad values.

The frame is a fixed, seed-free broadband pattern (no generated frame)."""

import numpy as np
import pytest

from denoisifier import BinFactors
from denoisifier._local_stripes import _THREADS_ENV, estimate_local_stripes


def _broadband(shape=(120, 260)):
    rows, cols = np.mgrid[0 : shape[0], 0 : shape[1]].astype(float)
    pattern = np.sin(0.37 * rows * cols + 0.11 * rows) + np.cos(1.9 * cols + 0.013 * rows**2)
    stripes = 0.8 * np.cos(2 * np.pi * (cols * 0.98 + rows * 0.17) / 4.5)
    return 10.0 + pattern + stripes + 0.5 * np.sin(2.9 * rows)


def test_threaded_bank_is_bit_identical_to_serial():
    frame = _broadband()
    light = np.ones(frame.shape, bool)
    serial = estimate_local_stripes(frame, light, BinFactors(), threads=1)
    for threads in (2, 4, 16):
        threaded = estimate_local_stripes(frame, light, BinFactors(), threads=threads)
        for field in ("ratio", "period", "angle_deg", "response", "local_mean"):
            assert np.array_equal(getattr(threaded, field), getattr(serial, field)), field


@pytest.mark.parametrize("value", ["x", "0", "-1", "2.5"])
def test_invalid_thread_env_raises(monkeypatch, value):
    monkeypatch.setenv(_THREADS_ENV, value)
    frame = _broadband()
    with pytest.raises(ValueError, match=_THREADS_ENV):
        estimate_local_stripes(frame, np.ones(frame.shape, bool), BinFactors())


def test_thread_env_sets_the_bank_threads(monkeypatch):
    frame = _broadband()
    light = np.ones(frame.shape, bool)
    serial = estimate_local_stripes(frame, light, BinFactors(), threads=1)
    monkeypatch.setenv(_THREADS_ENV, "3")
    threaded = estimate_local_stripes(frame, light, BinFactors())
    assert np.array_equal(threaded.ratio, serial.ratio)
