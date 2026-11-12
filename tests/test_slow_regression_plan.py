"""The slow tier's regression plan (ticket agent-gates/05): consistency with the
saved full measurement and the operating rule. Non-slow; runs in `make check`.

The derivation is .scratch/agent-gates/handoffs/05-plan.md ("Exact-binomial
derivation"; its note on the false-alarm baseline records the owner-approved
rank-based bound of ticket stripe-detector/05). When `make measure` stores a
worse baseline, the rule test goes red; re-deriving the pass counts is then an
owner decision, never a silent edit.
"""

import json

import numpy as np
from scipy.stats import beta, binom, binomtest

import feasibility
import protected
from denoisifier._calibration import threshold_for_false_alarm_rate, threshold_rank
from protected import (
    FREE_RATE_BOUND_COVERAGE_TEST_SEED,
    FREE_RATE_BOUND_COVERAGE_TOL,
    FREE_RATE_BOUND_COVERAGE_TRIALS,
    GATE_SHAPE,
    GATE_STORED_THRESHOLD,
    PROBE_SHAPE,
    PROBE_STORED_THRESHOLD,
    REGRESSION_BAD_DETECTION_RATE,
    REGRESSION_BAD_FALSE_ALARM_RATE,
    REGRESSION_FREE_RATE_BOUND_QUANTILE,
    REGRESSION_FREE_SEEDS,
    REGRESSION_MAX_FALSE_ALARMS,
    REGRESSION_MAX_FALSE_RED,
    REGRESSION_MAX_PASS_BAD,
    REGRESSION_MIN_DETECTED,
    REGRESSION_PROBE_BAD_DETECTION_RATE,
    REGRESSION_PROBE_MIN_DETECTED,
    REGRESSION_PROBE_STRIPED_SEEDS,
    REGRESSION_STRIPED_SEEDS,
    REGRESSION_TIMED_FRAMES,
    REGRESSION_TINY_FREE_TEST_SEEDS,
    REGRESSION_TINY_PROBE_TEST_SEEDS,
    REGRESSION_TINY_STRIPED_TEST_SEEDS,
    TIMING_CASE,
    TIMING_SEED,
)


def _saved() -> dict:
    return json.loads(feasibility.DEFAULT_OUT.read_text())


def _ci(k: int, n: int) -> tuple[float, float]:
    ci = binomtest(k, n).proportion_ci(confidence_level=0.95, method="exact")
    return float(ci.low), float(ci.high)


def test_stored_thresholds_are_the_saved_measurement():
    saved = _saved()
    assert saved["gate"]["threshold"] == GATE_STORED_THRESHOLD, (
        "feasibility-gate.json has a new gate threshold: re-store GATE_STORED_THRESHOLD "
        "(an approved lockfile edit, CLAUDE.md)"
    )
    assert saved["probe"]["threshold"] == PROBE_STORED_THRESHOLD, (
        "feasibility-gate.json has a new probe threshold: re-store PROBE_STORED_THRESHOLD "
        "(an approved lockfile edit, CLAUDE.md)"
    )


def _free_rate_bound(k: int, n: int, x: int, n_free: int) -> float:
    """Upper REGRESSION_FREE_RATE_BOUND_QUANTILE bound on the stored threshold's
    true Stripe-free exceedance rate (owner approval, ticket stripe-detector/05,
    Comments; derivation note in .scratch/agent-gates/handoffs/.archived/05-plan.md).

    The threshold is the k-th largest of n calibration scores, so its true
    exceedance rate is Beta(k, n + 1 - k); x exceedances in n_free held-out
    frames update it to Beta(k + x, n + 1 - k + n_free - x). The bound covers
    the true rate with the stated probability averaged over calibration draws
    (not conditional on one fixed threshold), assuming i.i.d. continuous
    Stripe-free scores with no tie at rank k.
    """
    return float(beta.ppf(REGRESSION_FREE_RATE_BOUND_QUANTILE, k + x, n + 1 - k + n_free - x))


def test_regression_plan_meets_the_operating_rule():
    saved = _saved()
    gate, probe = saved["gate"], saved["probe"]
    # Detection: pessimistic ends of the stored baseline's exact 95% CIs.
    det0 = _ci(gate["detected"], gate["striped_n"])[0]
    probe0 = _ci(probe["detected"], probe["striped_n"])[0]
    # False alarms: the threshold's rank-based bound (owner approval, ticket
    # stripe-detector/05 Comments). It replaced the held-out count's own
    # Clopper-Pearson end: the stored threshold is a calibration rank, so the
    # held-out count is betabinom(N, k, n + 1 - k) for any detector, and that
    # CI end passed the rule on only about 38% of measures (05-implementer-7.md).
    fa0 = _free_rate_bound(gate["k"], gate["calibration_n"], gate["false_alarms"], gate["free_n"])

    n, c = len(REGRESSION_STRIPED_SEEDS), REGRESSION_MIN_DETECTED
    nf, a = len(REGRESSION_FREE_SEEDS), REGRESSION_MAX_FALSE_ALARMS
    np_, cp = len(REGRESSION_PROBE_STRIPED_SEEDS), REGRESSION_PROBE_MIN_DETECTED
    false_red = {
        "detection": float(binom.cdf(c - 1, n, det0)),
        "false alarms": float(binom.sf(a, nf, fa0)),
        "full frame": float(binom.cdf(cp - 1, np_, probe0)),
    }
    pass_bad = {
        "detection": float(binom.sf(c - 1, n, REGRESSION_BAD_DETECTION_RATE)),
        "false alarms": float(binom.cdf(a, nf, REGRESSION_BAD_FALSE_ALARM_RATE)),
        "full frame": float(binom.sf(cp - 1, np_, REGRESSION_PROBE_BAD_DETECTION_RATE)),
    }
    union = 1.0
    for p in false_red.values():
        union *= 1.0 - p
    union = 1.0 - union
    assert union <= REGRESSION_MAX_FALSE_RED, f"P(any false red) {union:.4%}: {false_red}"
    assert sum(false_red.values()) <= REGRESSION_MAX_FALSE_RED, (
        f"Bonferroni sum {sum(false_red.values()):.4%}: {false_red}"
    )
    for name, p in pass_bad.items():
        assert p <= REGRESSION_MAX_PASS_BAD, f"{name}: P(pass a bad detector) {p:.4%}"
    assert 0 < REGRESSION_TIMED_FRAMES <= np_


def test_stored_threshold_rank_is_untied():
    """The rank-based bound assumes no tie at the threshold's rank k. The
    calibration scores are not saved, only how many lie above the threshold, so
    this guards the ranks above k: exactly k - 1 calibration scores exceed it. A
    tie with ranks below k (k + 1, ...) is not visible in the saved measurement."""
    saved = _saved()
    gate = saved["gate"]
    assert gate["k"] == threshold_rank(gate["calibration_n"], saved["run_info"]["rate"])
    assert gate["calibration_above"] == gate["k"] - 1, (
        f"{gate['calibration_above']} calibration scores exceed the threshold, "
        f"not k - 1 = {gate['k'] - 1}: the threshold's rank is tied"
    )


def test_free_rate_bound_covers_the_true_rate_for_continuous_scores():
    """Uniform (continuous, i.i.d.) scores at the saved measurement's sizes: the
    true exceedance rate of the order-statistic threshold lies at or below the
    bound in about REGRESSION_FREE_RATE_BOUND_QUANTILE of calibration draws."""
    gate = _saved()["gate"]
    k, n, n_free = gate["k"], gate["calibration_n"], gate["free_n"]
    rng = np.random.default_rng(FREE_RATE_BOUND_COVERAGE_TEST_SEED)
    covered = 0
    for _ in range(FREE_RATE_BOUND_COVERAGE_TRIALS):
        threshold = threshold_for_false_alarm_rate(rng.random(n), feasibility.RATE)
        x = int((rng.random(n_free) > threshold).sum())
        covered += 1.0 - threshold <= _free_rate_bound(k, n, x, n_free)
    coverage = covered / FREE_RATE_BOUND_COVERAGE_TRIALS
    assert abs(coverage - REGRESSION_FREE_RATE_BOUND_QUANTILE) <= FREE_RATE_BOUND_COVERAGE_TOL, (
        f"coverage {coverage:.4f}"
    )


def test_regression_sets_are_balanced_over_the_cases():
    n_cases = len(feasibility.CASES)
    for name in (
        "REGRESSION_STRIPED_SEEDS",
        "REGRESSION_FREE_SEEDS",
        "REGRESSION_PROBE_STRIPED_SEEDS",
    ):
        r = getattr(protected, name)
        assert r.step == 1
        assert r.start % n_cases == 0, f"{name} starts at {r.start}"
        assert len(r) % n_cases == 0, f"{name} has {len(r)} seeds"


def test_time_full_frame_times_the_timing_frame(monkeypatch):
    frames: list[tuple] = []
    analysed: list[object] = []

    def fake_frame(seed, depth, shape, case):
        frames.append((seed, depth, shape, case))
        return (seed, depth, shape, case)

    monkeypatch.setattr(feasibility, "_frame", fake_frame)
    monkeypatch.setattr(feasibility, "analyse", analysed.append)
    times = feasibility.time_full_frame(repeats=4)
    timed = (TIMING_SEED, feasibility.DEPTH, PROBE_SHAPE, TIMING_CASE)
    warm_up = (TIMING_SEED, 0.0, GATE_SHAPE, TIMING_CASE)
    assert sorted(frames) == sorted([timed, warm_up])
    assert analysed == [warm_up, timed, timed, timed, timed]
    assert len(times) == 4


TINY = feasibility.RegressionPlan(
    gate_shape=(40, 40),
    probe_shape=(40, 40),
    gate_threshold=GATE_STORED_THRESHOLD,
    probe_threshold=PROBE_STORED_THRESHOLD,
    striped=REGRESSION_TINY_STRIPED_TEST_SEEDS,
    free=REGRESSION_TINY_FREE_TEST_SEEDS,
    probe_striped=REGRESSION_TINY_PROBE_TEST_SEEDS,
    timed=1,
    min_detected=1,
    max_false_alarms=1,
    probe_min_detected=1,
)


def test_regression_check_runs_on_a_tiny_plan():
    result = feasibility.regression_check(TINY, workers=2)
    assert result["striped"]["n"] == len(REGRESSION_TINY_STRIPED_TEST_SEEDS)
    assert result["free"]["n"] == len(REGRESSION_TINY_FREE_TEST_SEEDS)
    assert result["probe"]["n"] == len(REGRESSION_TINY_PROBE_TEST_SEEDS)
    assert 0 <= result["striped"]["detected"] <= result["striped"]["n"]
    assert 0 <= result["free"]["false_alarms"] <= result["free"]["n"]
    assert 0 <= result["probe"]["detected"] <= result["probe"]["n"]
    assert sum(c["n"] for c in result["striped"]["cases"]) == result["striped"]["n"]
    assert len(result["timing"]["seconds"]) == 1
    assert result["timing"]["median_s"] == result["timing"]["seconds"][0]
    assert result["run_info"]["workers"] == 2
    assert set(result["loadavg"]) == {"start", "end"}
    assert "OMP_NUM_THREADS" in result["threads"]
    assert result["wall_clock_s"] > 0
    assert json.loads(json.dumps(result))["plan"]["striped"] == [60, 61]  # written as JSON
