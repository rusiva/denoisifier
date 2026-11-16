"""Ticket 13 AC 1 (plan section 4): the speed frame exercises every stage, and its
pipeline stays within the slow tier's limit. The 5 s target is gated in make bench."""

import json
from statistics import median

import pytest

import speed
from denoisifier import analyse
from protected import PROBE_SHAPE, SLOW_TIMING_LIMIT_S, SPEED_SLOW_REPEATS

# A quarter of the full frame per side: the breaks and the Fork scale with it.
_SMALL = (PROBE_SHAPE[0] // 4, PROBE_SHAPE[1] // 4)


def test_speed_frame_exercises_every_stage():
    report = analyse(speed.speed_frame(_SMALL))
    assert len(report.regions) >= 1
    assert len(report.phase_breaks) == 2
    assert len(report.forks) == 1


@pytest.mark.slow
def test_speed_pipeline_meets_the_slow_limit():
    seconds, text = speed.time_speed_pipeline(SPEED_SLOW_REPEATS)
    report = json.loads(text)
    assert median(seconds) <= SLOW_TIMING_LIMIT_S, f"speed pipeline times {seconds} s"
    assert len(report["phase_breaks"]) >= 1
    assert len(report["forks"]) >= 1
