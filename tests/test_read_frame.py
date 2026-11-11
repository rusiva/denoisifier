import numpy as np
import pytest

from denoisifier import read_frame
from denoisifier.frame_io import write_frame_csv
from denoisifier.synthetic import generate
from protected import CSV_ROUND_TRIP_TEST_SEED


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
    result = read_frame(_write(tmp_path, "0,5,5\n1,5,5\n2,5,5\n"))
    assert result.frame.shape == (3, 3)
    assert np.array_equal(result.frame[:, 0], [0, 1, 2])


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


def test_trailing_comma_is_rejected(tmp_path):
    with pytest.raises(ValueError, match=r"line 1, column 3: '' is not a number"):
        read_frame(_write(tmp_path, "1,2,\n3,4,\n"))


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
