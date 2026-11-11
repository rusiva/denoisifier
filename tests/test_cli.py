import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from borderline import BORDERLINE, borderline_frame
from denoisifier.frame_io import write_frame_csv
from denoisifier.synthetic import generate
from protected import (
    CLI_MISSING_OUTPUT_DIR_TEST_SEED,
    CLI_STDOUT_TEST_SEED,
    CLI_STRIPED_CSV_TEST_SEED,
    DEPTH_TOL,
)
from truth_match import assert_matches_truth

SOLIS = Path(__file__).parent / "data" / "solis"


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
    s = generate(seed=CLI_STRIPED_CSV_TEST_SEED, period=8, angle_deg=6, modulation_depth=0.6)
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
    s = generate(seed=CLI_STDOUT_TEST_SEED, modulation_depth=0.0)
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
    write_frame_csv(generate(seed=CLI_MISSING_OUTPUT_DIR_TEST_SEED).frame, frame_path)
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


def _smooth_frame():
    """A deterministic 64x64 spot; its first column rises then falls, so it reads with no notes."""
    y, x = np.mgrid[0:64, 0:64]
    return 1 + 100 * np.exp(-((x - 32) ** 2 + (y - 32) ** 2) / (2 * 15**2))


def _write_solis_shaped(frame, tmp_path):
    """``frame`` with an axis column, a header line and a footer line, like a Solis export."""
    grid_path = tmp_path / "grid.csv"
    write_frame_csv(np.column_stack([np.arange(frame.shape[0]), frame]), grid_path)
    path = tmp_path / "solis.csv"
    path.write_text("Andor Solis export\n" + grid_path.read_text() + "Gain:,300\n")
    return path


def test_cli_drops_axis_column_on_request_and_reports_reader_notes(tmp_path):
    frame = _smooth_frame()
    plain_path = tmp_path / "plain.csv"
    write_frame_csv(frame, plain_path)
    solis_path = _write_solis_shaped(frame, tmp_path)
    plain_out = tmp_path / "plain.json"
    solis_out = tmp_path / "solis.json"

    plain = _run(plain_path, "-o", plain_out)
    solis = _run(solis_path, "--drop-axis-column", "-o", solis_out)

    assert plain.returncode == 0, plain.stderr
    assert solis.returncode == 0, solis.stderr
    plain_report = json.loads(plain_out.read_text())
    solis_report = json.loads(solis_out.read_text())
    assert plain_report.pop("reader_notes") == []
    solis_notes = solis_report.pop("reader_notes")
    assert len(solis_notes) == 3
    assert "before" in solis_notes[0]
    assert "after" in solis_notes[1]
    assert "dropped" in solis_notes[2]
    assert plain_report == solis_report


def test_cli_keeps_axis_column_by_default_and_warns_in_the_report(tmp_path):
    solis_path = _write_solis_shaped(_smooth_frame(), tmp_path)
    out = tmp_path / "report.json"
    result = _run(solis_path, "-o", out)
    assert result.returncode == 0, result.stderr
    warnings = [n for n in json.loads(out.read_text())["reader_notes"] if n.startswith("warning: ")]
    assert len(warnings) == 1
    assert "--drop-axis-column" in warnings[0]


def test_cli_fails_cleanly_on_uneven_rows(tmp_path):
    frame_path = tmp_path / "frame.csv"
    frame_path.write_text("1,2,3\n4,5\n")
    _assert_clean_failure(_run(frame_path), "line 2")


def test_cli_fails_cleanly_on_non_finite_values(tmp_path):
    frame = _smooth_frame()
    frame[10, 10] = np.nan
    frame_path = tmp_path / "frame.csv"
    write_frame_csv(frame, frame_path)
    _assert_clean_failure(_run(frame_path), "non-finite")


def test_cli_fails_cleanly_on_kinetic_series():
    _assert_clean_failure(_run(SOLIS / "kinetic.asc"), "kinetic series are not supported")
