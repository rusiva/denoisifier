"""Striped Region test frames and comparisons (ticket 05).

Frame geometry comes from protected.py: one region of semi-axes
max(5 P, 45) x max(6.6 P, 60) px, centred in a 512x512 frame, and the
two-region layout (TWO_REGION_*). ``iou`` and ``match`` compare a report with
the generator's truth; a truth region's pixels are ``truth_pixels`` (its soft
mask at or above TRUTH_LEVEL).
"""

from functools import cache

import numpy as np

from denoisifier import analyse
from denoisifier.synthetic import Emccd, StripedRegion, generate
from protected import (
    REGION_EDGE_PX,
    REGION_FRAME_SHAPE,
    REGION_SEMI_AXES_FLOOR_PX,
    REGION_SEMI_AXES_PERIODS,
    TWO_REGION_GAP_WINDOWS,
    TWO_REGION_SHAPE,
)

TYPICAL = dict(noise=Emccd())  # about 100 photons at the peak
# A truth region's pixels: its soft mask at or above this (the generator's
# ellipse is the 0.5 contour; ``synthetic.RegionTruth``).
TRUTH_LEVEL = 0.5


def truth_pixels(truth):
    """The pixels of a truth region (``RegionTruth``): mask >= TRUTH_LEVEL."""
    return truth.mask >= TRUTH_LEVEL


def semi_axes(period):
    """Test region semi-axes (rows, cols) for ``period``."""
    return tuple(
        max(k * period, floor)
        for k, floor in zip(REGION_SEMI_AXES_PERIODS, REGION_SEMI_AXES_FLOOR_PX, strict=True)
    )


def single_region(period, angle_deg, depth=0.5, center=None):
    rows, cols = REGION_FRAME_SHAPE
    if center is None:
        center = ((rows - 1) / 2, (cols - 1) / 2)
    return StripedRegion(
        center=center,
        semi_axes=semi_axes(period),
        rotation_deg=0.0,
        edge_px=REGION_EDGE_PX,
        period=float(period),
        angle_deg=float(angle_deg),
        modulation_depth=depth,
    )


def two_regions(
    left_period,
    right_period,
    angle_deg=(4.0, -6.0),
    depth=(0.5, 0.5),
    edge_px=REGION_EDGE_PX,
    gap_windows=TWO_REGION_GAP_WINDOWS,
):
    """Two regions side by side, each sized for its own Period, centred on the
    frame's middle row; the gap between their 0.5 contours is ``gap_windows``
    windows (3 Periods each) at the longer Period. ``depth`` is (left, right)."""
    rows, cols = TWO_REGION_SHAPE
    left_axes, right_axes = semi_axes(left_period), semi_axes(right_period)
    gap = gap_windows * 3 * max(left_period, right_period)
    span = 2 * left_axes[1] + gap + 2 * right_axes[1]
    left_c = (cols - 1) / 2 - span / 2 + left_axes[1]
    right_c = left_c + left_axes[1] + gap + right_axes[1]
    row_c = (rows - 1) / 2
    return [
        StripedRegion(
            center=(row_c, left_c),
            semi_axes=left_axes,
            rotation_deg=0.0,
            edge_px=edge_px,
            period=float(left_period),
            angle_deg=angle_deg[0],
            modulation_depth=depth[0],
        ),
        StripedRegion(
            center=(row_c, right_c),
            semi_axes=right_axes,
            rotation_deg=0.0,
            edge_px=edge_px,
            period=float(right_period),
            angle_deg=angle_deg[1],
            modulation_depth=depth[1],
        ),
    ]


@cache
def single_region_case(seed, period, angle_deg, mottle="scorched"):
    """(Synthetic, Report) for one typical-noise single-region frame, cached per run."""
    s = generate(
        seed=seed,
        shape=REGION_FRAME_SHAPE,
        mottle=mottle,
        regions=[single_region(period, angle_deg)],
        **TYPICAL,
    )
    return s, analyse(s.frame)


def iou(a, b):
    union = (a | b).sum()
    return float((a & b).sum() / union) if union else 0.0


def truth_bbox(mask):
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    return rows[0], rows[-1] + 1, cols[0], cols[-1] + 1


def match(report_regions, labels, truth_regions):
    """Pair each reported region with the truth region it overlaps most:
    a list of (region, truth) pairs, in report order."""
    pairs = []
    for region in report_regions:
        own = labels == region.label
        best = max(truth_regions, key=lambda t: (own & truth_pixels(t)).sum())
        pairs.append((region, best))
    return pairs


def assert_labels_consistent(report):
    """Labels take 0..N; each label's pixels fill its tight bbox and number area_px."""
    labels = report.labels
    assert labels.dtype == np.int32
    assert set(np.unique(labels)) <= set(range(len(report.regions) + 1))
    for k, region in enumerate(report.regions, start=1):
        assert region.label == k
        own = labels == k
        assert own.sum() == region.area_px > 0
        b = region.bbox
        assert truth_bbox(own) == (b.row_start, b.row_stop, b.col_start, b.col_stop)
