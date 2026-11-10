"""Ticket 03 feasibility gate: weak stripes (m = 0.2) at 1% False Alarms.

The limit tests check the saved measurement, feasibility-gate.json, and, in the
slow tier (`make check-slow`; its duration is noted at the `fresh` timeout
below), a fresh measurement. Re-measure and save with
`uv run python tests/feasibility.py`. The write-up is
.scratch/stripe-detector/feasibility-gate.md.
"""

import json
from itertools import combinations

import pytest

import feasibility

# Seeds already used before ticket 03: tests and ticket 02 (0-199), the
# planner's pre-measurement (1000-1399, 2000-2031) and prototype P1.
USED_SEEDS = [
    range(0, 200),
    range(1000, 1400),
    range(2000, 2032),
    range(50_000, 50_300),
    range(59_999, 60_100),
]


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


@pytest.mark.parametrize(("cpus", "workers"), [(16, 12), (8, 6), (2, 2), (1, 1), (None, 2)])
def test_default_workers_are_three_quarters_of_the_cpus(monkeypatch, cpus, workers):
    monkeypatch.setattr(feasibility.os, "cpu_count", lambda: cpus)
    assert feasibility.resolve_workers() == workers
    assert feasibility.resolve_workers(5) == 5


def test_run_info_records_the_worker_count():
    assert feasibility.run_info(workers=3)["workers"] == 3


@pytest.fixture(scope="module")
def saved():
    return json.loads(feasibility.DEFAULT_OUT.read_text())


@pytest.fixture(
    scope="module",
    params=["saved", pytest.param("fresh", marks=pytest.mark.slow)],
)
def measurement(request):
    if request.param == "fresh":
        return feasibility.measure_all()
    return request.getfixturevalue("saved")


def test_saved_measurement_is_from_clean_code_and_the_current_seed_plan(saved):
    info = saved["run_info"]
    assert not info["commit"].endswith("-dirty"), "re-measure from a clean tree"
    assert tuple(info["gate_shape"]) == feasibility.GATE.shape
    assert tuple(info["probe_shape"]) == feasibility.PROBE.shape
    assert info["seeds"] == {name: [r[0], r[-1]] for name, r in feasibility.SEED_SETS.items()}, (
        "the seed plan changed since the saved measurement: re-measure"
    )


# The module-scoped fresh measurement is paid for by the first test that uses it,
# this one (first in the file; pytest keeps file order within a param). The fresh
# measurement took about 39 min with 8 workers (feasibility-gate.md); 5400 s is
# about 2.3x that. This is the one source for the slow tier's duration. Every
# other test keeps the global 60 s limit.
@pytest.mark.parametrize(
    "measurement",
    ["saved", pytest.param("fresh", marks=[pytest.mark.slow, pytest.mark.timeout(5400)])],
    indirect=True,
)
def test_full_frame_is_analysed_within_10_s(measurement):
    timing = measurement["timing"]
    assert len(timing["seconds"]) == 3
    assert timing["median_s"] <= feasibility.TIMING_LIMIT_S, f"analyse times {timing['seconds']} s"


def test_held_out_false_alarm_rate_is_about_one_percent(measurement):
    gate = measurement["gate"]
    lo, hi = gate["false_alarm_tolerance"]
    assert (lo, hi) == (3, 18)
    assert gate["free_n"] == len(feasibility.GATE.free)
    assert lo <= gate["false_alarms"] <= hi, (
        f"{gate['false_alarms']}/{gate['free_n']} held-out False Alarms at threshold "
        f"{gate['threshold']:.2f}: outside {lo}-{hi}, so the measurement is broken"
    )


def test_weak_stripes_are_detected_at_least_90_percent(measurement):
    gate = measurement["gate"]
    assert gate["striped_n"] == len(feasibility.GATE.striped)
    assert gate["detected"] / gate["striped_n"] >= 0.90, (
        f"{gate['detected']}/{gate['striped_n']} detected,"
        f" exact 95% CI {gate['detection_interval']}"
    )


def test_full_frame_probe_detects_at_least_95_percent(measurement):
    # The probe's False Alarm count is recorded in the write-up, not asserted:
    # its tolerance includes 0, so it cannot show "about 1%" (plan B4).
    probe = measurement["probe"]
    assert probe["striped_n"] == len(feasibility.PROBE.striped)
    assert probe["detected"] / probe["striped_n"] >= feasibility.PROBE_MIN_RATE, (
        f"{probe['detected']}/{probe['striped_n']} detected at full frame, exact 95% CI "
        f"{probe['detection_interval']}"
    )
