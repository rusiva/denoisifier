import numpy as np

from denoisifier import read_frame


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
