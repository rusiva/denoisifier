"""How close a measured Period and Angle must be to the generator's ground truth."""

PERIOD_REL_TOL = 0.05
ANGLE_TOL_DEG = 1.0


def assert_matches_truth(period_px, angle_deg, truth):
    assert abs(period_px - truth.period) <= PERIOD_REL_TOL * truth.period
    assert abs(angle_deg - truth.angle_deg) <= ANGLE_TOL_DEG
