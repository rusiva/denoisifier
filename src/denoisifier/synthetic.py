"""Seeded synthetic frames with known ground truth.

A developer tool and test oracle, not part of the experimenter-facing surface.
The forward model follows the spec:

    clean = profile * (1 + m * cos(phase))
    phase = 2*pi/period * (x*cos(t) + y*sin(t)) + phase0
    frame = clean + noise

Later tickets add mottle (``* mottle``) and swap the noise stage.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


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
    frame: np.ndarray
    truth: GroundTruth


def generate(
    *,
    seed: int,
    shape: tuple[int, int] = (256, 256),
    period: float = 8.0,
    angle_deg: float = 0.0,
    modulation_depth: float = 0.6,
    noise: float = 0.01,
    peak: float = 1000.0,
) -> Synthetic:
    """Generate one frame: profile times full-frame stripes, plus noise.

    ``period`` and ``angle_deg`` are the Period and Angle (GLOSSARY.md);
    ``angle_deg`` is ``t`` in ``phase = 2*pi/period * (x cos t + y sin t)``
    with ``x`` the column and ``y`` the row (increasing downward). ``noise`` is the additive
    Gaussian standard deviation as a fraction of ``peak``, the profile peak.
    ``modulation_depth=0`` gives a profile-only frame.
    """
    if len(shape) != 2 or shape[0] < 1 or shape[1] < 1:
        raise ValueError(f"shape must be two positive sizes, got {shape!r}")
    if not period > 0:
        raise ValueError(f"period must be > 0, got {period!r}")
    if not 0 <= modulation_depth <= 1:
        raise ValueError(f"modulation_depth must be in [0, 1], got {modulation_depth!r}")
    if noise < 0:
        raise ValueError(f"noise must be >= 0, got {noise!r}")

    rng = np.random.default_rng(seed)
    rows, cols = shape
    y, x = np.mgrid[0:rows, 0:cols].astype(float)

    profile = peak * _profile(rng, rows, cols, x, y)

    t = np.deg2rad(angle_deg)
    phase0 = rng.uniform(0, 2 * np.pi)
    phase = 2 * np.pi / period * (x * np.cos(t) + y * np.sin(t)) + phase0
    clean = profile * (1 + modulation_depth * np.cos(phase))

    frame = clean + rng.normal(0.0, noise * peak, size=shape)
    return Synthetic(
        frame=frame,
        truth=GroundTruth(
            period=float(period),
            angle_deg=float(angle_deg),
            modulation_depth=float(modulation_depth),
        ),
    )


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

