import dataclasses
import json
import re
from functools import cache
from itertools import combinations

import numpy as np
import pytest

from borderline import BORDERLINE, borderline_frame
from cases import CASES
from denoisifier import Report, analyse
from denoisifier.analysis import THRESHOLD
from denoisifier.synthetic import Emccd, StripedRegion, generate
from protected import (
    BBOX_TOL_PERIODS,
    BORDERLINE_SCORE_WINDOW,
    DARK_FRACTION,
    DARK_REGRESSION_CASES,
    DEPTH_REGRESSION_CASES,
    ENVELOPE_TEST_SEEDS,
    EXTREMES_TEST_SEEDS,
    FULL_FRAME_TEST_SEEDS,
    INPUT_NOT_MODIFIED_TEST_SEED,
    MASK_IOU_MIN,
    MIN_SIZE_ABOVE_FACTOR,
    MIN_SIZE_BELOW_FACTOR,
    MIN_SIZE_TEST_SEEDS,
    MOTTLED_TEST_SEEDS,
    MULTISCALE_TEST_SEEDS,
    PERIOD_REL_TOL,
    PROFILE_ONLY_TEST_SEEDS,
    REGION_FRAME_SHAPE,
    REGION_TEST_SEEDS,
    REPORT_TO_JSON_TEST_SEED,
    SCORE_AND_THRESHOLD_TEST_SEED,
    SINGLE_FRAME_TEST_SEED,
    STRONG_TEST_SEEDS,
    TWO_REGION_PAIRS,
    TWO_REGION_SHAPE,
    TWO_REGION_TEST_SEEDS,
)
from regions import (
    assert_labels_consistent,
    iou,
    match,
    single_region,
    single_region_case,
    truth_bbox,
    two_regions,
)
from truth_match import assert_depth_matches, assert_matches_truth

SHAPE = (256, 256)
SEEDS = MOTTLED_TEST_SEEDS
# About 100 photons at the peak, scorched mottle: the ticket 02 working point.
TYPICAL = dict(mottle="scorched", noise=Emccd())
TYPICAL_NOISE = dict(noise=Emccd())


@pytest.mark.parametrize("seed", SEEDS)
def test_stripe_free_mottled_frames_are_not_striped(seed):
    s = generate(seed=seed, shape=SHAPE, modulation_depth=0.0, **TYPICAL)
    report = analyse(s.frame)
    assert report.striped is False
    assert report.regions == ()
    assert not report.mask().any()


@pytest.mark.parametrize("seed", SEEDS)
def test_clear_stripes_in_mottle_are_found_and_measured(seed):
    period, angle_deg = CASES[seed % len(CASES)]
    s = generate(
        seed=seed, shape=SHAPE, period=period, angle_deg=angle_deg, modulation_depth=0.5, **TYPICAL
    )
    report = analyse(s.frame)
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


@pytest.mark.parametrize("noise", [0.0, 0.01])
@pytest.mark.parametrize(
    ("seed", "period", "angle_deg"),
    [
        (seed, *case)
        for seed, case in zip(
            FULL_FRAME_TEST_SEEDS,
            [(5, 0), (8, 6), (12, -8), (18, 3), (4, -4), (3, 10), (20, -10)],
            strict=True,
        )
    ],
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
@pytest.mark.parametrize("seed", PROFILE_ONLY_TEST_SEEDS)
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


def test_constant_frame_is_not_striped_and_has_finite_score():
    report = analyse(np.ones((64, 64)))
    assert report.striped is False
    assert report.score == 0.0
    assert report.regions == ()
    assert report.score < report.threshold
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
    assert list(data) == ["striped", "score", "threshold", "transposed", "regions"]
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


@pytest.mark.parametrize("seed", STRONG_TEST_SEEDS)
@pytest.mark.parametrize("period", [5, 12])
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
@pytest.mark.parametrize("seed", ENVELOPE_TEST_SEEDS)
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


@pytest.mark.parametrize("seed", MULTISCALE_TEST_SEEDS)
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


@pytest.mark.parametrize("seed", REGION_TEST_SEEDS)
def test_partial_region_is_reported_with_its_measurements(seed):
    period, angle_deg = CASES[seed % len(CASES)]
    s, report = single_region_case(seed, period, angle_deg)
    assert report.striped is True
    (region,) = report.regions
    (truth,) = s.truth.regions
    assert_matches_truth(region.period_px, region.angle_deg, truth)
    assert_depth_matches(region.modulation_depth, truth)
    r0, r1, c0, c1 = truth_bbox(truth.mask >= 0.5)
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


@pytest.mark.parametrize("mottle", ["scorched", "multiscale"])
@pytest.mark.parametrize("seed", REGION_TEST_SEEDS)
def test_mask_overlaps_the_true_region(seed, mottle):
    period, angle_deg = CASES[seed % len(CASES)]
    s, report = single_region_case(seed, period, angle_deg, mottle)
    (truth,) = s.truth.regions
    assert iou(report.mask(), truth.mask >= 0.5) >= MASK_IOU_MIN


@pytest.mark.parametrize(("left", "right"), TWO_REGION_PAIRS)
@pytest.mark.parametrize("seed", TWO_REGION_TEST_SEEDS)
def test_two_regions_with_different_periods_are_reported_separately(seed, left, right):
    s = generate(
        seed=seed,
        shape=TWO_REGION_SHAPE,
        mottle="scorched",
        regions=two_regions(left, right),
        **TYPICAL_NOISE,
    )
    report = analyse(s.frame)
    assert len(report.regions) == 2
    pairs = match(report.regions, report.labels, s.truth.regions)
    assert {id(t) for _, t in pairs} == {id(t) for t in s.truth.regions}
    for region, truth in pairs:
        assert_matches_truth(region.period_px, region.angle_deg, truth)
        assert iou(report.labels == region.label, truth.mask >= 0.5) >= MASK_IOU_MIN
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
SIZE_CASES = [(p, a) for p in (3, 8, 20) for a in (-10, 10)]


@pytest.mark.parametrize("shape", list(SIZE_SHAPES))
@pytest.mark.parametrize(("period", "angle_deg"), SIZE_CASES)
@pytest.mark.parametrize("seed", MIN_SIZE_TEST_SEEDS)
def test_region_below_the_minimum_is_not_reported(seed, period, angle_deg, shape):
    axes = SIZE_SHAPES[shape](period, MIN_SIZE_BELOW_FACTOR)
    report = analyse(_size_test_frame(seed, period, angle_deg, axes).frame)
    assert report.regions == ()
    assert report.striped is False


@pytest.mark.parametrize("shape", ["both", "wide_short", "narrow_tall"])
@pytest.mark.parametrize(("period", "angle_deg"), SIZE_CASES)
@pytest.mark.parametrize("seed", MIN_SIZE_TEST_SEEDS)
def test_region_above_the_minimum_is_reported(seed, period, angle_deg, shape):
    axes = SIZE_SHAPES[shape](period, MIN_SIZE_ABOVE_FACTOR)
    s = _size_test_frame(seed, period, angle_deg, axes)
    report = analyse(s.frame)
    (region,) = report.regions
    assert abs(region.period_px - period) <= PERIOD_REL_TOL * period


@pytest.mark.parametrize("seed", REGION_TEST_SEEDS[:3])
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


@pytest.mark.parametrize(
    ("seed", "case"),
    [
        *[(seed, case) for seed in ENVELOPE_TEST_SEEDS for case in DARK_CASES],
        # First fresh range's miss: two mask pixels in a corner at Profile 4.9%.
        *DARK_REGRESSION_CASES,
    ],
)
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
    """Two same-Period regions with Angles 12 deg apart, 8 px apart: their
    grown extents overlap, and they are not merged."""
    common = dict(semi_axes=(50.0, 60.0), rotation_deg=0.0, edge_px=4.0, period=8.0)
    regions = [
        StripedRegion(center=(127.5, 186.0), angle_deg=-6.0, modulation_depth=0.5, **common),
        StripedRegion(center=(127.5, 314.0), angle_deg=6.0, modulation_depth=0.5, **common),
    ]
    return generate(seed=TWO_REGION_TEST_SEEDS[0], shape=(256, 512), regions=regions).frame


SWEEP_FRAMES = {
    **{
        f"free-{seed}": (
            lambda seed=seed: (
                generate(seed=seed, shape=SHAPE, modulation_depth=0.0, **TYPICAL).frame
            )
        )
        for seed in MOTTLED_TEST_SEEDS[:5]
    },
    **{
        f"striped-{seed}": (
            lambda seed=seed: (
                generate(
                    seed=seed,
                    shape=SHAPE,
                    period=CASES[seed % len(CASES)].period,
                    angle_deg=CASES[seed % len(CASES)].angle_deg,
                    modulation_depth=0.5,
                    **TYPICAL,
                ).frame
            )
        )
        for seed in MOTTLED_TEST_SEEDS[:5]
    },
    **{
        f"borderline-{seed}-{period}": (lambda c=(seed, period): borderline_frame(*c))
        for seed, period in BORDERLINE
    },
    "two-region": lambda: (
        generate(
            seed=TWO_REGION_TEST_SEEDS[0],
            shape=TWO_REGION_SHAPE,
            mottle="scorched",
            regions=two_regions(*TWO_REGION_PAIRS[0]),
            **TYPICAL_NOISE,
        ).frame
    ),
    "overlapping-extents": _overlap_frame,
    "constant": lambda: np.ones((64, 64)),
}


# The thresholds of the verdict tests, by kind: each kind is its own test
# item, so no item runs more than three analyses of its frame (the two-region
# frame takes about 9 s per analysis; the per-test timeout is 60 s).
SWEEP_THRESHOLDS = ("zero", "THRESHOLD", "score", "above-score", "below-score", "inf")


def _sweep_threshold(name, kind):
    if kind == "THRESHOLD":
        return THRESHOLD
    score = _sweep_report(name, "THRESHOLD").score
    return {
        "zero": 0.0,
        "score": score,
        "above-score": np.nextafter(score, np.inf),
        # Below a zero score is negative, which analyse rejects: 0 again.
        "below-score": max(np.nextafter(score, -np.inf), 0.0),
        "inf": np.inf,
    }[kind]


@cache
def _sweep_report(name, kind):
    """``analyse`` of sweep frame ``name`` at threshold ``kind``, on the real path."""
    if kind == "THRESHOLD":
        return analyse(SWEEP_FRAMES[name]())
    return analyse(SWEEP_FRAMES[name](), threshold=_sweep_threshold(name, kind))


@pytest.mark.parametrize("kind", SWEEP_THRESHOLDS)
@pytest.mark.parametrize("name", list(SWEEP_FRAMES))
def test_verdict_is_striped_exactly_when_a_region_is_reported(name, kind):
    report = _sweep_report(name, kind)
    assert report.score == _sweep_report(name, "THRESHOLD").score
    t = _sweep_threshold(name, kind)
    assert report.threshold == t
    assert report.striped == bool(report.regions) == (report.score > t)
    assert_labels_consistent(report)
    if name == "constant":
        assert report.score == 0.0
        assert not report.regions
        assert not report.mask().any()


def test_sweep_thresholds_are_the_planned_ones():
    """The kinds give 0, THRESHOLD, the score, its two neighbours and inf."""
    name = "striped-" + str(MOTTLED_TEST_SEEDS[0])
    score = _sweep_report(name, "THRESHOLD").score
    assert score > 0
    got = {_sweep_threshold(name, k) for k in SWEEP_THRESHOLDS}
    want = {0.0, THRESHOLD, score, np.nextafter(score, np.inf), np.nextafter(score, -np.inf)}
    assert got == want | {np.inf}


def _regions_by_bbox(report):
    return {r.bbox: (r, report.labels == r.label) for r in report.regions}


@pytest.mark.parametrize(("kind_a", "kind_b"), list(combinations(SWEEP_THRESHOLDS, 2)))
@pytest.mark.parametrize(
    "name", ["two-region", "overlapping-extents", *[f"striped-{s}" for s in MOTTLED_TEST_SEEDS[:5]]]
)
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
