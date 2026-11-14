"""Phase Break test frames (ticket 09; plan .scratch/stripe-detector/handoffs/09-plan.md, 5).

Every frame is ``generate(..., phase_breaks=[...])`` analysed at the default calibration, cached
per run (``shared_cache.normalised_cache``). Region frames use the ``regions.single_region``
geometry (512x512, scorched Mottle, depth 0.5); full frames are PROBE_SHAPE. Lines pass through
the frame's or the region's centre, a half-integer point, so no pixel centre lies on them.
Binned frames are generated at sensor size and block-summed (``binning.py``).
"""

import math

import numpy as np

from binning import bin_sensor_frame
from cases import CASES
from denoisifier import BinFactors, analyse
from denoisifier.synthetic import Emccd, PhaseBreakLine, StripedRegion, generate
from protected import (
    BREAK_PAIR_SEPARATION_PERIODS,
    PHASE_BREAK_TEST_SEEDS,
    PROBE_SHAPE,
    REGION_FRAME_SHAPE,
    TWO_REGION_SHAPE,
)
from regions import TYPICAL, single_region, two_regions
from shared_cache import normalised_cache

PI = math.pi
# AC 2 (plan 5.2): line Angle offsets from the case Angle by seed % 3, jumps cycling by seed.
AC2_LINE_OFFSETS_DEG = (0, 5, -5)
AC2_JUMPS = (PI / 2, 2 * PI / 3, PI, -PI / 2, -3 * PI / 4)
GAUSSIAN = 0.01  # the generator's default Gaussian noise
EMCCD = Emccd()  # typical noise, about 100 photons at the peak


def ac2_line(seed):
    """(line Angle, jump) of the AC 2 frame of ``seed``."""
    case = CASES[seed % 10]
    k = seed - PHASE_BREAK_TEST_SEEDS[0]
    return float(case.angle_deg + AC2_LINE_OFFSETS_DEG[seed % 3]), AC2_JUMPS[k % len(AC2_JUMPS)]


def through(center, offset_px, line_angle_deg, jump):
    """A line at ``offset_px`` from ``center`` along its normal (toward its positive side)."""
    t = math.radians(line_angle_deg)
    point = (center[0] + offset_px * math.cos(t), center[1] - offset_px * math.sin(t))
    return PhaseBreakLine(point, line_angle_deg, jump)


@normalised_cache
def break_region_case(
    seed, jump, line_angle_deg, *, noise=EMCCD, period=None, angle_deg=None, height_periods=None
):
    """(Synthetic, Report): one region (CASES[seed % 10], or ``period`` and ``angle_deg``) with
    one break through its centre. ``height_periods`` sets the region's full height in Periods."""
    case = CASES[seed % 10]
    p = float(case.period if period is None else period)
    a = float(case.angle_deg if angle_deg is None else angle_deg)
    region = single_region(p, a)
    if height_periods is not None:
        region = StripedRegion(
            center=region.center,
            semi_axes=(height_periods / 2 * p, region.semi_axes[1]),
            rotation_deg=region.rotation_deg,
            edge_px=region.edge_px,
            period=p,
            angle_deg=a,
            modulation_depth=region.modulation_depth,
        )
    breaks = [] if jump is None else [through(region.center, 0.0, line_angle_deg, jump)]
    s = generate(
        seed=seed,
        shape=REGION_FRAME_SHAPE,
        mottle="scorched",
        regions=[region],
        noise=noise,
        phase_breaks=breaks,
    )
    return s, analyse(s.frame)


@normalised_cache
def break_full_frame_case(seed, breaks, bins=(1, 1), period=None, angle_deg=None):
    """(Synthetic at sensor size, Report, BinFactors): a PROBE_SHAPE frame of full-frame stripes
    (CASES[seed % 10], or ``period`` and ``angle_deg``; depth 0.5, typical noise, scorched
    Mottle). ``breaks`` is a tuple of (offset in Periods along the normal from the sensor
    centre, line Angle, jump)."""
    h, v = bins
    case = CASES[seed % 10]
    p = float(case.period if period is None else period)
    a = float(case.angle_deg if angle_deg is None else angle_deg)
    rows, cols = PROBE_SHAPE
    sensor = (rows * v, cols * h)
    center = ((sensor[0] - 1) / 2, (sensor[1] - 1) / 2)
    s = generate(
        seed=seed,
        shape=sensor,
        period=p,
        angle_deg=a,
        modulation_depth=0.5,
        mottle="scorched",
        phase_breaks=[through(center, off * p, la, j) for off, la, j in breaks],
        **TYPICAL,
    )
    factors = BinFactors(h, v)
    frame = s.frame if (h, v) == (1, 1) else bin_sensor_frame(s.frame, h, v)
    return s, analyse(frame, bin_factors=factors), factors


def full_frame_jump(seed):
    """AC 2 full frames: pi/2 and pi alternating by seed."""
    return (PI / 2, PI)[(seed - PHASE_BREAK_TEST_SEEDS[0]) % 2]


def break_pair(seed):
    """Two horizontal breaks BREAK_PAIR_SEPARATION_PERIODS apart about the centre, pi/2 and pi."""
    half = BREAK_PAIR_SEPARATION_PERIODS / 2
    return break_full_frame_case(seed, ((-half, 0.0, PI / 2), (half, 0.0, PI)))


def two_break_layout(seed):
    """(Period, gap windows, Angles, jump) of plan 5.4's two-region frame for ``seed``: two
    equal-Period regions whose Angles differ by more than the merge rule allows, so a break
    crossing both must leave them apart."""
    k = seed - PHASE_BREAK_TEST_SEEDS[0]
    p = (5, 8, 12, 6)[k % 4]
    g = (2 / 3, 1.0)[(k // 4) % 2]
    offset = (3.0, 10.0)[(k // 2) % 2]
    a = float(CASES[seed % 10].angle_deg)
    # Both Angles inside the searched range (within 10 deg of vertical): mirror the offset when
    # a + offset would leave it (09-critic-5).
    second = a + offset if abs(a + offset) <= 10 else a - offset
    return p, g, (a, second), (PI, PI / 2)[k % 2]


@normalised_cache
def two_break_case(seed):
    """(Synthetic, Report): two equal-Period regions whose Angles differ by more than the merge
    rule allows, crossed by one horizontal break through the frame centre."""
    p, g, angles, jump = two_break_layout(seed)
    rows, cols = TWO_REGION_SHAPE
    center = ((rows - 1) / 2, (cols - 1) / 2)
    s = generate(
        seed=seed,
        shape=TWO_REGION_SHAPE,
        mottle="scorched",
        regions=two_regions(p, p, angle_deg=angles, gap_windows=g),
        phase_breaks=[through(center, 0.0, 0.0, jump)],
        **TYPICAL,
    )
    return s, analyse(s.frame)


def compatible_pair_frame(seed):
    """Synthetic: ``two_break_case``'s layout for ``seed`` with no break and both regions at the
    first Angle, so the two regions are _compatible and close enough for the pass to search the
    gap between them for a bridging break."""
    p, g, (a, _), _ = two_break_layout(seed)
    return generate(
        seed=seed,
        shape=TWO_REGION_SHAPE,
        mottle="scorched",
        regions=two_regions(p, p, angle_deg=(a, a), gap_windows=g),
        **TYPICAL,
    )


def region_breaks(report, label):
    return [b for b in report.phase_breaks if b.region == label]


def ones(shape):
    return np.ones(shape, dtype=bool)
