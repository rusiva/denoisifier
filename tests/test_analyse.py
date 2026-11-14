import dataclasses
import json
import re
from functools import cache
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest
from scipy import ndimage
from scipy.ndimage import gaussian_filter

from binning import bin_sensor_frame, bin_truth_mask
from borderline import BORDERLINE, borderline_frame
from cases import CASES, case_frame, clipped_at
from denoisifier import BinFactors, Report, analyse, analysis
from denoisifier.analysis import _ENVELOPE_SIGMA
from denoisifier.calibration import DEFAULT_FALSE_ALARM_RATE, Calibration, stored_calibration
from denoisifier.synthetic import (
    _SPIKE_BRIGHTNESS,
    _SPIKE_MAX_LENGTH,
    Emccd,
    StripedRegion,
    generate,
)
from inner_loop import WIDE, diagonal, inner
from protected import (
    AC4_MIN_CLIPPED_PIXELS,
    BBOX_TOL_PERIODS,
    BINNING_TEST_SEEDS,
    BORDERLINE_SCORE_WINDOW,
    CANDIDATE_CAP_HEADROOM,
    CLIP_DEPTH_EPS,
    CLIP_LEVEL_FRACTION,
    CLIP_MIN_SHARE,
    CLIP_TEST_SEEDS,
    DARK_FRACTION,
    DARK_REGRESSION_CASES,
    DEPTH_REGRESSION_CASES,
    ENVELOPE_TEST_SEEDS,
    EXTREMES_TEST_SEEDS,
    FALSE_ALARM_RATE_OPTION_TEST_SEED,
    FULL_FRAME_TEST_SEEDS,
    GATE_STORED_THRESHOLD,
    INNER_LOOP_SEED_COUNT,
    INPUT_NOT_MODIFIED_TEST_SEED,
    MASK_IOU_MIN,
    MILD_CLIP_LEVEL_FRACTION,
    MIN_SIZE_ABOVE_FACTOR,
    MIN_SIZE_BELOW_FACTOR,
    MIN_SIZE_TEST_SEEDS,
    MOTTLED_TEST_SEEDS,
    MULTISCALE_TEST_SEEDS,
    OTHER_FALSE_ALARM_RATE,
    OVERRIDE_LEVEL_FRACTION,
    PACKAGE_STORED_THRESHOLD,
    PACKAGE_STORED_THRESHOLD_5PCT,
    PARTIAL_CLIP_TEST_SEEDS,
    PEDESTAL_OFFSET,
    PERIOD_REL_TOL,
    PHASE_BREAK_TEST_SEED,
    PROFILE_ONLY_TEST_SEEDS,
    REGION_EDGE_PX,
    REGION_FRAME_SHAPE,
    REGION_TEST_SEEDS,
    REPORT_TO_JSON_TEST_SEED,
    SATURATING_CLIP_FACTOR,
    SCORE_AND_THRESHOLD_TEST_SEED,
    SINGLE_FRAME_TEST_SEED,
    SPIKE_BOUNDARY_TEST_SEED,
    SPIKE_PASS_MARK_PHOTONS,
    SPIKE_PIXELS_ABS_TOL,
    SPIKE_PIXELS_REL_TOL,
    SPIKE_SCORE_MEDIAN_TOL,
    SPIKE_STRESS_COUNT,
    SPIKE_TEST_COUNT,
    SPIKE_TEST_SEEDS,
    STRONG_TEST_SEEDS,
    TWO_REGION_PAIRS,
    TWO_REGION_TEST_SEEDS,
)
from regions import (
    assert_labels_consistent,
    iou,
    match,
    single_region,
    single_region_case,
    truth_bbox,
    truth_pixels,
    two_region_case,
)
from shared_cache import analysed
from truth_match import assert_depth_matches, assert_matches_truth

SHAPE = (256, 256)
SEEDS = MOTTLED_TEST_SEEDS
# About 100 photons at the peak, scorched mottle: the ticket 02 working point.
TYPICAL = dict(mottle="scorched", noise=Emccd())
TYPICAL_NOISE = dict(noise=Emccd())

# make test-fast runs the unmarked parameters only; the `wide` ones (tests/inner_loop.py) run
# in make check (ticket agent-gates/07).


@pytest.mark.parametrize("seed", inner(SEEDS))
def test_stripe_free_mottled_frames_are_not_striped(seed):
    _, report = analysed(seed=seed, shape=SHAPE, modulation_depth=0.0, **TYPICAL)
    assert report.striped is False
    assert report.regions == ()
    assert not report.mask().any()


# Every CASES entry runs in the inner loop: CASES[seed % 10] over the first 10 seeds.
CLEAR_STRIPES_PARAMS = inner(SEEDS, keep=len(CASES))


@pytest.mark.parametrize("seed", CLEAR_STRIPES_PARAMS)
def test_clear_stripes_in_mottle_are_found_and_measured(seed):
    period, angle_deg = CASES[seed % len(CASES)]
    s, report = analysed(
        seed=seed, shape=SHAPE, period=period, angle_deg=angle_deg, modulation_depth=0.5, **TYPICAL
    )
    assert_every_region_matches(report, s.truth)


def assert_every_region_matches(report, truth, depth=True):
    """Full-frame stripes: Striped, and every reported region (fragments are
    merged, ruling O3) has the true Period, Angle and depth."""
    assert report.striped is True
    assert report.regions
    for region in report.regions:
        assert_matches_truth(region.period_px, region.angle_deg, truth)
        if depth:
            assert_depth_matches(region.modulation_depth, truth)


FULL_FRAME_CASES = [(5, 0), (8, 6), (12, -8), (18, 3), (4, -4), (3, 10), (20, -10)]


@pytest.mark.parametrize("noise", [0.0, 0.01])
@pytest.mark.parametrize(
    ("seed", "period", "angle_deg"),
    [(seed, *case) for seed, case in zip(FULL_FRAME_TEST_SEEDS, FULL_FRAME_CASES, strict=True)],
)
def test_clear_full_frame_stripes_are_found_and_measured(seed, period, angle_deg, noise):
    s = generate(
        seed=seed,
        shape=SHAPE,
        period=period,
        angle_deg=angle_deg,
        modulation_depth=0.6,
        noise=noise,
    )
    report = analyse(s.frame)
    assert isinstance(report, Report)
    assert_every_region_matches(report, s.truth)


@pytest.mark.parametrize("noise", [0.0, 0.001, 0.01])
@pytest.mark.parametrize("seed", inner(PROFILE_ONLY_TEST_SEEDS))
def test_profile_only_frame_is_not_striped(seed, noise):
    s = generate(seed=seed, shape=SHAPE, modulation_depth=0.0, noise=noise)
    report = analyse(s.frame)
    assert report.striped is False
    assert report.regions == ()
    assert not report.mask().any()


def test_report_has_score_and_threshold():
    seed = SCORE_AND_THRESHOLD_TEST_SEED
    striped = analyse(generate(seed=seed, shape=SHAPE, period=9, modulation_depth=0.6).frame)
    plain = analyse(generate(seed=seed, shape=SHAPE, modulation_depth=0.0).frame)
    assert striped.score > striped.threshold
    assert plain.score < plain.threshold


# The Threshold options (ticket 07, plan 2.3): an injected Calibration, a false-alarm rate,
# or an explicit threshold.


@cache
def _option_frame():
    seed = SCORE_AND_THRESHOLD_TEST_SEED
    return generate(seed=seed, shape=SHAPE, period=9, modulation_depth=0.6).frame


def _scores_1_to_199():
    # n = 199: k = floor(0.01 * 200) = 2 -> 198; k = floor(0.05 * 200) = 10 -> 190.
    ids = [f"f{i}" for i in range(199)]
    return Calibration.from_scores(ids, np.arange(1.0, 200.0), (256, 256))


def test_an_injected_calibration_sets_the_threshold_at_the_default_rate():
    report = analyse(_option_frame(), calibration=_scores_1_to_199())
    assert report.threshold == 198.0
    assert report.striped == (report.score > 198.0) == bool(report.regions)
    assert report.score == analyse(_option_frame(), threshold=0.0).score


def test_a_false_alarm_rate_picks_the_threshold_of_the_calibration():
    report = analyse(_option_frame(), calibration=_scores_1_to_199(), false_alarm_rate=0.05)
    assert report.threshold == 190.0
    assert report.striped == (report.score > 190.0) == bool(report.regions)


def test_the_default_threshold_is_the_stored_calibration_at_one_percent():
    """AC 4, default path: no option gives the stored calibration's 1% Threshold."""
    report = analyse(_option_frame())
    assert report.threshold == stored_calibration().threshold(DEFAULT_FALSE_ALARM_RATE)
    assert report.threshold == PACKAGE_STORED_THRESHOLD
    assert report.striped == (report.score > report.threshold) == bool(report.regions)
    assert not hasattr(analysis, "THRESHOLD")


def test_false_alarm_rate_option_sets_the_threshold_and_verdict():
    """AC 2b/4: false_alarm_rate=0.05 on the stored calibration gives its 5% Threshold,
    the verdict ``score > threshold`` and the default path's score."""
    seed = FALSE_ALARM_RATE_OPTION_TEST_SEED
    case = CASES[seed % len(CASES)]
    frame = generate(
        seed=seed,
        shape=SHAPE,
        period=case.period,
        angle_deg=case.angle_deg,
        modulation_depth=0.2,
        noise=Emccd(),
    ).frame
    option = analyse(frame, false_alarm_rate=OTHER_FALSE_ALARM_RATE)
    default = analyse(frame)
    assert option.threshold == stored_calibration().threshold(OTHER_FALSE_ALARM_RATE)
    assert option.threshold == PACKAGE_STORED_THRESHOLD_5PCT
    assert option.striped == (option.score > option.threshold)
    assert option.score == default.score
    assert option.score > 0


def test_a_zero_false_alarm_rate_raises_on_the_stored_calibration():
    with pytest.raises(ValueError, match="false-alarm rate must be between 0 and 1"):
        analyse(_option_frame(), false_alarm_rate=0.0)


def test_an_explicit_threshold_is_used_as_is():
    assert analyse(_option_frame(), threshold=123.5).threshold == 123.5


@pytest.mark.parametrize("rate", [0.0, 1.0, -0.01])
def test_an_invalid_false_alarm_rate_raises(rate):
    with pytest.raises(ValueError, match="false-alarm rate must be between 0 and 1"):
        analyse(_option_frame(), calibration=_scores_1_to_199(), false_alarm_rate=rate)


@pytest.mark.parametrize(
    "other", [{"false_alarm_rate": 0.05}, {"calibration": "custom"}], ids=["rate", "calibration"]
)
def test_an_explicit_threshold_excludes_a_rate_or_a_calibration(other):
    if "calibration" in other:
        other = {"calibration": _scores_1_to_199()}
    with pytest.raises(ValueError, match="threshold= excludes false_alarm_rate= and calibration="):
        analyse(_option_frame(), threshold=100.0, **other)


def test_constant_frame_is_not_striped_and_has_finite_score():
    report = analyse(np.ones((64, 64)))
    assert report.striped is False
    assert report.score == 0.0
    assert report.regions == ()
    assert report.score < report.threshold
    assert report.spike_pixels == 0
    assert report.clipped_pixels == 0
    json.loads(report.to_json())


@pytest.mark.parametrize("value", [0.0, -5.0])
def test_frame_with_no_positive_light_is_rejected(value):
    with pytest.raises(
        ValueError, match="^" + re.escape("envelope max <= 0: frame has no positive light")
    ):
        analyse(np.full((64, 64), value))


def test_rejects_frame_smaller_than_min_side():
    with pytest.raises(
        ValueError, match="^" + re.escape("frame is 39x64; both sides must be at least")
    ):
        analyse(np.ones((39, 64)))
    report = analyse(
        generate(seed=SINGLE_FRAME_TEST_SEED, shape=(40, 64), modulation_depth=0.0).frame
    )
    assert isinstance(report, Report)


def test_rejects_non_2d_input():
    with pytest.raises(ValueError, match="^" + re.escape("frame must be 2D, got 1D")):
        analyse(np.ones(100))


def test_rejects_non_finite_values():
    frame = generate(seed=SINGLE_FRAME_TEST_SEED, shape=(64, 64)).frame
    frame[10, 10] = np.nan
    with pytest.raises(ValueError, match="^" + re.escape("frame contains non-finite values")):
        analyse(frame)


def test_input_frame_is_not_modified():
    frame = generate(seed=INPUT_NOT_MODIFIED_TEST_SEED, shape=(64, 64)).frame
    before = frame.copy()
    analyse(frame)
    assert np.array_equal(frame, before)


@pytest.mark.parametrize("modulation_depth", [0.6, 0.0])
def test_report_converts_to_json(modulation_depth):
    report = analyse(
        generate(
            seed=REPORT_TO_JSON_TEST_SEED, shape=SHAPE, modulation_depth=modulation_depth
        ).frame
    )
    data = json.loads(report.to_json())
    assert list(data) == [
        "striped",
        "score",
        "threshold",
        "transposed",
        "bin_factors",
        "units",
        "regions",
        "spike_pixels",
        "clipped_pixels",
        "unresolved_period_px",
        "warnings",
    ]
    assert data["bin_factors"] == {"horizontal": 1, "vertical": 1}
    assert data["unresolved_period_px"] is None
    assert data["warnings"] == []
    for key in ("spike_pixels", "clipped_pixels"):
        assert type(data[key]) is int
        assert data[key] == getattr(report, key)
    assert type(data["striped"]) is bool
    assert type(data["score"]) is float
    assert type(data["threshold"]) is float
    assert data["transposed"] is False
    assert len(data["regions"]) == len(report.regions) == (1 if modulation_depth else 0)
    for entry, region in zip(data["regions"], report.regions, strict=True):
        assert list(entry) == [
            "label",
            "period_px",
            "angle_deg",
            "modulation_depth",
            "bbox",
            "area_px",
        ]
        assert list(entry["bbox"]) == ["row_start", "row_stop", "col_start", "col_stop"]
        assert all(type(v) is int for v in entry["bbox"].values())
        assert type(entry["label"]) is int
        assert type(entry["area_px"]) is int
        for key in ("period_px", "angle_deg", "modulation_depth"):
            assert type(entry[key]) is float
        assert entry == {
            "label": region.label,
            "period_px": region.period_px,
            "angle_deg": region.angle_deg,
            "modulation_depth": region.modulation_depth,
            "bbox": dataclasses.asdict(region.bbox),
            "area_px": region.area_px,
        }
    assert data["striped"] == report.striped
    assert data["score"] == report.score
    assert data["threshold"] == report.threshold


@pytest.mark.parametrize(("period", "seed"), diagonal(STRONG_TEST_SEEDS, [(5,), (12,)]))
def test_strong_stripes_are_measured(seed, period):
    s = generate(
        seed=seed, shape=SHAPE, period=period, angle_deg=6, modulation_depth=0.8, **TYPICAL
    )
    report = analyse(s.frame)
    assert_every_region_matches(report, s.truth)


def _crop_columns(profile, rows, width=128, step=8):
    """Bright and dim column windows, by mean Profile level (fraction of its peak)."""
    peak = profile.max()
    starts = list(range(0, profile.shape[1] - width + 1, step))
    level = {c0: profile[rows, c0 : c0 + width].mean() / peak for c0 in starts}
    bright = max(starts, key=level.get)
    # Dim: the flank whose edge window is darker, at the highest level <= 0.3.
    if level[starts[0]] <= level[starts[-1]]:
        flank = [c0 for c0 in starts if c0 < bright]
    else:
        flank = [c0 for c0 in starts if c0 > bright]
    dim = max((c0 for c0 in flank if level[c0] <= 0.3), key=level.get)
    return (bright, level[bright]), (dim, level[dim])


@pytest.mark.parametrize("noise", [0.0, Emccd()], ids=["noise-free", "emccd"])
@pytest.mark.parametrize("seed", inner(ENVELOPE_TEST_SEEDS))
def test_modulation_depth_is_relative_to_local_envelope(seed, noise):
    shape = (256, 640)
    s = generate(
        seed=seed,
        shape=shape,
        period=8,
        angle_deg=4,
        modulation_depth=0.5,
        mottle="scorched",
        noise=noise,
    )
    # Same seed and shape draw the same Profile, so this frame's clean is the Profile alone.
    profile = generate(seed=seed, shape=shape, modulation_depth=0.0, mottle="none", noise=0.0).clean
    rows = slice(64, 192)
    (bright, bright_level), (dim, dim_level) = _crop_columns(profile, rows)
    assert 0.2 <= dim_level <= 0.3
    assert bright_level >= 2.5 * dim_level

    depths = []
    for c0 in (bright, dim):
        report = analyse(s.frame[rows, c0 : c0 + 128])
        assert report.striped is True
        largest = report.regions[0]
        assert_depth_matches(largest.modulation_depth, s.truth)
        depths.append(largest.modulation_depth)
    assert abs(depths[0] - depths[1]) <= 0.05


EXTREMES = [(3, -10), (3, 0), (3, 10), (20, -10), (20, 0), (20, 10), (3, 5), (20, -5)]


@pytest.mark.parametrize(
    ("seed", "period", "angle_deg"),
    [(seed, *case) for seed, case in zip(EXTREMES_TEST_SEEDS, EXTREMES, strict=True)],
)
def test_period_and_angle_extremes_are_detected(seed, period, angle_deg):
    s = generate(
        seed=seed, shape=SHAPE, period=period, angle_deg=angle_deg, modulation_depth=0.5, **TYPICAL
    )
    report = analyse(s.frame)
    assert_every_region_matches(report, s.truth, depth=False)


@pytest.mark.parametrize("seed", inner(MULTISCALE_TEST_SEEDS))
def test_multiscale_mottle_is_handled(seed):
    common = dict(seed=seed, shape=SHAPE, mottle="multiscale", noise=Emccd())
    assert analyse(generate(**common, modulation_depth=0.0).frame).striped is False

    period, angle_deg = [3, 8, 20][seed % 3], [-10, 0, 10][(seed // 3) % 3]
    s = generate(**common, period=period, angle_deg=angle_deg, modulation_depth=0.5)
    report = analyse(s.frame)
    assert_every_region_matches(report, s.truth, depth=False)


@pytest.mark.parametrize(("seed", "period"), BORDERLINE)
def test_borderline_striped_frame_has_finite_measurements(seed, period):
    report = analyse(borderline_frame(seed, period))
    assert report.threshold < report.score < BORDERLINE_SCORE_WINDOW * report.threshold
    assert report.striped is True
    for region in report.regions:
        for value in (region.period_px, region.angle_deg, region.modulation_depth):
            assert np.isfinite(value)
    json.loads(report.to_json())


# --- Striped Regions (ticket 05) ---------------------------------------------


@pytest.mark.parametrize("seed", inner(REGION_TEST_SEEDS))
def test_partial_region_is_reported_with_its_measurements(seed):
    period, angle_deg = CASES[seed % len(CASES)]
    s, report = single_region_case(seed, period, angle_deg)
    assert report.striped is True
    (region,) = report.regions
    (truth,) = s.truth.regions
    assert_matches_truth(region.period_px, region.angle_deg, truth)
    assert_depth_matches(region.modulation_depth, truth)
    r0, r1, c0, c1 = truth_bbox(truth_pixels(truth))
    b = region.bbox
    tol = BBOX_TOL_PERIODS * period
    for got, want in ((b.row_start, r0), (b.row_stop, r1), (b.col_start, c0), (b.col_stop, c1)):
        assert abs(got - want) <= tol
    assert_labels_consistent(report)


@pytest.mark.parametrize(("seed", "period", "angle_deg", "mottle"), DEPTH_REGRESSION_CASES)
def test_depth_is_measured_on_the_region_interior(seed, period, angle_deg, mottle):
    """First fresh range's misses: the depth came from a seed area reaching
    into the blurred skirt and measured 0.38-0.39 against 0.5."""
    s, report = single_region_case(seed, period, angle_deg, mottle)
    (region,) = report.regions
    (truth,) = s.truth.regions
    assert_matches_truth(region.period_px, region.angle_deg, truth)
    assert_depth_matches(region.modulation_depth, truth)


@pytest.mark.parametrize(
    ("seed", "mottle"),
    diagonal(REGION_TEST_SEEDS, [("scorched",), ("multiscale",)], seed_first=True),
)
def test_mask_overlaps_the_true_region(seed, mottle):
    period, angle_deg = CASES[seed % len(CASES)]
    s, report = single_region_case(seed, period, angle_deg, mottle)
    (truth,) = s.truth.regions
    assert iou(report.mask(), truth_pixels(truth)) >= MASK_IOU_MIN


# The 640x1024 frame is the slowest to analyse: the inner loop analyses it once, for
# (76, 5, 12), shared through two_region_case with the verdict sweep's "two-region" frame.
TWO_REGION_PARAMS = inner(
    [(seed, *pair) for seed in TWO_REGION_TEST_SEEDS for pair in TWO_REGION_PAIRS],
    keep=1,
    multi=True,
)


@pytest.mark.parametrize(("seed", "left", "right"), TWO_REGION_PARAMS)
def test_two_regions_with_different_periods_are_reported_separately(seed, left, right):
    s, report = two_region_case(seed, left, right)
    assert len(report.regions) == 2
    pairs = match(report.regions, report.labels, s.truth.regions)
    assert {id(t) for _, t in pairs} == {id(t) for t in s.truth.regions}
    for region, truth in pairs:
        assert_matches_truth(region.period_px, region.angle_deg, truth)
        assert iou(report.labels == region.label, truth_pixels(truth)) >= MASK_IOU_MIN
    assert_labels_consistent(report)


def _size_test_frame(seed, period, angle_deg, semi_axes_px):
    """One region at low noise (no Mottle, Gaussian 0.01), sharp edge, m = 0.6."""
    region = StripedRegion(
        center=(127.5, 127.5),
        semi_axes=semi_axes_px,
        rotation_deg=0.0,
        edge_px=1.0,
        period=float(period),
        angle_deg=float(angle_deg),
        modulation_depth=0.6,
    )
    return generate(seed=seed, shape=SHAPE, regions=[region])


# Semi-axes (rows, cols) per shape, for Period p and factor f: the 0.5-contour
# box is 2 x rows tall and 2 x cols wide; the minimum is 2p tall, 3p wide.
SIZE_SHAPES = {
    "both": lambda p, f: (f * p, 1.5 * f * p),  # 2fp tall, 3fp wide
    "wide_short": lambda p, f: (f * p, 2.0 * p),  # 2fp tall, 4p wide: height only
    "four_by_one": lambda p, _f: (0.5 * p, 2.0 * p),  # 1p tall, 4p wide
    "narrow_tall": lambda p, f: (2.0 * p, 1.5 * f * p),  # 4p tall, 3fp wide: width only
}
SIZE_PERIODS = (3, 8, 20)
SIZE_ANGLES = (-10, 10)
SIZE_CASES = [(p, a) for p in SIZE_PERIODS for a in SIZE_ANGLES]


def _size_params(shapes):
    """(seed, Period, Angle, shape) over every seed, SIZE_CASE and shape. The inner loop keeps
    each (shape i, Period j) once, at Angle SIZE_ANGLES[(i + j) % 2], on the first seeds in
    turn: every shape meets every Period, and every Period both Angles."""

    def cover(case):
        period, angle_deg, shape = case
        i, j = shapes.index(shape), SIZE_PERIODS.index(period)
        return angle_deg == SIZE_ANGLES[(i + j) % len(SIZE_ANGLES)]

    cases = [(period, angle_deg, shape) for period, angle_deg in SIZE_CASES for shape in shapes]
    return diagonal(MIN_SIZE_TEST_SEEDS, cases, seed_first=True, cover=cover)


BELOW_SIZE_PARAMS = _size_params(list(SIZE_SHAPES))
ABOVE_SIZE_PARAMS = _size_params(["both", "wide_short", "narrow_tall"])


@pytest.mark.parametrize(("seed", "period", "angle_deg", "shape"), BELOW_SIZE_PARAMS)
def test_region_below_the_minimum_is_not_reported(seed, period, angle_deg, shape):
    axes = SIZE_SHAPES[shape](period, MIN_SIZE_BELOW_FACTOR)
    report = analyse(_size_test_frame(seed, period, angle_deg, axes).frame)
    assert report.regions == ()
    assert report.striped is False


@pytest.mark.parametrize(("seed", "period", "angle_deg", "shape"), ABOVE_SIZE_PARAMS)
def test_region_above_the_minimum_is_reported(seed, period, angle_deg, shape):
    axes = SIZE_SHAPES[shape](period, MIN_SIZE_ABOVE_FACTOR)
    s = _size_test_frame(seed, period, angle_deg, axes)
    report = analyse(s.frame)
    (region,) = report.regions
    assert abs(region.period_px - period) <= PERIOD_REL_TOL * period


@pytest.mark.parametrize("seed", inner(REGION_TEST_SEEDS[:3]))
def test_stripes_on_one_flank_of_the_envelope_are_found(seed):
    period, angle_deg = CASES[seed % len(CASES)]
    rows, cols = REGION_FRAME_SHAPE
    region = single_region(period, angle_deg, center=((rows - 1) / 2, cols / 4))
    s = generate(seed=seed, shape=REGION_FRAME_SHAPE, regions=[region], **TYPICAL)
    report = analyse(s.frame)
    assert report.striped is True
    (found,) = report.regions
    assert found.bbox.col_stop <= cols // 2
    assert abs(found.period_px - period) <= PERIOD_REL_TOL * period


DARK_CASES = {
    "full-frame-noise-free": dict(modulation_depth=0.6, noise=0.0),
    "full-frame-typical": dict(modulation_depth=0.6, mottle="scorched", **TYPICAL_NOISE),
    "spilling-region": dict(
        regions=[
            StripedRegion(
                center=(127.5, 127.5),
                semi_axes=(200.0, 200.0),
                rotation_deg=0.0,
                edge_px=6.0,
                period=8.0,
                angle_deg=4.0,
                modulation_depth=0.6,
            )
        ],
        noise=0.0,
    ),
}


DARK_PARAMS = [
    *inner(
        [(seed, case) for seed in ENVELOPE_TEST_SEEDS for case in DARK_CASES],
        key=lambda value: value[0],
        multi=True,
    ),
    # First fresh range's miss: two mask pixels in a corner at Profile 4.9%. Always run.
    *DARK_REGRESSION_CASES,
]


@pytest.mark.parametrize(("seed", "case"), DARK_PARAMS)
def test_dark_area_is_never_reported_as_striped(seed, case):
    kwargs = DARK_CASES[case]
    report = analyse(generate(seed=seed, shape=SHAPE, **kwargs).frame)
    assert report.striped is True
    # "Dark" is the surround outside the spot: the Profile (no Mottle, same
    # seed, noise 0) below DARK_FRACTION of its max. Mottle holes inside the
    # spot are not dark: the truth mask of a region includes them (ruling R2).
    profile = generate(seed=seed, shape=SHAPE, regions=(), mottle="none", noise=0.0).clean
    dark = profile < DARK_FRACTION * profile.max()
    assert dark.any()
    assert not report.mask()[dark].any()


def _overlap_frame():
    """Two regions, Periods 8 and 16 (so not merged) and Angles -6 and 6 deg,
    whose ellipses overlap by 40 px across: their grown extents overlap
    (test_overlapping_extents_frame_settles_an_overlap)."""
    common = dict(semi_axes=(50.0, 60.0), rotation_deg=0.0, edge_px=4.0, modulation_depth=0.5)
    regions = [
        StripedRegion(center=(127.5, 215.5), period=8.0, angle_deg=-6.0, **common),
        StripedRegion(center=(127.5, 295.5), period=16.0, angle_deg=6.0, **common),
    ]
    return generate(seed=TWO_REGION_TEST_SEEDS[0], shape=(256, 512), regions=regions).frame


def test_overlapping_extents_frame_settles_an_overlap(monkeypatch):
    """The "overlapping-extents" sweep frame does what its name says: two
    qualifying groups whose grown extents overlap reach the overlap settling,
    and each overlap pixel goes to exactly one reported region."""
    settled = []
    settle = analysis._settle_overlaps

    def spy(groups, *rest):
        survivors = settle(groups, *rest)
        settled.append((list(groups), survivors))
        return survivors

    monkeypatch.setattr(analysis, "_settle_overlaps", spy)
    report = analyse(_overlap_frame(), threshold=0.0)
    ((groups, survivors),) = settled
    overlaps = [a.grown & b.grown for a, b in combinations(groups, 2)]
    overlap = np.logical_or.reduce(overlaps) if overlaps else np.zeros(report.labels.shape, bool)
    assert overlap.any(), "no two qualifying groups' grown extents overlap"
    assert len(report.regions) == len(survivors) >= 2
    # Settled: the overlap is reported, and each pixel under one label only.
    assert report.mask()[overlap].all()
    assert sum(s.area_px for s in survivors) == report.mask().sum()
    assert_labels_consistent(report)


def _frame_and_report(case):
    """(frame, Report) of a cached (Synthetic, Report)."""
    s, report = case
    return s.frame, report


def _typical_sweep_frame(seed, **kwargs):
    return _frame_and_report(analysed(seed=seed, shape=SHAPE, **kwargs, **TYPICAL))


def _analysed_frame(frame):
    return frame, analyse(frame)


# Each sweep frame by name: a function giving (frame, its Report at the default threshold).
# The free and striped frames share that analysis with the other tests of the same generate call
# (shared_cache.analysed); the two-region frame with test_two_regions_* (two_region_case).
SWEEP_FRAMES = {
    **{
        f"free-{seed}": (lambda seed=seed: _typical_sweep_frame(seed, modulation_depth=0.0))
        for seed in MOTTLED_TEST_SEEDS[:5]
    },
    **{
        f"striped-{seed}": (
            lambda seed=seed: _typical_sweep_frame(
                seed,
                period=CASES[seed % len(CASES)].period,
                angle_deg=CASES[seed % len(CASES)].angle_deg,
                modulation_depth=0.5,
            )
        )
        for seed in MOTTLED_TEST_SEEDS[:5]
    },
    **{
        f"borderline-{seed}-{period}": (
            lambda c=(seed, period): _analysed_frame(borderline_frame(*c))
        )
        for seed, period in BORDERLINE
    },
    "two-region": lambda: _frame_and_report(
        two_region_case(TWO_REGION_TEST_SEEDS[0], *TWO_REGION_PAIRS[0])
    ),
    "overlapping-extents": lambda: _analysed_frame(_overlap_frame()),
    "constant": lambda: _analysed_frame(np.ones((64, 64))),
}


# The default path's threshold: the stored calibration at the default rate (ticket 07).
DEFAULT_THRESHOLD = stored_calibration().threshold(DEFAULT_FALSE_ALARM_RATE)

# The thresholds of the verdict tests, by kind: each kind is its own test
# item, so no item runs more than three analyses of its frame (the two-region
# frame takes about 9 s per analysis; the per-test timeout is 60 s).
SWEEP_THRESHOLDS = ("zero", "default", "score", "above-score", "below-score", "inf")


def _sweep_threshold(name, kind):
    if kind == "default":
        return DEFAULT_THRESHOLD
    score = _sweep_report(name, "default").score
    return {
        "zero": 0.0,
        "score": score,
        "above-score": np.nextafter(score, np.inf),
        # Below a zero score is negative, which analyse rejects: 0 again.
        "below-score": max(np.nextafter(score, -np.inf), 0.0),
        "inf": np.inf,
    }[kind]


@cache
def _sweep_frame(name):
    """(frame, Report at the default threshold) of sweep frame ``name``, built once per run."""
    return SWEEP_FRAMES[name]()


@cache
def _sweep_report(name, kind):
    """``analyse`` of sweep frame ``name`` at threshold ``kind``, on the real path."""
    frame, report = _sweep_frame(name)
    if kind == "default":
        return report
    return analyse(frame, threshold=_sweep_threshold(name, kind))


# The inner loop's striped sweep frames: the first INNER_LOOP_SEED_COUNT seeds.
_INNER_STRIPED = [f"striped-{seed}" for seed in MOTTLED_TEST_SEEDS[:INNER_LOOP_SEED_COUNT]]
# The lowering test's inner pairs: every threshold kind, on frames the verdict sweep analyses.
# Only a pair whose high side is below the score has regions to compare, so (zero, default)
# and (zero, below-score) carry the teeth; (below-score, score) and (above-score, inf) are
# there for kind coverage. The two-region frame is wide: the inner loop analyses it once.
_ZERO_VS_DEFAULT = frozenset(("zero", "default"))
LOWERING_INNER_PAIRS = {
    _INNER_STRIPED[0]: {
        _ZERO_VS_DEFAULT,
        frozenset(("zero", "below-score")),
        frozenset(("below-score", "score")),
        frozenset(("above-score", "inf")),
    },
    **{name: {_ZERO_VS_DEFAULT} for name in _INNER_STRIPED[1:]},
    "overlapping-extents": {_ZERO_VS_DEFAULT},
}


def _verdict_runs_in_the_inner_loop(name, kind):
    """Every sweep frame at the default threshold (one analysis, mostly shared); every
    threshold kind on the constant frame and on the analyses the lowering test's inner
    pairs read; and the first stripe-free frame at zero, where it reports groups below
    the default."""
    return (
        kind == "default"
        or name == "constant"
        or any(kind in pair for pair in LOWERING_INNER_PAIRS.get(name, ()))
        or (name, kind) == (f"free-{MOTTLED_TEST_SEEDS[0]}", "zero")
    )


VERDICT_PARAMS = [
    (name, kind)
    if _verdict_runs_in_the_inner_loop(name, kind)
    else pytest.param(name, kind, marks=WIDE)
    for name in SWEEP_FRAMES
    for kind in SWEEP_THRESHOLDS
]


@pytest.mark.parametrize(("name", "kind"), VERDICT_PARAMS)
def test_verdict_is_striped_exactly_when_a_region_is_reported(name, kind):
    report = _sweep_report(name, kind)
    assert report.score == _sweep_report(name, "default").score
    t = _sweep_threshold(name, kind)
    assert report.threshold == t
    assert report.striped == bool(report.regions) == (report.score > t)
    assert_labels_consistent(report)
    if name == "constant":
        assert report.score == 0.0
        assert not report.regions
        assert not report.mask().any()


def test_sweep_thresholds_are_the_planned_ones():
    """The kinds give 0, the default threshold, the score, its two neighbours and inf."""
    name = "striped-" + str(MOTTLED_TEST_SEEDS[0])
    score = _sweep_report(name, "default").score
    assert score > 0
    got = {_sweep_threshold(name, k) for k in SWEEP_THRESHOLDS}
    want = {
        0.0,
        DEFAULT_THRESHOLD,
        score,
        np.nextafter(score, np.inf),
        np.nextafter(score, -np.inf),
    }
    assert got == want | {np.inf}


def _regions_by_bbox(report):
    return {r.bbox: (r, report.labels == r.label) for r in report.regions}


LOWERING_PARAMS = [
    (name, a, b)
    if frozenset((a, b)) in LOWERING_INNER_PAIRS.get(name, ())
    else pytest.param(name, a, b, marks=WIDE)
    for name in [
        "two-region",
        "overlapping-extents",
        *[f"striped-{s}" for s in MOTTLED_TEST_SEEDS[:5]],
    ]
    for a, b in combinations(SWEEP_THRESHOLDS, 2)
]


@pytest.mark.parametrize(("name", "kind_a", "kind_b"), LOWERING_PARAMS)
def test_lowering_the_threshold_keeps_reported_regions_unchanged(name, kind_a, kind_b):
    if name == "overlapping-extents":
        assert len(_sweep_report(name, "zero").regions) >= 2
    low, high = sorted(
        (_sweep_report(name, kind_a), _sweep_report(name, kind_b)), key=lambda r: r.threshold
    )
    low_regions = _regions_by_bbox(low)
    for bbox, (region, pixels) in _regions_by_bbox(high).items():
        assert bbox in low_regions
        other, other_pixels = low_regions[bbox]
        assert dataclasses.replace(other, label=region.label) == region
        assert np.array_equal(other_pixels, pixels)


@pytest.mark.parametrize("threshold", [-1.0, np.nan])
def test_rejects_negative_or_nan_threshold(threshold):
    with pytest.raises(ValueError, match="^" + re.escape("threshold must be >= 0")):
        analyse(np.ones((64, 64)), threshold=threshold)


def test_rejects_nan_clip_level():
    with pytest.raises(
        ValueError, match="^" + re.escape("clip_level must be a number or inf, got nan")
    ):
        analyse(np.ones((64, 64)), clip_level=np.nan)


# Ticket 06: Spikes and Clipped Pixels (plan .scratch/stripe-detector/handoffs/06-plan.md,
# section 3). "Typical" frames: TYPICAL, SHAPE, CASES[seed % 10] for Period and Angle.
# C(f) = f x the same frame's clean maximum. The spike-count seeds pass the out-of-model
# stimulus check (no hit run taller than _SPIKE_MAX_LENGTH; ticket Comments, step 5a).

SPIKE_FRAMES = {
    "typical-m0": dict(modulation_depth=0.0, **TYPICAL),
    "typical-m0.5": dict(modulation_depth=0.5, **TYPICAL),
    "gaussian-m0.5": dict(modulation_depth=0.5, mottle="scorched", noise=0.01),
    "pass-mark-m0.5": dict(
        modulation_depth=0.5, mottle="scorched", noise=Emccd(photons_peak=SPIKE_PASS_MARK_PHOTONS)
    ),
}


def _case_frame(seed, **kwargs):
    return case_frame(seed, shape=SHAPE, **kwargs)


def assert_spike_count(reported, true):
    assert abs(reported - true) <= max(SPIKE_PIXELS_ABS_TOL, SPIKE_PIXELS_REL_TOL * true)


def assert_spikes_in_the_model(truth):
    """The stimulus precondition (plan section 3), on the generator's truth only: no
    8-connected group of hit pixels spans more than _SPIKE_MAX_LENGTH rows (two hits
    overlapping into a longer vertical run are outside the spike model)."""
    labels, _ = ndimage.label(truth.spike_mask, structure=np.ones((3, 3)))
    heights = [rows.stop - rows.start for rows, _ in ndimage.find_objects(labels)]
    assert heights
    assert max(heights) <= _SPIKE_MAX_LENGTH


def _verdicts_and_region_counts(frame):
    """(striped, number of regions) at THRESHOLD and at GATE_STORED_THRESHOLD."""
    reports = (analyse(frame), analyse(frame, threshold=GATE_STORED_THRESHOLD))
    return [(r.striped, len(r.regions)) for r in reports]


@pytest.mark.parametrize(("kind", "seed"), diagonal(SPIKE_TEST_SEEDS, [(k,) for k in SPIKE_FRAMES]))
def test_report_counts_spike_pixels(kind, seed):
    """AC 2 is about the count. On striped frames the detection is paired with the same
    seed without Spikes (verdict and region count at both thresholds), not asserted
    against the truth: stripes at the 30-photon pass mark are outside ticket 06 (ticket
    06 Comments, orchestrator ruling on the 5c acceptance)."""
    s = _case_frame(seed, spikes=SPIKE_TEST_COUNT, **SPIKE_FRAMES[kind])
    assert_spikes_in_the_model(s.truth)
    report = analyse(s.frame)
    assert_spike_count(report.spike_pixels, s.truth.spike_pixels)
    assert report.clipped_pixels == 0
    if SPIKE_FRAMES[kind]["modulation_depth"] > 0:
        free = _case_frame(seed, **SPIKE_FRAMES[kind])
        assert _verdicts_and_region_counts(s.frame) == _verdicts_and_region_counts(free.frame)


@pytest.mark.parametrize(
    ("kind", "seed"), diagonal(SPIKE_TEST_SEEDS, [("typical-m0",), ("typical-m0.5",)])
)
def test_saturated_spikes_are_counted_as_spikes(kind, seed):
    """A clip at SATURATING_CLIP_FACTOR x the clean maximum saturates the bright Spikes; on a
    dim column a saturated Spike is still a Spike, and the rest of the plateau is clipped."""
    kwargs = dict(spikes=SPIKE_TEST_COUNT, **SPIKE_FRAMES[kind])
    s, _ = clipped_at(SATURATING_CLIP_FACTOR, _case_frame, seed=seed, **kwargs)
    assert_spikes_in_the_model(s.truth)
    report = analyse(s.frame)
    assert_spike_count(report.spike_pixels, s.truth.spike_pixels)
    assert report.clipped_pixels == s.truth.clipped_pixels


def test_spike_count_ignores_the_pedestal():
    """A higher Pedestal (a bias offset) or a constant dark subtraction (negative pixels)
    changes nothing."""
    s = _case_frame(SPIKE_TEST_SEEDS[0], spikes=SPIKE_TEST_COUNT, **SPIKE_FRAMES["typical-m0.5"])
    frame = s.frame
    # Half the light peak _light sees (the smoothed clean frame; B2/B3), not a Spike.
    shifted = frame - gaussian_filter(s.clean, _ENVELOPE_SIGMA).max() / 2
    assert (shifted < 0).any()
    counts = [analyse(f).spike_pixels for f in (frame, frame + PEDESTAL_OFFSET, shifted)]
    assert counts[0] == counts[1] == counts[2]
    assert_spike_count(counts[0], s.truth.spike_pixels)


def test_dimmest_spikes_are_found():
    """Single pixels at exactly the dimmest generated Spike brightness, spread apart."""
    s = _case_frame(SPIKE_BOUNDARY_TEST_SEED, **SPIKE_FRAMES["typical-m0.5"])
    frame = s.frame.copy()
    rows = np.linspace(20, SHAPE[0] - 21, 5).round().astype(int)
    cols = np.linspace(20, SHAPE[1] - 21, 6).round().astype(int)
    hits = [(r, c) for r in rows for c in cols]
    assert len(hits) == SPIKE_TEST_COUNT
    for r, c in hits:
        frame[r, c] += _SPIKE_BRIGHTNESS[0] * s.clean.max()
    assert_spike_count(analyse(frame).spike_pixels, len(hits))


def _phase_break_frame(period):
    """Stripes whose lower half is shifted sideways by half a Period (noise 0, m 1)."""
    s = generate(
        seed=PHASE_BREAK_TEST_SEED, shape=SHAPE, period=period, modulation_depth=1.0, noise=0.0
    )
    frame = s.frame.copy()
    half = SHAPE[0] // 2
    frame[half:] = np.roll(frame[half:], round(period / 2), axis=1)
    return frame


def _params_per_seed(seeds, params_of):
    """The pytest.params ``params_of(seed)`` for every seed, in seed order; those of seeds
    beyond the inner loop's first ones are WIDE."""
    params = []
    for value in inner(seeds):
        if isinstance(value, int):
            params += params_of(value)
        else:
            params += inner(params_of(*value.values), keep=0)
    return params


def _case_report(seed, **kwargs):
    """``analyse`` of ``_case_frame(seed, **kwargs)``, shared with every test of the same
    generate call (shared_cache.analysed)."""
    case = CASES[seed % len(CASES)]
    s_kwargs = dict(period=case.period, angle_deg=case.angle_deg, **kwargs)
    return analysed(seed=seed, shape=SHAPE, **s_kwargs)[1]


# Each spike-free frame: a function giving its Report at the defaults.
SPIKE_FREE_FRAMES = [
    *_params_per_seed(
        MOTTLED_TEST_SEEDS,
        lambda seed: [
            pytest.param(
                lambda seed=seed, m=m: _case_report(seed, modulation_depth=m, **TYPICAL),
                id=f"mottled-{seed}-m{m}",
            )
            for m in (0.0, 0.5)
        ],
    ),
    *[
        pytest.param(
            lambda seed=seed, case=case, noise=noise: analyse(
                generate(
                    seed=seed,
                    shape=SHAPE,
                    period=case[0],
                    angle_deg=case[1],
                    modulation_depth=0.6,
                    noise=noise,
                ).frame
            ),
            id=f"full-frame-{seed}-P{case[0]}-{case[1]}deg-noise{noise}",
        )
        for seed, case in zip(FULL_FRAME_TEST_SEEDS, FULL_FRAME_CASES, strict=True)
        for noise in (0.0, 0.01)
    ],
    *_params_per_seed(
        PROFILE_ONLY_TEST_SEEDS,
        lambda seed: [
            pytest.param(
                lambda seed=seed: analyse(
                    generate(seed=seed, shape=SHAPE, modulation_depth=0.0, noise=0.0).frame
                ),
                id=f"profile-only-{seed}",
            )
        ],
    ),
    *[
        pytest.param(lambda p=p: analyse(_phase_break_frame(p)), id=f"phase-break-P{p}")
        for p in (3, 20)
    ],
]


@pytest.mark.parametrize("make_report", SPIKE_FREE_FRAMES)
def test_spike_free_frames_report_no_spikes(make_report):
    report = make_report()
    assert report.spike_pixels <= SPIKE_PIXELS_ABS_TOL
    assert report.clipped_pixels == 0


@cache
def _clipped_full_frame(seed):
    """Typical m 0.5, spike-free, clipped at C(CLIP_LEVEL_FRACTION):
    (synthetic, clip level, auto report, inf report)."""
    kwargs = SPIKE_FRAMES["typical-m0.5"]
    s, level = clipped_at(CLIP_LEVEL_FRACTION, _case_frame, seed=seed, **kwargs)
    return s, level, analyse(s.frame), analyse(s.frame, clip_level=np.inf)


@pytest.mark.parametrize("seed", CLIP_TEST_SEEDS)
def test_report_counts_clipped_pixels(seed):
    s, _, report, _ = _clipped_full_frame(seed)
    assert report.clipped_pixels == s.truth.clipped_pixels
    assert report.spike_pixels <= SPIKE_PIXELS_ABS_TOL


@pytest.mark.parametrize("seed", inner(CLIP_TEST_SEEDS))
def test_clipped_and_spike_totals_match_at_a_peak_level_clip(seed):
    """A Spike saturated inside the clip plateau is counted as clipped, so only the total
    of the two counts is compared with the truth's."""
    kwargs = dict(spikes=SPIKE_TEST_COUNT, **SPIKE_FRAMES["typical-m0.5"])
    s, _ = clipped_at(CLIP_LEVEL_FRACTION, _case_frame, seed=seed, **kwargs)
    assert_spikes_in_the_model(s.truth)
    report = analyse(s.frame)
    assert_spike_count(
        report.spike_pixels + report.clipped_pixels,
        s.truth.spike_pixels + s.truth.clipped_pixels,
    )


@cache
def _spike_pair_scores(seed, clip):
    """Paired per seed: the scores of the same stripe-free frame without and with
    SPIKE_STRESS_COUNT Spikes (with ``clip``, the spiked frame is also clipped at
    SATURATING_CLIP_FACTOR x the clean maximum, auto detection). The stripe-free frame is
    generated and analysed once per seed, shared by both clips and the other tests of the same
    generate call (shared_cache.analysed)."""
    kwargs = dict(modulation_depth=0.0, **TYPICAL)
    free, free_report = analysed(seed=seed, shape=SHAPE, **kwargs)
    level = SATURATING_CLIP_FACTOR * free.clean.max() if clip else None
    spiked = generate(seed=seed, shape=SHAPE, spikes=SPIKE_STRESS_COUNT, clip_level=level, **kwargs)
    return free_report.score, analyse(spiked.frame).score


SPIKE_PAIRS = [(seed, clip) for clip in (False, True) for seed in SEEDS]


@pytest.mark.parametrize("clip", [False, True], ids=["spikes", "spikes-clipped"])
@pytest.mark.parametrize("seed", SEEDS)
def test_spikes_do_not_change_the_verdict_on_stripe_free_frames(seed, clip):
    """The verdict at a threshold T is ``score > T`` (pinned by
    test_verdict_is_striped_exactly_when_a_region_is_reported), so one analysis gives the
    verdict at the default threshold and at GATE_STORED_THRESHOLD. No per-seed score tolerance: the
    score jumps when a sub-threshold group appears or vanishes under the hard group gating
    (ticket 06 Comments, ruling after critic 3; ticket 07)."""
    free, spiked = _spike_pair_scores(seed, clip)
    assert (spiked > DEFAULT_THRESHOLD) == (free > DEFAULT_THRESHOLD)
    assert (spiked > GATE_STORED_THRESHOLD) == (free > GATE_STORED_THRESHOLD)


def test_spikes_leave_the_typical_stripe_free_score_unchanged():
    """The median paired |score change| over every pair of the verdict test is at most
    SPIKE_SCORE_MEDIAN_TOL: it ignores the gating jumps while fewer than half the pairs
    jump, and has teeth (P3 block medians 0.18-1.35; 58.5 with rejection off)."""
    scores = [_spike_pair_scores(seed, clip) for seed, clip in SPIKE_PAIRS]
    changes = [abs(spiked - free) for free, spiked in scores]
    assert np.median(changes) <= SPIKE_SCORE_MEDIAN_TOL


@pytest.mark.parametrize("seed", inner(SEEDS))
def test_clipped_stripe_free_frames_are_not_striped(seed):
    kwargs = dict(seed=seed, shape=SHAPE, modulation_depth=0.0, **TYPICAL)
    s, _ = clipped_at(CLIP_LEVEL_FRACTION, generate, **kwargs)
    report = analyse(s.frame)
    assert report.striped is False
    assert report.regions == ()


def _depth_error(report, truth):
    return max(abs(r.modulation_depth - truth.modulation_depth) for r in report.regions)


def test_clipped_stripe_peaks_keep_the_modulation_depth():
    """Full frames clipped at CLIP_LEVEL_FRACTION of the clean maximum: every region within
    DEPTH_TOL on every seed. Teeth: against no exclusion (clip_level=inf) the error is never
    worse by more than CLIP_DEPTH_EPS and is lower on average."""
    errors, errors_inf = [], []
    for seed in CLIP_TEST_SEEDS:
        s, _, report, no_exclusion = _clipped_full_frame(seed)
        assert s.truth.clipped_pixels >= CLIP_MIN_SHARE * s.frame.size
        assert_every_region_matches(report, s.truth)
        assert no_exclusion.regions
        err, err_inf = _depth_error(report, s.truth), _depth_error(no_exclusion, s.truth)
        assert err <= err_inf + CLIP_DEPTH_EPS
        errors.append(err)
        errors_inf.append(err_inf)
    assert np.mean(errors) < np.mean(errors_inf)


def _clipped_partial_frame(seed, fraction):
    period, angle_deg = CASES[seed % len(CASES)]
    kwargs = dict(
        seed=seed,
        shape=REGION_FRAME_SHAPE,
        mottle="scorched",
        regions=[single_region(period, angle_deg)],
        noise=Emccd(),
    )
    s, _ = clipped_at(fraction, generate, **kwargs)
    truth = s.truth.regions[0]
    assert (s.truth.clipped_mask & truth_pixels(truth)).sum() >= AC4_MIN_CLIPPED_PIXELS
    return s, truth


@pytest.mark.parametrize("seed", inner(PARTIAL_CLIP_TEST_SEEDS))
def test_clipping_does_not_harm_a_partial_region(seed):
    """A mild clip (MILD_CLIP_LEVEL_FRACTION) on a partial region: a no-harm guard. It has no
    teeth against flattening (without the exclusion the depth also stays within tolerance)."""
    s, truth = _clipped_partial_frame(seed, MILD_CLIP_LEVEL_FRACTION)
    report = analyse(s.frame)
    assert len(report.regions) == 1
    region = report.regions[0]
    assert_matches_truth(region.period_px, region.angle_deg, truth)
    assert_depth_matches(region.modulation_depth, truth)


@pytest.mark.parametrize("seed", inner(PARTIAL_CLIP_TEST_SEEDS))
def test_heavily_clipped_partial_region_is_no_worse_than_no_exclusion(seed):
    """At CLIP_LEVEL_FRACTION about a fifth or more of a partial region is clipped; the
    depth then drifts toward the flattened value, and AC 4 is met only in part there (ticket
    06 Comments): the error is only asserted not worse than with no exclusion."""
    s, truth = _clipped_partial_frame(seed, CLIP_LEVEL_FRACTION)
    report = analyse(s.frame)
    no_exclusion = analyse(s.frame, clip_level=np.inf)
    ((region, _),) = match(report.regions, report.labels, [truth])
    ((region_inf, _),) = match(no_exclusion.regions, no_exclusion.labels, [truth])
    err = abs(region.modulation_depth - truth.modulation_depth)
    err_inf = abs(region_inf.modulation_depth - truth.modulation_depth)
    assert err <= err_inf + CLIP_DEPTH_EPS


@pytest.mark.parametrize("override", ["level", "below", "inf", "nan"])
def test_clip_level_override(override):
    s, level, report, _ = _clipped_full_frame(CLIP_TEST_SEEDS[0])
    frame = s.frame
    if override == "level":
        assert analyse(frame, clip_level=level) == report
    elif override == "below":
        below = OVERRIDE_LEVEL_FRACTION * level
        assert analyse(frame, clip_level=below).clipped_pixels == (frame >= below).sum()
    elif override == "inf":
        assert analyse(frame, clip_level=np.inf).clipped_pixels == 0
    else:
        with pytest.raises(ValueError, match=r"^clip_level must be a number or inf, got nan"):
            analyse(frame, clip_level=np.nan)


def test_clipping_is_detected_after_a_constant_dark_subtraction():
    s, _, report, _ = _clipped_full_frame(CLIP_TEST_SEEDS[0])
    shifted = s.frame - s.frame.max() / 2
    assert (shifted < 0).any()
    assert report.clipped_pixels > 0
    assert analyse(shifted).clipped_pixels == report.clipped_pixels


REGION_CALIBRATION = Path(__file__).parents[1] / ".scratch/stripe-detector/region-calibration.json"


def test_candidate_cap_has_headroom_over_the_calibration_reach():
    """Plan 2.3 (N9): _MAX_CANDIDATES is at least CANDIDATE_CAP_HEADROOM x the
    most grown candidates any region calibration frame needed to reach its last
    qualifying group (tests/calibrate_regions.py ``tune``, recorded at the
    current knobs)."""
    saved = json.loads(REGION_CALIBRATION.read_text())
    assert saved["mode"] == "tune"
    assert not saved["overrides"]
    assert saved["knobs"] == {k: getattr(analysis, k) for k in saved["knobs"]}, (
        "region-calibration.json is not at the current knobs: re-run the tune"
    )
    reach = max(r["reach_last_member"] for r in saved["records"])
    assert analysis._MAX_CANDIDATES >= CANDIDATE_CAP_HEADROOM * reach, (
        f"cap {analysis._MAX_CANDIDATES} < {CANDIDATE_CAP_HEADROOM} x reach {reach}"
    )


# Ticket 08: bin factors (plan .scratch/stripe-detector/handoffs/08-plan.md, section 5).


@pytest.mark.parametrize(
    ("value", "error"),
    [(0, ValueError), (-1, ValueError), (1.5, TypeError), (True, TypeError), ("2", TypeError)],
)
@pytest.mark.parametrize("axis", ["horizontal", "vertical"])
def test_invalid_bin_factors_raise(value, error, axis):
    with pytest.raises(error, match=axis):
        BinFactors(**{axis: value})


def test_bin_factors_read_back_from_their_dict():
    b = BinFactors(horizontal=2, vertical=3)
    assert b.to_dict() == {"horizontal": 2, "vertical": 3}
    assert BinFactors.from_dict({"horizontal": 2, "vertical": 3}) == b
    assert BinFactors() == BinFactors(1, 1)
    for bad in (
        {"horizontal": 2},
        {"horizontal": 2, "vertical": 1, "x": 1},
        [2, 1],
        {"horizontal": "2", "vertical": 1},
    ):
        with pytest.raises(ValueError, match="bin factor"):
            BinFactors.from_dict(bad)


def _identity_frame(kind):
    """A frame of each kind for the 1x1 identity (AC 5), and its no-option Report."""
    seed = BINNING_TEST_SEEDS[0]
    if kind == "two regions":
        s, report = two_region_case(TWO_REGION_TEST_SEEDS[0], *TWO_REGION_PAIRS[0])
        return s.frame, report
    if kind == "clear stripes":
        s, report = analysed(
            seed=seed, shape=SHAPE, period=8, angle_deg=6, modulation_depth=0.5, **TYPICAL
        )
        return s.frame, report
    if kind == "spikes and clipped":
        s, _ = clipped_at(
            MILD_CLIP_LEVEL_FRACTION,
            generate,
            seed=seed,
            shape=SHAPE,
            period=12,
            angle_deg=-8,
            modulation_depth=0.5,
            spikes=SPIKE_TEST_COUNT,
            **TYPICAL,
        )
        report = analyse(s.frame)
        assert report.spike_pixels > 0
        assert report.clipped_pixels > 0
        return s.frame, report
    s, report = analysed(seed=seed, shape=SHAPE, modulation_depth=0.0, **TYPICAL)
    return s.frame, report


@pytest.mark.parametrize(
    "kind", ["clear stripes", "two regions", "spikes and clipped", "stripe-free mottled"]
)
def test_one_by_one_binning_equals_no_option(kind):
    frame, plain = _identity_frame(kind)
    binned = analyse(frame, bin_factors=BinFactors(1, 1))
    assert binned == plain
    assert np.array_equal(binned.labels, plain.labels)
    assert binned.to_json() == plain.to_json()
    if kind != "stripe-free mottled":
        assert plain.regions


def _binned(seed, h, v, frame_shape=SHAPE, **kwargs):
    """``(Synthetic at sensor size, the frame block-summed h x v)``; the frame is
    ``frame_shape``, so the sensor is ``frame_shape`` times (v, h)."""
    rows, cols = frame_shape
    s = generate(seed=seed, shape=(rows * v, cols * h), **kwargs)
    return s, bin_sensor_frame(s.frame, h, v)


def _spectral_peak_angle_deg(frame):
    """Angle (deg) of the strongest 2D FFT peak of ``frame`` minus its local
    mean, over Periods 3-40 frame px with a positive horizontal frequency."""
    detail = frame - gaussian_filter(frame, sigma=_ENVELOPE_SIGMA)
    power = np.abs(np.fft.fft2(detail)) ** 2
    fy = np.fft.fftfreq(frame.shape[0])[:, None]
    fx = np.fft.fftfreq(frame.shape[1])[None, :]
    f = np.hypot(fx, fy)
    power[(fx <= 0) | (f < 1 / 40) | (f > 1 / 3)] = 0
    r, c = np.unravel_index(np.argmax(power), power.shape)
    return float(np.degrees(np.arctan2(fy[r, 0], fx[0, c])))


@pytest.mark.parametrize("angle_deg", [10, -10])
def test_one_by_two_binning_reports_the_physical_angle(angle_deg):
    """AC 1: a physical 10 deg tilt is about 19.4 deg in a 1x2-binned frame and
    is reported as about 10 deg."""
    s, frame = _binned(
        BINNING_TEST_SEEDS[0], 1, 2, period=8, angle_deg=angle_deg, modulation_depth=0.5, **TYPICAL
    )
    in_frame = np.degrees(np.arctan(2 * np.tan(np.radians(angle_deg))))
    assert abs(in_frame) == pytest.approx(19.43, abs=0.01)
    assert abs(_spectral_peak_angle_deg(frame) - in_frame) <= 2.0
    report = analyse(frame, bin_factors=BinFactors(horizontal=1, vertical=2))
    (region,) = report.regions
    assert_matches_truth(region.period_px, region.angle_deg, s.truth)


@pytest.mark.parametrize("angle_deg", [0, 10])
def test_two_by_one_binning_reports_the_physical_period(angle_deg):
    """AC 2: a physical 12 px Period in a 2x1-binned frame is 6 frame px and is
    reported as about 12 px."""
    s, frame = _binned(
        BINNING_TEST_SEEDS[1], 2, 1, period=12, angle_deg=angle_deg, modulation_depth=0.5, **TYPICAL
    )
    report = analyse(frame, bin_factors=BinFactors(horizontal=2, vertical=1))
    (region,) = report.regions
    assert abs(region.period_px - 12) <= PERIOD_REL_TOL * 12
    assert not abs(region.period_px - 6) <= PERIOD_REL_TOL * 6
    assert_matches_truth(region.period_px, region.angle_deg, s.truth)


def test_binned_region_bbox_and_mask_are_in_frame_pixels():
    """AC 4: under 2x1 the bbox and the mask are in frame px, the Period in sensor px."""
    h, v, period = 2, 1, 12
    rows, cols = SHAPE
    region = StripedRegion(
        center=((rows * v - 1) / 2, (cols * h - 1) / 2),
        semi_axes=(5.0 * period, 6.6 * period),
        rotation_deg=0.0,
        edge_px=REGION_EDGE_PX,
        period=float(period),
        angle_deg=4.0,
        modulation_depth=0.5,
    )
    s, frame = _binned(
        BINNING_TEST_SEEDS[2], h, v, regions=[region], mottle="scorched", **TYPICAL_NOISE
    )
    report = analyse(frame, bin_factors=BinFactors(h, v))
    assert report.labels.shape == frame.shape == SHAPE
    (found,) = report.regions
    (truth,) = s.truth.regions
    assert_matches_truth(found.period_px, found.angle_deg, truth)
    b = found.bbox
    assert 0 <= b.row_start < b.row_stop <= rows
    assert 0 <= b.col_start < b.col_stop <= cols
    r0, r1, c0, c1 = truth_bbox(bin_truth_mask(truth.mask, h, v) >= 0.5)
    row_tol, col_tol = BBOX_TOL_PERIODS * period / v, BBOX_TOL_PERIODS * period / h
    for got, want in ((b.row_start, r0), (b.row_stop, r1)):
        assert abs(got - want) <= row_tol
    for got, want in ((b.col_start, c0), (b.col_stop, c1)):
        assert abs(got - want) <= col_tol
    assert found.area_px == int((report.labels == found.label).sum())
    assert_labels_consistent(report)


@pytest.mark.parametrize("bins", [(2, 1), (1, 2)], ids=["2x1", "1x2"])
@pytest.mark.parametrize("size", ["below", "above"])
def test_size_minimum_is_in_sensor_periods_under_binning(bins, size):
    """The 3x2-Period minimum is in sensor px: the size tests' recipe at sensor
    size, binned. Below (0.8x) is not reported; above (1.4x) is."""
    h, v = bins
    period, factor = 8, (MIN_SIZE_BELOW_FACTOR if size == "below" else MIN_SIZE_ABOVE_FACTOR)
    rows, cols = SHAPE
    region = StripedRegion(
        center=((rows * v - 1) / 2, (cols * h - 1) / 2),
        semi_axes=SIZE_SHAPES["both"](period, factor),
        rotation_deg=0.0,
        edge_px=1.0,
        period=float(period),
        angle_deg=0.0,
        modulation_depth=0.6,
    )
    _, frame = _binned(MIN_SIZE_TEST_SEEDS[0], h, v, regions=[region])
    report = analyse(frame, bin_factors=BinFactors(h, v))
    if size == "below":
        assert report.regions == ()
    else:
        (found,) = report.regions
        assert abs(found.period_px - period) <= PERIOD_REL_TOL * period


def test_bin_factors_leaving_no_searchable_period_raise():
    frame = generate(seed=BINNING_TEST_SEEDS[0], shape=SHAPE).frame
    with pytest.raises(ValueError, match="11x1"):
        analyse(frame, bin_factors=BinFactors(11, 1))


REPORT_UNITS = {
    "period_px": "sensor px",
    "angle_deg": "degrees from vertical, sensor geometry",
    "modulation_depth": "relative to the local envelope, as measured on the (binned) frame",
    "bbox": "frame px (binned array; file layout when transposed)",
    "area_px": "frame px (binned array)",
    "mask": "frame px (binned array; file layout when transposed)",
    "spike_pixels": "frame px (binned array)",
    "clipped_pixels": "frame px (binned array)",
    "unresolved_period_px": "sensor px",
}


def test_report_states_units():
    """AC 4: every report states each field's unit (plan 2.5)."""
    assert Report.UNITS == REPORT_UNITS
    _, frame = _binned(BINNING_TEST_SEEDS[0], 2, 1, modulation_depth=0.0)
    data = json.loads(analyse(frame, bin_factors=BinFactors(2, 1), threshold=1e3).to_json())
    assert data["units"] == REPORT_UNITS
    assert data["bin_factors"] == {"horizontal": 2, "vertical": 1}


def test_two_by_one_binning_warns_below_four_px():
    """AC 3: under 2x1, physical Periods below 4 px are not searched, and the report says so."""
    _, frame = _binned(BINNING_TEST_SEEDS[0], 2, 1, period=12, modulation_depth=0.5, **TYPICAL)
    report = analyse(frame, bin_factors=BinFactors(2, 1), threshold=GATE_STORED_THRESHOLD)
    assert report.bin_factors == BinFactors(2, 1)
    assert report.unresolved_period_px == (3.0, 4.0)
    (warning,) = report.warnings
    assert "below 4 px" in warning
    assert "stripes" in warning
    assert "2x1" in warning
    with_calibration = analyse(frame, bin_factors=BinFactors(2, 1))
    assert warning in with_calibration.warnings


def test_one_by_two_binning_names_the_reference_in_its_warning():
    _, frame = _binned(BINNING_TEST_SEEDS[0], 1, 2, period=12, modulation_depth=0.5, **TYPICAL)
    report = analyse(frame, bin_factors=BinFactors(1, 2), threshold=GATE_STORED_THRESHOLD)
    assert report.unresolved_period_px == (3.0, 4.0)
    (warning,) = report.warnings
    assert "below 4 px" in warning
    assert "reference" in warning
    assert "1x2" in warning


def test_two_by_two_binning_names_both_filters_in_its_warning():
    _, frame = _binned(BINNING_TEST_SEEDS[0], 2, 2, period=12, modulation_depth=0.5, **TYPICAL)
    report = analyse(frame, bin_factors=BinFactors(2, 2), threshold=GATE_STORED_THRESHOLD)
    assert report.unresolved_period_px == (3.0, 4.0)
    (warning,) = report.warnings
    assert "stripes" in warning
    assert "reference" in warning


def test_one_by_one_has_no_period_warning():
    _, report = analysed(
        seed=BINNING_TEST_SEEDS[0],
        shape=SHAPE,
        period=8,
        angle_deg=6,
        modulation_depth=0.5,
        **TYPICAL,
    )
    assert report.bin_factors == BinFactors()
    assert report.unresolved_period_px is None
    assert report.warnings == ()


def test_report_in_file_layout_keeps_bin_factors_and_warnings():
    _, frame = _binned(BINNING_TEST_SEEDS[1], 2, 1, period=12, modulation_depth=0.5, **TYPICAL)
    report = analyse(frame, bin_factors=BinFactors(2, 1), threshold=GATE_STORED_THRESHOLD)
    assert report.regions
    flipped = report.in_file_layout()
    assert flipped.bin_factors == report.bin_factors
    assert flipped.unresolved_period_px == report.unresolved_period_px
    assert flipped.warnings == report.warnings
    assert flipped.transposed is True


# Calibration coverage note (plan 2.6): a Calibration that set the Threshold
# does not cover a frame of other bin factors or of more pixels.


def _small_calibration(shape, settings=None):
    """A Calibration of 99 made-up scores at ``shape``: Threshold 99 at 1%."""
    return Calibration.from_scores(
        [f"x{i}" for i in range(99)], np.arange(1.0, 100.0), shape, settings=settings
    )


def test_binned_frame_notes_the_calibration_does_not_cover_it():
    _, frame = _binned(BINNING_TEST_SEEDS[0], 2, 1, modulation_depth=0.0, **TYPICAL)
    report = analyse(frame, bin_factors=BinFactors(2, 1))
    notes = [w for w in report.warnings if "calibration" in w]
    assert notes == [
        "the calibration was made at 1x1 binning; its false-alarm rate does not cover 2x1 "
        "frames (binning makes the Mottle directional in the frame: Stripe-free scores up to "
        "1.9x at the shortest searched Period)"
    ]


def test_frame_with_more_pixels_than_the_calibration_is_noted():
    frame = generate(seed=BINNING_TEST_SEEDS[0], shape=(128, 128), **TYPICAL).frame
    report = analyse(frame, calibration=_small_calibration((64, 64)))
    assert report.warnings == (
        "frame 128x128 has more pixels than the calibration's 64x64; its false-alarm rate "
        "is not covered",
    )


def test_frame_with_fewer_pixels_is_not_noted():
    frame = generate(seed=BINNING_TEST_SEEDS[0], shape=(64, 64), **TYPICAL).frame
    assert analyse(frame, calibration=_small_calibration((128, 128))).warnings == ()
    # 512x512 is 41% of the stored calibration's 400x1600 pixels.
    big = generate(seed=BINNING_TEST_SEEDS[0], shape=(512, 512), **TYPICAL).frame
    assert analyse(big).warnings == ()


def test_explicit_threshold_has_no_calibration_note():
    frame = generate(seed=BINNING_TEST_SEEDS[0], shape=(128, 128), **TYPICAL).frame
    assert analyse(frame, threshold=GATE_STORED_THRESHOLD).warnings == ()
    _, binned = _binned(BINNING_TEST_SEEDS[0], 2, 1, modulation_depth=0.0, **TYPICAL)
    report = analyse(binned, bin_factors=BinFactors(2, 1), threshold=GATE_STORED_THRESHOLD)
    assert not [w for w in report.warnings if "calibration" in w]


def test_calibration_with_matching_bin_factors_has_no_note():
    _, frame = _binned(BINNING_TEST_SEEDS[0], 2, 1, modulation_depth=0.0, **TYPICAL)
    cal = _small_calibration(SHAPE, settings={"bin_factors": {"horizontal": 2, "vertical": 1}})
    report = analyse(frame, bin_factors=BinFactors(2, 1), calibration=cal)
    assert len(report.warnings) == 1
    assert "below 4 px" in report.warnings[0]
