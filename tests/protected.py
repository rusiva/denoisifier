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
# docs/regression-plan.md). make check-slow scores fresh seeds
# at the thresholds stored by the last full measurement (make measure), with no
# per-run calibration. The pass counts meet the operating rule
# (test_regression_plan_meets_the_operating_rule): at most REGRESSION_MAX_FALSE_RED
# chance of any false red at the pessimistic end of the stored baseline (exact 95%
# CIs for detection; the threshold's rank-based bound for false alarms),
# at most REGRESSION_MAX_PASS_BAD chance per check of passing a detector at its
# bad rate. Never edit the pass counts to make check-slow green.
GATE_STORED_THRESHOLD = 49.7159577445053  # = feasibility-gate.json gate.threshold
PROBE_STORED_THRESHOLD = 85.17105365821853  # = feasibility-gate.json probe.threshold
REGRESSION_STRIPED_SEEDS = range(80_000, 80_300)  # 256x256, m = WEAK_DEPTH, 30 per case
REGRESSION_FREE_SEEDS = range(81_000, 81_850)  # 256x256, stripe-free (850: ruling 2026-11-13)
REGRESSION_PROBE_STRIPED_SEEDS = range(82_000, 82_030)  # 400x1600, m = WEAK_DEPTH, 3 per case
REGRESSION_TIMED_FRAMES = 3  # first 3 probe seeds, timed serially; counted in the 30
REGRESSION_MIN_DETECTED = 280
REGRESSION_MAX_FALSE_ALARMS = 24
REGRESSION_PROBE_MIN_DETECTED = 26
REGRESSION_MAX_FALSE_RED = 0.01  # gate-wide: union over the three checks
REGRESSION_MAX_PASS_BAD = 0.05  # per check
# An unchanged detector's fresh make measure meets the rule at least this often
# (owner approval 2026-11-13, ticket agent-gates/05 Comments).
REGRESSION_MIN_PASS_PROBABILITY = 0.95
REGRESSION_BAD_DETECTION_RATE = 0.90
REGRESSION_BAD_FALSE_ALARM_RATE = 0.04
# Declared (ruling O1): a collapse check, not the 0.95 full-run bar
# (PROBE_MIN_DETECTION_RATE, enforced by make measure at milestones).
REGRESSION_PROBE_BAD_DETECTION_RATE = 0.70
SLOW_TIMING_LIMIT_S = 30.0  # check-slow: real slowdowns only (owner, 2026-11-10)
BENCH_REPEATS = 5  # make bench: median of this many runs, asserted against TIMING_LIMIT_S
TARGET_TIMING_S = 5.0  # ticket 13's target; make bench reports it without failing
BENCH_IDLE_LOAD = 1.0  # bench, check-slow, measure warn, without failing, above this 1-min load
# False-alarm baseline of the operating rule (owner approval, ticket
# stripe-detector/05 Comments): the upper quantile of the stored threshold's
# rank-based rate, Beta(k + x, n + 1 - k + N - x), not the held-out count's CI.
REGRESSION_FREE_RATE_BOUND_QUANTILE = 0.975
# test_slow_regression_plan.py: the bound's coverage on uniform scores (sd about
# 0.0025 at 4000 trials, so the tolerance is 4 sd).
FREE_RATE_BOUND_COVERAGE_TEST_SEED = 41
FREE_RATE_BOUND_COVERAGE_TRIALS = 4000
FREE_RATE_BOUND_COVERAGE_TOL = 0.01
# test_slow_regression_plan.py: the tiny-plan run of regression_check.
REGRESSION_TINY_STRIPED_TEST_SEEDS = range(60, 62)
REGRESSION_TINY_FREE_TEST_SEEDS = range(62, 64)
REGRESSION_TINY_PROBE_TEST_SEEDS = range(64, 66)

# Calibration seeds outside the feasibility gate (ticket agent-gates/04).
# _A0 (_local_stripes.py) was tuned on ticket 01's profile-only frames, seeds
# 0-9; THRESHOLD (analysis.py) was set on seeds 100-199.
A0_CALIBRATION_SEEDS = range(0, 10)
THRESHOLD_CALIBRATION_SEEDS = range(100, 200)
# Ticket 05's region knobs (analysis.py) are tuned on 90_000-90_399 and the
# informational numbers measured on 90_400-90_599 (tests/calibrate_regions.py).
REGION_CALIBRATION_SEEDS = range(90_000, 90_600)
# Ticket 05's fresh held-out evaluation (orchestrator, "Evaluation hygiene"):
# predeclared before the post-freeze fixes, looked at once after the new freeze
# by a one-off driver (tests/evaluate_regions.py), never tuned on.
REGION_EVALUATION_SEEDS = range(93_000, 94_000)
# Consumed at 2107a40 (AC2 39/40, AC6 dark 29/30). The second fresh range
# (orchestrator, "Rulings on the fresh-range misses"): predeclared before the
# depth and dark-surround fixes, evaluated once after the third freeze with the
# same driver and cases; pass rule: every frame meets every criterion.
REGION_EVALUATION_2_SEEDS = range(94_000, 95_000)
# The first range's misses, kept as regression cases (same ruling): single
# regions whose depth measured low (seed, Period, Angle, Mottle), and a
# full-frame typical frame whose mask reached a dark corner (seed, case). Both
# are seeds of the consumed REGION_EVALUATION_SEEDS, so not named *_SEED(S).
DEPTH_REGRESSION_CASES = ((93_024, 20, -10, "scorched"), (93_048, 10, 3, "multiscale"))
DARK_REGRESSION_CASES = ((93_130, "full-frame-typical"),)
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
# test_synthetic.py, the generator's region masks (a region of semi-axes a x b):
MASK_SATURATION_TOL = 1e-6  # the mask is 1 at the centre and 0 far out, within this
MASK_CONTOUR_TOL_PX = 1.0  # the 0.5 contour vs the ellipse, along the minor axis
MASK_EDGE_WIDTH_TOL_PX = 1.0  # the 0.9 -> 0.1 band's width vs edge_px
MASK_AREA_REL_TOL = 0.02  # truth pixels (mask >= 0.5) vs pi a b
MASK_TAIL = 1e-12  # outside a region: mask below this (tanh never reaches 0)
OUTSIDE_REGIONS_RTOL = 1e-9  # clean frame outside every region vs the region-free one

# Ticket 05 (Striped Regions): acceptance tests (tests/regions.py builds the frames).
MASK_IOU_MIN = 0.8  # spec Further Notes: mask IoU >= 0.8
CANDIDATE_CAP_HEADROOM = 2  # plan 2.3 (N9): _MAX_CANDIDATES >= this x calibration reach
BBOX_TOL_PERIODS = 1.0  # reported bbox vs the truth's (mask >= 0.5), per side, in Periods
MIN_SIZE_BELOW_FACTOR = 0.8  # x the 3x2-Period minimum: never reported (low noise)
MIN_SIZE_ABOVE_FACTOR = 1.4  # x the minimum: always reported (low noise)
DARK_FRACTION = 0.05  # "dark": envelope below this x its max (the light: _LIGHT_FRACTION 0.1)
# Test region: semi-axes max(5 P, 45) x max(6.6 P, 60) px (rows x cols), centred.
REGION_SEMI_AXES_PERIODS = (5.0, 6.6)
REGION_SEMI_AXES_FLOOR_PX = (45, 60)
REGION_EDGE_PX = 6.0
REGION_FRAME_SHAPE = (512, 512)
# Two regions side by side in a wide frame; gap between their 0.5 contours in
# windows (3 Periods) of the longer Period.
TWO_REGION_PAIRS = ((5, 12), (8, 16), (4, 10))
TWO_REGION_SHAPE = (640, 1024)
TWO_REGION_GAP_WINDOWS = 2.0
REGION_TEST_SEEDS = range(66, 76)  # CASES[seed % 10]: every case once
TWO_REGION_TEST_SEEDS = range(76, 78)
MIN_SIZE_TEST_SEEDS = range(78, 80)
CLI_MASK_TEST_SEED = 80

# Ticket 06 (Spikes and Clipped Pixels; plan .scratch/stripe-detector/handoffs/06-plan.md,
# section 4). Test seeds, never generated by a prototype.
SPIKE_GENERATOR_TEST_SEED = 34  # the generator's spike and clip tests
CLI_CLIP_TEST_SEED = 35  # the CLI's spike and clip tests
SPIKE_BOUNDARY_TEST_SEED = 36  # hand-placed spikes at the dimmest generated brightness
PHASE_BREAK_TEST_SEED = 37  # hand-made Phase Break frames, spike-free
# The first ten seeds from 81 whose spike truth is in the model (no 8-connected
# hit run longer than _SPIKE_MAX_LENGTH vertically) for every spike-count test
# configuration; 82 and 87 fail it (plan step 5a, generator only; ticket Comments).
SPIKE_TEST_SEEDS = (81, 83, 84, 85, 86, 88, 89, 90, 91, 92)
CLIP_TEST_SEEDS = SPIKE_TEST_SEEDS  # shared (allowed for test seeds)
SPIKE_TEST_COUNT = 30  # spike events per frame in the spike-count tests
SPIKE_STRESS_COUNT = 100  # spike events per frame in the stripe-free verdict test
CLI_SPIKE_COUNT = 5  # spike events in the CLI's 96x160 frame
SPIKE_PASS_MARK_PHOTONS = 30.0  # spec.md:141 low end; evidence/06-prototype-p1.md
# Reported spike_pixels vs the truth: within max(ABS, REL x truth) pixels.
SPIKE_PIXELS_ABS_TOL = 2
SPIKE_PIXELS_REL_TOL = 0.05
SATURATING_CLIP_FACTOR = 3.0  # clip at 3 x clean max: every bright spike saturates (P1)
MILD_CLIP_LEVEL_FRACTION = 0.8  # clip at 0.8 x clean max: the no-harm guard (P2)
OVERRIDE_LEVEL_FRACTION = 0.9  # an override below the clip plateau
BASELINE_OFFSET = 1000.0  # a bias offset of the order of Solis frames (B3)
# Clipped pixels inside the truth region of a partial-region depth test (B4, N7):
# below P2's minimum at 0.8 (37 at 100 photons).
AC4_MIN_CLIPPED_PIXELS = 30

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
    # Ticket 05: seeds the plan review (N8) and prototypes P1, P1-D and P2 looked at.
    range(300_001, 300_006),
    range(310_000, 310_400),
    range(320_000, 320_200),
    range(330_000, 330_100),
    range(340_000, 340_004),
    range(350_000, 350_002),
    range(360_000, 360_060),
    range(390_000, 390_008),
    range(390_100, 390_108),
    range(390_200, 390_208),
    range(390_300, 390_308),
    range(391_000, 391_008),
    range(391_100, 391_108),
    range(391_200, 391_208),
    range(410_000, 410_080),
    range(411_000, 411_004),
    # Ticket 05: the implementer's scratch checks.
    range(95_000, 95_300),
    # Ticket 05: the fresh evaluation range (reserved before it is looked at).
    REGION_EVALUATION_SEEDS,
    REGION_EVALUATION_2_SEEDS,
    # Ticket 06: prototypes P1 and P2 (396_000-396_399) and critic 2 (396_400-396_405).
    range(396_000, 396_406),
    # Ticket 06: the pre-freeze check P3 (reserved before it is looked at).
    range(396_500, 396_700),
    # Ticket 06: critic 1's scratch checks.
    range(700_000, 700_006),
    range(700_100, 700_140),
]

# Calibration seed ranges, by name. tests/seed_guard.py refuses any of these
# seeds in generate() outside a seed_guard.calibrating(...) block for that
# range (ticket agent-gates/04).
CALIBRATION_SEEDS = {
    "A0_CALIBRATION_SEEDS": A0_CALIBRATION_SEEDS,
    "THRESHOLD_CALIBRATION_SEEDS": THRESHOLD_CALIBRATION_SEEDS,
    "GATE_CALIBRATION_SEEDS": GATE_CALIBRATION_SEEDS,
    "PROBE_CALIBRATION_SEEDS": PROBE_CALIBRATION_SEEDS,
    "REGION_CALIBRATION_SEEDS": REGION_CALIBRATION_SEEDS,
}
