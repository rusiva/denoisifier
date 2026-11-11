"""The slow tier's regression plan (ticket agent-gates/05): consistency with the
saved full measurement and the operating rule. Non-slow; runs in `make check`.

The derivation is .scratch/agent-gates/handoffs/05-plan.md ("Exact-binomial
derivation"). When `make measure` stores a worse baseline, the rule test goes
red; re-deriving the pass counts is then an owner decision, never a silent edit.
"""

import json

from scipy.stats import binom, binomtest

import feasibility
import protected
from protected import (
    GATE_SHAPE,
    GATE_STORED_THRESHOLD,
    PROBE_SHAPE,
    PROBE_STORED_THRESHOLD,
    REGRESSION_BAD_DETECTION_RATE,
    REGRESSION_BAD_FALSE_ALARM_RATE,
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


def test_regression_plan_meets_the_operating_rule():
    saved = _saved()
    gate, probe = saved["gate"], saved["probe"]
    # Pessimistic ends of the stored baseline's exact 95% CIs.
    det0 = _ci(gate["detected"], gate["striped_n"])[0]
    fa0 = _ci(gate["false_alarms"], gate["free_n"])[1]
    probe0 = _ci(probe["detected"], probe["striped_n"])[0]

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
