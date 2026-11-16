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
least ``MIN_FRAME_PERIOD_PX`` (``searched_periods``); the rest of the bank's
range is ``unresolved_periods``. Every sensor/frame conversion of a length or
a frequency, here and in analysis.py, goes through the helpers below
(``frame_px``, ``sensor_frequency``, ``pixel_size``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, TypeVar, cast

import numpy as np
import scipy.fft
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

# Every Gaussian filter is evaluated only where it exceeds exp(-K^2 / 2) of
# its peak, K = _GAUSS_TRUNC_SIGMAS (1.3e-14 at 8; ticket 13 slice 5).
_GAUSS_TRUNC_SIGMAS = 8.0

# Reflect padding before the FFT. analysis.py asserts it is below MIN_SIDE,
# so reflect padding is always valid.
_PAD = 32

# Stripe Angles whose energies lie within this fraction of the largest count as tied, and the
# first of them (in _STRIPE_ANGLES_DEG order) wins (ticket 13 slice 4b; orchestrator approval
# 2026-11-16). Mirror-symmetric places, such as the reflect-padded edge columns, tie +theta and
# -theta up to rounding; without it the Angle and response there follow the rounding. 1e-9 is
# the largest decade that changed no Angle off the mirror columns on ticket 13's harness frames
# (prototypes/p13/tie_bound.py).
_BANK_TIE_REL = 1e-9

# Ratio floor, in Modulation Depth units: the reference energy is never taken
# below that of a depth-A0 modulation, so noise-free frames (both energies
# tiny) cannot score on deterministic leakage. With A0 = 3e-3, ticket 01's
# profile-only frames (Gaussian noise 0 / 0.001 / 0.01, seeds 0-9) scored at
# most ~72 on ticket 03's score and at most 38.3 on today's (ticket 07, P1);
# with A0 = 1e-3 they reached ~420. What this means for shallow stripes
# depends on the Threshold and is noted in analysis.py.
_A0 = 3e-3

# The shortest frame Period (px) a bank filter may have; below it the filter
# is past the frame's Nyquist limit. Prototype P1 of ticket 08: under 2x1,
# sensor Period 4.2 px (2.1 frame px) still resolved 8 of 8 frames within 0.1%
# in Period and 0.02 deg in Angle.
MIN_FRAME_PERIOD_PX = 2.0

# A length (px) or a frequency (cycles/px), or a grid of them.
_Value = TypeVar("_Value", float, NDArray[np.float64])


def frame_px(bins: BinFactors, height: _Value, width: _Value) -> tuple[_Value, _Value]:
    """A height (down the frame) and a width (across it) in sensor px, in frame px."""
    return height / bins.vertical, width / bins.horizontal


def sensor_frequency(bins: BinFactors, fy: _Value, fx: _Value) -> tuple[_Value, _Value]:
    """Frequencies down (``fy``) and across (``fx``) the frame, in cycles per
    frame px, in cycles per sensor px."""
    return fy / bins.vertical, fx / bins.horizontal


def pixel_size(bins: BinFactors) -> tuple[int, int]:
    """A frame pixel's (height, width) in sensor px."""
    return bins.vertical, bins.horizontal


def _frame_frequency_scale(bins: BinFactors, t: np.ndarray) -> np.ndarray:
    """The frame frequency of a filter over its sensor frequency, at each
    wavevector angle ``t`` (radians from the frame's x axis):
    ``hypot(h cos t, v sin t)``."""
    return np.asarray(np.hypot(bins.horizontal * np.cos(t), bins.vertical * np.sin(t)))


def _frame_frequency_scales(bins: BinFactors) -> tuple[np.ndarray, np.ndarray]:
    """``(stripe, reference)``: ``_frame_frequency_scale`` at each bank
    Angle, for the stripe filters and for their references (+ 90 deg)."""
    t = np.deg2rad(np.asarray(_STRIPE_ANGLES_DEG))
    return _frame_frequency_scale(bins, t), _frame_frequency_scale(bins, t + np.pi / 2)


def searched_periods(bins: BinFactors) -> np.ndarray:
    """The bank Periods (sensor px, in ``_PERIODS`` order) at which every
    bank filter, stripe and reference, keeps a frame Period of at least
    ``MIN_FRAME_PERIOD_PX``; ``_PERIODS`` itself at 1x1."""
    stripe, reference = _frame_frequency_scales(bins)
    scale = max(stripe.max(), reference.max())
    keep = _PERIODS / scale >= MIN_FRAME_PERIOD_PX
    return _PERIODS if keep.all() else _PERIODS[keep]


@dataclass(frozen=True)
class UnresolvedPeriods:
    """The part of the bank's Period range, ``shortest`` up to ``limit``
    (sensor px), that is not searched under some bin factors. ``by`` names
    the filters that fall under ``MIN_FRAME_PERIOD_PX`` frame px there."""

    shortest: float
    limit: float
    by: Literal["stripe", "reference", "both"]


def unresolved_periods(bins: BinFactors) -> UnresolvedPeriods | None:
    """The bank's unsearched Periods under ``bins``, or ``None`` when all are
    searched. ``limit`` is ``MIN_FRAME_PERIOD_PX`` times the largest
    frame-over-sensor frequency of any bank filter."""
    stripe, reference = _frame_frequency_scales(bins)
    s, r = float(stripe.max()), float(reference.max())
    limit = MIN_FRAME_PERIOD_PX * max(s, r)
    shortest = float(_PERIODS[0])
    if limit <= shortest:
        return None
    by: Literal["stripe", "reference", "both"] = (
        "both" if np.isclose(s, r) else ("stripe" if s > r else "reference")
    )
    return UnresolvedPeriods(shortest=shortest, limit=limit, by=by)


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
    """The padded frame's FFT and its frequency axes (x = columns, y = rows),
    in cycles per sensor pixel: each axis's frame frequency over its bin factor.

    Every filter is a Gaussian in frequency (``gaussian``), applied on its
    support box only and inverted by a pruned 2D inverse FFT (ticket 13)."""

    def __init__(self, frame: np.ndarray, bins: BinFactors):
        self.bins = bins
        self.shape = (int(frame.shape[0]), int(frame.shape[1]))
        padded = np.pad(frame, _PAD, mode="reflect")
        self.f = scipy.fft.fft2(padded)
        # fftfreq is float64 at runtime; numpy's stub says floating[Any].
        fy = cast(NDArray[np.float64], np.fft.fftfreq(padded.shape[0]))
        fx = cast(NDArray[np.float64], np.fft.fftfreq(padded.shape[1]))
        self.fy, self.fx = sensor_frequency(bins, fy, fx)

    def gaussian(
        self,
        period: float | None,
        angle_deg: float,
        sigma_across: float,
        sigma_along: float,
        *,
        truncate: bool = True,
    ) -> np.ndarray:
        """The frame filtered by a Gaussian of frequency sigmas ``sigma_across``
        and ``sigma_along`` (cycles per sensor px), complex, frame shape.

        With a ``period`` it is centred on the stripe frequency ``1 / period``
        at ``angle_deg``, its sigmas across and along the stripes (a Gabor,
        peak gain 1). With ``None`` it is centred on DC with ``sigma_across``
        along x and ``sigma_along`` along y (the local mean, gain 1 at DC;
        ``angle_deg`` is not used). It is evaluated where it exceeds
        ``exp(-_GAUSS_TRUNC_SIGMAS**2 / 2)`` of its peak: the box of the
        frequency rows and columns holding that ellipse, picked by their
        ``fftfreq`` value as the full grid evaluates them: a box around DC is
        the two index runs at both ends of the axis, and a box that reaches
        past Nyquist (P3) is clipped there, as the full-grid kernel is, never
        wrapped; ``truncate=False`` evaluates the whole grid."""
        if period is None:
            c, s, cx, cy = 1.0, 0.0, 0.0, 0.0
        else:
            t = math.radians(angle_deg)
            c, s = math.cos(t), math.sin(t)
            cx, cy = c / period, s / period
        if truncate:
            k = _GAUSS_TRUNC_SIGMAS
            half_x = k * math.hypot(sigma_across * c, sigma_along * s)
            half_y = k * math.hypot(sigma_across * s, sigma_along * c)
            cols = np.flatnonzero(np.abs(self.fx - cx) <= half_x)
            rows = np.flatnonzero(np.abs(self.fy - cy) <= half_y)
        else:
            cols, rows = np.arange(self.fx.size), np.arange(self.fy.size)
        fx, fy = self.fx[cols][None, :], self.fy[rows][:, None]
        if period is None:
            across, along = fx, fy
        else:
            across = fx * c + fy * s - 1.0 / period
            along = -fx * s + fy * c
        kernel = np.exp(-0.5 * ((across / sigma_across) ** 2 + (along / sigma_along) ** 2))
        return self._inverse(rows, cols, kernel)

    def _inverse(self, rows: np.ndarray, cols: np.ndarray, kernel: np.ndarray) -> np.ndarray:
        """The frame-shaped crop of the inverse FFT of the spectrum times ``kernel``
        on ``rows`` x ``cols`` (zero elsewhere): the x pass on those rows only,
        cropped to the frame's columns, then the y pass on those columns."""
        height, width = self.f.shape
        h, w = self.shape
        x = np.zeros((rows.size, width), dtype=complex)
        x[:, cols] = self.f[np.ix_(rows, cols)] * kernel
        x = scipy.fft.ifft(x, axis=1, overwrite_x=True)[:, _PAD : _PAD + w]
        y = np.zeros((height, w), dtype=complex)
        y[rows] = x
        return np.asarray(scipy.fft.ifft(y, axis=0, overwrite_x=True)[_PAD : _PAD + h])

    def gabor(self, period: float, angle_deg: float) -> np.ndarray:
        """Complex Gabor, peak gain 1, tuned to ``period`` and ``angle_deg``."""
        return self.gaussian(period, angle_deg, *_bank_sigmas(period))

    def local_mean(self, period: float) -> np.ndarray:
        """The Gabor window at f = 0 (gain 1 at DC)."""
        return np.real(self.gaussian(None, 0.0, *_bank_sigmas(period)))


def _bank_sigmas(period: float) -> tuple[float, float]:
    """The bank window's frequency sigmas (across, along the stripes) at ``period``."""
    return 1.0 / (2 * np.pi * _ACROSS * period), 1.0 / (2 * np.pi * _ALONG * period)


def gabor_at(
    frame: np.ndarray, period: float, angle_deg: float, bins: BinFactors
) -> tuple[np.ndarray, np.ndarray]:
    """``(response, local_mean)`` of one bank-style filter at any Period and Angle."""
    spec = _Spectrum(frame, bins)
    return spec.gabor(period, angle_deg), spec.local_mean(period)


@dataclass(frozen=True)
class _BankBuffers:
    """Work arrays for one bank Period, reused from Period to Period: the
    five stripe responses (complex) and their energies (or the references')."""

    stripe: np.ndarray
    energy: np.ndarray

    @classmethod
    def of(cls, shape: tuple[int, ...]) -> _BankBuffers:
        n = len(_STRIPE_ANGLES_DEG)
        return cls(np.empty((n, *shape), dtype=complex), np.empty((n, *shape)))


@dataclass(frozen=True)
class _PeriodMatch:
    """The bank at one Period: the ratio, the index of the best stripe Angle
    (its response is left in the buffers' ``stripe``) and the local mean."""

    ratio: np.ndarray
    angle_index: np.ndarray
    mean: np.ndarray


def _match_period(
    spec: _Spectrum, p: float, light: np.ndarray, buffers: _BankBuffers
) -> _PeriodMatch:
    stripe, energy = buffers.stripe, buffers.energy
    for i, a in enumerate(_STRIPE_ANGLES_DEG):
        stripe[i] = spec.gabor(p, a)
    np.abs(stripe, out=energy)
    energy **= 2
    e_stripe = energy.max(axis=0)
    angle_index = np.argmax(energy >= e_stripe * (1.0 - _BANK_TIE_REL), axis=0)
    for i, a in enumerate(_STRIPE_ANGLES_DEG):
        np.abs(spec.gabor(p, a + 90.0), out=energy[i])
    energy **= 2
    e_reference = energy.max(axis=0)
    mean = spec.local_mean(p)

    # 2p tall, 3p wide (sensor px), in frame px.
    height, width = frame_px(spec.bins, 2 * p, 3 * p)
    box = (max(3, round(height)), max(3, round(width)))
    floor = (_A0 * np.abs(uniform_filter(mean, box)) / 2) ** 2
    denom = np.maximum(uniform_filter(e_reference, box), floor)
    ratio = np.zeros(light.shape)
    np.divide(uniform_filter(e_stripe, box), denom, out=ratio, where=light & (denom > 0))
    return _PeriodMatch(ratio=ratio, angle_index=angle_index, mean=mean)


def estimate_local_stripes(
    frame: np.ndarray, light: np.ndarray, bins: BinFactors, spectrum: _Spectrum | None = None
) -> LocalStripes:
    """Run the bank over ``frame``; ``light`` (bool, frame shape) masks the dark
    surround. Periods and Angles are in sensor px under ``bins``; only
    ``searched_periods(bins)`` are run. ``spectrum``, when given, is
    ``_Spectrum(frame, bins)`` already computed (``analyse`` shares one)."""
    spec = _Spectrum(frame, bins) if spectrum is None else spectrum
    shape = frame.shape
    best_ratio = np.zeros(shape)
    best_period = np.zeros(shape)
    best_angle = np.zeros(shape)
    best_response = np.zeros(shape, dtype=complex)
    best_mean = np.zeros(shape)
    angles = np.asarray(_STRIPE_ANGLES_DEG)
    buffers = _BankBuffers.of(shape)

    for p in searched_periods(bins):
        match = _match_period(spec, p, light, buffers)
        better = match.ratio > best_ratio
        index = match.angle_index[better]
        best_ratio[better] = match.ratio[better]
        best_period[better] = p
        best_angle[better] = angles[index]
        rows, cols = np.nonzero(better)
        best_response[better] = buffers.stripe[index, rows, cols]
        best_mean[better] = match.mean[better]

    return LocalStripes(
        ratio=best_ratio,
        period=best_period,
        angle_deg=best_angle,
        response=best_response,
        local_mean=best_mean,
    )
