"""Ticket 13 AC 3: the stage timer wraps the live analysis functions."""

from pathlib import Path

import speed
import stage_timings
from denoisifier import analysis
from denoisifier.frame_io import write_frame_csv


def test_stage_timer_wraps_live_functions(tmp_path: Path):
    for name in stage_timings.STAGES:
        assert callable(getattr(analysis, name)), name
    csv = tmp_path / "f.csv"
    write_frame_csv(speed.speed_frame((64, 256)), csv)
    originals = {name: getattr(analysis, name) for name in stage_timings.STAGES}
    times = stage_timings.run_once(csv, tmp_path / "m.csv")
    assert {name: getattr(analysis, name) for name in stage_timings.STAGES} == originals
    assert times["estimate_local_stripes"] > 0
    assert sum(times.get(name, 0.0) for name in stage_timings.STAGES) <= times["analyse"]
