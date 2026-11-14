"""The Phase Break finder (``denoisifier._local_phase``, ticket 09 plan 2.2) on noise-free
phasor fields and on noise-free generated frames.

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
    _finder_sigma_n,
    break_response,
    find_phase_breaks,
    frame_period,
    line_side,
    wrap_jump,
)
from denoisifier._local_stripes import _Spectrum
from denoisifier.synthetic import PhaseBreakLine, generate
from protected import (
    BREAK_EXACT_JUMP_TOL_RAD,
    BREAK_EXACT_POSITION_TOL_PERIODS,
    BREAK_PHASOR_FIELD_ATOL,
    BREAK_PHASOR_FIELD_RADIUS_PX,
    PHASE_BREAK_TEST_SEEDS,
)

ONE = BinFactors()
SHAPE = (200, 200)
CENTER = (99.5, 99.5)
PERIOD = 8.0
STRIPE_ANGLE = 0.0


def _grid():
    return np.mgrid[0 : SHAPE[0], 0 : SHAPE[1]].astype(float)


def _field(breaks=(), period=PERIOD, angle_deg=STRIPE_ANGLE, magnitude=None, winding=0):
    """exp(i (2 pi / P (x cos A + y sin A) + sum jump [side > 0] + winding * azimuth))."""
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
