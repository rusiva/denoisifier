import numpy as np

from denoisifier.synthetic import generate


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

