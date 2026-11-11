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

# Slow-tier regression check (ticket agent-gates/05; derivation:
# .scratch/agent-gates/handoffs/05-plan.md). make check-slow scores fresh seeds
# at the thresholds stored by the last full measurement (make measure), with no
# per-run calibration. The pass counts meet the operating rule
# (test_regression_plan_meets_the_operating_rule): at most REGRESSION_MAX_FALSE_RED
# chance of any false red at the pessimistic end of the stored baseline's 95% CI,
# at most REGRESSION_MAX_PASS_BAD chance per check of passing a detector at its
# bad rate. Never edit the pass counts to make check-slow green.
GATE_STORED_THRESHOLD = 74.11851980928641  # = feasibility-gate.json gate.threshold
PROBE_STORED_THRESHOLD = 105.80269099368302  # = feasibility-gate.json probe.threshold
REGRESSION_STRIPED_SEEDS = range(80_000, 80_300)  # 256x256, m = WEAK_DEPTH, 30 per case
REGRESSION_FREE_SEEDS = range(81_000, 81_800)  # 256x256, stripe-free
REGRESSION_PROBE_STRIPED_SEEDS = range(82_000, 82_030)  # 400x1600, m = WEAK_DEPTH, 3 per case
REGRESSION_TIMED_FRAMES = 3  # first 3 probe seeds, timed serially; counted in the 30
REGRESSION_MIN_DETECTED = 280
REGRESSION_MAX_FALSE_ALARMS = 22
REGRESSION_PROBE_MIN_DETECTED = 26
REGRESSION_MAX_FALSE_RED = 0.01  # gate-wide: union over the three checks
REGRESSION_MAX_PASS_BAD = 0.05  # per check
REGRESSION_BAD_DETECTION_RATE = 0.90
REGRESSION_BAD_FALSE_ALARM_RATE = 0.04
# Declared (ruling O1): a collapse check, not the 0.95 full-run bar
# (PROBE_MIN_DETECTION_RATE, enforced by make measure at milestones).
REGRESSION_PROBE_BAD_DETECTION_RATE = 0.70
SLOW_TIMING_LIMIT_S = 30.0  # check-slow: real slowdowns only (owner, 2026-11-10)
BENCH_REPEATS = 5  # make bench: median of this many runs, asserted against TIMING_LIMIT_S
TARGET_TIMING_S = 5.0  # ticket 13's target; make bench reports it without failing
BENCH_IDLE_LOAD = 1.0  # make bench warns, without failing, above this 1-min load average
# test_slow_regression_plan.py: the tiny-plan run of regression_check.
REGRESSION_TINY_STRIPED_TEST_SEEDS = range(60, 62)
REGRESSION_TINY_FREE_TEST_SEEDS = range(62, 64)
REGRESSION_TINY_PROBE_TEST_SEEDS = range(64, 66)

# Calibration seeds outside the feasibility gate (ticket agent-gates/04).
# _A0 (_local_stripes.py) was tuned on ticket 01's profile-only frames, seeds
# 0-9; THRESHOLD (analysis.py) was set on seeds 100-199.
A0_CALIBRATION_SEEDS = range(0, 10)
THRESHOLD_CALIBRATION_SEEDS = range(100, 200)
# Seeds of the non-slow tests: every *_TEST_SEED(S) lies in here.
TEST_SEED_BLOCK = range(10, 100)

# Test seeds (ticket agent-gates/04, owner ruling O1): each seed s in 0-9, now
# A0_CALIBRATION_SEEDS, moved to s + 20; seeds 10-19 stayed. CASES[seed % 10]
# and the other seed-derived cases are unchanged by the +20 shift.
MOTTLED_TEST_SEEDS = range(10, 30)  # test_analyse.SEEDS
FULL_FRAME_TEST_SEEDS = range(20, 27)  # zipped with its 7 cases, in order
PROFILE_ONLY_TEST_SEEDS = range(20, 30)
STRONG_TEST_SEEDS = range(20, 25)
ENVELOPE_TEST_SEEDS = range(20, 23)
EXTREMES_TEST_SEEDS = range(20, 28)  # zipped with test_analyse.EXTREMES
MULTISCALE_TEST_SEEDS = range(20, 30)
STRIPE_FREE_SPECTRUM_TEST_SEEDS = range(20, 30)
SAME_SEED_TEST_SEEDS = (23, 24)
SINGLE_FRAME_TEST_SEED = 20  # single-frame tests whose seed was 0
# Single-frame tests whose seed was 1, 2, 3, 5 or 7, one name per test.
CLI_STRIPED_CSV_TEST_SEED = 21  # test_cli_writes_json_report_for_striped_csv (was 1)
REPORT_TO_JSON_TEST_SEED = 21  # test_report_converts_to_json (was 1)
CLI_STDOUT_TEST_SEED = 22  # test_cli_prints_json_to_stdout_without_output_flag (was 2)
INPUT_NOT_MODIFIED_TEST_SEED = 22  # test_input_frame_is_not_modified (was 2)
CLI_MISSING_OUTPUT_DIR_TEST_SEED = 23  # test_cli_fails_cleanly_when_output_dir_missing (was 3)
MOTTLE_NONE_TEST_SEED = 23  # test_mottle_none_is_unchanged_from_ticket_01 (was 3)
CSV_ROUND_TRIP_TEST_SEED = 25  # test_written_csv_reads_back_as_the_same_frame (was 5)
SCORE_AND_THRESHOLD_TEST_SEED = 27  # test_report_has_score_and_threshold (was 7)
# borderline.BORDERLINE. The first entry was (0, 20); 22 is the lowest Period
# 20 seed in 20-99 that scores in the borderline window (ruling O3).
BORDERLINE_TEST_CASES = [(22, 20), (13, 5), (13, 8), (12, 20), (16, 8)]

# Ticket 05 (Striped Regions): generator tests.
DIGEST_TEST_SEEDS = range(30, 33)  # test_default_frames_are_unchanged_by_regions
REGION_GENERATOR_TEST_SEED = 33  # the generator's region-mask tests

# test_seed_guard.py (ticket agent-gates/04). The held-out free and striped
# seeds of test_measure_calibrates_inside_the_block_and_evaluates_outside's
# small SeedPlan.
MEASURE_PLAN_FREE_TEST_SEEDS = range(40, 50)
MEASURE_PLAN_STRIPED_TEST_SEEDS = range(50, 60)
# subprocess timeout of test_feasibility_script_guards_itself_and_its_workers:
# bounds a hung child; the run takes about 1-2 s.
FEASIBILITY_SCRIPT_TIMEOUT_S = 45

# Seeds already used before ticket 03: tests and ticket 02 (0-199, split by
# use), the planner's pre-measurement (1000-1399, 2000-2031) and prototype P1.
# Every range here and every other seed range in this module is disjoint
# (test_seed_sets_are_disjoint_and_unused).
USED_SEEDS = [
    A0_CALIBRATION_SEEDS,
    TEST_SEED_BLOCK,
    THRESHOLD_CALIBRATION_SEEDS,
    range(1000, 1400),
    range(2000, 2032),
    range(50_000, 50_300),
    range(59_999, 60_100),
]

# Calibration seed ranges, by name. tests/seed_guard.py refuses any of these
# seeds in generate() outside a seed_guard.calibrating(...) block for that
# range (ticket agent-gates/04).
CALIBRATION_SEEDS = {
    "A0_CALIBRATION_SEEDS": A0_CALIBRATION_SEEDS,
    "THRESHOLD_CALIBRATION_SEEDS": THRESHOLD_CALIBRATION_SEEDS,
    "GATE_CALIBRATION_SEEDS": GATE_CALIBRATION_SEEDS,
    "PROBE_CALIBRATION_SEEDS": PROBE_CALIBRATION_SEEDS,
}
