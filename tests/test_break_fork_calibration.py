"""Ticket 11: the break and Fork thresholds from stored per-frame evidence on break- and
Fork-free striped frames (plan `.scratch/stripe-detector/handoffs/11-plan.md`)."""

from __future__ import annotations

import json
import math
from functools import cache

import pytest

import threshold_calibration as tc
from breaks import ac2_line, break_region_case, compatible_pair_frame
from denoisifier import analyse, analysis
from denoisifier._local_phase import _BREAK_MIN_EVIDENCE, _FORK_MIN_EVIDENCE
from denoisifier.calibration import (
    DEFAULT_BREAK_FORK_FALSE_ALARM_RATE,
    _BreakForkCalibration,
    _BreakForkThresholds,
)
from forks import ac2_case
from protected import FORK_TEST_SEEDS, PHASE_BREAK_TEST_SEEDS, PROBE_SHAPE


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
    with pytest.raises(ValueError, match="finite and at least 0"):
        _calibration([0.1, math.inf], [0.0, 0.0])
    with pytest.raises(ValueError, match="finite and at least 0"):
        _calibration([0.1, -0.1], [0.0, 0.0])
    with pytest.raises(ValueError, match="1 ids for 2"):
        _calibration([0.1], [0.0, 0.0])
    with pytest.raises(ValueError, match="unique"):
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
    with pytest.raises(ValueError, match="malformed"):
        _BreakForkCalibration.from_json('{"format": 1, "evidence": "break-fork-v1"}')


# --- The evidence scalars against the real path (plan section 2, T7 and T8) ----------------


def _evidence_frames():
    """(name, frame) of T7: a 09 break frame, a break-free region frame, a spiked full frame at
    the calibration recipe and a compatible pair (the bridge domain)."""
    seed = PHASE_BREAK_TEST_SEEDS[0]
    line_angle, jump = ac2_line(seed)
    return [
        ("break", break_region_case(seed, jump, line_angle)[0].frame),
        ("break-free region", break_region_case(seed, None, line_angle)[0].frame),
        ("spiked full frame", tc.synthetic(seed, PROBE_SHAPE, 0.5).frame),
        ("compatible pair", compatible_pair_frame(seed).frame),
    ]


def _fork_frame():
    return ac2_case(FORK_TEST_SEEDS[0])[0].frame


@cache
def _evidence(name):
    frames = dict(_evidence_frames(), fork=_fork_frame())
    frame = frames[name]
    return frame, analysis._break_fork_evidence(frame)


EVIDENCE_NAMES = ["break", "break-free region", "spiked full frame", "compatible pair", "fork"]


def _found_breaks(frame, threshold):
    front = _front(frame)
    if front.field is None:
        return 0
    settled = analysis._with_phase_breaks(
        front.reported, front.filters, front.clipped, front.field, break_threshold=threshold
    )
    return sum(len(found) for _, found in settled)


def _found_forks(frame, threshold):
    front = _front(frame)
    if front.responses is None:
        return 0
    settled = [(g, []) for g in front.reported]
    return len(
        analysis._post_break_forks(
            settled, front.refused, front.responses, front.bins, fork_threshold=threshold
        )
    )


def _front(frame):
    return analysis._front_half(
        frame,
        false_alarm_rate=None,
        calibration=None,
        threshold=None,
        clip_level=None,
        bin_factors=None,
    )


@pytest.mark.parametrize("name", EVIDENCE_NAMES)
def test_break_evidence_is_where_the_first_break_is_found(name):
    """T7: the break pass on the frame's reported regions finds no break at S_b and at least
    one just below it (when S_b > 0)."""
    frame, evidence = _evidence(name)
    assert evidence.breaks >= 0
    assert _found_breaks(frame, evidence.breaks) == 0
    if evidence.breaks > 0:
        assert _found_breaks(frame, math.nextafter(evidence.breaks, 0)) >= 1
    if name == "break":
        assert evidence.breaks > _BREAK_MIN_EVIDENCE


@pytest.mark.parametrize("name", EVIDENCE_NAMES)
def test_fork_evidence_is_where_the_first_fork_is_found(name):
    """T7: the post-break Fork search with no break explained away finds no Fork at S_f and at
    least one just below it (when S_f > 0)."""
    frame, evidence = _evidence(name)
    assert evidence.forks >= 0
    assert _found_forks(frame, evidence.forks) == 0
    if evidence.forks > 0:
        assert _found_forks(frame, math.nextafter(evidence.forks, 0)) >= 1
    if name == "fork":
        assert evidence.forks > _FORK_MIN_EVIDENCE


def _hand(breaks, forks):
    """A 300-frame calibration whose thresholds at the default rate (k = 7) are ``breaks`` and
    ``forks`` raised to the floors: 10 frames at those values, the rest at 0."""
    n, high = 300, 10
    return _calibration([breaks] * high + [0.0] * (n - high), [forks] * high + [0.0] * (n - high))


def test_evidence_bounds_the_public_report(monkeypatch):
    """T8: with the stored calibration replaced by ones that put the thresholds just above and
    (where the scalar is above its floor) just below each frame's scalars, the public report
    obeys: a reported break => S_b > T_b; a reported Fork => S_f > T_f or a break; S_b <= T_b
    and S_f <= T_f => no break and no Fork."""
    below_checked = 0
    for name in EVIDENCE_NAMES:
        frame, ev = _evidence(name)
        choices_b = [math.nextafter(ev.breaks, math.inf)]
        choices_f = [math.nextafter(ev.forks, math.inf)]
        if ev.breaks > _BREAK_MIN_EVIDENCE:
            choices_b.append(math.nextafter(ev.breaks, 0))
        if ev.forks > _FORK_MIN_EVIDENCE:
            choices_f.append(math.nextafter(ev.forks, 0))
        for t_b in choices_b:
            for t_f in choices_f:
                cal = _hand(t_b, t_f)
                limits = cal.thresholds(DEFAULT_BREAK_FORK_FALSE_ALARM_RATE)
                # N10: a "just below" threshold sits above its floor, so it is the one used.
                if t_b < ev.breaks:
                    assert limits.breaks == t_b
                    below_checked += 1
                if t_f < ev.forks:
                    assert limits.forks == t_f
                    below_checked += 1
                monkeypatch.setattr(analysis, "_stored_break_fork_calibration", lambda c=cal: c)
                report = analyse(
                    frame, break_fork_false_alarm_rate=DEFAULT_BREAK_FORK_FALSE_ALARM_RATE
                )
                if report.phase_breaks:
                    assert ev.breaks > limits.breaks, name
                if report.forks:
                    assert ev.forks > limits.forks or ev.breaks > limits.breaks, name
                if ev.breaks <= limits.breaks and ev.forks <= limits.forks:
                    assert report.phase_breaks == (), name
                    assert report.forks == (), name
    assert below_checked >= 2


def test_analyse_and_evidence_share_the_front_half(monkeypatch):
    """B5 (supporting): one call of the shared front half from each."""
    calls = []
    real = analysis._front_half

    def spy(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(analysis, "_front_half", spy)
    frame = _evidence_frames()[0][1]
    analyse(frame)
    assert len(calls) == 1
    analysis._break_fork_evidence(frame)
    assert len(calls) == 2
