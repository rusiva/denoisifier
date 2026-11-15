"""The Fork match metric (plan 5.1) on hand-built forks."""

from denoisifier import BinFactors, Fork
from denoisifier.synthetic import ForkTruth
from protected import FORK_POSITION_TOL_PERIODS
from truth_match import fork_problems

ONE = BinFactors()
P = 10.0
TRUE = (ForkTruth((100.5, 200.5), 1), ForkTruth((100.5, 300.5), -1))


def test_matching_forks_have_no_problems():
    found = (Fork(1, (101.0, 203.0), 1), Fork(1, (99.0, 296.5), -1))
    assert fork_problems(found, TRUE, P, ONE) == []


def test_a_wrong_direction_fails():
    found = (Fork(1, (100.5, 200.5), -1), Fork(1, (100.5, 300.5), -1))
    assert fork_problems(found, TRUE, P, ONE)


def test_an_extra_fork_fails():
    found = (
        Fork(1, (100.5, 200.5), 1),
        Fork(1, (100.5, 300.5), -1),
        Fork(1, (150.5, 250.5), 1),
    )
    assert fork_problems(found, TRUE, P, ONE)


def test_a_missing_fork_fails():
    assert fork_problems((Fork(1, (100.5, 200.5), 1),), TRUE, P, ONE)


def test_a_fork_just_past_one_period_fails():
    off = 1.01 * FORK_POSITION_TOL_PERIODS * P
    found = (Fork(1, (100.5 + off, 200.5), 1), Fork(1, (100.5, 300.5), -1))
    assert fork_problems(found, TRUE, P, ONE)
    inside = (Fork(1, (100.5 + 0.99 * P, 200.5), 1), Fork(1, (100.5, 300.5), -1))
    assert fork_problems(inside, TRUE, P, ONE) == []


def test_two_reported_forks_near_one_true_fork_fail():
    found = (Fork(1, (100.5, 200.5), 1), Fork(1, (101.5, 201.5), 1), Fork(1, (100.5, 300.5), -1))
    assert fork_problems(found, TRUE, P, ONE)


def test_binned_forks_are_compared_in_sensor_geometry():
    """Frame pixel (r, c) under 2x1 (h 2, v 1) has its sensor centre at (r, 2 c + 0.5)."""
    bins = BinFactors(2, 1)
    truth = (ForkTruth((100.5, 400.5), 1),)
    assert fork_problems((Fork(1, (100.5, 200.0), 1),), truth, P, bins) == []
    assert fork_problems((Fork(1, (100.5, 400.5), 1),), truth, P, bins)
