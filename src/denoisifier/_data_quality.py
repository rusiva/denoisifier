"""Spike rejection and clip detection: the first steps of ``analyse`` (ticket 06).

``reject_spikes`` finds the Spike pixels and returns a working copy with each
one replaced by the median of its column neighbours; every later step of
``analyse`` runs on that copy, and the caller's frame is never changed.
``find_clipped`` finds the Clipped Pixels, which are left out of the
Modulation Depth only.

A pixel is a Spike pixel when its excess over the median of its column
neighbours (rows +-1 to +-``_SPIKE_NEIGHBOUR_ROWS``, itself excluded) is both
``_SPIKE_SIGMAS`` times the local noise scale and at least
``_SPIKE_FLOOR_FRACTION`` times the frame's peak-over-pedestal scale. Every
pixel is tested, clipped or not, so a saturated Spike on a dim column is a
Spike; a Spike saturated inside the clip plateau of a bright region cannot
exceed its neighbours by the floor and stays a Clipped Pixel.

Limits: the count is reliable from about 30 photons at the peak (at 10
photons a twice-the-peak Spike sits in the tail of the EM gain's excess
noise); two overlapping hits forming a vertical run longer than three pixels
are partly missed; hot pixels dimmer than the floor and long tracks are not
rejected.

Constants: prototype P1 (``.scratch/stripe-detector/evidence/06-prototype-p1.md``,
seeds 396_000-396_399; 30 spike events per frame, 40 frames per setting).
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import map_coordinates, median_filter

# Column neighbours on each side (rows +-1..3, 6 values, self excluded): a
# vertical streak of up to 3 pixels leaves at least 4 clean neighbours, so
# their upper middle value is clean. Near-vertical stripes vary little along
# a column, so the median follows them.
_SPIKE_NEIGHBOUR_ROWS = 3
# Excess over the column median, in local noise scales. P1: at 8 (with the
# floor below) 0 false spike pixels on 80 typical spike-free frames, and
# every typical setting within max(2, 5%) of the truth.
_SPIKE_SIGMAS = 8.0
# Excess over the column median, as a fraction of the frame's scale (peak
# over Pedestal). P1: 1.0 keeps Phase Break and P 3 stripe frames at noise 0
# free of false spike pixels; the dimmest generated Spikes (2x the clean
# maximum) still pass (2.0-2.2x boundary run).
_SPIKE_FLOOR_FRACTION = 1.0
# The scale's peak: this-th largest value of the 3x3-median frame, so
# overlapping hits cannot lift it (P1, "rank10" against "max3").
_SPIKE_PEAK_RANK = 10
# The scale's Pedestal: this percentile of the 3x3-median frame, so bias
# offsets and constant dark subtraction leave the scale unchanged (plan B3).
# Not swept: P1 ran every setting with 5 and found 0 false spike pixels on 80
# typical spike-free frames (100 photons, m 0 and 0.5) and 0 flags on the
# Solis crop raw (bias 713 counts), +1000 and minus half its median.
_SPIKE_PEDESTAL_PERCENTILE = 5.0
# The local noise scale: median |excess| over tiles of this side (px),
# bilinearly interpolated to the frame. Not swept: P1 ran every setting with
# 16 (256 pixels per tile median); with it, 0 false spike pixels on 80 typical
# spike-free frames and on 30-photon m 0 frames (0.25 per frame, max 2, at
# m 0.5), recall >= 0.9996 from 30 photons up.
_NOISE_TILE_PX = 16
# Median absolute deviation to Gaussian standard deviation.
_MAD_TO_SIGMA = 1.4826

# Clip auto-detection: the frame's maximum is a clip level when at least
# this many pixels share it (an unclipped frame's maximum is almost always
# unique; prototype P2, evidence/06-prototype-p2.md).
_MIN_CLIPPED_PIXELS = 4


def find_clipped(frame: np.ndarray, clip_level: float | None) -> np.ndarray:
    """Boolean, frame shape: the pixels at or above the clip level.

    ``clip_level=None`` detects it: the frame's maximum, when at least
    ``_MIN_CLIPPED_PIXELS`` pixels share it and the frame is not constant (a
    constant frame shows no level); otherwise nothing is clipped. A float is
    used as given (``inf``: nothing is clipped).
    """
    if clip_level is not None:
        return np.asarray(frame >= clip_level)
    top = frame.max()
    at_top = frame == top
    if at_top.sum() >= _MIN_CLIPPED_PIXELS and frame.min() < top:
        return np.asarray(at_top)
    return np.zeros(frame.shape, dtype=bool)


def reject_spikes(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(working copy, spike mask)``: the Spike pixels (bool, frame shape)
    and a copy of ``frame`` with each one replaced by the median of its column
    neighbours. ``frame`` (at least ``2 * _SPIKE_NEIGHBOUR_ROWS + 1`` rows) is
    not modified."""
    med = _column_median(frame)
    excess = frame - med
    noise = _MAD_TO_SIGMA * _tile_median(np.abs(excess))
    smooth = median_filter(frame, size=3, mode="mirror").ravel()
    peak = np.partition(smooth, smooth.size - _SPIKE_PEAK_RANK)[smooth.size - _SPIKE_PEAK_RANK]
    scale = peak - np.percentile(smooth, _SPIKE_PEDESTAL_PERCENTILE)
    spikes = (excess > _SPIKE_SIGMAS * noise) & (excess > _SPIKE_FLOOR_FRACTION * scale)
    work = frame.copy()
    work[spikes] = med[spikes]
    return work, np.asarray(spikes)


def _column_median(frame: np.ndarray) -> np.ndarray:
    """Median of each pixel's column neighbours at rows +-1..+-n (2n values,
    self excluded), the upper middle value. In the top and bottom n rows the
    window shifts inward (rows 0..2n or R-2n-1..R-1, self excluded) instead of
    reflecting, so a vertical streak at the edge is never its own neighbour."""
    n = _SPIKE_NEIGHBOUR_ROWS
    footprint = np.ones((2 * n + 1, 1), dtype=bool)
    footprint[n] = False
    med = median_filter(frame, footprint=footprint, mode="mirror")
    rows = frame.shape[0]
    for i in [*range(n), *range(rows - n, rows)]:
        start = 0 if i < n else rows - 2 * n - 1
        window = [j for j in range(start, start + 2 * n + 1) if j != i]
        med[i] = np.sort(frame[window], axis=0)[n]
    return np.asarray(med)


def _tile_median(values: np.ndarray) -> np.ndarray:
    """Median over ``_NOISE_TILE_PX``-square tiles (edge tiles padded by
    repeating the edge), bilinearly interpolated back to the frame."""
    tile = _NOISE_TILE_PX
    rows, cols = values.shape
    tiles_r, tiles_c = -(-rows // tile), -(-cols // tile)
    padded = np.pad(values, ((0, tiles_r * tile - rows), (0, tiles_c * tile - cols)), mode="edge")
    blocks = padded.reshape(tiles_r, tile, tiles_c, tile).transpose(0, 2, 1, 3)
    medians = np.median(blocks.reshape(tiles_r, tiles_c, -1), axis=2)
    y = (np.arange(rows) + 0.5) / tile - 0.5
    x = (np.arange(cols) + 0.5) / tile - 0.5
    yy, xx = np.meshgrid(y, x, indexing="ij")
    return np.asarray(map_coordinates(medians, [yy, xx], order=1, mode="nearest"))
