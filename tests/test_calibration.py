import re

import numpy as np
import pytest
from scipy.stats import betabinom

from denoisifier._calibration import (
    false_alarm_tolerance,
    rate_interval,
    threshold_for_false_alarm_rate,
    threshold_rank,
)
from denoisifier.calibration import DEFAULT_FALSE_ALARM_RATE, Calibration

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
