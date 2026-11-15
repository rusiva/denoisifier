"""Ticket 11: the break and Fork thresholds from stored per-frame evidence on break- and
Fork-free striped frames (plan `.scratch/stripe-detector/handoffs/11-plan.md`)."""

from __future__ import annotations

import json
import math

import pytest

from denoisifier._local_phase import _BREAK_MIN_EVIDENCE, _FORK_MIN_EVIDENCE
from denoisifier.calibration import (
    DEFAULT_BREAK_FORK_FALSE_ALARM_RATE,
    _BreakForkCalibration,
    _BreakForkThresholds,
)


def _calibration(breaks, forks, **kwargs):
    ids = [f"seed:{i}" for i in range(len(breaks))]
    return _BreakForkCalibration.from_evidence(ids, breaks, forks, (400, 1600), **kwargs)


def test_default_break_fork_false_alarm_rate_is_five_percent():
    """About once per 20 frames (ticket 11, spec)."""
    assert DEFAULT_BREAK_FORK_FALSE_ALARM_RATE == 0.05


def test_break_fork_thresholds_are_marginal_order_statistics_with_floors():
    """r/2 for each kind: k = floor(r/2 (n + 1)) of each kind's evidence, never under its floor."""
    n = 300
    # Distinct values above both floors, largest first: 0.9, 0.899, ...
    high = [0.9 - 0.001 * i for i in range(n)]
    cal = _calibration(high, list(reversed(high)))
    # n = 300, r = 0.05: k = floor(0.025 * 301) = 7, the 7th largest.
    assert cal.thresholds(0.05) == _BreakForkThresholds(breaks=high[6], forks=high[6])
    # r = 0.2: k = floor(0.1 * 301) = 30.
    assert cal.thresholds(0.2) == _BreakForkThresholds(breaks=high[29], forks=high[29])

    # Ties at 0 (no candidate on most frames): the floors set the thresholds.
    zeros = [0.0] * n
    assert _calibration(zeros, zeros).thresholds(0.05) == _BreakForkThresholds(
        breaks=_BREAK_MIN_EVIDENCE, forks=_FORK_MIN_EVIDENCE
    )
    # One kind above its floor, the other at it.
    mixed = _calibration([0.5] * 10 + [0.0] * (n - 10), [0.2] * n)
    assert mixed.thresholds(0.05) == _BreakForkThresholds(breaks=0.5, forks=_FORK_MIN_EVIDENCE)


def test_break_fork_thresholds_smallest_valid_rate_is_two_over_n_plus_one():
    cal = _calibration([0.0] * 300, [0.0] * 300)
    cal.thresholds(2 / 301)  # k = 1
    with pytest.raises(ValueError, match=r"0\.00664"):
        cal.thresholds(0.006)
    for bad in (0.0, 1.0, -0.1, 1.5, math.nan):
        with pytest.raises(ValueError, match="between 0 and 1"):
            cal.thresholds(bad)


def test_break_fork_calibration_refuses_malformed_evidence():
    with pytest.raises(ValueError):
        _calibration([0.1, math.inf], [0.0, 0.0])
    with pytest.raises(ValueError):
        _calibration([0.1, -0.1], [0.0, 0.0])
    with pytest.raises(ValueError):
        _calibration([0.1], [0.0, 0.0])
    with pytest.raises(ValueError):
        _BreakForkCalibration.from_evidence(["a", "a"], [0, 0], [0, 0], (400, 1600))


def test_break_fork_calibration_round_trips_json_and_digest():
    cal = _calibration(
        [0.0, 0.25, 0.125],
        [0.5, 0.0, 0.0],
        settings={"depth": 0.5, "shape": (400, 1600)},
        run_info={"wall_clock_s": 1.0},
    )
    doc = json.loads(cal.to_json())
    assert doc["format"] == 1
    assert doc["evidence"] == "break-fork-v1"
    assert doc["frames"][1] == {"id": "seed:1", "breaks": 0.25, "forks": 0.0}
    back = _BreakForkCalibration.from_json(cal.to_json())
    assert back == cal
    assert back.run_info == {"wall_clock_s": 1.0}
    assert back.digest() == cal.digest()

    other_run = _calibration(
        [0.0, 0.25, 0.125], [0.5, 0.0, 0.0], settings={"depth": 0.5, "shape": (400, 1600)}
    )
    assert other_run.digest() == cal.digest()
    moved = _calibration(
        [0.0, 0.25, 0.125], [0.5, 0.0, 1e-9], settings={"depth": 0.5, "shape": (400, 1600)}
    )
    assert moved.digest() != cal.digest()

    for key, value in (("format", 2), ("evidence", "break-fork-v0")):
        bad = dict(doc, **{key: value})
        with pytest.raises(ValueError, match=key):
            _BreakForkCalibration.from_json(json.dumps(bad))
    with pytest.raises(ValueError):
        _BreakForkCalibration.from_json('{"format": 1, "evidence": "break-fork-v1"}')
