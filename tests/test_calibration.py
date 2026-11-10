import numpy as np
import pytest
from scipy.stats import betabinom

from denoisifier._calibration import false_alarm_tolerance, rate_interval, threshold_for_false_alarm_rate


def test_threshold_is_the_kth_largest_score():
    # n = 2000, rate 0.01 -> k = floor(0.01 * 2001) = 20 -> 20th largest of 1..2000.
    assert threshold_for_false_alarm_rate(np.arange(1, 2001), 0.01) == 1981


def test_threshold_needs_enough_scores_for_the_rate():
    # 50 scores at 1%: k = floor(0.51) = 0, no order statistic gives that rate.
    with pytest.raises(ValueError):
        threshold_for_false_alarm_rate(np.arange(50.0), 0.01)


def test_threshold_rejects_non_finite_scores():
    scores = np.arange(2000.0)
    scores[7] = np.nan
    with pytest.raises(ValueError):
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
