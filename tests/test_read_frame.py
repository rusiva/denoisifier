from pathlib import Path

import numpy as np
import pytest

from denoisifier import read_frame
from denoisifier.frame_io import write_frame_csv
from denoisifier.synthetic import generate
from protected import CSV_ROUND_TRIP_TEST_SEED

SOLIS = Path(__file__).parent / "data" / "solis"
CROP = SOLIS / "xpos_ypos_crop.asc"
TRAILING_NOTE = "every grid row ends with a trailing comma; the empty last field was ignored"


def _write(tmp_path, text):
    path = tmp_path / "frame.csv"
    path.write_text(text)
    return path


def test_plain_grid_gives_2d_array_of_right_shape(tmp_path):
    result = read_frame(_write(tmp_path, "1.5,2,3\n-4,5e2,6\n"))
    assert result.frame.shape == (2, 3)
    assert result.frame.dtype == np.float64
    assert np.array_equal(result.frame, [[1.5, 2, 3], [-4, 500, 6]])
    assert result.notes == ()


def test_single_row_is_still_2d(tmp_path):
    result = read_frame(_write(tmp_path, "1,2,3\n"))
    assert result.frame.shape == (1, 3)


def test_every_column_is_kept_even_when_first_counts_up(tmp_path):
    # The rising side of a profile crop: a real intensity column that counts up.
    result = read_frame(_write(tmp_path, "10,12,15\n11,14,18\n13,17,22\n"))
    assert np.array_equal(result.frame, [[10, 12, 15], [11, 14, 18], [13, 17, 22]])
    assert len(result.notes) == 1
    assert result.notes[0].startswith("warning: ")


def test_plain_grid_with_falling_first_column_has_no_notes(tmp_path):
    result = read_frame(_write(tmp_path, "9,1,1\n7,1,1\n8,1,1\n"))
    assert np.array_equal(result.frame, [[9, 1, 1], [7, 1, 1], [8, 1, 1]])
    assert result.notes == ()


def test_numeric_header_row_is_kept_as_data(tmp_path):
    result = read_frame(_write(tmp_path, "1,2,3\n9,5,6\n8,7,8\n"))
    assert np.array_equal(result.frame, [[1, 2, 3], [9, 5, 6], [8, 7, 8]])
    assert result.notes == ()


def test_axis_column_is_kept_by_default_with_a_warning(tmp_path):
    result = read_frame(_write(tmp_path, "0,5,6\n1,7,8\n2,9,10\n"))
    assert np.array_equal(result.frame, [[0, 5, 6], [1, 7, 8], [2, 9, 10]])
    assert len(result.notes) == 1
    assert result.notes[0].startswith("warning: ")
    assert "--drop-axis-column" in result.notes[0]


def test_written_csv_reads_back_as_the_same_frame(tmp_path):
    s = generate(seed=CSV_ROUND_TRIP_TEST_SEED, shape=(40, 50))
    path = tmp_path / "frame.csv"
    write_frame_csv(s.frame, path)
    lines = path.read_text().splitlines()
    assert len(lines) == 40
    assert lines[0].count(",") == 49
    float(lines[0].split(",")[0])  # no header: the first line is numbers
    assert np.allclose(read_frame(path).frame, s.frame, rtol=1e-8, atol=0)


def test_uneven_rows_raise_naming_the_row(tmp_path):
    path = _write(tmp_path, "1,2,3\n4,5\n6,7,8\n")
    with pytest.raises(ValueError, match=r"line 2 has 2 values") as excinfo:
        read_frame(path)
    assert "line 1" in str(excinfo.value)
    assert str(path) in str(excinfo.value)


def test_non_number_in_grid_raises_naming_its_position(tmp_path):
    with pytest.raises(ValueError, match=r"line 2, column 2: 'x' is not a number"):
        read_frame(_write(tmp_path, "1,2,3\n4,x,6\n7,8,9\n"))


def test_empty_field_in_grid_raises_naming_its_position(tmp_path):
    with pytest.raises(ValueError, match=r"line 2, column 2: '' is not a number"):
        read_frame(_write(tmp_path, "1,2,3\n4,,6\n"))


def test_trailing_comma_on_every_row_is_accepted_and_noted(tmp_path):
    result = read_frame(_write(tmp_path, "4,2,\n3,1,\n"))
    assert np.array_equal(result.frame, [[4, 2], [3, 1]])
    assert result.notes == (TRAILING_NOTE,)


def test_one_row_trailing_comma_reads_as_a_trailing_delimiter(tmp_path):
    # The documented limit: a one-row file cannot show a missing last value.
    result = read_frame(_write(tmp_path, "5,6,\n"))
    assert np.array_equal(result.frame, [[5, 6]])
    assert result.notes == (TRAILING_NOTE,)


def test_trailing_comma_missing_on_one_row_raises_naming_it(tmp_path):
    path = _write(tmp_path, "1,2,\n3,4\n5,6,\n")
    with pytest.raises(ValueError, match=r"line 2 does not end with a trailing comma") as excinfo:
        read_frame(path)
    assert "line 1" in str(excinfo.value)
    assert str(path) in str(excinfo.value)


def test_trailing_comma_on_only_some_rows_raises_naming_it(tmp_path):
    with pytest.raises(ValueError, match=r"line 2 ends with a trailing comma"):
        read_frame(_write(tmp_path, "1,2\n3,4,\n5,6\n"))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("1,2,3\n4,5,\n", r"line 2 ends with a trailing comma"),
        ("1,2,\n4,5,6\n", r"line 2 does not end with a trailing comma"),
    ],
    ids=["later-row-lost-its-last-value", "first-row-lost-its-last-value"],
)
def test_missing_last_value_on_one_row_is_caught(tmp_path, text, message):
    with pytest.raises(ValueError, match=message):
        read_frame(_write(tmp_path, text))


def test_empty_interior_field_with_trailing_commas_raises_naming_it(tmp_path):
    with pytest.raises(ValueError, match=r"line 1, column 2: '' is not a number"):
        read_frame(_write(tmp_path, "1,,3,\n4,5,6,\n"))


def test_byte_order_mark_does_not_hide_the_first_row(tmp_path):
    path = tmp_path / "frame.csv"
    path.write_bytes(b"\xef\xbb\xbf3,2\n1,4\n")
    result = read_frame(path)
    assert np.array_equal(result.frame, [[3, 2], [1, 4]])
    assert result.notes == ()


def test_negative_values_load_unchanged(tmp_path):
    result = read_frame(_write(tmp_path, "-1.5,-2e-3,0\n-4,-0,7\n"))
    assert np.array_equal(result.frame, [[-1.5, -2e-3, 0], [-4, -0.0, 7]])
    assert result.notes == ()


def test_float_syntax_includes_non_finite_values(tmp_path):
    result = read_frame(_write(tmp_path, "nan,1\n-inf,2\n"))
    assert np.isnan(result.frame[0, 0])
    assert result.frame[1, 0] == -np.inf
    assert result.frame[0, 1] == 1
    assert result.frame[1, 1] == 2


def test_metadata_lines_before_and_after_the_grid_are_skipped_and_counted(tmp_path):
    text = (
        "Andor Solis export\n"
        "Exposure Time (secs):,0.1\n"
        "6,5\n"
        "4,7\n"
        "Date and Time:,Mon Nov 10\n"
        "Gain:,300\n"
        "Software Version:,4.32\n"
        "\n"
    )
    result = read_frame(_write(tmp_path, text))
    assert np.array_equal(result.frame, [[6, 5], [4, 7]])
    assert result.notes == (
        "skipped 2 metadata lines before the grid",
        "skipped 3 metadata lines after the grid",
    )


def test_bad_value_in_last_row_is_an_error_not_metadata(tmp_path):
    with pytest.raises(ValueError, match=r"line 3, column 3"):
        read_frame(_write(tmp_path, "1,2,3\n4,5,6\n7,8,abc\n"))


@pytest.mark.parametrize(
    "text",
    ["Andor Solis export\nGain:,300\n", "", "\n  \n\t\n"],
    ids=["metadata-only", "empty", "whitespace-only"],
)
def test_file_with_no_numbers_is_an_error(tmp_path, text):
    with pytest.raises(ValueError, match="no rows of numbers"):
        read_frame(_write(tmp_path, text))


@pytest.mark.parametrize(
    ("content", "line"),
    [
        (b"abc,8,9\n1,2,3\n4,5,6\n", 1),
        (b"1,2,3\n4,5,6\nabc,8,9\n", 3),
        (b"\xff,8,9\n1,2,3\n4,5,6\n", 1),
    ],
    ids=["first-row", "last-row", "undecodable-byte"],
)
def test_corrupted_first_or_last_row_is_an_error_not_metadata(tmp_path, content, line):
    path = tmp_path / "frame.csv"
    path.write_bytes(content)
    with pytest.raises(ValueError, match=rf"line {line}, column 1: .* is not a number"):
        read_frame(path)


def test_metadata_line_between_grid_rows_is_an_error(tmp_path):
    with pytest.raises(ValueError, match=r"line 2 has 2 values"):
        read_frame(_write(tmp_path, "1,2,3\nGain:,300\n4,5,6\n"))


def test_axis_column_is_dropped_when_requested(tmp_path):
    result = read_frame(_write(tmp_path, "0,5,6\n1,7,8\n2,9,10\n"), drop_axis_column=True)
    assert np.array_equal(result.frame, [[5, 6], [7, 8], [9, 10]])
    assert len(result.notes) == 1
    assert "dropped" in result.notes[0]
    assert not any(note.startswith("warning: ") for note in result.notes)


def test_spectral_axis_column_is_dropped_when_requested(tmp_path):
    text = "532.1,5,6\n532.4,7,8\n532.8,9,10\n"
    result = read_frame(_write(tmp_path, text), drop_axis_column=True)
    assert np.array_equal(result.frame, [[5, 6], [7, 8], [9, 10]])


def test_dropping_a_column_that_does_not_count_up_warns(tmp_path):
    result = read_frame(_write(tmp_path, "3,5,6\n1,7,8\n"), drop_axis_column=True)
    assert np.array_equal(result.frame, [[5, 6], [7, 8]])
    assert len(result.notes) == 2
    assert "dropped" in result.notes[0]
    assert not result.notes[0].startswith("warning: ")
    assert result.notes[1].startswith("warning: ")


def test_dropping_the_only_column_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="only one column"):
        read_frame(_write(tmp_path, "1\n2\n"), drop_axis_column=True)


def test_dropping_on_a_one_row_grid_drops_without_assessing(tmp_path):
    result = read_frame(_write(tmp_path, "3,5,6\n"), drop_axis_column=True)
    assert np.array_equal(result.frame, [[5, 6]])
    assert len(result.notes) == 1
    assert "dropped" in result.notes[0]
    assert "not assessed" in result.notes[0]
    assert not result.notes[0].startswith("warning: ")


def test_solis_export_with_axis_and_metadata_loads_when_dropping(tmp_path):
    text = "Andor Solis export\n0,5,6\n1,7,8\n2,9,10\nGain:,300\n"
    result = read_frame(_write(tmp_path, text), drop_axis_column=True)
    assert np.array_equal(result.frame, [[5, 6], [7, 8], [9, 10]])
    assert len(result.notes) == 3
    assert "before" in result.notes[0]
    assert "after" in result.notes[1]
    assert "dropped" in result.notes[2]


def test_real_solis_export_loads_by_default_with_notes():
    result = read_frame(CROP)
    assert result.frame.shape == (64, 65)
    assert np.array_equal(result.frame[:, 0], np.arange(1359, 1423))
    assert result.frame[31, 32] == 2022
    assert len(result.notes) == 3
    assert result.notes[0] == "skipped 27 metadata lines after the grid"
    assert result.notes[1] == TRAILING_NOTE
    assert result.notes[2].startswith("warning: ")
    assert "1359 to 1422" in result.notes[2]
    assert "--drop-axis-column" in result.notes[2]


def test_real_solis_export_with_axis_dropped_is_the_source_crop():
    result = read_frame(CROP, drop_axis_column=True)
    assert result.frame.shape == (64, 64)
    text = CROP.read_text()
    expected = [[float(x) for x in line.split(",")[1:-1]] for line in text.splitlines()[:64]]
    assert np.array_equal(result.frame, expected)
    assert result.frame[0, 0] == 984
    assert result.frame[0, 63] == 735
    assert result.frame[63, 0] == 856
    assert result.frame[63, 63] == 754
    assert result.frame[31, 31] == 2022
    assert result.frame.sum() == 4886612
    assert len(result.notes) == 3
    assert result.notes[0] == "skipped 27 metadata lines after the grid"
    assert result.notes[1] == TRAILING_NOTE
    assert "dropped" in result.notes[2]
    assert not any(note.startswith("warning: ") for note in result.notes)


@pytest.mark.parametrize(
    ("text", "line"),
    [
        ("abc,8,9,\n1,2,3,\n4,5,6,\n", 1),
        ("1,2,3,\n4,5,6,\nabc,8,9,\n", 3),
        ("abc,8,9\n1,2,3,\n4,5,6,\n", 1),
        ("1,2,3,\n4,5,6,\nabc,8,9\n", 3),
        ("1,2,3\n4,5,6\nabc,8,9,\n", 3),
    ],
    ids=[
        "trailing-both-first",
        "trailing-both-last",
        "lost-comma-first",
        "lost-comma-last",
        "extra-comma-last",
    ],
)
def test_corrupted_boundary_row_raises_with_or_without_its_trailing_comma(tmp_path, text, line):
    with pytest.raises(ValueError, match=rf"line {line}, column 1: 'abc' is not a number"):
        read_frame(_write(tmp_path, text))


@pytest.mark.parametrize(
    ("grid", "shape"),
    [
        ("9,5,6,7,8,9,\n8,5,6,7,8,9,\n7,5,6,7,8,9,\n", (3, 6)),
        ("9,5,6,7,8,9,10,\n8,5,6,7,8,9,10,\n7,5,6,7,8,9,10,\n", (3, 7)),
    ],
    ids=["raw-width-match", "value-count-match"],
)
def test_real_roi_line_next_to_a_trailing_comma_grid_is_skipped(tmp_path, grid, shape):
    # The ROI line copied from tests/data/solis/kinetic.asc, line 217.
    text = grid + "{left,right,bottom,top}:      1,20,1071,1090\n"
    result = read_frame(_write(tmp_path, text))
    assert result.frame.shape == shape
    assert result.notes == ("skipped 1 metadata line after the grid", TRAILING_NOTE)


@pytest.mark.parametrize("drop_axis_column", [False, True], ids=["axis-kept", "axis-dropped"])
def test_kinetic_series_is_rejected(drop_axis_column):
    path = SOLIS / "kinetic.asc"
    assert b"\r\n" in path.read_bytes()  # the fixture keeps its real CRLF line endings
    with pytest.raises(
        ValueError, match=r"line 215 says the file is a kinetic series of 10 frames"
    ) as excinfo:
        read_frame(path, drop_axis_column=drop_axis_column)
    assert "kinetic series are not supported" in str(excinfo.value)


def test_series_length_of_one_reads_normally(tmp_path):
    result = read_frame(_write(tmp_path, "6,5\n4,7\nNumber in Kinetics Series:    1\n"))
    assert np.array_equal(result.frame, [[6, 5], [4, 7]])
    assert result.notes == ("skipped 1 metadata line after the grid",)


def test_unreadable_series_length_is_an_error(tmp_path):
    with pytest.raises(ValueError, match=r"line 3: cannot read the kinetic series length 'ten'"):
        read_frame(_write(tmp_path, "6,5\n4,7\nNumber in Kinetics Series:    ten\n"))
