"""Seeded synthetic frames with known ground truth.

A developer tool and test oracle, not part of the experimenter-facing surface.
The forward model follows the spec:

    clean = profile * mottle * (1 + m * cos(phase))
    phase = 2*pi/period * (x*cos(t) + y*sin(t)) + phase0
    mottle = exp(strength * g),  g a unit-std isotropic Gaussian random field
    frame = clean + noise

Noise is either additive Gaussian (``noise`` a float) or the EMCCD chain
(``noise`` an ``Emccd``): Poisson photons plus spurious charge, EM gain as a
Gamma distribution, Gaussian read noise, divided back by the gain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


MottleKind = Literal["none", "scorched", "multiscale"]

_TYPICAL_MOTTLE_STRENGTH = {"scorched": 0.4, "multiscale": 0.35}


@dataclass(frozen=True)
class Emccd:
    """EMCCD noise chain. Output is in ~photon units (divided by ``em_gain``).

    ``photons_peak``: photons at the brightest clean pixel. ``em_gain``: EM
    gain; 1.0 turns it off (no Gamma stage). ``read_noise_e``: Gaussian read
    noise std in electrons. ``cic``: spurious charge from clocking, mean
    photon-equivalents per pixel.
    """

    photons_peak: float = 100.0
    em_gain: float = 300.0
    read_noise_e: float = 50.0
    cic: float = 0.005


@dataclass(frozen=True)
class GroundTruth:
    """What the generator put into a frame.

    ``period`` is the Period in pixels; ``angle_deg`` is the Angle in degrees,
    with the sign convention in GLOSSARY.md.
    """

    period: float
    angle_deg: float
    modulation_depth: float


@dataclass(frozen=True)
class Synthetic:
    """A generated frame, its ground truth, and ``clean``: the noise-free
    frame in the same units as ``frame``, so ``frame - clean`` is pure noise
    (spurious charge included)."""

    frame: np.ndarray
    truth: GroundTruth
    clean: np.ndarray


def generate(
    *,
    seed: int,
    shape: tuple[int, int] = (256, 256),
    period: float = 8.0,
    angle_deg: float = 0.0,
    modulation_depth: float = 0.6,
    mottle: MottleKind = "none",
    mottle_strength: float | None = None,
    noise: float | Emccd = 0.01,
    peak: float = 1000.0,
) -> Synthetic:
    """Generate one frame: profile times full-frame stripes, plus noise.

    ``period`` and ``angle_deg`` are the Period and Angle (GLOSSARY.md);
    ``angle_deg`` is ``t`` in ``phase = 2*pi/period * (x cos t + y sin t)``
    with ``x`` the column and ``y`` the row (increasing downward). A float
    ``noise`` is the additive Gaussian standard deviation as a fraction of
    ``peak``, the profile peak; an ``Emccd`` selects the EMCCD chain, whose
    scale is set by ``Emccd.photons_peak`` instead of ``peak``.
    ``modulation_depth=0`` gives a profile-only frame.

    ``mottle`` picks the Mottle: ``"scorched"`` (blotchy, saturated; typical
    strength 0.4) or ``"multiscale"`` (power-law; typical strength 0.35).
    ``mottle_strength`` is the std of the log-mottle; ``None`` takes the
    typical value. Mottle is isotropic (ADR 0001).
    """
    if len(shape) != 2 or shape[0] < 1 or shape[1] < 1:
        raise ValueError(f"shape must be two positive sizes, got {shape!r}")
    if not period > 0:
        raise ValueError(f"period must be > 0, got {period!r}")
    if not 0 <= modulation_depth <= 1:
        raise ValueError(f"modulation_depth must be in [0, 1], got {modulation_depth!r}")
    if mottle not in ("none", "scorched", "multiscale"):
        raise ValueError(f"mottle must be 'none', 'scorched' or 'multiscale', got {mottle!r}")
    if mottle_strength is not None:
        if mottle == "none":
            raise ValueError("mottle_strength given with mottle='none'")
        if mottle_strength < 0:
            raise ValueError(f"mottle_strength must be >= 0, got {mottle_strength!r}")
    if isinstance(noise, Emccd):
        _check_emccd(noise)
    elif noise < 0:
        raise ValueError(f"noise must be >= 0, got {noise!r}")

    rng = np.random.default_rng(seed)
    rows, cols = shape
    y, x = np.mgrid[0:rows, 0:cols].astype(float)

    # RNG draw order is fixed: profile, stripe phase offset, mottle, noise.
    # So for one seed and shape, profile and mottle do not depend on the
    # stripe or noise settings.
    # The Gaussian path scales the profile first, as ticket 01 did, so
    # mottle-free Gaussian frames stay bit-identical to ticket 01.
    scale = 1.0 if isinstance(noise, Emccd) else peak
    profile = scale * _profile(rng, rows, cols, x, y)

    t = np.deg2rad(angle_deg)
    phase0 = rng.uniform(0, 2 * np.pi)
    phase = 2 * np.pi / period * (x * np.cos(t) + y * np.sin(t)) + phase0

    envelope = profile
    if mottle != "none":
        strength = _TYPICAL_MOTTLE_STRENGTH[mottle] if mottle_strength is None else mottle_strength
        envelope = profile * _mottle(rng, shape, mottle, strength)
    clean = envelope * (1 + modulation_depth * np.cos(phase))

    if isinstance(noise, Emccd):
        clean = clean / clean.max() * noise.photons_peak
        frame = _emccd(rng, clean, noise)
    else:
        frame = clean + rng.normal(0.0, noise * peak, size=shape)
    return Synthetic(
        frame=frame,
        truth=GroundTruth(
            period=float(period),
            angle_deg=float(angle_deg),
            modulation_depth=float(modulation_depth),
        ),
        clean=clean,
    )


def _check_emccd(emccd: Emccd) -> None:
    if not emccd.photons_peak > 0:
        raise ValueError(f"photons_peak must be > 0, got {emccd.photons_peak!r}")
    if not emccd.em_gain >= 1:
        raise ValueError(f"em_gain must be >= 1, got {emccd.em_gain!r}")
    if not emccd.read_noise_e >= 0:
        raise ValueError(f"read_noise_e must be >= 0, got {emccd.read_noise_e!r}")
    if not emccd.cic >= 0:
        raise ValueError(f"cic must be >= 0, got {emccd.cic!r}")


def _emccd(rng, clean, emccd: Emccd):
    """Photons + spurious charge -> Poisson -> EM gain (Gamma) -> read noise."""
    n = rng.poisson(clean + emccd.cic)
    if emccd.em_gain > 1:
        electrons = np.zeros(clean.shape)
        lit = n > 0
        electrons[lit] = rng.gamma(n[lit], emccd.em_gain)
    else:
        electrons = n.astype(float)
    electrons = electrons + rng.normal(0.0, emccd.read_noise_e, size=clean.shape)
    return electrons / emccd.em_gain


def _profile(rng, rows, cols, x, y):
    """Elliptical, rotated, mildly asymmetric Gaussian with peak 1."""
    cx = (cols - 1) / 2 + rng.uniform(-3, 3)
    cy = (rows - 1) / 2 + rng.uniform(-3, 3)
    rot = np.deg2rad(rng.uniform(-30, 30))
    sigma_major = 0.30 * cols * rng.uniform(0.95, 1.05)
    sigma_minor = 0.22 * rows * rng.uniform(0.95, 1.05)
    dx, dy = x - cx, y - cy
    u = dx * np.cos(rot) + dy * np.sin(rot)
    v = -dx * np.sin(rot) + dy * np.cos(rot)
    # Mild asymmetry: one side of the major axis is ~15% wider.
    sigma_u = np.where(u >= 0, sigma_major * 1.15, sigma_major)
    return np.exp(-0.5 * ((u / sigma_u) ** 2 + (v / sigma_minor) ** 2))


def _mottle(rng, shape, kind, strength):
    """Log-normal Mottle, ``exp(strength * g)`` with ``g`` of unit std."""
    if kind == "scorched":
        field = _standardise(np.tanh(2.5 * _grf(rng, shape, 3.0)) + 0.4 * _grf(rng, shape, 1.5))
    else:
        field = _grf(rng, shape, 2.2)
    return np.exp(strength * field)


def _grf(rng, shape, beta):
    """Isotropic Gaussian random field with power ~ k^-beta, unit std."""
    ky = np.fft.fftfreq(shape[0])[:, None]
    kx = np.fft.fftfreq(shape[1])[None, :]
    freq = np.hypot(kx, ky)
    freq[0, 0] = 1.0
    amp = freq ** (-beta / 2)
    amp[0, 0] = 0.0
    field = np.real(np.fft.ifft2(np.fft.fft2(rng.normal(size=shape)) * amp))
    return _standardise(field)


def _standardise(a):
    """Zero mean, unit std."""
    return (a - a.mean()) / a.std()
