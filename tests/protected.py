"""Protected numbers: every test-side number that decides a pass (ticket agent-gates/03).

Each module-level number here, and each module- and class-level number in the
denoisifier package, is recorded in protected_numbers.lock;
test_protected_numbers fails when a live value differs from the lockfile or a
number is missing from it. Changing a value here is a weakening move (changing
a tolerance or expected value), and so is editing the lockfile: owner approval
first (CLAUDE.md).
"""

from cases import Case

# Measured Period, Angle and Modulation Depth vs the generator's ground truth
# (truth_match.py).
PERIOD_REL_TOL = 0.05
ANGLE_TOL_DEG = 1.0
DEPTH_TOL = 0.1

# Spectral oracle (spectrum.py): the vertical band is Angles within +-10 deg
# plus a 2 deg margin, so a peak at exactly +-10 deg is not cut off by the
# frequency grid; the horizontal band is the same rotated 90 deg.
SPECTRAL_BAND_DEG = 12.0

# Borderline frames (borderline.py) must score in (THRESHOLD, this x THRESHOLD).
BORDERLINE_SCORE_WINDOW = 1.5

# Feasibility gate (feasibility.py, test_feasibility_gate.py): weak stripes at
# 1% False Alarms.
FALSE_ALARM_RATE = 0.01
# Central 95% of the held-out False Alarm count: betabinom(1000, 20, 1982).
FALSE_ALARM_TOLERANCE = (3, 18)
MIN_DETECTION_RATE = 0.90
PROBE_MIN_DETECTION_RATE = 0.95
TIMING_LIMIT_S = 10.0
WEAK_DEPTH = 0.2
GATE_SHAPE = (256, 256)  # the gate is judged here (plan R3)
PROBE_SHAPE = (400, 1600)  # full frame

# Named seed ranges of the feasibility gate.
GATE_CALIBRATION_SEEDS = range(10_000, 12_000)  # 2000
GATE_FREE_SEEDS = range(20_000, 21_000)  # 1000
GATE_STRIPED_SEEDS = range(30_000, 30_500)  # 500: 50 per case
PROBE_CALIBRATION_SEEDS = range(70_000, 70_300)  # 300 -> k = 3
PROBE_FREE_SEEDS = range(71_000, 71_200)  # 200
PROBE_STRIPED_SEEDS = range(72_000, 72_100)  # 100: 10 per case
# One full-frame (PROBE_SHAPE) frame, m = WEAK_DEPTH.
TIMING_SEED = 40_000
TIMING_CASE = Case(period=8, angle_deg=0)

# Seeds already used before ticket 03: tests and ticket 02 (0-199), the
# planner's pre-measurement (1000-1399, 2000-2031) and prototype P1. The gate's
# seed ranges must not overlap them.
USED_SEEDS = [
    range(0, 200),
    range(1000, 1400),
    range(2000, 2032),
    range(50_000, 50_300),
    range(59_999, 60_100),
]
