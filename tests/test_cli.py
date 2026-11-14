import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from binning import bin_sensor_frame
from borderline import BORDERLINE, borderline_frame
from breaks import ac2_line, break_region_case
from cases import case_frame, clipped_at
from denoisifier import BinFactors, analyse, read_frame
from denoisifier.calibration import DEFAULT_FALSE_ALARM_RATE, Calibration, stored_calibration
from denoisifier.frame_io import write_frame_csv
from denoisifier.synthetic import Emccd, StripedRegion, generate
from protected import (
    BINNING_TEST_SEEDS,
    BREAK_JUMP_TOL_RAD,
    CLI_CLIP_TEST_SEED,
    CLI_MASK_TEST_SEED,
    CLI_MISSING_OUTPUT_DIR_TEST_SEED,
    CLI_SPIKE_COUNT,
    CLI_STDOUT_TEST_SEED,
    CLI_STRIPED_CSV_TEST_SEED,
    DEPTH_TOL,
    MILD_CLIP_LEVEL_FRACTION,
    OTHER_FALSE_ALARM_RATE,
    OVERRIDE_LEVEL_FRACTION,
    PHASE_BREAK_TEST_SEEDS,
)
from regions import truth_bbox, truth_pixels
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


# --- Threshold options (ticket 07, plan 2.4) ------------------------------------------


def _threshold_report(tmp_path, *flags):
    s = generate(seed=CLI_STDOUT_TEST_SEED, modulation_depth=0.0)
    frame_path = tmp_path / "frame.csv"
    write_frame_csv(s.frame, frame_path)
    result = _run(frame_path, *flags)
    return result, (json.loads(result.stdout) if result.returncode == 0 else None)


def test_cli_reports_the_default_score_and_threshold(tmp_path):
    result, report = _threshold_report(tmp_path)
    assert result.returncode == 0, result.stderr
    assert report["threshold"] == stored_calibration().threshold(DEFAULT_FALSE_ALARM_RATE)
    assert report["striped"] == (report["score"] > report["threshold"])


def test_cli_false_alarm_rate_sets_the_threshold(tmp_path):
    _, default = _threshold_report(tmp_path)
    result, report = _threshold_report(tmp_path, "--false-alarm-rate", OTHER_FALSE_ALARM_RATE)
    assert result.returncode == 0, result.stderr
    assert report["threshold"] == stored_calibration().threshold(OTHER_FALSE_ALARM_RATE)
    assert report["score"] == default["score"]
    assert report["striped"] == (report["score"] > report["threshold"])


def test_cli_zero_false_alarm_rate_is_an_error(tmp_path):
    result, _ = _threshold_report(tmp_path, "--false-alarm-rate", 0)
    _assert_clean_failure(result, "false-alarm rate")


def test_cli_calibration_file_sets_the_threshold(tmp_path):
    cal = Calibration.from_scores([f"f{i}" for i in range(199)], np.arange(1.0, 200.0), (64, 64))
    cal_path = tmp_path / "calibration.json"
    cal_path.write_text(cal.to_json())
    result, report = _threshold_report(tmp_path, "--calibration", cal_path)
    assert result.returncode == 0, result.stderr
    assert report["threshold"] == cal.threshold(DEFAULT_FALSE_ALARM_RATE) == 198.0
    result, report = _threshold_report(
        tmp_path, "--calibration", cal_path, "--false-alarm-rate", OTHER_FALSE_ALARM_RATE
    )
    assert result.returncode == 0, result.stderr
    assert report["threshold"] == cal.threshold(OTHER_FALSE_ALARM_RATE) == 190.0
    assert "score" in report


def test_cli_missing_calibration_file_is_an_error(tmp_path):
    result, _ = _threshold_report(tmp_path, "--calibration", tmp_path / "missing.json")
    _assert_clean_failure(result, "missing.json")


# Ticket 08: --bin HxV (plan 2.2).


def _binned_csv(tmp_path, h, v, transpose=False, **kwargs):
    """A 2x1-style binned 128x128 frame of a sensor (128 v) x (128 h), as a CSV
    (transposed in the file on request); returns (path, Synthetic)."""
    s = generate(seed=BINNING_TEST_SEEDS[0], shape=(128 * v, 128 * h), **kwargs)
    frame = bin_sensor_frame(s.frame, h, v)
    path = tmp_path / "binned.csv"
    write_frame_csv(frame.T if transpose else frame, path)
    return path, s


def test_cli_bin_flag_reports_bin_factors_and_warning(tmp_path):
    path, s = _binned_csv(tmp_path, 2, 1, period=12, modulation_depth=0.5)
    result = _run(path, "--bin", "2x1")
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    report = json.loads(result.stdout)
    assert report["bin_factors"] == {"horizontal": 2, "vertical": 1}
    assert report["unresolved_period_px"] == [3.0, 4.0]
    assert any("below 4 px" in w for w in report["warnings"])
    (region,) = report["regions"]
    assert_matches_truth(region["period_px"], region["angle_deg"], s.truth)


def test_cli_bin_with_transpose_keeps_bin_factors_in_sensor_axes(tmp_path):
    path, s = _binned_csv(tmp_path, 2, 1, transpose=True, period=12, modulation_depth=0.5)
    result = _run(path, "--transpose", "--bin", "2x1")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["transposed"] is True
    assert report["bin_factors"] == {"horizontal": 2, "vertical": 1}
    expected = analyse(
        read_frame(path, transpose=True).frame, bin_factors=BinFactors(2, 1)
    ).in_file_layout()
    assert [r["bbox"] for r in report["regions"]] == [r.bbox.to_dict() for r in expected.regions]
    (region,) = report["regions"]
    assert_matches_truth(region["period_px"], region["angle_deg"], s.truth)


def test_cli_bin_one_by_one_equals_no_flag(tmp_path):
    path, _ = _binned_csv(tmp_path, 1, 1, period=8, angle_deg=6, modulation_depth=0.5)
    plain = _run(path)
    binned = _run(path, "--bin", "1X1")
    assert plain.returncode == binned.returncode == 0
    assert binned.stdout == plain.stdout


@pytest.mark.parametrize("value", ["2*1", "2x", "x1", "0x1", "1x0", "2x1x1"])
def test_cli_rejects_malformed_bin(tmp_path, value):
    path, _ = _binned_csv(tmp_path, 1, 1, modulation_depth=0.0)
    result = _run(path, "--bin", value)
    assert result.returncode == 2
    assert "--bin" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_bin_leaving_no_searchable_period_fails_cleanly(tmp_path):
    path, _ = _binned_csv(tmp_path, 1, 1, modulation_depth=0.0)
    _assert_clean_failure(_run(path, "--bin", "11x1"), "11x1")


# Ticket 09: Phase Breaks in the JSON (plan 5.2, AC 5 CLI).


def _side(line, pixel):
    """PhaseBreak's rule: > 0 on the positive side, cross(end - start, p - start) with
    cross(a, b) = a_col b_row - a_row b_col."""
    (r0, c0), (r1, c1) = line
    return (c1 - c0) * (pixel[0] - r0) - (r1 - r0) * (pixel[1] - c0)


def test_cli_reports_phase_breaks(tmp_path):
    seed = PHASE_BREAK_TEST_SEEDS[0]
    line_angle, jump = ac2_line(seed)
    s, _ = break_region_case(seed, jump, line_angle)
    (truth,) = s.truth.phase_breaks
    plain_path, file_path = tmp_path / "frame.csv", tmp_path / "transposed.csv"
    write_frame_csv(s.frame, plain_path)
    write_frame_csv(s.frame.T, file_path)
    plain = _run(plain_path)
    flipped = _run(file_path, "--transpose")
    assert plain.returncode == flipped.returncode == 0
    assert plain.stderr == flipped.stderr == ""
    (brk,) = json.loads(plain.stdout)["phase_breaks"]
    (file_brk,) = json.loads(flipped.stdout)["phase_breaks"]
    assert file_brk["line"] == [[c, r] for r, c in reversed(brk["line"])]
    assert file_brk["jump_rad"] == brk["jump_rad"]
    assert file_brk["region"] == brk["region"]
    # The reported direction agrees with the truth's (a near-horizontal line, col
    # increasing), so the shifted side is the positive side, in both layouts.
    assert abs(brk["jump_rad"] - truth.jump_rad) <= BREAK_JUMP_TOL_RAD
    region = truth_pixels(s.truth.regions[0])
    rows, cols = np.nonzero(truth.shifted & region)
    far = np.argmax(np.abs(rows - truth.point[0]))  # the shifted pixel farthest from the line
    pixel = (int(rows[far]), int(cols[far]))
    assert _side(brk["line"], pixel) > 0
    assert _side(file_brk["line"], pixel[::-1]) > 0
