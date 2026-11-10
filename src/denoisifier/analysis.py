"""``analyse``: decide whether a frame is striped and measure the stripes.

Method: local periodicity plus near-vertical orientation, not feature size
(ADR 0001); the filter bank lives in ``_local_stripes``.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter

from denoisifier._local_stripes import LocalStripes, estimate_local_stripes, gabor_at
from denoisifier.report import Report

# Provisional verdict threshold (ticket 07 replaces it with a calibrated value).
# Measured on calibration seeds outside the test seeds, 256x256 frames,
# ~100 photons at the peak, EMCCD: highest stripe-free score 83.7 (scorched,
# seeds 100-199; multiscale 100-149: 55.7); lowest m = 0.5 score 363
# (scorched and multiscale, seeds 100-119, Periods 3-20, Angles +-10).
# 150 leaves 1.8x above the stripe-free maximum and 2.4x below m = 0.5 (the
# log-midpoint would be ~174). m = 0.2 scores 80-205: ticket 03's problem.
THRESHOLD = 150.0

# Smallest side accepted: 2 x the longest period searched; the sigma = 10
# envelope filter needs at least that.
MIN_SIDE = 40

_ENVELOPE_SIGMA = 10.0
_MASK_FRACTION = 0.1
# The measured area keeps pixels whose bank Period is within this factor of
# the Period at the score peak (spec: Period roughly constant in a region).
_PERIOD_SPREAD = 1.25
# Fewer horizontal or vertical neighbour pairs than this in the measured area
# and the bank Period and Angle at the peak are reported instead.
MIN_PAIRS = 8


def analyse(frame: np.ndarray) -> Report:
    """Decide whether ``frame`` is striped and measure one Period, Angle and Modulation Depth.

    ``frame`` is a 2D array of intensities, shape ``(rows, cols)``. It is not
    modified.
    """
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
    # Only keeps the dark surround out of the score.
    light = env > _MASK_FRACTION * env_max

    local = estimate_local_stripes(frame, light)
    score = float(local.ratio.max())
    if not score > THRESHOLD:
        return Report(
            striped=False,
            score=score,
            threshold=THRESHOLD,
            period_px=None,
            angle_deg=None,
            modulation_depth=None,
        )

    period_px, angle_deg, depth = _measure(frame, local)
    return Report(
        striped=True,
        score=score,
        threshold=THRESHOLD,
        period_px=period_px,
        angle_deg=angle_deg,
        modulation_depth=depth,
    )


def _measure(frame: np.ndarray, local: LocalStripes) -> tuple[float, float, float]:
    """Period, Angle and Modulation Depth over the area around the score peak.

    Ticket 05 replaces the measured area with real Striped Regions.
    """
    peak = np.unravel_index(np.argmax(local.ratio), local.ratio.shape)
    p_star = float(local.period[peak])
    hot = local.ratio > THRESHOLD
    log_spread = np.zeros(local.ratio.shape)
    np.log(local.period / p_star, out=log_spread, where=hot)
    area = hot & (np.abs(log_spread) <= np.log(_PERIOD_SPREAD))

    period_px, angle_deg = p_star, float(local.angle_deg[peak])
    h_pairs = area[:, :-1] & area[:, 1:]
    v_pairs = area[:-1, :] & area[1:, :]
    if h_pairs.sum() >= MIN_PAIRS and v_pairs.sum() >= MIN_PAIRS:
        # Local frequency from the phase step between neighbours. Not
        # np.gradient of the phase: central differences are biased at short
        # Periods.
        g = local.response
        cx = (g[:, 1:] * np.conj(g[:, :-1]))[h_pairs].sum()
        cy = (g[1:, :] * np.conj(g[:-1, :]))[v_pairs].sum()
        fx, fy = np.angle(cx) / (2 * np.pi), np.angle(cy) / (2 * np.pi)
        f = np.hypot(fx, fy)
        if f > 0:
            period_px, angle_deg = float(1.0 / f), float(np.degrees(np.arctan2(fy, fx)))

    # Re-tune one filter to the measured Period and Angle: removes the bank's
    # grid-mismatch loss (up to ~15% low otherwise).
    response, local_mean = gabor_at(frame, period_px, angle_deg)
    lit = area & (local_mean > 0)
    if not lit.any():
        lit = area
    depth = 2 * np.abs(response[lit]) / np.maximum(np.abs(local_mean[lit]), np.finfo(float).tiny)
    return period_px, angle_deg, float(np.median(depth))
