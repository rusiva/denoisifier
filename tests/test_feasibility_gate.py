"""Ticket 03 feasibility gate: weak stripes (m = 0.2) at 1% False Alarms.

The slow tests run the real measurement (about 40 min); run them with
`uv run pytest -m slow tests/test_feasibility_gate.py`. The written result is
.scratch/stripe-detector/feasibility-gate.md.
"""

from itertools import combinations
from statistics import median

import pytest

import feasibility as fz

# Seeds already used before ticket 03: tests and ticket 02 (0-199), the
# planner's pre-measurement (1000-1399, 2000-2031) and prototype P1.
USED_SEEDS = [range(0, 200), range(1000, 1400), range(2000, 2032), range(50_000, 50_300), range(59_999, 60_100)]


def test_seed_sets_are_disjoint_and_unused():
    fresh = {
        "calibration": fz.CALIBRATION_SEEDS,
        "held-out stripe-free": fz.HELD_OUT_FREE_SEEDS,
        "held-out striped": fz.HELD_OUT_STRIPED_SEEDS,
        "probe calibration": fz.PROBE_CALIBRATION_SEEDS,
        "probe stripe-free": fz.PROBE_FREE_SEEDS,
        "probe striped": fz.PROBE_STRIPED_SEEDS,
        "timing": range(fz.TIMING_SEED, fz.TIMING_SEED + 1),
    }
    assert [len(r) for r in fresh.values()] == [2000, 1000, 500, 300, 200, 100, 1]
    for (a, ra), (b, rb) in combinations(fresh.items(), 2):
        assert not set(ra) & set(rb), f"{a} and {b} share seeds"
    for name, r in fresh.items():
        for used in USED_SEEDS:
            assert not set(r) & set(used), f"{name} reuses seeds {used}"


# First of the slow tests, so no worker pool has run yet.
@pytest.mark.slow
def test_full_frame_is_analysed_within_10_s():
    times = fz.time_full_frame()
    assert len(times) == 3
    assert median(times) <= fz.TIMING_LIMIT_S, f"analyse times {times} s"


@pytest.fixture(scope="module")
def gate():
    return fz.measure_gate()


@pytest.mark.slow
def test_held_out_false_alarm_rate_is_about_one_percent(gate):
    lo, hi = gate.false_alarm_tolerance
    assert (lo, hi) == (3, 18)
    assert gate.free_n == len(fz.HELD_OUT_FREE_SEEDS)
    assert lo <= gate.false_alarms <= hi, (
        f"{gate.false_alarms}/{gate.free_n} held-out False Alarms at threshold "
        f"{gate.threshold:.2f}: outside {lo}-{hi}, so the measurement is broken"
    )


@pytest.mark.slow
def test_weak_stripes_are_detected_at_least_90_percent(gate):
    assert gate.striped_n == len(fz.HELD_OUT_STRIPED_SEEDS)
    assert gate.detection_rate >= 0.90, (
        f"{gate.detected}/{gate.striped_n} detected, exact 95% CI {gate.detection_interval}; "
        f"per case {gate.per_case_summary()}"
    )


@pytest.fixture(scope="module")
def probe():
    return fz.measure_probe()


@pytest.mark.slow
def test_full_frame_probe_detects_at_least_95_percent(probe):
    # The probe's False Alarm count is recorded in the result doc, not asserted:
    # its tolerance includes 0, so it cannot show "about 1%" (plan B4).
    assert probe.striped_n == len(fz.PROBE_STRIPED_SEEDS)
    assert probe.detection_rate >= fz.PROBE_MIN_RATE, (
        f"{probe.detected}/{probe.striped_n} detected at full frame, exact 95% CI "
        f"{probe.detection_interval}; per case {probe.per_case_summary()}"
    )
