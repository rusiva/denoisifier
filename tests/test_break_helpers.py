"""The Phase Break test helpers (truth_match.py, plan 5.1 and 5.3) on hand-built breaks."""

import math
from types import SimpleNamespace

import numpy as np
import pytest

from denoisifier import BinFactors, PhaseBreak
from denoisifier.synthetic import BreakTruth
from truth_match import (
    assert_break_matches,
    assert_region_covers_both_sides,
    break_problems,
    truth_lit_mask,
)

ONE = BinFactors()
PERIOD = 5.0
SHAPE = (100, 100)


def _truth(angle=0.0, jump=math.pi / 2):
    return BreakTruth(
        point=(50.5, 50.5), line_angle_deg=angle, jump_rad=jump, shifted=np.zeros(SHAPE, bool)
    )


def _box(r0, r1, c0, c1):
    mask = np.zeros(SHAPE, dtype=bool)
    mask[r0:r1, c0:c1] = True
    return mask


REGION = _box(20, 80, 10, 90)  # its chord along row 50.5 runs from col 10 to col 89


def _problems(line, jump=math.pi / 2, truth=None):
    brk = PhaseBreak(region=1, line=line, jump_rad=jump)
    return break_problems(brk, truth or _truth(), REGION, REGION, PERIOD, ONE)


def test_a_break_on_the_true_line_matches():
    assert _problems(((50.0, 10.0), (51.0, 89.0))) == []


def test_reversed_points_with_a_negated_jump_are_the_same_break():
    assert _problems(((51.0, 89.0), (50.0, 10.0)), jump=-math.pi / 2) == []
    assert _problems(((51.0, 89.0), (50.0, 10.0)), jump=math.pi / 2) != []


@pytest.mark.parametrize(
    ("line", "jump", "rule"),
    [
        (((57.0, 10.0), (57.0, 89.0)), math.pi / 2, "line"),
        (((50.5, 10.0), (50.5, 50.0)), math.pi / 2, "coverage"),
        (((50.5, 0.0), (50.5, 89.0)), math.pi / 2, "overshoot"),
        (((50.5, 10.0), (50.5, 89.0)), math.pi / 2 + 0.8, "jump"),
    ],
)
def test_each_rule_rejects_on_its_own(line, jump, rule):
    (problem,) = _problems(line, jump)
    assert problem.startswith(rule)


def test_jump_tolerance_wraps_around_pi():
    truth = _truth(jump=math.pi)
    assert _problems(((50.5, 10.0), (50.5, 89.0)), jump=-math.pi + 0.1, truth=truth) == []


def test_exactly_one_break_must_match():
    good = PhaseBreak(region=1, line=((50.5, 10.0), (50.5, 89.0)), jump_rad=math.pi / 2)
    far = PhaseBreak(region=1, line=((70.5, 10.0), (70.5, 89.0)), jump_rad=math.pi / 2)
    assert assert_break_matches([far, good], _truth(), REGION, REGION, PERIOD, ONE) is good
    with pytest.raises(AssertionError):
        assert_break_matches([good, good], _truth(), REGION, REGION, PERIOD, ONE)
    with pytest.raises(AssertionError):
        assert_break_matches([far], _truth(), REGION, REGION, PERIOD, ONE)


def test_binned_points_are_compared_at_their_sensor_centres():
    """Under 1x2 frame row r is sensor rows 2r and 2r + 1, centred at 2r + 0.5."""
    truth = BreakTruth(
        point=(60.5, 50.5), line_angle_deg=0.0, jump_rad=1.0, shifted=np.zeros(SHAPE, bool)
    )
    bins = BinFactors(1, 2)
    brk = PhaseBreak(region=1, line=((30.0, 10.0), (30.0, 89.0)), jump_rad=1.0)
    assert break_problems(brk, truth, REGION, REGION, PERIOD, bins) == []


def test_region_covering_both_sides_passes():
    assert_region_covers_both_sides(REGION, REGION, _truth(), PERIOD, ONE)


def test_region_covering_one_side_fails():
    with pytest.raises(AssertionError, match="positive side"):
        assert_region_covers_both_sides(_box(20, 50, 10, 90), REGION, _truth(), PERIOD, ONE)


def test_empty_side_fails():
    """critic-3 section 5: a side with no truth pixels beyond the exclusion is a failure."""
    upper = _box(20, 55, 10, 90)  # nothing farther than 2.5 P below row 50.5
    with pytest.raises(AssertionError, match="no truth pixels on the positive side"):
        assert_region_covers_both_sides(upper, upper, _truth(), PERIOD, ONE)


def test_truth_lit_mask_is_block_meaned_from_the_sensor():
    clean = np.zeros((100, 200))
    clean[30:70, 60:140] = 1.0
    lit = truth_lit_mask(SimpleNamespace(clean=clean), BinFactors(2, 1))
    assert lit.shape == (100, 100)
    assert lit[50, 50]
    assert not lit[0, 0]
    assert not lit[50, 5]
