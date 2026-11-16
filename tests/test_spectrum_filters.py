"""The Gaussian filters on the shared spectrum (ticket 13 slice 5): evaluated on their support box
only, with a pruned inverse FFT, they match the full-grid evaluation.

The frame is a fixed, seed-free broadband pattern (no generated frame), so every frequency the
box could miss carries power."""

import math

import numpy as np
import pytest

from denoisifier import BinFactors
from denoisifier._local_phase import (
    _BREAK_SIGMA_ACROSS_PERIODS,
    _BREAK_SIGMA_ALONG_PERIODS,
    break_response,
)
from denoisifier._local_stripes import _ACROSS, _ALONG, _PAD, _Spectrum, _window_sigmas
from protected import FULL_GRID_REL_TOL


def _broadband(shape=(150, 230)):
    rows, cols = np.mgrid[0 : shape[0], 0 : shape[1]].astype(float)
    pattern = np.sin(0.37 * rows * cols + 0.11 * rows) + np.cos(1.9 * cols + 0.013 * rows**2)
    return 10.0 + pattern + 0.5 * np.sin(2.9 * rows)


def _bank_sigmas(period):
    return _window_sigmas(period, _ACROSS, _ALONG)


def test_window_sigmas_are_the_spatial_window_in_frequency():
    # A spatial Gaussian of sigma s px is a frequency Gaussian of sigma 1 / (2 pi s) cycles/px:
    # at P 4 a window 1 x 1.5 Periods is 4 x 6 px, so 1 / (8 pi) and 1 / (12 pi).
    expected = (0.039788735772973836, 0.0265258238486492)
    assert _window_sigmas(4.0, 1.0, 1.5) == pytest.approx(expected)


def _rel(got, ref):
    return float(np.abs(got - ref).max() / np.abs(ref).max())


FILTERS = [
    # Nyquist clip at P3: the box reaches past the Nyquist edge at the bank's outer Angles and is
    # clipped there, as the full grid is (never wrapped); the low-pass local-mean box is the two
    # index runs around DC.
    pytest.param((1, 1), 3.0, -10.0, False, id="P3-nyquist-clip-minus10"),
    pytest.param((1, 1), 3.0, 10.0, False, id="P3-nyquist-clip-plus10"),
    pytest.param((1, 1), 3.0, 0.0, True, id="P3-local-mean-DC"),
    # Binned grids: the box is chosen on non-unit frame frequency scales.
    pytest.param((2, 1), 3.0, 5.0, False, id="P3-2x1"),
    pytest.param((1, 2), 3.0, 5.0, False, id="P3-1x2"),
    pytest.param((2, 1), 6.0, -5.0, False, id="P6-2x1"),
    pytest.param((1, 2), 6.0, -5.0, False, id="P6-1x2"),
    pytest.param((1, 2), 6.0, 0.0, True, id="P6-1x2-local-mean"),
    # The 90 deg references of a P3 and a P6 bank filter.
    pytest.param((1, 1), 3.0, 80.0, False, id="P3-reference"),
    pytest.param((1, 1), 6.0, 100.0, False, id="P6-reference"),
]


@pytest.mark.parametrize(("bins", "period", "angle_deg", "local_mean"), FILTERS)
def test_support_box_filter_matches_full_grid(bins, period, angle_deg, local_mean):
    spec = _Spectrum(_broadband(), BinFactors(*bins))
    across, along = _bank_sigmas(period)
    centre = None if local_mean else period
    got = spec.gaussian(centre, angle_deg, across, along)
    ref = spec.gaussian(centre, angle_deg, across, along, truncate=False)
    assert got.shape == ref.shape == _broadband().shape
    assert _rel(got, ref) <= FULL_GRID_REL_TOL


def _full_grid(frame, kernel_of):
    """An independent full-grid filter: one numpy ifft2 of the whole padded spectrum times
    ``kernel_of(fx, fy)``, cropped to the frame (no ``_Spectrum`` code)."""
    padded = np.pad(frame, _PAD, mode="reflect")
    f = np.fft.fft2(padded)
    fy = np.fft.fftfreq(padded.shape[0])[:, None]
    fx = np.fft.fftfreq(padded.shape[1])[None, :]
    return np.fft.ifft2(f * kernel_of(fx, fy))[_PAD:-_PAD, _PAD:-_PAD]


@pytest.mark.parametrize(("period", "angle_deg"), [(3.0, -10.0), (6.0, 5.0)])
def test_bank_gabor_matches_independent_full_grid(period, angle_deg):
    # The box cases above share _Spectrum._inverse with their reference; this one does not.
    frame = _broadband()
    t = math.radians(angle_deg)
    sigma_across, sigma_along = _bank_sigmas(period)

    def kernel(fx, fy):
        across = fx * np.cos(t) + fy * np.sin(t) - 1.0 / period
        along = -fx * np.sin(t) + fy * np.cos(t)
        return np.exp(-0.5 * ((across / sigma_across) ** 2 + (along / sigma_along) ** 2))

    got = _Spectrum(frame, BinFactors()).gabor(period, angle_deg)
    assert _rel(got, _full_grid(frame, kernel)) <= FULL_GRID_REL_TOL


@pytest.mark.parametrize(("period", "angle_deg"), [(3.0, 10.0), (6.0, -5.0)])
def test_break_response_matches_full_grid(period, angle_deg):
    frame = _broadband()
    spec = _Spectrum(frame, BinFactors())
    # The finder's response on the full grid: one inverse FFT of the whole padded spectrum.
    padded = np.pad(frame, _PAD, mode="reflect")
    f = np.fft.fft2(padded)
    fy = np.fft.fftfreq(padded.shape[0])[:, None]
    fx = np.fft.fftfreq(padded.shape[1])[None, :]
    t = math.radians(angle_deg)
    sa = 2 * np.pi * _BREAK_SIGMA_ACROSS_PERIODS * period
    sl = 2 * np.pi * _BREAK_SIGMA_ALONG_PERIODS * period
    across = fx * np.cos(t) + fy * np.sin(t) - 1.0 / period
    along = -fx * np.sin(t) + fy * np.cos(t)

    def full(kernel):
        return np.fft.ifft2(f * kernel)[_PAD:-_PAD, _PAD:-_PAD]

    response = full(np.exp(-0.5 * ((across * sa) ** 2 + (along * sl) ** 2)))
    mean = np.real(full(np.exp(-0.5 * ((fx * sa) ** 2 + (fy * sl) ** 2))))
    ref = 2 * response / mean
    assert (mean > 0).all()
    assert _rel(break_response(spec, period, angle_deg), ref) <= FULL_GRID_REL_TOL
