"""Protected numbers: every test-side number that decides a pass (ticket agent-gates/03).

Each module-level number here, and each module- and class-level number in the
denoisifier package, is recorded in protected_numbers.lock;
test_protected_numbers fails when a live value differs from the lockfile or a
number is missing from it. Changing a value here is a weakening move (changing
a tolerance or expected value), and so is editing the lockfile: owner approval
first (CLAUDE.md).
"""

import math

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

# Borderline frames (borderline.py) must score in (T, this x T) at the default threshold T.
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
TARGET_TIMING_S = 5.0  # ticket 13's AC 1: make bench fails above it (warm pipeline and cold CLI)
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
# 0-9; the former analysis.THRESHOLD (154, removed in ticket 07) was set on seeds 100-199.
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
# Ticket 13's speed frame (tests/speed.py; plan section 1, orchestrator approval
# 2026-11-16): the profile's worst frame, P 3 at Angle 3 (Period, Angle), two Phase
# Breaks ((row, col), tilt from the Angle in deg, jump in rad) and one Fork (row, col).
SPEED_TEST_SEED = 38  # only tests/speed.py and stage_timings.py (its typical P 6 frame) use it
SPEED_CASE = (3.0, 3.0)
SPEED_BREAK_LINES = (((130.0, 500.0), 4.0, math.pi), ((280.0, 1100.0), -3.0, -2.0))
SPEED_FORK_POINT = (200.5, 800.5)
SPEED_SPIKES = 30
# make test-fast (ticket agent-gates/07): the first this-many seeds of a seed range run in the
# inner loop; the rest are pytest.mark.wide (tests/inner_loop.py) and run in make check only.
INNER_LOOP_SEED_COUNT = 2

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
# borderline.BORDERLINE. Re-picked at ticket 07 step 6 for the stored default threshold
# by the frozen W4(c) rule (keep a seed still in the window, else the first seed from 10 up
# in the window at that Period not already chosen for it); was [(22, 20), (13, 5), (13, 8),
# (12, 20), (16, 8)] at THRESHOLD = 154. Scan table: ticket 07 Comments.
BORDERLINE_TEST_CASES = [(11, 20), (11, 5), (11, 8), (13, 20), (21, 8)]

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
# The partial-region depth tests (512x512, three analyses per seed): the first
# five clip seeds.
PARTIAL_CLIP_TEST_SEEDS = CLIP_TEST_SEEDS[:5]
# The generator's streak test, one Spike event per frame; its own seeds from the
# free end of TEST_SEED_BLOCK (reserved in USED_SEEDS through the block).
STREAK_TEST_SEEDS = range(93, 99)
SPIKE_TEST_COUNT = 30  # spike events per frame in the spike-count tests
SPIKE_STRESS_COUNT = 100  # spike events per frame in the stripe-free verdict test
CLI_SPIKE_COUNT = 5  # spike events in the CLI's 96x160 frame
SPIKE_PASS_MARK_PHOTONS = 30.0  # spec.md:141 low end; evidence/06-prototype-p1.md
# Reported spike_pixels vs the truth: within max(ABS, REL x truth) pixels.
SPIKE_PIXELS_ABS_TOL = 2
SPIKE_PIXELS_REL_TOL = 0.05
SATURATING_CLIP_FACTOR = 3.0  # clip at 3 x clean max: every bright spike saturates (P1)
# A mild clip near the light peak, 0.8 x clean max: a small plateau. The
# partial-region no-harm guard (P2), and the CLI frame, whose auto-detected
# plateau is small enough that Spikes on dim columns stay Spikes.
MILD_CLIP_LEVEL_FRACTION = 0.8
OVERRIDE_LEVEL_FRACTION = 0.9  # an override below the clip plateau
# test_data_quality.py: a rejected Spike pixel's working value is within this
# fraction of the frame's maximum of its spike-free value.
REJECTED_VALUE_TOL_FRACTION = 0.2
PEDESTAL_OFFSET = 1000.0  # a Pedestal of the order of Solis frames' bias offset (B3)
# Clipped pixels inside the truth region of a partial-region depth test (B4, N7):
# below P2's minimum at 0.8 (37 at 100 photons).
AC4_MIN_CLIPPED_PIXELS = 30
# Frozen at step 5c from the pre-freeze check P3 (evidence/06-prototype-p3.md).
CLIP_LEVEL_FRACTION = 0.4  # AC 4 clip at 0.4 x clean max (P3 margin: worst error 0.060 <= 0.08)
CLIP_MIN_SHARE = 0.02  # AC 4 precondition: clipped share of the frame (P3 minimum 2.07%)
CLIP_DEPTH_EPS = 0.01  # depth error vs clip_level=inf: max(0.01, P3 largest excess + 0.005)
# AC 3: median paired |score change| over the stripe-free pairs (ticket 06 Comments,
# ruling after critic 3): P3 block medians 0.18-1.35; 58.5 with rejection off.
SPIKE_SCORE_MEDIAN_TOL = 5

# Ticket 07 (calibrated stripe score; plan .scratch/stripe-detector/handoffs/07-plan.md,
# sections 4, 5 and 7). The Calibration Set is generated only inside the one
# seed_guard.calibrating(...) block of threshold_calibration.calibrate_synthetic; the
# held-out ranges are looked at only by make check-held-out, the clipped range once.
STRIPE_FREE_CALIBRATION_SEEDS = range(100_000, 100_300)  # n = 300 -> k = 3 at 1%, 15 at 5%
CALIBRATED_FREE_SEEDS = range(101_000, 101_300)  # AC 2 held-out, Stripe-free
CALIBRATED_STRIPED_SEEDS = range(102_000, 102_100)  # AC 3 held-out, m = WEAK_DEPTH, 10 per case
CLIPPED_FREE_EVALUATION_SEEDS = range(103_000, 103_200)  # one-off clipped measurement (step 10)
CALIBRATION_SHAPE = PROBE_SHAPE  # one shipped calibration, at the full frame (ruling Q1)
# Spike events per calibration frame: a synthetic assumption (ruling Q3, ADR 0002), above
# the expected real rate, so that spike rejection is exercised; not SPIKE_TEST_COUNT.
CALIBRATION_SPIKES = 30
OTHER_FALSE_ALARM_RATE = 0.05  # AC 2b: the other requested rate
# Per-assertion level of the held-out False Alarm tolerances; their Bonferroni union over
# AC 2a and 2b stays under CALIBRATION_MAX_FALSE_RED (AC 3 is outside it, plan C1).
CALIBRATION_TOLERANCE_LEVEL = 0.995
CALIBRATION_MAX_FALSE_RED = 0.01
HELD_OUT_OPTION_FRAMES = 20  # AC 2b: frames also analysed with false_alarm_rate=0.05 (N3)
CALIBRATION_TIMEOUT_S = 2400  # per test of the calibration slow modules (W6)
# The shipped calibration (src/denoisifier/stripe_free_calibration.json), from the step-5
# run at c20b28d (W4, W9): its thresholds at 1% (k = 3) and 5% (k = 15), and the SHA-256
# of its canonical {ids, scores, shape, settings} (Calibration.digest) as an int, so the
# lockfile pins the whole payload (W4(b)). Re-stored only by the procedure in CLAUDE.md.
PACKAGE_STORED_THRESHOLD = 100.80547983306298
PACKAGE_STORED_THRESHOLD_5PCT = 60.91880891139576
PACKAGE_CALIBRATION_DIGEST = int(
    "4140b3db8edcb56dce3567cd42bc321e1df1512d616e37647e6dc0823d2e0f6a", 16
)
# Test seeds of ticket 07 (fixed at step 0, before use).
CALIBRATION_FOLDER_TEST_SEEDS = range(10, 22)  # AC 5: 12 frames, 64x64
CALIBRATION_TINY_TEST_SEEDS = range(40, 44)  # the tiny plan's calibration (core, no guard)
CALIBRATION_TINY_FREE_TEST_SEEDS = range(44, 48)  # the tiny plan's held-out Stripe-free
CALIBRATION_TINY_STRIPED_TEST_SEEDS = range(50, 60)  # the tiny plan's held-out striped
RUN_POOL_TEST_SEEDS = range(60, 64)  # serial-vs-pool equivalence (plan C2)
FALSE_ALARM_RATE_OPTION_TEST_SEED = 28  # test_false_alarm_rate_option_sets_the_threshold_...

# Ticket 08 (bin factors; plan .scratch/stripe-detector/handoffs/08-plan.md, section 5).
# Test frames generated at sensor size, block-summed (tests/binning.py), then analysed.
BINNING_TEST_SEEDS = range(10, 14)
# Prototype P1 of ticket 08 (08-prototype-p1.md): seeds it looked at, reserved.
BINNING_PROTOTYPE_SEEDS = range(108_000, 108_400)
# AC 1: a 10 deg sensor Angle under 1x2 is this Angle (deg) in the frame, within the tol.
BINNED_FRAME_ANGLE_DEG = 19.43
BINNED_FRAME_ANGLE_TOL_DEG = 0.01

# Ticket 09 (Phase Breaks; plan .scratch/stripe-detector/handoffs/09-plan.md, sections 5 and 7).
# Test seeds, never run before the plan; CASES[seed % 10] gives P 3, 5, 8, 12, 20, 4, 16, 6, 10, 14.
PHASE_BREAK_TEST_SEEDS = range(10, 20)
# A found break (truth_match.assert_break_matches, plan 5.1; spec tolerances).
BREAK_POSITION_TOL_PERIODS = 1.0  # every segment point within this x P of the true line
BREAK_JUMP_TOL_RAD = math.pi / 4  # found jump vs the true jump, directions aligned
BREAK_MIN_FOUND_JUMP_RAD = math.pi / 2  # AC 2: the smallest jump that must be found
BREAK_CHORD_COVER_MIN = 0.6  # segment covers this share of the true chord (P1: min 0.776)
# AC 4 (plan 5.3): each side of the true line, truth pixels farther than
# BREAK_SIDE_EXCLUDE_PERIODS x P from it, is covered at least this much by the one region.
BREAK_SIDE_COVER_MIN = 0.5
BREAK_SIDE_EXCLUDE_PERIODS = 2.5
# Full frames' chord: the generator-side lit mask, clean smoothed at this sigma (sensor px),
# at or above this x its maximum (truth_match.truth_lit_mask).
BREAK_LIT_SIGMA_PX = 10.0
BREAK_LIT_LEVEL = 0.1
BREAK_PHASE_ATOL = 1e-9  # the generator's break phase, noise-free
# _local_phase unit tests on noise-free phasor fields. The position tolerance is the finder's
# sample stride (_BREAK_SAMPLE_STRIDE_PERIODS); measured max 0.364 P over 480 noise-free runs
# (09-critic-4; raised from 0.25 with the orchestrator's approval, ticket 09 Comments).
BREAK_EXACT_POSITION_TOL_PERIODS = 0.5
BREAK_EXACT_JUMP_TOL_RAD = 0.05
# The blurred-step phasor field of those tests against break_response of a hard-step frame, over
# twice the depth, inside this radius (px) of the centre: measured max 0.043 at 60 px (P 8,
# lines 0, 30, 90; 09-critic-4: 0.06); the frame edge raises it to 0.19 at 90 px.
BREAK_PHASOR_FIELD_RADIUS_PX = 60.0
BREAK_PHASOR_FIELD_ATOL = 0.1
# Two parallel breaks this many Periods apart (P1 v2 validation 20/20 at 6 P), at case
# Periods of at least BREAK_PAIR_MIN_PERIOD.
BREAK_PAIR_SEPARATION_PERIODS = 6
BREAK_PAIR_MIN_PERIOD = 5
# The end-to-end sign test: Period (px), stripe Angle 0, line 10 deg, jump +pi/2.
BREAK_SIGN_TEST_SEED = PHASE_BREAK_TEST_SEEDS[0]
BREAK_SIGN_TEST_PERIOD = 10
# The frame-period refusal: sensor Period under 2x1 (frame Period 2.35, between
# MIN_FRAME_PERIOD_PX 2.0 and the finder's 2.5).
BREAK_REFUSAL_TEST_PERIOD = 4.7
# A region this many Periods tall gets no break (the finder's small-region rule).
BREAK_SMALL_REGION_PERIODS = 5
# Prototype P1 of ticket 09 (09-prototype-p1.md): explore, and the validation ranges
# (v1 109_600-109_999, v2 110_000-110_399, gate 110_400-110_459). Reserved.
BREAK_PROTOTYPE_SEEDS = range(109_000, 109_600)
BREAK_VALIDATION_SEEDS = range(109_600, 110_460)

# Ticket 10 (Forks; plan .scratch/stripe-detector/handoffs/10-plan.md, sections 5 and 7).
# Test seeds, never run with forks before the plan; CASES[seed % 10] as above.
FORK_TEST_SEEDS = range(10, 20)
# A found fork (truth_match.assert_forks_match, plan 5.1; spec tolerance).
FORK_POSITION_TOL_PERIODS = 1.0
# _local_phase unit tests on noise-free phasor fields (P1 noise-free max 0.172 P, 96/96).
FORK_EXACT_POSITION_TOL_PERIODS = 0.25
# AC 3 (plan 5.3): a fork this many Periods from a Phase Break's line.
FORK_NEAR_BREAK_PERIODS = 4.0
# Two forks this many Periods apart (plan 5.4; P2 pairbig 26/27 at 4 P).
FORK_PAIR_SEPARATION_PERIODS = 4.0
# The large round region of AC 3 and the pair test: semi-axes max(this x P, the floor) px.
FORK_BIG_REGION_SEMI_PERIODS = 11.0
FORK_BIG_REGION_SEMI_FLOOR_PX = 60.0
# The correction undoes the generator term: resultant length of the phase difference
# against the fork-free twin (P2 measured 1.000; the wrong sign at most 0.14).
FORK_CORRECTION_MIN_RESULTANT = 0.99
# The sign tests: end-to-end seed, Period (px), the generator test's row offset (Periods)
# and its frame shape (wide rows, plan review B1).
FORK_SIGN_TEST_SEED = FORK_TEST_SEEDS[0]
FORK_SIGN_TEST_PERIOD = 10
FORK_SIGN_ROW_OFFSET_PERIODS = 5
FORK_SIGN_FRAME_SHAPE = (400, 1600)
FORK_PHASE_ATOL = 1e-9  # the generator's fork phase, noise-free
# The break pass's field against the hand-turned raw response (float rounding only).
FORK_EXPLAINED_RESPONSE_ATOL = 1e-12
# Prototypes P1 and P2 of ticket 10 (explore), and the one validation run (2/3 scale).
# Reserved. 111_200-111_599 and 111_733-111_999 were never generated and stay unused
# (free for the follow-up ticket 18's explore and validation).
FORK_PROTOTYPE_SEEDS = range(111_000, 111_200)
FORK_VALIDATION_SEEDS = range(111_600, 111_733)

# Ticket 11 (calibrated fake Phase Breaks and Forks; plan
# .scratch/stripe-detector/handoffs/11-plan.md, sections 5, 6 and 10). The Calibration Set
# is generated only inside the one seed_guard.calibrating(...) block of
# break_fork_calibration.calibrate_break_forks; the held-out ranges are looked at only by
# make check-held-out, once; the _2 ranges are a reserved second look, unused unless ruled.
BREAK_FORK_PROTOTYPE_SEEDS = range(112_000, 112_200)  # P1, every arm (11-prototype-p1.md)
BREAK_FORK_FREE_CALIBRATION_SEEDS = range(113_000, 113_300)  # n = 300 -> k = 7 at 2.5 %
BREAK_FORK_FREE_HELD_OUT_SEEDS = range(114_000, 114_300)  # AC 2, the calibration recipe
BREAK_FORK_FREE_HELD_OUT_2_SEEDS = range(114_300, 114_600)
BREAK_FORK_DETECTION_HELD_OUT_SEEDS = range(115_000, 115_200)  # AC 3(c): 100 break, 100 Fork
BREAK_FORK_DETECTION_HELD_OUT_2_SEEDS = range(115_200, 115_400)
# The check-slow reproduction re-runs this prefix of the Calibration Set (6 per case); the
# full 300 are reproduced in make check-held-out (P1: OQ8 prefix branch).
BREAK_FORK_REPRODUCTION_PREFIX = 60
# The calibration recipe: full-frame stripes at this depth (the 09/10 frames' depth), the
# ticket-07 typical settings (CALIBRATION_SPIKES Spike events, unclipped).
BREAK_FORK_CALIBRATION_SHAPE = PROBE_SHAPE
BREAK_FORK_CALIBRATION_DEPTH = 0.5
BREAK_FORK_FALSE_ALARM_RATE = 0.05  # the default rate the held-out tests check
# AC 2: the total count of reported breaks and Forks on the 300 held-out frames is at most
# this: the one-sided point of the single-order-statistic count model at r = 0.05 (k = 15),
# betabinom(300, 15, 286): P(X > 29) = 0.0090 <= CALIBRATION_MAX_FALSE_RED
# (test_break_fork_plan_meets_its_false_red_budget).
BREAK_FORK_MAX_FAKES = 29
# Per-case alarm (recorded, not asserted): a case with this many frames with a fake of its
# 30 (binomial tail 0.33 % at 0.05) is flagged in the measurement JSON.
BREAK_FORK_CASE_ALARM_FRAMES = 6
# AC 3(c): pooled detection on the held-out break and Fork frames.
BREAK_FORK_MIN_DETECTION_RATE = 0.95
BREAK_FORK_DETECTION_BREAK_FRAMES = 100
BREAK_FORK_DETECTION_FORK_FRAMES = 100
# Test seeds of the tiny plans (test_break_fork_calibration.py).
BREAK_FORK_TINY_CALIBRATION_TEST_SEEDS = range(40, 44)
BREAK_FORK_TINY_FREE_TEST_SEEDS = range(44, 48)
BREAK_FORK_TINY_BREAK_TEST_SEEDS = range(10, 12)
BREAK_FORK_TINY_FORK_TEST_SEEDS = range(12, 14)
# The package's stored break and Fork calibration
# (src/denoisifier/break_fork_free_calibration.json): its thresholds at
# BREAK_FORK_FALSE_ALARM_RATE (the floors: S_b = S_f = 0 on all 300 frames) and
# its digest. Re-stored only by the procedure in CLAUDE.md.
PACKAGE_BREAK_FORK_BREAK_THRESHOLD = 0.1
PACKAGE_BREAK_FORK_FORK_THRESHOLD = 0.3
PACKAGE_BREAK_FORK_CALIBRATION_DIGEST = int(
    "148ba19d40307b00cacb210fd0b21159a0a1651635020a72a49fe67471656862", 16
)

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
    # Ticket 07: scratch range; P1 used 104_000-104_049, the plan review's N6 timing 104_000.
    range(104_000, 104_100),
    # Ticket 08: prototype P1.
    BINNING_PROTOTYPE_SEEDS,
    # Ticket 09: prototype P1 (explore, validations, gate seeds).
    BREAK_PROTOTYPE_SEEDS,
    BREAK_VALIDATION_SEEDS,
    # Ticket 10: prototypes P1/P2 (explore) and the validation run. 111_200-111_599 and
    # 111_733-111_999 were never generated: not reserved, free for ticket 18.
    FORK_PROTOTYPE_SEEDS,
    FORK_VALIDATION_SEEDS,
    # Ticket 11: prototype P1, and the reserved second looks (unused unless ruled).
    BREAK_FORK_PROTOTYPE_SEEDS,
    BREAK_FORK_FREE_HELD_OUT_2_SEEDS,
    BREAK_FORK_DETECTION_HELD_OUT_2_SEEDS,
    # Ticket 13: the equality harness (prototypes/p13/identity.py), the null screen
    # (prototypes/p13/null_screen.py) and the finder's fresh frames (slice 7, C1).
    range(601_000, 601_100),
    range(602_000, 602_160),
    range(603_000, 603_100),
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
    # Ticket 07 (W1). THRESHOLD_CALIBRATION_SEEDS stays registered: those seeds stay spent.
    "STRIPE_FREE_CALIBRATION_SEEDS": STRIPE_FREE_CALIBRATION_SEEDS,
    # Ticket 11 (A2).
    "BREAK_FORK_FREE_CALIBRATION_SEEDS": BREAK_FORK_FREE_CALIBRATION_SEEDS,
}
