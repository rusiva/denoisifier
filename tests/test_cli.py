import json
import shutil
import subprocess
import sys

import numpy as np

from denoisifier.frame_io import write_frame_csv
from denoisifier.synthetic import generate
from test_analyse import BORDERLINE, borderline_frame
from truth_match import DEPTH_TOL, assert_matches_truth


def _run(*args, cmd=(sys.executable, "-m", "denoisifier")):
    return subprocess.run([*cmd, *map(str, args)], capture_output=True, text=True)


def _assert_clean_failure(result, *details):
    """Exit 1 with one ``denoisifier: error:`` line naming the cause."""
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    lines = result.stderr.splitlines()
    assert len(lines) == 1, result.stderr
    assert lines[0].startswith("denoisifier: error: "), result.stderr
    for detail in details:
        assert detail in lines[0], result.stderr


def test_cli_writes_json_report_for_striped_csv(tmp_path):
    s = generate(seed=1, period=8, angle_deg=6, modulation_depth=0.6)
    frame_path = tmp_path / "frame.csv"
    out = tmp_path / "report.json"
    write_frame_csv(s.frame, frame_path)
    result = _run(frame_path, "-o", out)
    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text())
    assert report["striped"] is True
    assert_matches_truth(report["period_px"], report["angle_deg"], s.truth)
    assert abs(report["modulation_depth"] - 0.6) <= DEPTH_TOL


def test_cli_reports_borderline_frame(tmp_path):
    frame_path = tmp_path / "frame.csv"
    out = tmp_path / "report.json"
    write_frame_csv(borderline_frame(*BORDERLINE[0]), frame_path)
    result = _run(frame_path, "-o", out)
    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text())
    assert report["striped"] is True
    for key in ("period_px", "angle_deg", "modulation_depth"):
        assert np.isfinite(report[key])


def test_cli_prints_json_to_stdout_without_output_flag(tmp_path):
    s = generate(seed=2, modulation_depth=0.0)
    frame_path = tmp_path / "frame.csv"
    write_frame_csv(s.frame, frame_path)
    result = _run(frame_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["striped"] is False


def test_cli_fails_cleanly_on_missing_file(tmp_path):
    missing = tmp_path / "missing.csv"
    _assert_clean_failure(_run(missing), str(missing))


def test_cli_fails_cleanly_on_frame_with_no_positive_light(tmp_path):
    frame_path = tmp_path / "frame.csv"
    out = tmp_path / "report.json"
    write_frame_csv(np.zeros((64, 64)), frame_path)
    _assert_clean_failure(_run(frame_path, "-o", out), "no positive light")
    assert not out.exists()


def test_cli_fails_cleanly_when_output_dir_missing(tmp_path):
    frame_path = tmp_path / "frame.csv"
    write_frame_csv(generate(seed=3).frame, frame_path)
    out = tmp_path / "nope" / "r.json"
    _assert_clean_failure(_run(frame_path, "-o", out), str(out))


def test_cli_without_arguments_is_a_usage_error():
    result = _run()
    assert result.returncode == 2
    assert "usage: denoisifier" in result.stderr
    assert "Traceback" not in result.stderr


def test_console_script_is_installed():
    exe = shutil.which("denoisifier")
    assert exe is not None
    assert _run("--help", cmd=(exe,)).returncode == 0
