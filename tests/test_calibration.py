import json
import re
import subprocess
import sys
from functools import cache
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import betabinom

from denoisifier import analyse
from denoisifier._calibration import (
    false_alarm_tolerance,
    rate_interval,
    threshold_for_false_alarm_rate,
    threshold_rank,
)
from denoisifier.calibration import (
    DEFAULT_FALSE_ALARM_RATE,
    Calibration,
    calibrate,
    calibrate_folder,
    stripe_free_score,
)
from denoisifier.frame_io import read_frame, write_frame_csv
from denoisifier.synthetic import Emccd, generate
from protected import CALIBRATION_FOLDER_TEST_SEEDS

TOO_FEW = "^" + re.escape("50 scores are too few for a false-alarm rate of 0.01: need at least 99")


def test_threshold_is_the_kth_largest_score():
    # n = 2000, rate 0.01 -> k = floor(0.01 * 2001) = 20 -> 20th largest of 1..2000.
    assert threshold_for_false_alarm_rate(np.arange(1, 2001), 0.01) == 1981


def test_threshold_rank_is_floor_of_rate_times_n_plus_one():
    assert threshold_rank(2000, 0.01) == 20
    assert threshold_rank(300, 0.01) == 3
    # 0.29 * 100 is 28.999999999999996 in floating point; the rank is still 29.
    assert threshold_rank(99, 0.29) == 29


def test_threshold_rank_needs_enough_scores_for_the_rate():
    with pytest.raises(ValueError, match=TOO_FEW):
        threshold_rank(50, 0.01)


def test_threshold_needs_enough_scores_for_the_rate():
    # 50 scores at 1%: k = floor(0.51) = 0, no order statistic gives that rate.
    with pytest.raises(ValueError, match=TOO_FEW):
        threshold_for_false_alarm_rate(np.arange(50.0), 0.01)


def test_threshold_rejects_non_finite_scores():
    scores = np.arange(2000.0)
    scores[7] = np.nan
    with pytest.raises(ValueError, match="^" + re.escape("scores must all be finite")):
        threshold_for_false_alarm_rate(scores, 0.01)


def test_false_alarm_tolerance_for_the_gate_batch_sizes():
    # Beta-binomial betabinom(1000, 20, 1982) central 95%: worked out in plan section 4.
    assert false_alarm_tolerance(2000, 1000, 0.01) == (3, 18)


def test_rate_interval_is_the_exact_clopper_pearson_interval():
    lo, hi = rate_interval(450, 500)
    assert lo == pytest.approx(0.8703, abs=1e-3)
    assert hi == pytest.approx(0.9249, abs=1e-3)


def test_false_alarm_tolerance_covers_simulated_held_out_counts():
    # Threshold from 2000 exchangeable scores, count exceedances in 1000 more,
    # and check the simulated coverage of the tolerance against the exact one.
    rng = np.random.default_rng(3)
    lo, hi = false_alarm_tolerance(2000, 1000, 0.01)
    trials = 2000
    inside = 0
    for _ in range(trials):
        threshold = threshold_for_false_alarm_rate(rng.random(2000), 0.01)
        count = int((rng.random(1000) > threshold).sum())
        inside += lo <= count <= hi
    mc = inside / trials
    d = betabinom(1000, 20, 1982)  # k = 20, n + 1 - k = 1982
    exact = d.cdf(hi) - d.cdf(lo - 1)
    sd = np.sqrt(exact * (1 - exact) / trials)
    assert exact >= 0.95
    assert abs(mc - exact) <= 4 * sd


# The public Calibration (ticket 07, plan 2.1).


def _cal(scores, **kwargs):
    ids = tuple(f"seed:{i}" for i in range(len(scores)))
    return Calibration.from_scores(ids, scores, (400, 1600), **kwargs)


def test_default_false_alarm_rate_is_one_percent():
    assert DEFAULT_FALSE_ALARM_RATE == 0.01


def test_threshold_at_n_300_is_the_3rd_and_15th_largest():
    # Scores 1..300 in shuffled order: k = floor(0.01 * 301) = 3 -> 298; k = 15 -> 286.
    scores = np.random.default_rng(0).permutation(np.arange(1.0, 301.0))
    cal = _cal(scores)
    assert cal.threshold(0.01) == 298.0
    assert cal.threshold(0.05) == 286.0


@pytest.mark.parametrize("rate", [0.0, 1.0, -0.1, 1.5, float("nan")])
def test_threshold_refuses_a_rate_outside_zero_to_one(rate):
    with pytest.raises(ValueError, match="false-alarm rate must be between 0 and 1"):
        _cal(np.arange(300.0)).threshold(rate)


def test_threshold_refuses_a_rate_too_small_for_n():
    with pytest.raises(ValueError, match=TOO_FEW):
        _cal(np.arange(50.0)).threshold(0.01)


def test_threshold_refuses_a_rate_too_high_for_n():
    # k = floor(rate * 4) = 4 > n = 3.
    with pytest.raises(ValueError, match="too high for 3 scores"):
        _cal([1.0, 2.0, 3.0]).threshold(1 - 1e-12)


def test_ties_at_the_threshold_give_a_realised_rate_at_most_the_request():
    # 290 zeros (the 0.0 atom) and 10 positive scores; at 5% (k = 15) the threshold is 0.0,
    # and only the 10 positive scores exceed it: 10/300 < 5%.
    scores = np.concatenate([np.zeros(290), np.arange(1.0, 11.0)])
    cal = _cal(scores)
    t = cal.threshold(0.05)
    assert t == 0.0
    assert (scores > t).sum() == 10
    # A tie of equal maxima at rank 3: 5 scores of 7.0, the rest lower.
    tied = _cal(np.concatenate([np.full(5, 7.0), np.arange(295.0) / 100]))
    assert tied.threshold(0.01) == 7.0
    assert (np.array(tied.scores) > 7.0).sum() == 0


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_from_scores_refuses_non_finite_scores(bad):
    with pytest.raises(ValueError, match="scores must all be finite"):
        _cal([1.0, bad, 2.0])


def test_from_scores_refuses_mismatched_ids_and_an_empty_set():
    with pytest.raises(ValueError, match="2 ids for 3 scores"):
        Calibration.from_scores(("a", "b"), [1.0, 2.0, 3.0], (64, 64))
    with pytest.raises(ValueError, match="no scores"):
        Calibration.from_scores((), [], (64, 64))


def test_json_round_trip_keeps_everything_and_run_info_is_not_compared():
    settings = {"source": "synthetic", "shape": (400, 1600), "emccd": {"photons_peak": 100.0}}
    run_info = {"commit": "abc1234", "wall_clock_s": 12.5}
    cal = _cal([0.0, 1.5, 0.1 + 0.2], settings=settings, run_info=run_info)
    back = Calibration.from_json(cal.to_json())
    assert back == cal
    assert back.scores == (0.0, 1.5, 0.30000000000000004)
    assert back.ids == ("seed:0", "seed:1", "seed:2")
    assert back.shape == (400, 1600)
    # Settings are JSON-normalised: the tuple is a list on both sides.
    assert back.settings == {
        "source": "synthetic",
        "shape": [400, 1600],
        "emccd": {"photons_peak": 100.0},
    }
    assert back.run_info == run_info
    other_run = _cal([0.0, 1.5, 0.1 + 0.2], settings=settings, run_info={"commit": "def5678"})
    assert other_run == cal
    assert _cal([0.0, 1.5, 0.3], settings=settings) != cal


def test_json_refuses_non_finite_and_an_unknown_format():
    text = _cal([1.0, 2.0]).to_json()
    with pytest.raises(ValueError, match="format"):
        Calibration.from_json(text.replace('"format": 1', '"format": 2'))
    with pytest.raises(ValueError, match="may not contain NaN"):
        Calibration.from_json(text.replace("2.0", "NaN"))


def test_digest_changes_with_any_one_score_and_ignores_run_info():
    scores = np.arange(1.0, 301.0)
    cal = _cal(scores, settings={"a": 1}, run_info={"commit": "x"})
    assert cal.digest() == _cal(scores, settings={"a": 1}, run_info={"commit": "y"}).digest()
    for i in (0, 2, 14, 150, 299):  # not only the ranks 3 and 15
        changed = scores.copy()
        changed[i] = np.nextafter(changed[i], np.inf)
        assert _cal(changed, settings={"a": 1}).digest() != cal.digest()
    assert _cal(scores, settings={"a": 2}).digest() != cal.digest()
    assert len(cal.digest()) == 64


# Folder input (AC 5, plan 2.6): generated 64x64 Stripe-free frames at typical settings.

SOLIS = Path(__file__).parent / "data" / "solis"
FOLDER_SHAPE = (64, 64)


@cache
def _folder_frame(seed):
    return generate(
        seed=seed, shape=FOLDER_SHAPE, modulation_depth=0.0, mottle="scorched", noise=Emccd()
    ).frame


def _csv_folder(folder):
    """The 12 folder frames as plain CSVs; returns the (name, array as read) pairs, by name."""
    folder.mkdir(exist_ok=True)
    for seed in CALIBRATION_FOLDER_TEST_SEEDS:
        write_frame_csv(_folder_frame(seed), folder / f"frame-{seed}.csv")
    return [(p.name, read_frame(p).frame) for p in sorted(folder.glob("*.csv"))]


def _solis_text(frame):
    """A frame in the real Solis layout (test_read_frame.py): an axis column 1..N, a
    trailing comma on every row, two blank lines, then Key: value metadata."""
    rows = [
        ",".join([str(i + 1), *(repr(float(v)) for v in row)]) + "," for i, row in enumerate(frame)
    ]
    meta = ["Date and Time:                Fri Jun 29 18:42:06 2018", "Exposure Time (secs): 0.5"]
    return "\n".join([*rows, "", "", *meta]) + "\n"


def test_stripe_free_score_is_the_score_of_the_full_pipeline():
    frame = _folder_frame(CALIBRATION_FOLDER_TEST_SEEDS[0])
    assert stripe_free_score(frame) == analyse(frame, threshold=0.0).score
    assert stripe_free_score(frame, clip_level=np.inf) == (
        analyse(frame, threshold=0.0, clip_level=np.inf).score
    )


def test_folder_of_csv_frames_calibrates_like_the_frames_themselves(tmp_path):
    frames = _csv_folder(tmp_path / "free")
    cal = calibrate_folder(tmp_path / "free")
    assert cal == calibrate(frames, settings=cal.settings)
    assert cal.ids == tuple(f"frame-{s}.csv" for s in CALIBRATION_FOLDER_TEST_SEEDS)
    assert cal.shape == FOLDER_SHAPE
    assert cal.scores == tuple(stripe_free_score(f) for _, f in frames)
    # n = 12 at 10%: k = floor(1.3) = 1, the largest score.
    assert cal.threshold(0.1) == max(cal.scores)


def test_folder_of_solis_exports_with_a_real_one_calibrates_like_the_frames_as_read(tmp_path):
    folder = tmp_path / "solis"
    folder.mkdir()
    for seed in CALIBRATION_FOLDER_TEST_SEEDS[:11]:
        (folder / f"gen-{seed}.asc").write_text(_solis_text(_folder_frame(seed)))
    (folder / "xpos_ypos_crop.asc").write_bytes((SOLIS / "xpos_ypos_crop.asc").read_bytes())
    (folder / ".hidden.asc").write_text("not a frame\n")
    (folder / "notes.txt").write_text("not a frame\n")
    cal = calibrate_folder(folder, drop_axis_column=True)
    as_read = [
        (p.name, read_frame(p, drop_axis_column=True).frame)
        for p in sorted(folder.glob("[!.]*.asc"))
    ]
    assert len(as_read) == 12
    assert cal == calibrate(as_read, settings=cal.settings)
    assert cal.ids[-1] == "xpos_ypos_crop.asc"
    assert cal.shape == FOLDER_SHAPE


def test_folder_calibration_with_two_workers_is_the_same(tmp_path):
    _csv_folder(tmp_path / "free")
    assert calibrate_folder(tmp_path / "free", workers=2) == calibrate_folder(tmp_path / "free")


def test_folder_calibration_refuses_an_empty_folder_mixed_shapes_and_unreadable_files(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError, match=r"no \.csv or \.asc files"):
        calibrate_folder(tmp_path / "empty")
    mixed = tmp_path / "mixed"
    _csv_folder(mixed)
    write_frame_csv(np.ones((64, 80)), mixed / "wide.csv")
    with pytest.raises(ValueError, match="differing shapes"):
        calibrate_folder(mixed)
    bad = tmp_path / "bad"
    _csv_folder(bad)
    (bad / "kinetic.asc").write_bytes((SOLIS / "kinetic.asc").read_bytes())
    with pytest.raises(ValueError, match=r"^kinetic\.asc: .*kinetic series"):
        calibrate_folder(bad, drop_axis_column=True)


def test_calibrate_refuses_no_frames_and_mixed_shapes():
    with pytest.raises(ValueError, match="no frames"):
        calibrate([])
    a = _folder_frame(CALIBRATION_FOLDER_TEST_SEEDS[0])
    with pytest.raises(ValueError, match="differing shapes"):
        calibrate([("a", a), ("b", np.ones((64, 80)))])


def test_folder_calibration_round_trips_and_drives_analyse(tmp_path):
    cal = calibrate_folder(_csv_folder_path(tmp_path))
    back = Calibration.from_json(cal.to_json())
    assert back == cal
    frame = _folder_frame(CALIBRATION_FOLDER_TEST_SEEDS[0])
    report = analyse(frame, calibration=back, false_alarm_rate=0.1)
    assert report.threshold == cal.threshold(0.1)
    assert report.striped == (report.score > cal.threshold(0.1))
    # 12 scores are too few for the default 1% (k = floor(0.13) = 0).
    with pytest.raises(
        ValueError, match=re.escape("12 scores are too few for a false-alarm rate of 0.01")
    ):
        analyse(frame, calibration=back)


def _csv_folder_path(tmp_path):
    _csv_folder(tmp_path / "free")
    return tmp_path / "free"


def test_recalibrate_module_writes_the_folder_calibration(tmp_path):
    folder = _csv_folder_path(tmp_path)
    out = tmp_path / "cal.json"
    result = subprocess.run(
        [sys.executable, "-m", "denoisifier.recalibrate", str(folder), "-o", str(out)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    written = Calibration.from_json(out.read_text())
    assert written == calibrate_folder(folder)
    assert json.loads(out.read_text())["format"] == 1
