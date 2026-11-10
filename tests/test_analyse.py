import json

import numpy as np
import pytest

from borderline import BORDERLINE, borderline_frame
from cases import CASES
from denoisifier import Report, analyse
from denoisifier.synthetic import Emccd, generate
from truth_match import assert_depth_matches, assert_matches_truth

SHAPE = (256, 256)
SEEDS = range(20)
# About 100 photons at the peak, scorched mottle: the ticket 02 working point.
TYPICAL = dict(mottle="scorched", noise=Emccd())


@pytest.mark.parametrize("seed", SEEDS)
def test_stripe_free_mottled_frames_are_not_striped(seed):
    s = generate(seed=seed, shape=SHAPE, modulation_depth=0.0, **TYPICAL)
    report = analyse(s.frame)
    assert report.striped is False
    assert report.period_px is None
    assert report.angle_deg is None
    assert report.modulation_depth is None


@pytest.mark.parametrize("seed", SEEDS)
def test_clear_stripes_in_mottle_are_found_and_measured(seed):
    period, angle_deg = CASES[seed % len(CASES)]
    s = generate(
        seed=seed, shape=SHAPE, period=period, angle_deg=angle_deg, modulation_depth=0.5, **TYPICAL
    )
    report = analyse(s.frame)
    assert report.striped is True
    assert_matches_truth(report.period_px, report.angle_deg, s.truth)
    assert_depth_matches(report.modulation_depth, s.truth)


@pytest.mark.parametrize("noise", [0.0, 0.01])
@pytest.mark.parametrize(
    ("seed", "period", "angle_deg"),
    [
        (0, 5, 0),
        (1, 8, 6),
        (2, 12, -8),
        (3, 18, 3),
        (4, 4, -4),
        (5, 3, 10),
        (6, 20, -10),
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
    assert report.striped is True
    assert_matches_truth(report.period_px, report.angle_deg, s.truth)
    assert_depth_matches(report.modulation_depth, s.truth)


@pytest.mark.parametrize("noise", [0.0, 0.001, 0.01])
@pytest.mark.parametrize("seed", range(10))
def test_profile_only_frame_is_not_striped(seed, noise):
    s = generate(seed=seed, shape=SHAPE, modulation_depth=0.0, noise=noise)
    report = analyse(s.frame)
    assert report.striped is False
    assert report.period_px is None
    assert report.angle_deg is None
    assert report.modulation_depth is None


def test_report_has_score_and_threshold():
    striped = analyse(generate(seed=7, shape=SHAPE, period=9, modulation_depth=0.6).frame)
    plain = analyse(generate(seed=7, shape=SHAPE, modulation_depth=0.0).frame)
    assert striped.score > striped.threshold
    assert plain.score < plain.threshold


def test_constant_frame_is_not_striped_and_has_finite_score():
    report = analyse(np.ones((64, 64)))
    assert report.striped is False
    assert np.isfinite(report.score)
    assert report.score < report.threshold
    json.loads(report.to_json())


@pytest.mark.parametrize("value", [0.0, -5.0])
def test_frame_with_no_positive_light_is_rejected(value):
    with pytest.raises(ValueError):
        analyse(np.full((64, 64), value))


def test_rejects_frame_smaller_than_min_side():
    with pytest.raises(ValueError):
        analyse(np.ones((39, 64)))
    report = analyse(generate(seed=0, shape=(40, 64), modulation_depth=0.0).frame)
    assert isinstance(report, Report)


def test_rejects_non_2d_input():
    with pytest.raises(ValueError):
        analyse(np.ones(100))


def test_rejects_non_finite_values():
    frame = generate(seed=0, shape=(64, 64)).frame
    frame[10, 10] = np.nan
    with pytest.raises(ValueError):
        analyse(frame)


def test_input_frame_is_not_modified():
    frame = generate(seed=2, shape=(64, 64)).frame
    before = frame.copy()
    analyse(frame)
    assert np.array_equal(frame, before)


@pytest.mark.parametrize("modulation_depth", [0.6, 0.0])
def test_report_converts_to_json(modulation_depth):
    report = analyse(generate(seed=1, shape=SHAPE, modulation_depth=modulation_depth).frame)
    data = json.loads(report.to_json())
    assert list(data) == [
        "striped",
        "score",
        "threshold",
        "period_px",
        "angle_deg",
        "modulation_depth",
    ]
    assert type(data["striped"]) is bool
    assert type(data["score"]) is float
    assert type(data["threshold"]) is float
    for key in ("period_px", "angle_deg", "modulation_depth"):
        assert data[key] is None or type(data[key]) is float
    assert data == {
        "striped": report.striped,
        "score": report.score,
        "threshold": report.threshold,
        "period_px": report.period_px,
        "angle_deg": report.angle_deg,
        "modulation_depth": report.modulation_depth,
    }


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("period", [5, 12])
def test_strong_stripes_are_measured(seed, period):
    s = generate(
        seed=seed, shape=SHAPE, period=period, angle_deg=6, modulation_depth=0.8, **TYPICAL
    )
    report = analyse(s.frame)
    assert report.striped is True
    assert_matches_truth(report.period_px, report.angle_deg, s.truth)
    assert_depth_matches(report.modulation_depth, s.truth)


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
@pytest.mark.parametrize("seed", range(3))
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
        assert_depth_matches(report.modulation_depth, s.truth)
        depths.append(report.modulation_depth)
    assert abs(depths[0] - depths[1]) <= 0.05


EXTREMES = [(3, -10), (3, 0), (3, 10), (20, -10), (20, 0), (20, 10), (3, 5), (20, -5)]


@pytest.mark.parametrize(
    ("seed", "period", "angle_deg"), [(i, *case) for i, case in enumerate(EXTREMES)]
)
def test_period_and_angle_extremes_are_detected(seed, period, angle_deg):
    s = generate(
        seed=seed, shape=SHAPE, period=period, angle_deg=angle_deg, modulation_depth=0.5, **TYPICAL
    )
    report = analyse(s.frame)
    assert report.striped is True
    assert_matches_truth(report.period_px, report.angle_deg, s.truth)


@pytest.mark.parametrize("seed", range(10))
def test_multiscale_mottle_is_handled(seed):
    common = dict(seed=seed, shape=SHAPE, mottle="multiscale", noise=Emccd())
    assert analyse(generate(**common, modulation_depth=0.0).frame).striped is False

    period, angle_deg = [3, 8, 20][seed % 3], [-10, 0, 10][(seed // 3) % 3]
    s = generate(**common, period=period, angle_deg=angle_deg, modulation_depth=0.5)
    report = analyse(s.frame)
    assert report.striped is True
    assert_matches_truth(report.period_px, report.angle_deg, s.truth)


@pytest.mark.parametrize(("seed", "period"), BORDERLINE)
def test_borderline_striped_frame_has_finite_measurements(seed, period):
    report = analyse(borderline_frame(seed, period))
    assert report.threshold < report.score < 1.5 * report.threshold
    assert report.striped is True
    for value in (report.period_px, report.angle_deg, report.modulation_depth):
        assert np.isfinite(value)
    json.loads(report.to_json())
