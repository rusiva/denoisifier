import json

import numpy as np
import pytest

from denoisifier import Report, analyse
from denoisifier.synthetic import generate
from truth_match import assert_matches_truth

SHAPE = (256, 256)


@pytest.mark.parametrize("noise", [0.0, 0.01])
@pytest.mark.parametrize(
    "seed, period, angle_deg",
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


@pytest.mark.parametrize("noise", [0.0, 0.001, 0.01])
@pytest.mark.parametrize("seed", range(10))
def test_profile_only_frame_is_not_striped(seed, noise):
    s = generate(seed=seed, shape=SHAPE, modulation_depth=0.0, noise=noise)
    report = analyse(s.frame)
    assert report.striped is False
    assert report.period_px is None
    assert report.angle_deg is None


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
    assert list(data) == ["striped", "score", "threshold", "period_px", "angle_deg"]
    assert type(data["striped"]) is bool
    assert type(data["score"]) is float
    assert type(data["threshold"]) is float
    for key in ("period_px", "angle_deg"):
        assert data[key] is None or type(data[key]) is float
    assert data == {
        "striped": report.striped,
        "score": report.score,
        "threshold": report.threshold,
        "period_px": report.period_px,
        "angle_deg": report.angle_deg,
    }
