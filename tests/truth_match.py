"""How close a measured Period, Angle and Modulation Depth must be to the generator's ground
truth. The tolerances are protected numbers (protected.py)."""

from protected import ANGLE_TOL_DEG, DEPTH_TOL, PERIOD_REL_TOL


def assert_matches_truth(period_px, angle_deg, truth):
    assert abs(period_px - truth.period) <= PERIOD_REL_TOL * truth.period
    assert abs(angle_deg - truth.angle_deg) <= ANGLE_TOL_DEG


def assert_depth_matches(depth, truth):
    assert abs(depth - truth.modulation_depth) <= DEPTH_TOL
