"""Held-out statistical calibration tests (ticket 07, AC 2a, 2b, 3).

Marked slow **and** held_out: stamped (a slow-tier file), but **not** run by
`make check-slow` (`-m "slow and not held_out"`), so a green check-slow does not
cover them. `make check-held-out` runs them, once at ticket 07's close and at
`make measure` milestones (after any re-store); nothing else generates their seeds
(plan 2.11). Each module fixture writes its part of `.gate/held-out-calibration.json`.

AC 2a: False Alarms of the default path (stored calibration, 1%) on
CALIBRATED_FREE_SEEDS lie in the betabinomial tolerance at CALIBRATION_TOLERANCE_LEVEL.
AC 2b: the count above the stored 5% threshold lies in its tolerance, and the
``false_alarm_rate`` option agrees on the first HELD_OUT_OPTION_FRAMES frames.
AC 3: at least MIN_DETECTION_RATE of the m = WEAK_DEPTH frames of
CALIBRATED_STRIPED_SEEDS are detected on the default path (pooled; the per-case
breakdown is reported, not asserted).

A red is a finding (plan section 13, rule 1): no re-seeding, no change of sizes,
spikes, level or MIN_DETECTION_RATE, and no second look.

Duration: about 300 (+20 option) and 100 full frames in two module fixtures, each
paid under the per-test timeout of the first test that uses it (W6).
"""

import pytest

import threshold_calibration as tc
from protected import (
    CALIBRATION_TIMEOUT_S,
    PACKAGE_STORED_THRESHOLD,
    PACKAGE_STORED_THRESHOLD_5PCT,
)

pytestmark = [pytest.mark.slow, pytest.mark.held_out]


@pytest.fixture(scope="module")
def free() -> dict:
    result = tc.held_out_free(tc.HELD_OUT)
    tc.record(tc.HELD_OUT_MEASUREMENT, "free", result, fresh=True)
    return result


@pytest.fixture(scope="module")
def striped() -> dict:
    result = tc.held_out_striped(tc.HELD_OUT)
    tc.record(tc.HELD_OUT_MEASUREMENT, "striped", result)
    return result


@pytest.mark.timeout(CALIBRATION_TIMEOUT_S)
def test_held_out_false_alarms_at_the_default_rate(free):
    assert free["n"] == len(tc.HELD_OUT.free)
    problems = tc.false_alarm_problems(free, PACKAGE_STORED_THRESHOLD)
    assert problems == [], "\n".join(problems)


@pytest.mark.timeout(CALIBRATION_TIMEOUT_S)
def test_held_out_false_alarms_at_five_percent(free):
    assert len(free["option_frames"]) == tc.HELD_OUT.option_frames
    problems = tc.other_rate_problems(free, PACKAGE_STORED_THRESHOLD_5PCT)
    assert problems == [], "\n".join(problems)


@pytest.mark.timeout(CALIBRATION_TIMEOUT_S)
def test_weak_stripes_detected_at_the_default_rate(striped):
    assert striped["n"] == len(tc.HELD_OUT.striped)
    assert striped["thresholds_seen"] == [PACKAGE_STORED_THRESHOLD]
    problems = tc.detection_problems(striped)
    assert problems == [], "\n".join(problems)
