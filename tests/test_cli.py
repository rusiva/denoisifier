import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from borderline import BORDERLINE, borderline_frame
from cases import case_frame, clipped_at
from denoisifier import analyse, read_frame
from denoisifier.frame_io import write_frame_csv
from denoisifier.synthetic import Emccd, StripedRegion, generate
from protected import (
    CLI_CLIP_TEST_SEED,
    CLI_MASK_TEST_SEED,
    CLI_MISSING_OUTPUT_DIR_TEST_SEED,
    CLI_SPIKE_COUNT,
    CLI_STDOUT_TEST_SEED,
    CLI_STRIPED_CSV_TEST_SEED,
    DEPTH_TOL,
    MILD_CLIP_LEVEL_FRACTION,
    OVERRIDE_LEVEL_FRACTION,
)
from regions import truth_bbox
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
    assert report["regions"]
    for region in report["regions"]:
        assert_matches_truth(region["period_px"], region["angle_deg"], s.truth)
        assert abs(region["modulation_depth"] - 0.6) <= DEPTH_TOL


def test_cli_reports_borderline_frame(tmp_path):
    frame_path = tmp_path / "frame.csv"
    out = tmp_path / "report.json"
    write_frame_csv(borderline_frame(*BORDERLINE[0]), frame_path)
    result = _run(frame_path, "-o", out)
    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text())
    assert report["striped"] is True
    for key in ("period_px", "angle_deg", "modulation_depth"):
        assert np.isfinite(report["regions"][0][key])


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


def _run_crop_and_plain(tmp_path, plain_frame, *flags):
    """Reports for the real Solis crop read with ``flags``, and for ``plain_frame`` as plain CSV."""
    plain_path = tmp_path / "plain.csv"
    write_frame_csv(plain_frame, plain_path)
    plain_out = tmp_path / "plain.json"
    solis_out = tmp_path / "solis.json"
    plain = _run(plain_path, "-o", plain_out)
    solis = _run(SOLIS / "xpos_ypos_crop.asc", *flags, "-o", solis_out)
    assert plain.returncode == 0, plain.stderr
    assert solis.returncode == 0, solis.stderr
    return json.loads(plain_out.read_text()), json.loads(solis_out.read_text())


def test_cli_reads_real_solis_export_and_reports_reader_notes(tmp_path):
    frame = read_frame(SOLIS / "xpos_ypos_crop.asc", drop_axis_column=True).frame
    plain_report, solis_report = _run_crop_and_plain(tmp_path, frame, "--drop-axis-column")
    plain_report.pop("reader_notes")
    solis_notes = solis_report.pop("reader_notes")
    assert len(solis_notes) == 3
    assert "after" in solis_notes[0]
    assert "trailing comma" in solis_notes[1]
    assert "dropped" in solis_notes[2]
    assert plain_report == solis_report


def test_cli_transposes_real_solis_export_on_request(tmp_path):
    frame = read_frame(SOLIS / "xpos_ypos_crop.asc", drop_axis_column=True).frame
    plain_report, solis_report = _run_crop_and_plain(
        tmp_path, frame.T, "--drop-axis-column", "--transpose"
    )
    plain_report.pop("reader_notes")
    assert "transposed" in solis_report.pop("reader_notes")[-1]
    assert plain_report.pop("transposed") is False
    assert solis_report.pop("transposed") is True
    # The crop's bboxes are in the file's layout: the plain frame's, transposed.
    for region in plain_report["regions"]:
        b = region["bbox"]
        region["bbox"] = {
            "row_start": b["col_start"],
            "row_stop": b["col_stop"],
            "col_start": b["row_start"],
            "col_stop": b["row_stop"],
        }
    assert plain_report == solis_report


def _mask_test_frame():
    """96x160, low noise, one Period-5 region off the centre (rows and columns)."""
    region = StripedRegion(
        center=(40.0, 62.0),
        semi_axes=(30.0, 40.0),
        rotation_deg=0.0,
        edge_px=6.0,
        period=5.0,
        angle_deg=0.0,
        modulation_depth=0.6,
    )
    return generate(seed=CLI_MASK_TEST_SEED, shape=(96, 160), regions=[region]).frame


def _assert_bboxes_are_tight(report, mask):
    for region in report["regions"]:
        b = region["bbox"]
        bbox = (b["row_start"], b["row_stop"], b["col_start"], b["col_stop"])
        assert truth_bbox(mask == region["label"]) == bbox


def test_cli_writes_mask_csv_laid_out_like_the_frame(tmp_path):
    frame = _mask_test_frame()
    frame_path, out, mask_path = tmp_path / "frame.csv", tmp_path / "r.json", tmp_path / "m.csv"
    write_frame_csv(frame, frame_path)
    result = _run(frame_path, "-o", out, "--mask", mask_path)
    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text())
    mask = read_frame(mask_path).frame
    assert mask.shape == frame.shape
    assert np.array_equal(mask, np.round(mask))
    assert set(np.unique(mask)) <= set(range(len(report["regions"]) + 1))
    assert report["regions"]
    assert np.array_equal(mask, analyse(frame).labels)
    _assert_bboxes_are_tight(report, mask)
    assert report["transposed"] is False


def test_cli_writes_all_zero_mask_for_stripe_free_frame(tmp_path):
    frame = generate(seed=CLI_MASK_TEST_SEED, shape=(96, 160), modulation_depth=0.0).frame
    frame_path, out, mask_path = tmp_path / "frame.csv", tmp_path / "r.json", tmp_path / "m.csv"
    write_frame_csv(frame, frame_path)
    result = _run(frame_path, "-o", out, "--mask", mask_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(out.read_text())["regions"] == []
    mask = read_frame(mask_path).frame
    assert mask.shape == frame.shape
    assert not mask.any()


def test_cli_mask_and_bboxes_follow_the_file_layout_when_transposing(tmp_path):
    frame = _mask_test_frame()
    frame_path, out, mask_path = tmp_path / "frame.csv", tmp_path / "r.json", tmp_path / "m.csv"
    write_frame_csv(frame.T, frame_path)  # 160x96 file, one sensor column per file row
    result = _run(frame_path, "--transpose", "-o", out, "--mask", mask_path)
    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text())
    # The CLI analyses the frame as written to the CSV (%.9g), read back transposed.
    expected = analyse(read_frame(frame_path, transpose=True).frame)
    mask = read_frame(mask_path).frame
    assert mask.shape == (160, 96)
    assert report["regions"]
    assert np.array_equal(mask, expected.labels.T)
    _assert_bboxes_are_tight(report, mask)
    assert [(r["period_px"], r["angle_deg"]) for r in report["regions"]] == [
        (r.period_px, r.angle_deg) for r in expected.regions
    ]
    assert report["transposed"] is True


def test_cli_mask_follows_the_solis_crop_layout(tmp_path):
    mask_path = tmp_path / "m.csv"
    solis = SOLIS / "xpos_ypos_crop.asc"
    result = _run(solis, "--drop-axis-column", "--transpose", "--mask", mask_path)
    assert result.returncode == 0, result.stderr
    grid = read_frame(solis, drop_axis_column=True).frame
    assert read_frame(mask_path).frame.shape == grid.shape


def test_cli_fails_cleanly_when_mask_dir_missing(tmp_path):
    frame_path = tmp_path / "frame.csv"
    write_frame_csv(_smooth_frame(), frame_path)
    mask_path = tmp_path / "nope" / "m.csv"
    _assert_clean_failure(_run(frame_path, "--mask", mask_path), str(mask_path))


@pytest.mark.parametrize(
    ("clash", "output_exists"),
    [
        ("frame", False),
        ("frame", True),
        ("frame_link", False),
        ("output", False),
        ("output", True),
        ("output_link", True),  # a link needs an existing -o file
    ],
)
def test_cli_refuses_a_mask_path_that_aliases_the_input_or_output(tmp_path, clash, output_exists):
    frame_path, out = tmp_path / "frame.csv", tmp_path / "r.json"
    write_frame_csv(_smooth_frame(), frame_path)
    if output_exists:
        out.write_text("previous report\n")
    frame_bytes = frame_path.read_bytes()
    target = {"frame": frame_path, "frame_link": frame_path}.get(clash, out)
    mask_path = target
    if clash.endswith("_link"):
        mask_path = tmp_path / "link.csv"
        os.symlink(target, mask_path)
    result = _run(frame_path, "-o", out, "--mask", mask_path)
    _assert_clean_failure(result, "--mask", "same file")
    assert frame_path.read_bytes() == frame_bytes
    if output_exists:
        assert out.read_text() == "previous report\n"
    else:
        assert not out.exists()


# --- Spikes and Clipped Pixels (ticket 06) -----------------------------------


def _spiked_clipped_csv(tmp_path):
    """96x160 typical frame (scorched Mottle, EMCCD at 100 photons, m 0.5) with
    spikes, clipped at MILD_CLIP_LEVEL_FRACTION x the clean maximum, as CSV:
    (path, clip level). The plateau is small, so auto-detection finds Clipped
    Pixels and the Spikes on dim columns stay Spikes."""
    s, level = clipped_at(
        MILD_CLIP_LEVEL_FRACTION,
        case_frame,
        seed=CLI_CLIP_TEST_SEED,
        shape=(96, 160),
        modulation_depth=0.5,
        mottle="scorched",
        noise=Emccd(),
        spikes=CLI_SPIKE_COUNT,
    )
    path = tmp_path / "frame.csv"
    write_frame_csv(s.frame, path)
    return path, level


def _cli_report(path, *flags):
    result = _run(path, *flags)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    report.pop("reader_notes", None)
    return report


def test_cli_reports_spike_and_clipped_pixels(tmp_path):
    path, _ = _spiked_clipped_csv(tmp_path)
    report = _cli_report(path)
    expected = analyse(read_frame(path).frame)
    assert expected.spike_pixels > 0
    assert expected.clipped_pixels > 0
    assert report["spike_pixels"] == expected.spike_pixels
    assert report["clipped_pixels"] == expected.clipped_pixels


@pytest.mark.parametrize("level", ["override", "inf"])
def test_cli_clip_level_flag_overrides_detection(tmp_path, level):
    """Each level changes the report from auto-detection's (an override below the
    plateau clips more pixels, inf none), so the flag must reach analyse."""
    path, clip = _spiked_clipped_csv(tmp_path)
    clip_level = OVERRIDE_LEVEL_FRACTION * clip if level == "override" else np.inf
    report = _cli_report(path, "--clip-level", str(float(clip_level)))
    frame = read_frame(path).frame
    expected = analyse(frame, clip_level=clip_level).to_dict()
    expected.pop("reader_notes", None)
    assert report == expected
    assert expected["clipped_pixels"] != analyse(frame).clipped_pixels
    assert (report["clipped_pixels"] > 0) == (level == "override")


def test_cli_fails_cleanly_on_nan_clip_level(tmp_path):
    path, _ = _spiked_clipped_csv(tmp_path)
    _assert_clean_failure(_run(path, "--clip-level", "nan"), "clip_level", "nan")
