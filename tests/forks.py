"""Fork test frames (ticket 10; plan .scratch/stripe-detector/handoffs/10-plan.md, 5).

Every frame is ``generate(..., forks=[...])`` analysed at the default calibration, cached per
run (``shared_cache.normalised_cache``). Region frames use the ``regions.single_region``
geometry (512x512, scorched Mottle, depth 0.5, typical EMCCD noise) or ``big_region``, a round
region large enough that a fork near its centre lies about 4 Periods or more inside its edge.
Full frames are PROBE_SHAPE. Every fork point is a half-integer pair, so no pixel centre lies on
a fork. Binned frames are generated at sensor size and block-summed (``binning.py``).
"""

import math

from binning import bin_sensor_frame
from breaks import EMCCD, PI, through
from cases import CASES
from denoisifier import BinFactors, analyse
from denoisifier.synthetic import ForkPoint, StripedRegion, generate
from protected import (
    FORK_BIG_REGION_SEMI_FLOOR_PX,
    FORK_BIG_REGION_SEMI_PERIODS,
    FORK_NEAR_BREAK_PERIODS,
    FORK_PAIR_SEPARATION_PERIODS,
    FORK_TEST_SEEDS,
    PROBE_SHAPE,
    REGION_EDGE_PX,
    REGION_FRAME_SHAPE,
)
from regions import TYPICAL, single_region
from shared_cache import normalised_cache

# AC 2 (plan 5.2): the fork's offset from the region centre, per axis, in Periods (rounded to
# whole px, so the point stays half-integer), by seed.
AC2_OFFSETS_PERIODS = (-1.0, -0.5, 0.0, 0.5, 1.0)
# AC 3 (plan 5.2): line Angle offsets from the case Angle by seed % 3, jumps cycling by seed,
# and the fork's position along the line (Periods).
NEAR_LINE_OFFSETS_DEG = (0, 5, -5)
NEAR_JUMPS = (PI / 2, PI, -3 * PI / 4)
NEAR_ALONG_PERIODS = (-0.5, 0.0, 0.5)
# Pairs (plan 5.4): the tilt of the pair's axis from horizontal (deg), by seed.
PAIR_TILTS_DEG = (-20.0, -10.0, 0.0, 10.0, 20.0)


def _k(seed):
    return seed - FORK_TEST_SEEDS[0]


def half_integer(value):
    """The half-integer nearest ``value``."""
    return math.floor(value) + 0.5


def half_integer_point(row, col):
    return (half_integer(row), half_integer(col))


def ac2_direction(seed):
    return (1, -1)[seed % 2]


def ac2_offset(seed, period):
    """(rows, cols): the AC 2 fork's whole-px offset from the region centre."""
    k = _k(seed)
    n = len(AC2_OFFSETS_PERIODS)
    dy = AC2_OFFSETS_PERIODS[k % n]
    dx = AC2_OFFSETS_PERIODS[(2 * k + 1) % n]
    return round(dy * period), round(dx * period)


def big_region(period, angle_deg):
    """A round region of semi-axes max(FORK_BIG_REGION_SEMI_PERIODS x P,
    FORK_BIG_REGION_SEMI_FLOOR_PX) at the centre of REGION_FRAME_SHAPE, depth 0.5."""
    rows, cols = REGION_FRAME_SHAPE
    semi = max(FORK_BIG_REGION_SEMI_PERIODS * period, FORK_BIG_REGION_SEMI_FLOOR_PX)
    return StripedRegion(
        center=((rows - 1) / 2, (cols - 1) / 2),
        semi_axes=(semi, semi),
        rotation_deg=0.0,
        edge_px=REGION_EDGE_PX,
        period=float(period),
        angle_deg=float(angle_deg),
        modulation_depth=0.5,
    )


@normalised_cache
def fork_region_case(
    seed, *, direction, offset, breaks=(), noise=EMCCD, period=None, angle_deg=None
):
    """(Synthetic, Report): one ``single_region`` (CASES[seed % 10], or ``period`` and
    ``angle_deg``) with one fork at its centre plus ``offset`` (whole px, rows and cols), or
    none when ``direction`` is None. ``breaks``: ``PhaseBreakLine``s."""
    case = CASES[seed % 10]
    p = float(case.period if period is None else period)
    a = float(case.angle_deg if angle_deg is None else angle_deg)
    region = single_region(p, a)
    forks = []
    if direction is not None:
        point = (region.center[0] + offset[0], region.center[1] + offset[1])
        forks = [ForkPoint(point, direction)]
    s = generate(
        seed=seed,
        shape=REGION_FRAME_SHAPE,
        mottle="scorched",
        regions=[region],
        noise=noise,
        phase_breaks=list(breaks),
        forks=forks,
    )
    return s, analyse(s.frame)


def ac2_case(seed):
    """The AC 2 region frame of ``seed``."""
    period = CASES[seed % 10].period
    return fork_region_case(seed, direction=ac2_direction(seed), offset=ac2_offset(seed, period))


@normalised_cache
def fork_full_frame_case(seed, direction, bins=(1, 1), period=None, angle_deg=None):
    """(Synthetic at sensor size, Report, BinFactors): a PROBE_SHAPE frame of full-frame stripes
    (CASES[seed % 10], or ``period`` and ``angle_deg``; depth 0.5, typical noise, scorched
    Mottle) with one fork at the sensor centre (none when ``direction`` is None)."""
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
        forks=[] if direction is None else [ForkPoint(center, direction)],
        **TYPICAL,
    )
    factors = BinFactors(h, v)
    frame = s.frame if (h, v) == (1, 1) else bin_sensor_frame(s.frame, h, v)
    return s, analyse(frame, bin_factors=factors), factors


def _big_region_frame(seed, region, breaks, forks):
    s = generate(
        seed=seed,
        shape=REGION_FRAME_SHAPE,
        mottle="scorched",
        regions=[region],
        noise=EMCCD,
        phase_breaks=breaks,
        forks=forks,
    )
    return s, analyse(s.frame)


def near_break_layout(seed):
    """(line Angle, jump, side, along in Periods, direction) of the AC 3 frame of ``seed``."""
    k = _k(seed)
    a = CASES[seed % 10].angle_deg
    return (
        float(a + NEAR_LINE_OFFSETS_DEG[seed % 3]),
        NEAR_JUMPS[k % len(NEAR_JUMPS)],
        (1, -1)[k % 2],
        NEAR_ALONG_PERIODS[(k // 2) % len(NEAR_ALONG_PERIODS)],
        (1, -1)[(k // 2) % 2],
    )


@normalised_cache
def fork_near_break_case(seed):
    """(Synthetic, Report): ``big_region`` with one break through its centre and one fork
    FORK_NEAR_BREAK_PERIODS Periods from the line, on the side ``near_break_layout`` gives."""
    case = CASES[seed % 10]
    p = float(case.period)
    region = big_region(p, case.angle_deg)
    line_angle, jump, side, along, direction = near_break_layout(seed)
    t = math.radians(line_angle)
    off, run = side * FORK_NEAR_BREAK_PERIODS * p, along * p
    # The line's normal is (cos t, -sin t) in (row, col), its direction (sin t, cos t).
    point = half_integer_point(
        region.center[0] + off * math.cos(t) + run * math.sin(t),
        region.center[1] - off * math.sin(t) + run * math.cos(t),
    )
    line = through(region.center, 0.0, line_angle, jump)
    return _big_region_frame(seed, region, [line], [ForkPoint(point, direction)])


@normalised_cache
def fork_pair_case(seed):
    """(Synthetic, Report): ``big_region`` with two forks FORK_PAIR_SEPARATION_PERIODS Periods
    apart about its centre, the pair's axis tilted by seed; opposite directions on even seeds,
    equal on odd."""
    k = _k(seed)
    case = CASES[seed % 10]
    p = float(case.period)
    region = big_region(p, case.angle_deg)
    tilt = math.radians(PAIR_TILTS_DEG[k % len(PAIR_TILTS_DEG)])
    half = FORK_PAIR_SEPARATION_PERIODS * p / 2
    d1 = (1, -1)[(k // 2) % 2]
    d2 = -d1 if seed % 2 == 0 else d1
    cy, cx = region.center
    points = [
        half_integer_point(cy + s * half * math.sin(tilt), cx + s * half * math.cos(tilt))
        for s in (-1, 1)
    ]
    return _big_region_frame(seed, region, [], [ForkPoint(points[0], d1), ForkPoint(points[1], d2)])
