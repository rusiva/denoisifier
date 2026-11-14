"""Binned test frames (ticket 08): a frame generated at sensor size, block-summed.

``h`` bins along a row (columns), ``v`` along a column (rows), as
``denoisifier.BinFactors(horizontal=h, vertical=v)``.
"""

import numpy as np


def bin_sensor_frame(frame: np.ndarray, h: int, v: int) -> np.ndarray:
    """Sum each ``v`` x ``h`` block of sensor pixels into one frame pixel."""
    rows, cols = frame.shape
    assert rows % v == 0, f"{rows} rows are not a multiple of {v}"
    assert cols % h == 0, f"{cols} columns are not a multiple of {h}"
    return np.asarray(frame, dtype=float).reshape(rows // v, v, cols // h, h).sum(axis=(1, 3))


def bin_truth_mask(mask: np.ndarray, h: int, v: int) -> np.ndarray:
    """The mean of each ``v`` x ``h`` block of a (soft) truth mask."""
    return bin_sensor_frame(mask, h, v) / (h * v)
