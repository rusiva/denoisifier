"""Band peak of a frame's spectrum: an oracle check on the generator only.

Independent of ``denoisifier.analysis``. The frame is flattened by its
sigma-10 smoothed copy, Hann-windowed, and 4x zero-padded. The search ring is
Periods 3-20 px; the vertical band is Angles within +-10 deg (stripes) plus a
2 deg margin, so a peak at exactly +-10 deg is not cut off by the frequency
grid; the horizontal band is the same ring rotated 90 deg.
"""

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter


_BAND_DEG = 12.0


@dataclass(frozen=True)
class BandPeak:
    period: float
    angle_deg: float
    vertical_to_horizontal: float


def band_peak(frame):
    rel = frame / gaussian_filter(frame, 10) - 1
    w = np.outer(np.hanning(frame.shape[0]), np.hanning(frame.shape[1]))
    g = (rel - (rel * w).sum() / w.sum()) * w
    power = np.abs(np.fft.fft2(g, s=(4 * frame.shape[0], 4 * frame.shape[1]))) ** 2
    fy = np.fft.fftfreq(power.shape[0])[:, None]
    fx = np.fft.fftfreq(power.shape[1])[None, :]
    fmag = np.hypot(fx, fy)
    ang = np.degrees(np.arctan2(fy, fx))
    ring = (fmag >= 1 / 20) & (fmag <= 1 / 3)
    vertical = ring & (fx > 0) & (np.abs(ang) <= _BAND_DEG)
    horizontal = ring & (fy > 0) & (np.abs(ang - 90) <= _BAND_DEG)
    i = np.unravel_index(np.argmax(np.where(vertical, power, 0)), power.shape)
    return BandPeak(
        period=float(1 / fmag[i]),
        angle_deg=float(ang[i]),
        vertical_to_horizontal=float(power[vertical].max() / power[horizontal].max()),
    )
