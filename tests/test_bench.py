"""make bench (ticket agent-gates/05): the speed gate outside check and check-slow,
and the heavy gates' warning on a busy machine."""

import json

import bench
import feasibility
import slow_stamp
import speed
from protected import BENCH_REPEATS, TARGET_TIMING_S, TIMING_LIMIT_S


def _times(monkeypatch, seconds: list[float]) -> list[int]:
    calls: list[int] = []

    def fake(repeats: int = 3) -> list[float]:
        calls.append(repeats)
        return seconds

    monkeypatch.setattr(feasibility, "time_full_frame", fake)
    _speed(monkeypatch, [3.0, 3.1, 2.9], [3.5, 3.6, 3.4])
    return calls


def _speed(monkeypatch, warm: list[float], cold: list[float]) -> list[tuple[str, int]]:
    """Stub ticket 13's two speed timers (tests/speed.py)."""
    calls: list[tuple[str, int]] = []

    def fake_warm(repeats: int) -> tuple[list[float], str]:
        calls.append(("warm", repeats))
        return warm, "{}"

    def fake_cold(repeats: int) -> list[float]:
        calls.append(("cold", repeats))
        return cold

    monkeypatch.setattr(speed, "time_speed_pipeline", fake_warm)
    monkeypatch.setattr(speed, "time_cold_cli", fake_cold)
    return calls


def test_bench_records_the_run_and_passes_under_the_limit(monkeypatch, tmp_path, capsys):
    calls = _times(monkeypatch, [7.2, 6.9, 7.0, 7.4, 7.1])
    out = tmp_path / "bench.json"
    assert bench.main(["--out", str(out)]) == 0
    assert calls == [BENCH_REPEATS]
    record = json.loads(out.read_text())
    assert record["seconds"] == [7.2, 6.9, 7.0, 7.4, 7.1]
    assert record["median_s"] == 7.1
    assert record["limit_s"] == TIMING_LIMIT_S
    assert record["target_s"] == TARGET_TIMING_S
    assert record["meets_limit"] is True
    assert record["meets_target"] is False
    assert {
        "commit",
        "cpu",
        "logical_cpus",
        "python",
        "numpy",
        "scipy",
        "threads",
        "loadavg",
        "shape",
    } <= set(record)
    assert set(record["loadavg"]) == {"start", "end"}
    assert record["threads"]["OMP_NUM_THREADS"] == "1"
    assert "target" in capsys.readouterr().out


def test_bench_fails_over_the_limit(monkeypatch, tmp_path, capsys):
    _times(monkeypatch, [10.4, 10.5, 10.6])
    out = tmp_path / "bench.json"
    assert bench.main(["--out", str(out)]) == 1
    assert json.loads(out.read_text())["meets_limit"] is False
    assert "make bench: median 10.50 s exceeds the 10.0 s limit" in capsys.readouterr().out


def test_bench_writes_local_state_by_default(monkeypatch, tmp_path):
    _times(monkeypatch, [4.0, 4.0, 4.0])
    monkeypatch.setattr(bench, "ROOT", tmp_path)
    assert bench.main([]) == 0
    assert json.loads((tmp_path / ".gate/bench.json").read_text())["meets_target"] is True


def test_measure_warns_at_start_on_a_busy_machine(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(feasibility, "loadavg", lambda: "3.50 2.00 1.00 2/900 4242")
    monkeypatch.setattr(feasibility, "measure_all", lambda *_args, **_kwargs: {"ok": 1})
    assert feasibility.main(["--out", str(tmp_path / "m.json")]) == 0
    assert "make measure: warning: load average 3.50" in capsys.readouterr().out


def test_bench_warns_at_start_on_a_busy_machine(monkeypatch, tmp_path, capsys):
    _times(monkeypatch, [4.0, 4.0, 4.0])
    monkeypatch.setattr(slow_stamp, "loadavg", lambda: "3.50 2.00 1.00 2/900 4242")
    assert bench.main(["--out", str(tmp_path / "bench.json")]) == 0
    assert "make bench: warning: load average 3.50" in capsys.readouterr().out


def test_bench_records_the_speed_frame_and_passes_under_the_target(monkeypatch, tmp_path):
    _times(monkeypatch, [4.0, 4.0, 4.0])
    calls = _speed(monkeypatch, [3.0, 3.2, 2.8], [3.6, 3.4, 3.5])
    out = tmp_path / "bench.json"
    assert bench.main(["--out", str(out)]) == 0
    assert sorted(calls) == [("cold", BENCH_REPEATS), ("warm", BENCH_REPEATS)]
    record = json.loads(out.read_text())
    assert record["speed_seconds"] == [3.0, 3.2, 2.8]
    assert record["speed_median_s"] == 3.0
    assert record["cold_cli_seconds"] == [3.6, 3.4, 3.5]
    assert record["cold_cli_s"] == 3.5
    assert record["speed_meets_target"] is True
    assert record["cold_cli_meets_target"] is True


def test_bench_fails_when_the_speed_pipeline_misses_the_target(monkeypatch, tmp_path, capsys):
    _times(monkeypatch, [4.0, 4.0, 4.0])
    _speed(monkeypatch, [5.2, 5.1, 5.3], [3.0, 3.0, 3.0])
    out = tmp_path / "bench.json"
    assert bench.main(["--out", str(out)]) == 1
    assert json.loads(out.read_text())["speed_meets_target"] is False
    assert "speed pipeline median 5.20 s exceeds the 5.0 s target" in capsys.readouterr().out


def test_bench_fails_when_the_cold_cli_misses_the_target(monkeypatch, tmp_path, capsys):
    _times(monkeypatch, [4.0, 4.0, 4.0])
    _speed(monkeypatch, [4.0, 4.1, 3.9], [5.4, 5.5, 5.6])
    out = tmp_path / "bench.json"
    assert bench.main(["--out", str(out)]) == 1
    record = json.loads(out.read_text())
    assert record["speed_meets_target"] is True
    assert record["cold_cli_meets_target"] is False
    assert "cold CLI median 5.50 s exceeds the 5.0 s target" in capsys.readouterr().out
