"""Local stripe estimation: an oriented Gabor filter bank (ADR 0001).

Stripes are several consecutive cycles at a consistent Period and phase,
near-vertical. Each bank filter is a complex Gabor whose window spans about
three cycles across the stripes, so it only responds to several cycles in
phase; its window along the stripes makes it select by Angle. Mottle and
Noise are isotropic, so the same bank rotated 90 deg (the reference) measures
their energy at the same scale and place, and the ratio of the two is
self-normalising across light level, EM gain and mottle strength.

Binned frames (``BinFactors``, ticket 08): every Period and Angle here is in
sensor pixels. The frequency grid of ``_Spectrum`` is in cycles per sensor
pixel (each axis's frame frequency divided by its bin factor), so a filter
specified by a sensor Period and Angle is exactly the frame filter at the
converted frame Period and Angle (under 1x2 a 10 deg filter sits at 19.4 deg
in the frame). A bank Period is searched only when every bank filter at it,
stripe filters and their 90 deg references alike, keeps a frame Period of at
least ``MIN_ARRAY_PERIOD_PX`` (``searched_periods``); the rest of the bank's
range is ``unresolved_period_range``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import uniform_filter

from denoisifier.report import BinFactors

# Bank: 18 Periods geometric from 3 to 20 px (x1.12 apart), stripe filters at
# Angles -10..10 deg every 5 deg, reference filters at the same + 90 deg.
_PERIODS = 3.0 * (20.0 / 3.0) ** (np.arange(18) / 17)
_STRIPE_ANGLES_DEG = (-10.0, -5.0, 0.0, 5.0, 10.0)

# Spatial window sigma, in Periods: across and along the stripes.
_ACROSS = 1.0
_ALONG = 1.5

# Reflect padding before the FFT. analysis.py asserts it is below MIN_SIDE,
# so reflect padding is always valid.
_PAD = 32

# Ratio floor, in Modulation Depth units: the reference energy is never taken
# below that of a depth-A0 modulation, so noise-free frames (both energies
# tiny) cannot score on deterministic leakage. With A0 = 3e-3, ticket 01's
# profile-only frames (Gaussian noise 0 / 0.001 / 0.01, seeds 0-9) scored at
# most ~72 on ticket 03's score and at most 38.3 on today's (ticket 07, P1);
# with A0 = 1e-3 they reached ~420. What this means for shallow stripes
# depends on the Threshold and is noted in analysis.py.
_A0 = 3e-3

# The shortest frame Period (px) a bank filter may have; below it the filter
# is past the frame's Nyquist limit (2 px). Prototype P1 of ticket 08: under
# 2x1, sensor Period 4.2 px (2.1 frame px) still resolved 8 of 8 frames
# within 0.1% in Period and 0.02 deg in Angle.
MIN_ARRAY_PERIOD_PX = 2.0


def _frame_frequency_scales(bins: BinFactors) -> tuple[np.ndarray, np.ndarray]:
    """``(stripe, reference)``: for each bank Angle, the frame frequency of a
    bank filter over its sensor frequency, ``hypot(h cos t, v sin t)`` at the
    filter's wavevector angle ``t`` (the Angle for stripe filters, + 90 deg
    for their references)."""
    h, v = bins.horizontal, bins.vertical
    t = np.deg2rad(np.asarray(_STRIPE_ANGLES_DEG))
    stripe = np.hypot(h * np.cos(t), v * np.sin(t))
    reference = np.hypot(h * np.cos(t + np.pi / 2), v * np.sin(t + np.pi / 2))
    return stripe, reference


def searched_periods(bins: BinFactors) -> np.ndarray:
    """The bank Periods (sensor px, in ``_PERIODS`` order) at which every
    bank filter, stripe and reference, keeps a frame Period of at least
    ``MIN_ARRAY_PERIOD_PX``; ``_PERIODS`` itself at 1x1."""
    stripe, reference = _frame_frequency_scales(bins)
    scale = max(stripe.max(), reference.max())
    keep = _PERIODS / scale >= MIN_ARRAY_PERIOD_PX
    return _PERIODS if keep.all() else _PERIODS[keep]


def unresolved_period_range(bins: BinFactors) -> tuple[float, float, str] | None:
    """``(3.0, limit, by)``: the part of the bank's Period range (sensor px)
    that is not searched under ``bins``, or ``None`` when all of it is.
    ``limit`` is ``MIN_ARRAY_PERIOD_PX`` times the largest frame-over-sensor
    frequency of any bank filter; ``by`` names the filters that set it:
    ``"stripe"``, ``"reference"`` or ``"both"``."""
    stripe, reference = _frame_frequency_scales(bins)
    s, r = float(stripe.max()), float(reference.max())
    limit = MIN_ARRAY_PERIOD_PX * max(s, r)
    shortest = float(_PERIODS[0])
    if limit <= shortest:
        return None
    by = "both" if np.isclose(s, r) else ("stripe" if s > r else "reference")
    return shortest, limit, by


@dataclass(frozen=True)
class LocalStripes:
    """Per-pixel best match over the filter bank. All arrays have the frame's shape.

    ``ratio`` is the local stripe-vs-reference energy ratio, box-averaged
    around each pixel (0 outside the light); ``analyse`` seeds its
    Striped Regions at its local maxima. ``period`` and ``angle_deg`` are the
    bank Period and Angle with the best ratio at each pixel (0 outside light);
    they are the coarse bank grid (Periods x1.12 apart, Angles 5 deg apart).
    Fine Period and Angle over an area come from the neighbour-product sum of
    ``response`` over that area (``analysis._phase_steps``), the one
    estimator for every region. ``response`` is the complex
    filter response at that Period and Angle (local phase = ``np.angle``);
    ``local_mean`` is the same-window local mean, so the local Modulation
    Depth is ``2 * |response| / local_mean``.
    """

    ratio: np.ndarray
    period: np.ndarray
    angle_deg: np.ndarray
    response: np.ndarray
    local_mean: np.ndarray


class _Spectrum:
    """The padded frame's FFT and its frequency grid (x = columns, y = rows),
    in cycles per sensor pixel: each axis's frame frequency over its bin factor."""

    def __init__(self, frame: np.ndarray, bins: BinFactors):
        self.bins = bins
        padded = np.pad(frame, _PAD, mode="reflect")
        self.f = np.fft.fft2(padded)
        self.fy = np.fft.fftfreq(padded.shape[0])[:, None] / bins.vertical
        self.fx = np.fft.fftfreq(padded.shape[1])[None, :] / bins.horizontal

    def filtered(self, kernel: np.ndarray) -> np.ndarray:
        return np.fft.ifft2(self.f * kernel)[_PAD:-_PAD, _PAD:-_PAD]

    def gabor(self, period: float, angle_deg: float) -> np.ndarray:
        """Complex Gabor, peak gain 1, tuned to ``period`` and ``angle_deg``."""
        t = np.deg2rad(angle_deg)
        across = self.fx * np.cos(t) + self.fy * np.sin(t) - 1.0 / period
        along = -self.fx * np.sin(t) + self.fy * np.cos(t)
        return self.filtered(_window(across, along, period))

    def local_mean(self, period: float) -> np.ndarray:
        """The Gabor window at f = 0 (gain 1 at DC)."""
        return np.real(self.filtered(_window(self.fx, self.fy, period)))


def _window(
    across: NDArray[np.float64], along: NDArray[np.float64], period: float
) -> NDArray[np.float64]:
    sigma_across = 1.0 / (2 * np.pi * _ACROSS * period)
    sigma_along = 1.0 / (2 * np.pi * _ALONG * period)
    return np.exp(-0.5 * ((across / sigma_across) ** 2 + (along / sigma_along) ** 2))


def gabor_at(
    frame: np.ndarray, period: float, angle_deg: float, bins: BinFactors
) -> tuple[np.ndarray, np.ndarray]:
    """``(response, local_mean)`` of one bank-style filter at any Period and Angle."""
    spec = _Spectrum(frame, bins)
    return spec.gabor(period, angle_deg), spec.local_mean(period)


def estimate_local_stripes(frame: np.ndarray, light: np.ndarray, bins: BinFactors) -> LocalStripes:
    """Run the bank over ``frame``; ``light`` (bool, frame shape) masks the dark
    surround. Periods and Angles are in sensor px under ``bins``; only
    ``searched_periods(bins)`` are run."""
    spec = _Spectrum(frame, bins)
    h, v = bins.horizontal, bins.vertical
    shape = frame.shape
    best_ratio = np.zeros(shape)
    best_period = np.zeros(shape)
    best_angle = np.zeros(shape)
    best_response = np.zeros(shape, dtype=complex)
    best_mean = np.zeros(shape)

    for p in searched_periods(bins):
        stripe = np.stack([spec.gabor(p, a) for a in _STRIPE_ANGLES_DEG])
        stripe_energy = np.abs(stripe) ** 2
        angle_index = np.argmax(stripe_energy, axis=0)
        e_stripe = np.take_along_axis(stripe_energy, angle_index[None], axis=0)[0]
        e_reference = np.max(
            [np.abs(spec.gabor(p, a + 90.0)) ** 2 for a in _STRIPE_ANGLES_DEG], axis=0
        )
        mean = spec.local_mean(p)

        # 2p tall, 3p wide, in sensor px, as frame px.
        box = (max(3, round(2 * p / v)), max(3, round(3 * p / h)))
        floor = (_A0 * np.abs(uniform_filter(mean, box)) / 2) ** 2
        denom = np.maximum(uniform_filter(e_reference, box), floor)
        ratio = np.zeros(shape)
        np.divide(uniform_filter(e_stripe, box), denom, out=ratio, where=light & (denom > 0))

        better = ratio > best_ratio
        best_ratio[better] = ratio[better]
        best_period[better] = p
        best_angle[better] = np.asarray(_STRIPE_ANGLES_DEG)[angle_index[better]]
        best_response[better] = np.take_along_axis(stripe, angle_index[None], axis=0)[0][better]
        best_mean[better] = mean[better]

    return LocalStripes(
        ratio=best_ratio,
        period=best_period,
        angle_deg=best_angle,
        response=best_response,
        local_mean=best_mean,
    )
