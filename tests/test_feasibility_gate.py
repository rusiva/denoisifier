"""Ticket 03 feasibility gate: weak stripes (m = 0.2) at 1% False Alarms.

The limit tests check the saved measurement, feasibility-gate.json, in
`make check`. Re-measure and save with `make measure` (about 39 min, on demand
at milestones; ticket agent-gates/05), which runs tests/feasibility.py and then
these tests. The slow tier (`make check-slow`) is the regression check in
test_slow_regression.py. The write-up is
.scratch/stripe-detector/feasibility-gate.md.
"""

import json
from itertools import combinations
from types import SimpleNamespace

import pytest

import feasibility
import protected
from denoisifier._local_stripes import _THREADS_ENV, bank_threads
from protected import (
    FALSE_ALARM_TOLERANCE,
    MIN_DETECTION_RATE,
    PROBE_MIN_DETECTION_RATE,
    TIMING_LIMIT_S,
    TIMING_SEED,
)


def seed_range_overlaps(namespace) -> list[str]:
    """Every pair of top-level seed ranges in ``namespace`` that share seeds.

    The top-level ranges are each module-level ``range`` (except
    ``*_TEST_SEEDS``), each ``USED_SEEDS[i]``, and each ``int`` named ``*_SEED``
    (except ``*_TEST_SEED``) as a one-seed range. Aliases (the same object) are
    counted once, under their first name; equal ranges under two names are
    different entries, so they overlap (ticket agent-gates/04).
    """
    entries: list[tuple[str, range]] = []

    def add(name: str, r: range) -> None:
        if not any(r is seen for _, seen in entries):
            entries.append((name, r))

    for name, value in vars(namespace).items():
        if isinstance(value, range) and not name.endswith("_TEST_SEEDS"):
            add(name, value)
        elif (
            isinstance(value, int)
            and not isinstance(value, bool)
            and name.endswith("_SEED")
            and not name.endswith("_TEST_SEED")
        ):
            add(name, range(value, value + 1))
    for i, r in enumerate(getattr(namespace, "USED_SEEDS", [])):
        add(f"USED_SEEDS[{i}]", r)
    overlaps = []
    for (a, ra), (b, rb) in combinations(entries, 2):
        shared = len(set(ra) & set(rb))
        if shared:
            overlaps.append(f"{a} = {ra!r} and {b} = {rb!r} share {shared} seeds")
    return overlaps


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
    assert seed_range_overlaps(protected) == []

    # Test seeds may share seeds with each other, but stay in the test block.
    for name, value in vars(protected).items():
        if name.endswith("_TEST_SEEDS"):
            seeds = list(value)
        elif name.endswith("_TEST_SEED"):
            seeds = [value]
        elif name == "BORDERLINE_TEST_CASES":
            seeds = [seed for seed, _ in value]
        else:
            continue
        outside = [s for s in seeds if s not in protected.TEST_SEED_BLOCK]
        assert not outside, f"{name} has seeds {outside} outside TEST_SEED_BLOCK"

    # Registry links: the calibration registry names top-level ranges, and
    # every feasibility seed set is a registered range.
    top_level = [v for v in vars(protected).values() if isinstance(v, range)]
    for name, r in protected.CALIBRATION_SEEDS.items():
        assert getattr(protected, name) is r, f"CALIBRATION_SEEDS[{name!r}] is not {name}"
    for name, r in seed_sets.items():
        assert r in top_level or r == range(TIMING_SEED, TIMING_SEED + 1), (
            f"SEED_SETS[{name!r}] = {r!r} is not a protected seed range"
        )
        if "calibration" in name:
            assert any(r is c for c in protected.CALIBRATION_SEEDS.values()), (
                f"SEED_SETS[{name!r}] is a calibration set missing from CALIBRATION_SEEDS"
            )


def test_equal_ranges_under_two_names_are_an_overlap():
    distinct = SimpleNamespace(A_SEEDS=range(5, 9), B_SEEDS=range(5, 9))
    assert seed_range_overlaps(distinct) == [
        "A_SEEDS = range(5, 9) and B_SEEDS = range(5, 9) share 4 seeds"
    ]
    a = range(5, 9)
    assert seed_range_overlaps(SimpleNamespace(A_SEEDS=a, B_SEEDS=a)) == []


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


def test_saved_measurement_is_from_clean_code_and_the_current_seed_plan(saved):
    info = saved["run_info"]
    assert not info["commit"].endswith("-dirty"), "re-measure from a clean tree"
    assert tuple(info["gate_shape"]) == feasibility.GATE.shape
    assert tuple(info["probe_shape"]) == feasibility.PROBE.shape
    assert info["seeds"] == {name: [r[0], r[-1]] for name, r in feasibility.SEED_SETS.items()}, (
        "the seed plan changed since the saved measurement: re-measure"
    )


def test_full_frame_is_analysed_within_10_s(saved):
    timing = saved["timing"]
    assert len(timing["seconds"]) == 3
    assert timing["median_s"] <= TIMING_LIMIT_S, f"analyse times {timing['seconds']} s"


def test_held_out_false_alarm_rate_is_about_one_percent(saved):
    gate = saved["gate"]
    lo, hi = gate["false_alarm_tolerance"]
    assert (lo, hi) == FALSE_ALARM_TOLERANCE
    assert gate["free_n"] == len(feasibility.GATE.free)
    assert lo <= gate["false_alarms"] <= hi, (
        f"{gate['false_alarms']}/{gate['free_n']} held-out False Alarms at threshold "
        f"{gate['threshold']:.2f}: outside {lo}-{hi}, so the measurement is broken"
    )


def test_weak_stripes_are_detected_at_least_90_percent(saved):
    gate = saved["gate"]
    assert gate["striped_n"] == len(feasibility.GATE.striped)
    assert gate["detected"] / gate["striped_n"] >= MIN_DETECTION_RATE, (
        f"{gate['detected']}/{gate['striped_n']} detected,"
        f" exact 95% CI {gate['detection_interval']}"
    )


def test_full_frame_probe_detects_at_least_95_percent(saved):
    # The probe's False Alarm count is recorded in the write-up, not asserted:
    # its tolerance includes 0, so it cannot show "about 1%" (plan B4).
    probe = saved["probe"]
    assert probe["striped_n"] == len(feasibility.PROBE.striped)
    assert probe["detected"] / probe["striped_n"] >= PROBE_MIN_DETECTION_RATE, (
        f"{probe['detected']}/{probe['striped_n']} detected at full frame, exact 95% CI "
        f"{probe['detection_interval']}"
    )


def test_pool_workers_run_the_bank_on_one_thread():
    # Each worker is one process of a pool sized to the CPUs: its bank must not add threads.
    assert feasibility.run_pool(bank_threads, [None, None, None], workers=2) == [1, 1, 1]


def test_thread_settings_record_the_bank_threads(monkeypatch):
    monkeypatch.setenv(_THREADS_ENV, "3")
    settings = feasibility.thread_settings()
    assert settings["bank_threads"] == 3
    assert settings[_THREADS_ENV] == "3"
    assert feasibility.run_info(workers=2)["bank_threads"] == {"in_process": 3, "pool_workers": 1}
