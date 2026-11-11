"""make bench (ticket agent-gates/05): the speed gate outside check and check-slow."""

import json

import bench
import feasibility
from protected import BENCH_REPEATS, TARGET_TIMING_S, TIMING_LIMIT_S


def _times(monkeypatch, seconds: list[float]) -> list[int]:
    calls: list[int] = []

    def fake(repeats: int = 3) -> list[float]:
        calls.append(repeats)
        return seconds

    monkeypatch.setattr(feasibility, "time_full_frame", fake)
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
