"""``analyse``: decide whether a frame is striped and measure the stripes."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter

from denoisifier.report import Report

# Provisional verdict threshold (ticket 07 replaces it with a calibrated value).
# Chosen on calibration seeds outside the test seeds (profile-only 100-199,
# striped 100-134): log-midpoint between the highest profile-only score (16.9)
# and the lowest m = 0.2 score (1.6e4), about 30x margin each side.
THRESHOLD = 500.0

# Score floor, in modulation-depth units. The denominator of the score is
# never below the peak power that a modulation of depth A0 would give, so
# deterministic leakage on noise-free frames cannot look like stripes.
# Measured floored scores (prototype, 256x256): profile-only 9-17 (noise >= 0.1),
# 0.2-0.4 (noise 0.01), ~0.003 (noise 0.001), ~1e-4 (noise 0);
# m = 0.2: 1.6e4-4.1e4; m = 0.6: 1.4e5-3.7e5.
A0 = 1e-3

# Smallest side accepted: 2 x the longest period searched; the sigma = 10
# envelope filter needs at least that.
MIN_SIDE = 40

_ENVELOPE_SIGMA = 10.0
_MASK_FRACTION = 0.1
_PAD = 4
_MIN_PERIOD = 3.0
_MAX_PERIOD = 20.0
_MAX_ANGLE_DEG = 12.0  # search +-10 deg from vertical, plus a small margin


def analyse(frame: np.ndarray) -> Report:
    """Decide whether ``frame`` is striped and measure one global period and angle.

    ``frame`` is a 2D array of intensities, shape ``(rows, cols)``. It is not
    modified.
    """
    # Ticket 01 only: a global FFT peak. ADR 0001 says this is fooled by
    # mottle; ticket 02 replaces it with local periodicity.
    frame = np.asarray(frame, dtype=float)
    if frame.ndim != 2:
        raise ValueError(f"frame must be 2D, got {frame.ndim}D")
    if min(frame.shape) < MIN_SIDE:
        raise ValueError(
            f"frame is {frame.shape[0]}x{frame.shape[1]}; "
            f"both sides must be at least {MIN_SIDE} pixels"
        )
    if not np.all(np.isfinite(frame)):
        raise ValueError("frame contains non-finite values (NaN or infinity)")

    env = gaussian_filter(frame, sigma=_ENVELOPE_SIGMA)
    env_max = env.max()
    if env_max <= 0:
        raise ValueError("envelope max <= 0: frame has no positive light")

    # Stripes multiply the envelope, so frame/env - 1 flattens the profile.
    mask = env > _MASK_FRACTION * env_max
    rel = np.zeros_like(frame)
    rel[mask] = frame[mask] / env[mask] - 1.0

    hann = np.outer(np.hanning(frame.shape[0]), np.hanning(frame.shape[1]))
    w = np.clip(env / env_max, 0.0, 1.0) * mask * hann
    w_sum = w.sum()
    if w_sum <= 0:
        raise ValueError("no pixels left to analyse: analysis weight is empty")

    # Weighted mean: a plain mean leaves a residual shaped like w that leaks
    # into the band (prototype: profile-only scores rose from ~15 to ~1500 at
    # noise 0.001 with a plain mean).
    rel = rel - (rel * w).sum() / w_sum
    g = rel * w

    n0, n1 = _PAD * frame.shape[0], _PAD * frame.shape[1]
    power = np.abs(np.fft.fft2(g, s=(n0, n1))) ** 2
    fy = np.fft.fftfreq(n0)[:, None]
    fx = np.fft.fftfreq(n1)[None, :]
    fmag = np.hypot(fx, fy)
    with np.errstate(divide="ignore", invalid="ignore"):
        ang = np.degrees(np.arctan2(fy, fx))
    band = (
        (fx > 0)
        & (fmag >= 1.0 / _MAX_PERIOD)
        & (fmag <= 1.0 / _MIN_PERIOD)
        & (np.abs(ang) <= _MAX_ANGLE_DEG)
    )

    band_power = power[band]
    i = int(np.argmax(band_power))
    p_peak = band_power[i]
    depth_floor = (A0 * w_sum / 2.0) ** 2
    score = float(p_peak / max(float(np.median(band_power)), depth_floor))

    striped = score > THRESHOLD
    if not striped:
        return Report(striped=False, score=score, threshold=THRESHOLD, period_px=None, angle_deg=None)

    fy_b = np.broadcast_to(fy, power.shape)[band][i]
    fx_b = np.broadcast_to(fx, power.shape)[band][i]
    return Report(
        striped=True,
        score=score,
        threshold=THRESHOLD,
        period_px=float(1.0 / np.hypot(fx_b, fy_b)),
        angle_deg=float(np.degrees(np.arctan2(fy_b, fx_b))),
    )
