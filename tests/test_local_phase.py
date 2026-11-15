"""The Phase Break finder (``denoisifier._local_phase``, ticket 09 plan 2.2) and the Fork finder
(ticket 10 plan 2.2) on noise-free phasor fields and on noise-free generated frames.

The phasor field is what the finder is given on the real path: ``break_response`` of stripes with
a sharp Phase Break, i.e. ``exp(i k . r)`` times the Phase Jump blurred by the finder's own window,
``(1 - Phi(side / sigma_n)) + Phi(side / sigma_n) exp(i jump)``
(``test_the_phasor_field_is_the_finder_response_to_a_sharp_phase_break`` checks this). The plan's
unblurred field ``exp(i (k . r + jump [side > 0]))`` is outside the finder's contract (ticket 09
Comments, 09-critic-4)."""

import math

import numpy as np
import pytest
from scipy.special import ndtr

from denoisifier import BinFactors
from denoisifier._local_phase import (
    _BREAK_FIT_HALF_WINDOW_PERIODS,
    _BREAK_MIN_FRAME_PERIOD_PX,
    _FORK_DOMAIN_CLOSE_PERIODS,
    _FORK_MIN_EVIDENCE,
    _finder_sigma_n,
    break_response,
    find_forks,
    find_phase_breaks,
    fork_domain,
    frame_period,
    line_side,
    wrap_jump,
)
from denoisifier._local_stripes import _Spectrum
from denoisifier.synthetic import ForkPoint, PhaseBreakLine, generate
from protected import (
    BREAK_EXACT_JUMP_TOL_RAD,
    BREAK_EXACT_POSITION_TOL_PERIODS,
    BREAK_PHASOR_FIELD_ATOL,
    BREAK_PHASOR_FIELD_RADIUS_PX,
    FORK_EXACT_POSITION_TOL_PERIODS,
    FORK_NEAR_BREAK_PERIODS,
    FORK_PAIR_SEPARATION_PERIODS,
    FORK_TEST_SEEDS,
    PHASE_BREAK_TEST_SEEDS,
)

ONE = BinFactors()
SHAPE = (200, 200)
CENTER = (99.5, 99.5)
PERIOD = 8.0
STRIPE_ANGLE = 0.0


def _grid():
    return np.mgrid[0 : SHAPE[0], 0 : SHAPE[1]].astype(float)


def _field(breaks=(), period=PERIOD, angle_deg=STRIPE_ANGLE, magnitude=None, winding=0, forks=()):
    """exp(i (2 pi / P (x cos A + y sin A) + sum jump [side > 0] + winding * azimuth)), times
    exp(i d atan2(y - y0, x - x0)) for each fork ((y0, x0), d) of ``forks``."""
    y, x = _grid()
    t = math.radians(angle_deg)
    phase = 2 * math.pi / period * (x * math.cos(t) + y * math.sin(t))
    z = np.exp(1j * phase)
    for point, line_angle, jump in breaks:
        step = ndtr(
            line_side(y, x, point, line_angle) / _finder_sigma_n(period, angle_deg, line_angle)
        )
        z = z * (1 - step + step * np.exp(1j * jump))
    if winding:
        z = z * np.exp(1j * winding * np.arctan2(y - CENTER[0], x - CENTER[1]))
    for (y0, x0), d in forks:
        z = z * np.exp(1j * d * np.arctan2(y - y0, x - x0))
    return z if magnitude is None else magnitude * z


def _disc(radius=90.0):
    y, x = _grid()
    return np.hypot(y - CENTER[0], x - CENTER[1]) <= radius


def _canonical(line_angle, jump):
    if line_angle > 90:
        return line_angle - 180, -jump
    if line_angle <= -90:
        return line_angle + 180, -jump
    return line_angle, jump


def _aligned_jump(found, line_angle_deg):
    """The found jump with directions aligned (plan 5.1): flipped iff the found direction and
    the true direction have a negative dot product (a line near 90 deg may come out at -89)."""
    dot = math.cos(math.radians(found.line_angle_deg - line_angle_deg))
    return found.jump_rad if dot >= 0 else -found.jump_rad


def _assert_on_line(found, point, line_angle_deg, domain, period=PERIOD):
    """``found`` lies within the exact tolerance of the true line wherever the true line crosses
    ``domain`` (both ends of its chord), and their angles agree."""
    y, x = _grid()
    t = math.radians(line_angle_deg)
    on = domain & (np.abs(line_side(y, x, point, line_angle_deg)) <= 0.5)
    along = math.cos(t) * (x[on] - point[1]) + math.sin(t) * (y[on] - point[0])
    for u in (along.min(), along.max()):
        py, px = point[0] + u * math.sin(t), point[1] + u * math.cos(t)
        d = line_side(py, px, found.point, found.line_angle_deg)
        assert abs(d) <= BREAK_EXACT_POSITION_TOL_PERIODS * period, (u, d)


@pytest.mark.parametrize("jump", [math.pi / 2, -math.pi / 2, math.pi])
@pytest.mark.parametrize("line_angle", [0, 30, 60, 90, 135])
def test_a_break_is_found_on_its_line_with_its_jump(line_angle, jump):
    point = (CENTER[0] + 3.3, CENTER[1] - 1.7)
    domain = _disc()
    z = _field([(point, line_angle, jump)])
    (found,) = find_phase_breaks(z, domain, PERIOD, STRIPE_ANGLE, ONE)
    want_angle, want_jump = _canonical(line_angle, jump)
    assert -90 < found.line_angle_deg <= 90
    _assert_on_line(found, point, want_angle, domain)
    assert abs(wrap_jump(_aligned_jump(found, want_angle) - want_jump)) <= BREAK_EXACT_JUMP_TOL_RAD
    assert found.evidence > 0


def test_a_positive_jump_is_found_positive():
    """C1 at the finder: +pi/2 on the positive side of a 10-deg line is reported as +pi/2."""
    point = CENTER
    z = _field([(point, 10.0, math.pi / 2)])
    (found,) = find_phase_breaks(z, _disc(), PERIOD, STRIPE_ANGLE, ONE)
    assert abs(found.jump_rad - math.pi / 2) <= BREAK_EXACT_JUMP_TOL_RAD


def test_a_break_free_field_has_no_break():
    assert find_phase_breaks(_field(), _disc(), PERIOD, STRIPE_ANGLE, ONE) == []


@pytest.mark.parametrize("winding", [1, -1])
def test_a_winding_is_not_a_break(winding):
    assert find_phase_breaks(_field(winding=winding), _disc(), PERIOD, STRIPE_ANGLE, ONE) == []


def test_a_break_through_a_dim_gap_between_two_parts_is_found():
    """The bridge's case: two half-discs with a dim band between them and a jump across it,
    searched on the union plus the gap, give one break through the gap."""
    y, _ = _grid()
    gap = np.abs(y - CENTER[0]) <= 1.5 * PERIOD
    magnitude = np.where(gap, 0.05, 1.0)
    z = _field([(CENTER, 0.0, math.pi)], magnitude=magnitude)
    domain = _disc()
    (found,) = find_phase_breaks(z, domain, PERIOD, STRIPE_ANGLE, ONE)
    _assert_on_line(found, CENTER, 0.0, domain)
    assert abs(wrap_jump(found.jump_rad - math.pi)) <= BREAK_EXACT_JUMP_TOL_RAD


def test_a_region_too_short_across_the_line_has_no_break():
    """The small-region rule: a region under 2 x the fit half-window across every line gets no
    break (the rule holds per line angle: a wide, short region can still hold a slightly
    tilted line, so the domain is a disc)."""
    diameter = 2 * _BREAK_FIT_HALF_WINDOW_PERIODS * PERIOD - PERIOD
    domain = _disc(diameter / 2)
    z = _field([(CENTER, 0.0, math.pi)])
    assert find_phase_breaks(z, domain, PERIOD, STRIPE_ANGLE, ONE) == []


def test_breaks_are_not_searched_under_the_frame_period_limit():
    bins = BinFactors(2, 1)
    period = 2 * _BREAK_MIN_FRAME_PERIOD_PX - 0.3  # frame Period 2.35 at Angle 0 under 2x1
    assert frame_period(period, 0.0, bins) < _BREAK_MIN_FRAME_PERIOD_PX
    z = _field([(CENTER, 0.0, math.pi)], period=period / 2)
    assert find_phase_breaks(z, _disc(), period, 0.0, bins) == []


def test_frame_period_is_along_the_stripe_normal_in_frame_px():
    assert frame_period(8.0, 0.0, BinFactors(2, 1)) == pytest.approx(4.0)
    assert frame_period(8.0, 90.0, BinFactors(2, 1)) == pytest.approx(8.0)
    assert frame_period(8.0, 0.0, ONE) == pytest.approx(8.0)


def test_break_response_finds_a_break_in_a_generated_frame():
    """Noise-free generated stripes with one break: the finder's response, then the finder."""
    point = (127.5, 127.5)
    s = generate(
        seed=PHASE_BREAK_TEST_SEEDS[0],
        noise=0.0,
        period=PERIOD,
        angle_deg=STRIPE_ANGLE,
        modulation_depth=0.5,
        phase_breaks=[PhaseBreakLine(point, 10.0, math.pi / 2)],
    )
    z = break_response(_Spectrum(s.frame, ONE), PERIOD, STRIPE_ANGLE)
    assert z.shape == s.frame.shape
    y, x = np.mgrid[0:256, 0:256]
    domain = np.hypot(y - point[0], x - point[1]) <= 100
    (found,) = find_phase_breaks(z, domain, PERIOD, STRIPE_ANGLE, ONE)
    t = math.radians(10.0)
    for u in (-90.0, 90.0):
        d = line_side(
            point[0] + u * math.sin(t),
            point[1] + u * math.cos(t),
            found.point,
            found.line_angle_deg,
        )
        assert abs(d) <= BREAK_EXACT_POSITION_TOL_PERIODS * PERIOD
    assert abs(found.jump_rad - math.pi / 2) <= BREAK_EXACT_JUMP_TOL_RAD


@pytest.mark.parametrize("line_angle", [0.0, 90.0])
def test_the_phasor_field_is_the_finder_response_to_a_sharp_phase_break(line_angle):
    """``break_response`` of noise-free stripes with a sharp Phase Break, over twice the depth,
    is the blurred-step phasor field away from the frame edge."""
    point = (CENTER[0] + 3.3, CENTER[1] - 1.7)
    y, x = _grid()
    depth = 0.5
    jump = math.pi / 2
    stripes = 2 * math.pi / PERIOD * x + jump * (line_side(y, x, point, line_angle) > 0)
    frame = 1 + depth * np.cos(stripes)
    z = break_response(_Spectrum(frame, ONE), PERIOD, STRIPE_ANGLE) / depth
    inner = _disc(BREAK_PHASOR_FIELD_RADIUS_PX)
    error = np.abs(z - _field([(point, line_angle, jump)]))[inner].max()
    assert error <= BREAK_PHASOR_FIELD_ATOL


def test_jumps_wrap_to_the_glossary_range():
    """``wrap_jump`` maps to (-pi, pi], the Phase Jump's range: -pi becomes pi, values already in
    range come back exactly, and values outside move by whole turns."""
    inside = np.array([np.nextafter(-math.pi, 0.0), -1.0, 0.0, 1e-20, 2.0, math.pi])
    assert np.array_equal(wrap_jump(inside), inside)
    assert wrap_jump(-math.pi) == math.pi
    assert wrap_jump(3 * math.pi) == pytest.approx(math.pi)
    assert wrap_jump(1.5 * math.pi) == pytest.approx(-0.5 * math.pi)
    assert wrap_jump(-1.5 * math.pi) == pytest.approx(0.5 * math.pi)


# --- Forks (ticket 10) ---------------------------------------------------------------------

FORK_SHAPE = (256, 256)
FORK_POINT = (127.5, 127.5)  # half-integer: no pixel centre on the fork


def _fork_frame_response(period, angle_deg, forks):
    """The finder's real input (09 critic-4 1a): ``break_response`` of a noise-free generated
    full frame with ``forks`` ((point, direction)), over the depth."""
    depth = 0.5
    s = generate(
        seed=FORK_TEST_SEEDS[0],
        shape=FORK_SHAPE,
        noise=0.0,
        period=period,
        angle_deg=angle_deg,
        modulation_depth=depth,
        forks=[ForkPoint(p, d) for p, d in forks],
    )
    return break_response(_Spectrum(s.frame, ONE), period, angle_deg) / depth


def _fork_disc(radius=110.0):
    y, x = np.mgrid[0 : FORK_SHAPE[0], 0 : FORK_SHAPE[1]]
    return np.hypot(y - FORK_POINT[0], x - FORK_POINT[1]) <= radius


def _near(found, point, period):
    return math.hypot(found.point[0] - point[0], found.point[1] - point[1]) <= (
        FORK_EXACT_POSITION_TOL_PERIODS * period
    )


@pytest.mark.parametrize("direction", [1, -1])
@pytest.mark.parametrize("angle", [0.0, 10.0, -10.0])
@pytest.mark.parametrize("period", [3.0, 5.0, 8.0, 20.0])
def test_a_fork_is_found_at_its_point_with_its_direction(period, angle, direction):
    z = _fork_frame_response(period, angle, [(FORK_POINT, direction)])
    (found,) = find_forks(z, _fork_disc(), period, angle, ONE)
    assert _near(found, FORK_POINT, period), found
    assert found.direction == direction
    assert found.evidence >= _FORK_MIN_EVIDENCE


def test_a_plane_wave_has_no_fork():
    assert find_forks(_field(), _disc(), PERIOD, STRIPE_ANGLE, ONE) == []


def test_a_plane_wave_off_the_searched_carrier_has_no_fork():
    """The finder demodulates by the field's own median carrier: stripes 10 % off in Period
    and 3 deg off in Angle from the searched ones give no fork."""
    z = _field(period=1.1 * PERIOD, angle_deg=STRIPE_ANGLE + 3.0)
    assert find_forks(z, _disc(), PERIOD, STRIPE_ANGLE, ONE) == []


def test_a_plane_wave_on_a_disc_cut_by_a_straight_edge_has_no_fork():
    y, _ = _grid()
    domain = _disc() & (y <= CENTER[0] + 30.0)
    assert find_forks(_field(), domain, PERIOD, STRIPE_ANGLE, ONE) == []


def test_a_sharp_phase_break_is_not_a_fork():
    z = _field([(CENTER, 0.0, math.pi)])
    assert find_forks(z, _disc(), PERIOD, STRIPE_ANGLE, ONE) == []


def test_a_fork_near_an_explained_break_is_found_alone():
    """A fork FORK_NEAR_BREAK_PERIODS Periods from a pi break's line, with the found break
    passed in: the fork only."""
    point = (CENTER[0] + FORK_NEAR_BREAK_PERIODS * PERIOD, CENTER[1] + 0.5)
    z = _field([(CENTER, 0.0, math.pi)], forks=[(point, 1)])
    breaks = find_phase_breaks(z, _disc(), PERIOD, STRIPE_ANGLE, ONE)
    assert len(breaks) == 1
    (found,) = find_forks(z, _disc(), PERIOD, STRIPE_ANGLE, ONE, breaks)
    assert _near(found, point, PERIOD), found
    assert found.direction == 1


def test_an_opposite_pair_is_found_as_two_forks():
    half = FORK_PAIR_SEPARATION_PERIODS * PERIOD / 2
    points = [(CENTER[0], CENTER[1] - half), (CENTER[0], CENTER[1] + half)]
    z = _field(forks=[(points[0], 1), (points[1], -1)])
    found = find_forks(z, _disc(), PERIOD, STRIPE_ANGLE, ONE)
    strong = [f for f in found if f.evidence >= _FORK_MIN_EVIDENCE]
    assert len(strong) == 2, found
    for point, d in zip(points, (1, -1), strict=True):
        (match,) = [f for f in strong if _near(f, point, PERIOD)]
        assert match.direction == d


def test_forks_are_not_searched_under_the_frame_period_limit():
    bins = BinFactors(2, 1)
    period = 2 * _BREAK_MIN_FRAME_PERIOD_PX - 0.3  # frame Period 2.35 at Angle 0 under 2x1
    z = _field(period=period / 2, forks=[(CENTER, 1)])
    assert find_forks(z, _disc(), period, 0.0, bins) == []


def test_fork_domain_keeps_a_convex_region():
    domain = _disc(60.0)
    none = np.zeros_like(domain)
    assert np.array_equal(fork_domain(domain, none, PERIOD, ONE), domain)


def test_fork_domain_fills_a_notch_narrower_than_the_closing_disc():
    y, x = _grid()
    notch = (np.abs(x - CENTER[1]) <= _FORK_DOMAIN_CLOSE_PERIODS * PERIOD / 2) & (
        y >= CENTER[0] + 30.0
    )
    region = _disc(60.0) & ~notch
    filled = fork_domain(region, np.zeros_like(region), PERIOD, ONE)
    assert filled[_disc(60.0) & notch & (y <= CENTER[0] + 50.0)].all()
    assert not (filled & ~_disc(61.0)).any()


def test_fork_domain_leaves_out_other_regions():
    y, x = _grid()
    region = _disc(60.0)
    other = (np.abs(y - CENTER[0]) <= 5) & (x >= CENTER[1] + 40.0)
    domain = fork_domain(region & ~other, other, PERIOD, ONE)
    assert not (domain & other).any()
