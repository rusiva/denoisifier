"""Statistics for setting a Threshold from Stripe-free scores and judging rates.

Private: used by the ticket 03 feasibility gate; ticket 07 may promote it.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike
from scipy.stats import betabinom, binomtest


def threshold_for_false_alarm_rate(scores: ArrayLike, rate: float) -> float:
    """Order-statistic threshold: with n scores and k = floor(rate * (n + 1)),
    return the k-th largest score. If the scores are exchangeable, a new
    Stripe-free frame exceeds it with probability k / (n + 1) (about rate).

    Raises ValueError if k < 1 (too few scores for this rate) or any score is
    not finite.
    """
    a = np.asarray(scores, dtype=float).ravel()
    if not np.all(np.isfinite(a)):
        raise ValueError("scores must all be finite")
    k = _order(a.size, rate)
    return float(np.sort(a)[::-1][k - 1])


def false_alarm_tolerance(n_calibration: int, n_held_out: int, rate: float, level: float = 0.95) -> tuple[int, int]:
    """Central interval of the held-out False Alarm count, given a threshold set
    from n_calibration scores by threshold_for_false_alarm_rate.

    The threshold's true false-alarm rate is Beta(k, n_calibration + 1 - k), so
    the held-out count is betabinom(n_held_out, k, n_calibration + 1 - k). The
    interval covers both calibration and held-out noise. The count is
    discrete, so its exact coverage is at least level.
    """
    d = _false_alarm_count(n_calibration, n_held_out, rate)
    return int(d.ppf((1 - level) / 2)), int(d.ppf((1 + level) / 2))


def rate_interval(k: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """Clopper-Pearson (exact) interval for a proportion of k out of n."""
    ci = binomtest(k, n).proportion_ci(confidence_level=level, method="exact")
    return float(ci.low), float(ci.high)


def _false_alarm_count(n_calibration: int, n_held_out: int, rate: float):
    k = _order(n_calibration, rate)
    return betabinom(n_held_out, k, n_calibration + 1 - k)


def _order(n: int, rate: float) -> int:
    """k = floor(rate * (n + 1)); the small slack absorbs float error such as
    0.29 * 100 = 28.999999999999996."""
    k = math.floor(rate * (n + 1) + 1e-9)
    if k < 1:
        raise ValueError(f"{n} scores are too few for a false-alarm rate of {rate}: need at least {math.ceil(1 / rate) - 1}")
    return k
