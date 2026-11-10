"""Local stripe estimation: an oriented Gabor filter bank (ADR 0001).

Stripes are several consecutive cycles at a consistent Period and phase,
near-vertical. Each bank filter is a complex Gabor whose window spans about
three cycles across the stripes, so it only responds to several cycles in
phase; its window along the stripes makes it select by Angle. Mottle and
Noise are isotropic, so the same bank rotated 90 deg (the reference) measures
their energy at the same scale and place, and the ratio of the two is
self-normalising across light level, EM gain and mottle strength.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import uniform_filter

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
# profile-only frames (Gaussian noise 0 / 0.001 / 0.01, seeds 0-9) score at
# most ~72; with A0 = 1e-3 they reached ~420. What this means for shallow
# stripes depends on THRESHOLD and is noted there (analysis.py).
_A0 = 3e-3


@dataclass(frozen=True)
class LocalStripes:
    """Per-pixel best match over the filter bank. All arrays have the frame's shape.

    ``ratio`` is the local stripe-vs-reference energy ratio, box-averaged
    around each pixel (0 outside the light mask); ``analyse`` takes its
    maximum. ``period`` and ``angle_deg`` are the bank
    Period and Angle with the best ratio at each pixel (0 outside light);
    they are the coarse bank grid (Periods x1.12 apart, Angles 5 deg apart).
    Fine Period and Angle over an area come from the neighbour-product sum of
    ``response`` over that area (``analysis._measure``); per-region estimates
    must use the same sum, not a second estimator. ``response`` is the complex
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
    """The padded frame's FFT and its frequency grid (x = columns, y = rows)."""

    def __init__(self, frame: np.ndarray):
        padded = np.pad(frame, _PAD, mode="reflect")
        self.f = np.fft.fft2(padded)
        self.fy = np.fft.fftfreq(padded.shape[0])[:, None]
        self.fx = np.fft.fftfreq(padded.shape[1])[None, :]

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


def _window(across, along, period):
    sigma_across = 1.0 / (2 * np.pi * _ACROSS * period)
    sigma_along = 1.0 / (2 * np.pi * _ALONG * period)
    return np.exp(-0.5 * ((across / sigma_across) ** 2 + (along / sigma_along) ** 2))


def gabor_at(frame: np.ndarray, period: float, angle_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """``(response, local_mean)`` of one bank-style filter at any Period and Angle."""
    spec = _Spectrum(frame)
    return spec.gabor(period, angle_deg), spec.local_mean(period)


def estimate_local_stripes(frame: np.ndarray, light: np.ndarray) -> LocalStripes:
    """Run the bank over ``frame``; ``light`` (bool, frame shape) masks the dark surround."""
    spec = _Spectrum(frame)
    shape = frame.shape
    best_ratio = np.zeros(shape)
    best_period = np.zeros(shape)
    best_angle = np.zeros(shape)
    best_response = np.zeros(shape, dtype=complex)
    best_mean = np.zeros(shape)

    for p in _PERIODS:
        stripe = np.stack([spec.gabor(p, a) for a in _STRIPE_ANGLES_DEG])
        stripe_energy = np.abs(stripe) ** 2
        angle_index = np.argmax(stripe_energy, axis=0)
        e_stripe = np.take_along_axis(stripe_energy, angle_index[None], axis=0)[0]
        e_reference = np.max([np.abs(spec.gabor(p, a + 90.0)) ** 2 for a in _STRIPE_ANGLES_DEG], axis=0)
        mean = spec.local_mean(p)

        box = (max(3, round(2 * p)), max(3, round(3 * p)))  # 2p tall, 3p wide
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
