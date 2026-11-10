"""Ticket 03 feasibility gate: weak stripes (m = 0.2) at 1% False Alarms.

The slow tests run the real measurement (about 40 min); run them with
`uv run pytest -m slow tests/test_feasibility_gate.py`. The written result is
.scratch/stripe-detector/feasibility-gate.md.
"""

from itertools import combinations
from statistics import median

import pytest

import feasibility

# Seeds already used before ticket 03: tests and ticket 02 (0-199), the
# planner's pre-measurement (1000-1399, 2000-2031) and prototype P1.
USED_SEEDS = [range(0, 200), range(1000, 1400), range(2000, 2032), range(50_000, 50_300), range(59_999, 60_100)]


def test_seed_sets_are_disjoint_and_unused():
    seed_sets = feasibility.SEED_SETS
    assert {name: len(r) for name, r in seed_sets.items()} == {
        "calibration": 2000,
        "held_out_free": 1000,
        "held_out_striped": 500,
        "probe_calibration": 300,
        "probe_free": 200,
        "probe_striped": 100,
        "timing": 1,
    }
    for (a, ra), (b, rb) in combinations(seed_sets.items(), 2):
        assert not set(ra) & set(rb), f"{a} and {b} share seeds"
    for name, r in seed_sets.items():
        for used in USED_SEEDS:
            assert not set(r) & set(used), f"{name} reuses seeds {used}"


def test_seed_sets_are_the_measured_plans():
    assert feasibility.GATE.shape == (256, 256)
    assert feasibility.PROBE.shape == (400, 1600)
    assert feasibility.SEED_SETS["calibration"] == feasibility.GATE.calibration
    assert feasibility.SEED_SETS["probe_striped"] == feasibility.PROBE.striped


def test_run_info_records_the_worker_count():
    assert feasibility.run_info(workers=3)["workers"] == 3


# First of the slow tests, so no worker pool has run yet.
@pytest.mark.slow
def test_full_frame_is_analysed_within_10_s():
    times = feasibility.time_full_frame()
    assert len(times) == 3
    assert median(times) <= feasibility.TIMING_LIMIT_S, f"analyse times {times} s"


@pytest.fixture(scope="module")
def gate():
    return feasibility.measure_gate()


@pytest.mark.slow
def test_held_out_false_alarm_rate_is_about_one_percent(gate):
    lo, hi = gate.false_alarm_tolerance
    assert (lo, hi) == (3, 18)
    assert gate.free_n == len(feasibility.GATE.free)
    assert lo <= gate.false_alarms <= hi, (
        f"{gate.false_alarms}/{gate.free_n} held-out False Alarms at threshold "
        f"{gate.threshold:.2f}: outside {lo}-{hi}, so the measurement is broken"
    )


@pytest.mark.slow
def test_weak_stripes_are_detected_at_least_90_percent(gate):
    assert gate.striped_n == len(feasibility.GATE.striped)
    assert gate.detection_rate >= 0.90, (
        f"{gate.detected}/{gate.striped_n} detected, exact 95% CI {gate.detection_interval}; "
        f"per case {gate.per_case_summary()}"
    )


@pytest.fixture(scope="module")
def probe():
    return feasibility.measure_probe()


@pytest.mark.slow
def test_full_frame_probe_detects_at_least_95_percent(probe):
    # The probe's False Alarm count is recorded in the result doc, not asserted:
    # its tolerance includes 0, so it cannot show "about 1%" (plan B4).
    assert probe.striped_n == len(feasibility.PROBE.striped)
    assert probe.detection_rate >= feasibility.PROBE_MIN_RATE, (
        f"{probe.detected}/{probe.striped_n} detected at full frame, exact 95% CI "
        f"{probe.detection_interval}; per case {probe.per_case_summary()}"
    )
