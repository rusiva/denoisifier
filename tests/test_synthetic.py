import numpy as np

from denoisifier import read_frame
from denoisifier.synthetic import generate, write_frame_csv


def test_same_seed_gives_same_frame():
    a = generate(seed=3)
    b = generate(seed=3)
    c = generate(seed=4)
    assert np.array_equal(a.frame, b.frame)
    assert not np.array_equal(a.frame, c.frame)


def test_returns_frame_and_ground_truth():
    s = generate(seed=0, shape=(64, 80), period=7.5, angle_deg=-4.0, modulation_depth=0.3)
    assert s.frame.shape == (64, 80)
    assert s.truth.period == 7.5
    assert s.truth.angle_deg == -4.0
    assert s.truth.modulation_depth == 0.3


def test_written_csv_reads_back_as_the_same_frame(tmp_path):
    s = generate(seed=5, shape=(40, 50))
    path = tmp_path / "frame.csv"
    write_frame_csv(s.frame, path)
    lines = path.read_text().splitlines()
    assert len(lines) == 40
    assert lines[0].count(",") == 49
    float(lines[0].split(",")[0])  # no header: the first line is numbers
    assert np.allclose(read_frame(path).frame, s.frame, rtol=1e-8, atol=0)
