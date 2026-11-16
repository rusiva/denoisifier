"""Ticket 13's speed frame and timers (AC 1; plan section 4).

The speed frame is the worst frame of the plan's profile (section 1): 400x1600
(``PROBE_SHAPE``), Period 3 and Angle 3 (``SPEED_CASE``), m 0.5, scorched Mottle,
``Emccd()``, ``SPEED_SPIKES`` spikes, the two Phase Breaks ``SPEED_BREAK_LINES`` and
the Fork ``SPEED_FORK_POINT``. Found on it: 2 breaks, 1 Fork, 1 region.

- ``time_speed_pipeline``: seconds of ``read_frame(csv) -> analyse -> Report.to_json``,
  the CSV written beforehand and not timed, after one untimed warm-up at
  ``GATE_SHAPE``; ``threads`` sets the bank's thread count (``analysis._analyse``;
  None: the shipped default);
- ``time_cold_cli``: wall seconds of a fresh ``python -m denoisifier f.csv -o r.json``.

``make bench`` gates both medians at ``TARGET_TIMING_S``; the slow tier asserts
only ``SLOW_TIMING_LIMIT_S`` on the pipeline (``test_speed.py``).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from denoisifier.analysis import _analyse
from denoisifier.frame_io import read_frame, write_frame_csv
from denoisifier.synthetic import Emccd, ForkPoint, PhaseBreakLine, generate
from protected import (
    GATE_SHAPE,
    PROBE_SHAPE,
    SPEED_BREAK_LINES,
    SPEED_CASE,
    SPEED_FORK_POINT,
    SPEED_SPIKES,
    SPEED_TEST_SEED,
)

_DEPTH = 0.5  # the profile's worst frame (plan section 1)
_FORK_DIRECTION = 1  # the profile's Fork (prototypes/p13/identity.py, ac1_worst)


def speed_frame(shape: tuple[int, int] = PROBE_SHAPE) -> np.ndarray:
    """The speed frame. At another ``shape`` the break points and the Fork are
    scaled with the frame (row by rows, column by columns), so the same
    features fall in the same places."""
    sy, sx = shape[0] / PROBE_SHAPE[0], shape[1] / PROBE_SHAPE[1]
    period, angle = SPEED_CASE
    breaks = [
        PhaseBreakLine((r * sy, c * sx), angle + tilt, jump)
        for (r, c), tilt, jump in SPEED_BREAK_LINES
    ]
    fr, fc = SPEED_FORK_POINT
    return generate(
        seed=SPEED_TEST_SEED,
        shape=shape,
        period=period,
        angle_deg=angle,
        modulation_depth=_DEPTH,
        mottle="scorched",
        noise=Emccd(),
        spikes=SPEED_SPIKES,
        phase_breaks=breaks,
        forks=[ForkPoint((fr * sy, fc * sx), _FORK_DIRECTION)],
    ).frame


def _pipeline(csv: Path, threads: int | None) -> str:
    return _analyse(read_frame(csv).frame, threads=threads).to_json()


def time_speed_pipeline(repeats: int, threads: int | None = None) -> tuple[list[float], str]:
    """Seconds of ``read_frame -> analyse -> to_json`` on the speed frame, ``repeats``
    times, in this process, and the last run's JSON report. Writing the CSVs and one
    warm-up at ``GATE_SHAPE`` are not timed."""
    with tempfile.TemporaryDirectory() as d:
        warm, csv = Path(d) / "warm.csv", Path(d) / "speed.csv"
        write_frame_csv(speed_frame(GATE_SHAPE), warm)
        write_frame_csv(speed_frame(), csv)
        _pipeline(warm, threads)
        times, report = [], ""
        for _ in range(repeats):
            t0 = time.perf_counter()
            report = _pipeline(csv, threads)
            times.append(time.perf_counter() - t0)
        return times, report


def time_cold_cli(repeats: int) -> list[float]:
    """Wall seconds of a fresh ``python -m denoisifier speed.csv -o r.json``
    subprocess on the speed frame, ``repeats`` times (the CSV written first, not
    timed). Each run must exit 0."""
    with tempfile.TemporaryDirectory() as d:
        csv, out = Path(d) / "speed.csv", Path(d) / "r.json"
        write_frame_csv(speed_frame(), csv)
        times = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            subprocess.run(
                [sys.executable, "-m", "denoisifier", str(csv), "-o", str(out)], check=True
            )
            times.append(time.perf_counter() - t0)
        return times
