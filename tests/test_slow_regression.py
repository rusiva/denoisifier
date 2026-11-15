"""The slow tier (`make check-slow`): a regression check of the detector at the
thresholds stored by the last full measurement (ticket agent-gates/05).

It scores fresh seeds at fixed stored thresholds, with no per-run calibration,
and asserts the pass counts derived in docs/regression-plan.md.
A detector change that moves the score scale is expected to go red here: run
`make measure` (the full ticket-03 measurement), then re-store the thresholds
(an approved lockfile edit); never edit the pass counts.

Duration: this module is the one source for the slow tier's duration. The
module fixture (regression_check) is estimated at about 5-6 min idle with the
default workers; the 1200 s timeout covers the whole module, so any single test
or rerun (`-k`, `--lf`) pays for the fixture under it (ticket agent-gates/05, W3).
Every other test keeps the global 60 s limit.

Since ticket 07, `make check-slow` (`-m "slow and not held_out"`) also runs
tests/test_slow_calibration.py, the calibration reproduction: 300 full frames,
about 14 min idle (ticket 07 step 5 measured 2.79 s per full frame, 838 s for the
300, with the default 12 workers), under its own per-test 2400 s timeout. So the
slow tier takes about 20 min idle in all (estimated from the step-5 rate; the
measured wall clocks are in ticket 07's Comments). tests/test_held_out_calibration.py
is slow too but carries held_out: `make check-slow` does not run it; `make
check-held-out` does (400 full frames plus 20 option analyses, about 20 min idle at
the step-5 rate).

Since ticket 11, `make check-slow` also runs tests/test_slow_break_fork_calibration.py,
the break and Fork calibration reproduction on the first 60 of its 300 frames (about
2.5 min idle: ticket 11 P1 measured about 2.5 s per frame for generation and the
evidence pass with 12 workers), so the slow tier takes about 22-23 min idle.
`make check-held-out` also runs tests/test_held_out_break_fork.py: the full 300-frame
reproduction (about 12.5 min), the held-out fake count (300 frames of `analyse` plus
the evidence pass, about 25 min) and the detection checks (200 frames at 512x512 at
the stored thresholds and at the floors, about 4 min), so it takes about 60 min idle.
"""

import json
import os

import pytest

import feasibility
import slow_stamp
from protected import (
    REGRESSION_MAX_FALSE_ALARMS,
    REGRESSION_MIN_DETECTED,
    REGRESSION_PROBE_MIN_DETECTED,
    SLOW_TIMING_LIMIT_S,
)

pytestmark = [pytest.mark.slow, pytest.mark.timeout(1200)]

MEASUREMENT = feasibility.ROOT / slow_stamp.MEASUREMENT
RESTORE_ADVICE = (
    "A detector change that moves the score scale goes red here: run `make measure`, then "
    "re-store the thresholds (approved lockfile edit); never edit the pass counts."
)


@pytest.fixture(scope="module")
def regression() -> dict:
    result = feasibility.regression_check()
    result["run_id"] = os.environ.get(slow_stamp.RUN_ID_VAR)
    MEASUREMENT.parent.mkdir(exist_ok=True)
    MEASUREMENT.write_text(json.dumps(result, indent=2) + "\n")
    return result


def _cases(part: dict) -> str:
    return ", ".join(
        f"{c['period']}px/{c['angle_deg']}deg {c['detected']}/{c['n']}" for c in part["cases"]
    )


def test_full_frame_is_analysed_within_30_s(regression):
    timing = regression["timing"]
    assert timing["median_s"] <= SLOW_TIMING_LIMIT_S, (
        f"analyse times {timing['seconds']} s at {timing['shape']}"
        f" (loadavg {regression['loadavg']})"
    )


def test_regression_weak_stripes_detected_at_256(regression):
    striped = regression["striped"]
    assert striped["n"] == len(feasibility.REGRESSION.striped)
    assert striped["detected"] >= REGRESSION_MIN_DETECTED, (
        f"{striped['detected']}/{striped['n']} detected at the stored threshold"
        f" {feasibility.REGRESSION.gate_threshold}: {_cases(striped)}. {RESTORE_ADVICE}"
    )


def test_regression_false_alarms_at_256(regression):
    free = regression["free"]
    assert free["n"] == len(feasibility.REGRESSION.free)
    assert free["false_alarms"] <= REGRESSION_MAX_FALSE_ALARMS, (
        f"{free['false_alarms']}/{free['n']} False Alarms at the stored threshold"
        f" {feasibility.REGRESSION.gate_threshold}. {RESTORE_ADVICE}"
    )


def test_regression_full_frame_detected(regression):
    """A collapse check at a declared bad rate of 0.70 (ruling O1), the timed
    frames included (ruling O2). The full-frame 0.95 bar
    (PROBE_MIN_DETECTION_RATE) is `make measure`'s."""
    probe = regression["probe"]
    assert probe["n"] == len(feasibility.REGRESSION.probe_striped)
    assert probe["detected"] >= REGRESSION_PROBE_MIN_DETECTED, (
        f"{probe['detected']}/{probe['n']} detected at full frame at the stored threshold"
        f" {feasibility.REGRESSION.probe_threshold}: {_cases(probe)}. {RESTORE_ADVICE}"
    )
