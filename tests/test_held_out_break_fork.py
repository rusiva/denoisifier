"""Held-out break and Fork calibration tests (ticket 11, AC 1 full, AC 2, AC 3(c)).

Marked slow **and** held_out: stamped (a slow-tier file), but **not** run by
`make check-slow`; `make check-held-out` runs them, once at ticket 11's close and after a
re-store; nothing else generates their seeds. The fixtures write their parts of
`.gate/held-out-break-fork.json`.

AC 1 (full): the calibration routine on all 300 frames reproduces the stored file.
AC 2: on BREAK_FORK_FREE_HELD_OUT_SEEDS (the calibration recipe: 400x1600 full-frame stripes,
depth 0.5, scorched Mottle, about 100 photons at the peak, 30 Spike events), every frame is
Striped, the default path's total count of reported Phase Breaks and Forks is at most
BREAK_FORK_MAX_FAKES, and the found/reported implications hold on every frame. Frames with a
fake, their exact upper limit and the per-case alarm flags are recorded, not asserted.
AC 3(c): 100 09-style break frames and 100 10-style Fork frames are each found at least
BREAK_FORK_MIN_DETECTION_RATE of the time on the default path, and none found at the floors is
lost at the stored thresholds.

A red is a finding for the orchestrator (plan section 9): no threshold, floor, recipe or seed
is edited; a second look uses the reserved _2 seed ranges.

Duration: about 300 full frames for AC 1, 300 full frames (analyse + evidence) for AC 2 and
200 region frames (two analyses each) for AC 3(c); see tests/test_slow_regression.py.
"""

import pytest

import break_fork_calibration as bfc
import threshold_calibration as tc
from denoisifier.calibration import _BreakForkThresholds, _stored_break_fork_calibration
from protected import (
    BREAK_FORK_FREE_CALIBRATION_SEEDS,
    CALIBRATION_TIMEOUT_S,
    PACKAGE_BREAK_FORK_BREAK_THRESHOLD,
    PACKAGE_BREAK_FORK_FORK_THRESHOLD,
)

pytestmark = [pytest.mark.slow, pytest.mark.held_out]

STORED = _BreakForkThresholds(
    breaks=PACKAGE_BREAK_FORK_BREAK_THRESHOLD, forks=PACKAGE_BREAK_FORK_FORK_THRESHOLD
)


@pytest.fixture(scope="module")
def fakes() -> dict:
    result = bfc.held_out_fakes(bfc.HELD_OUT_FAKES)
    tc.record(bfc.HELD_OUT_MEASUREMENT, "fakes", result, fresh=True)
    return result


@pytest.fixture(scope="module")
def detection() -> dict:
    result = bfc.held_out_detection(bfc.HELD_OUT_DETECTION)
    tc.record(bfc.HELD_OUT_MEASUREMENT, "detection", result)
    return result


@pytest.mark.timeout(CALIBRATION_TIMEOUT_S)
def test_held_out_fake_breaks_and_forks_at_the_default_rate(fakes):
    assert fakes["n"] == len(bfc.HELD_OUT_FAKES.seeds)
    problems = bfc.fake_problems(fakes, STORED)
    assert problems == [], "\n".join(problems)


@pytest.mark.timeout(CALIBRATION_TIMEOUT_S)
def test_breaks_still_found_after_calibration(detection):
    assert detection["breaks"]["n"] == len(bfc.HELD_OUT_DETECTION.breaks)
    problems = bfc.detection_problems(detection, "breaks")
    assert problems == [], "\n".join(problems)


@pytest.mark.timeout(CALIBRATION_TIMEOUT_S)
def test_forks_still_found_after_calibration(detection):
    assert detection["forks"]["n"] == len(bfc.HELD_OUT_DETECTION.forks)
    problems = bfc.detection_problems(detection, "forks")
    assert problems == [], "\n".join(problems)


@pytest.mark.timeout(CALIBRATION_TIMEOUT_S)
def test_break_fork_calibration_reproduces_all_frames():
    result = bfc.reproduction_check(_stored_break_fork_calibration(), bfc.calibrate_break_forks)
    tc.record(bfc.HELD_OUT_MEASUREMENT, "reproduction", result)
    assert result["n"] == len(BREAK_FORK_FREE_CALIBRATION_SEEDS)
    problems = bfc.reproduction_problems(
        result, PACKAGE_BREAK_FORK_BREAK_THRESHOLD, PACKAGE_BREAK_FORK_FORK_THRESHOLD
    )
    assert problems == [], "\n".join(problems)
