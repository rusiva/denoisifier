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


def test_stage_timer_runs_at_a_given_thread_count(tmp_path: Path):
    csv = tmp_path / "f.csv"
    write_frame_csv(speed.speed_frame((64, 256)), csv)
    times = stage_timings.run_once(csv, tmp_path / "m.csv", threads=1)
    assert times["estimate_local_stripes"] > 0


def test_table_quotes_base_beside_both_thread_counts():
    keys = (*stage_timings.OUTER, stage_timings.WARM, *stage_timings.STAGES)
    results = {
        "speed (AC 1), threads 1": dict.fromkeys(keys, 1.0),
        "speed (AC 1), threads 4 (default)": dict.fromkeys(keys, 0.5),
    }
    text = stage_timings.markdown(
        results, {"importtime_s": 0.3, "wall_s": 0.5}, cold=2.0, default_threads=4
    )
    header = next(line for line in text.splitlines() if line.startswith("| stage"))
    assert "BASE" in header
    assert "threads 1" in header
    assert "threads 4 (default)" in header
    # P1's BASE bank time on the worst frame (plan section 1), quoted in its column.
    bank_row = next(line for line in text.splitlines() if "`estimate_local_stripes`" in line)
    assert "5.63" in bank_row
    assert "warm pipeline" in text
    for slice_name, _ in stage_timings.SLICES:
        assert slice_name in text
    assert "adopted" in text
    assert "dropped" in text
