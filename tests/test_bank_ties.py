"""Bank Angle ties (ticket 13 slice 4b): stripe Angles whose energies tie within rounding resolve
to the first bank Angle, so the chosen Angle never depends on floating-point rounding.

The frame is a fixed, seed-free broadband pattern made mirror-symmetric about its centre column.
Both sides and the reflect-padded, periodic FFT grid are symmetric there, so at that column the
+theta and -theta filters' energies are equal up to rounding."""

import numpy as np

from denoisifier import BinFactors
from denoisifier._local_stripes import _STRIPE_ANGLES_DEG, estimate_local_stripes


def _mirrored_broadband(shape=(101, 151)):
    rows, cols = np.mgrid[0 : shape[0], 0 : shape[1]].astype(float)
    centre = (shape[1] - 1) / 2
    x = np.abs(cols - centre)
    pattern = np.sin(0.37 * rows * x + 0.11 * rows) + np.cos(1.9 * x + 0.013 * rows**2)
    return 10.0 + pattern + 0.5 * np.sin(2.9 * rows) + 0.7 * np.cos(0.8 * x + 0.5 * rows)


def test_mirror_tied_angles_resolve_to_the_first_bank_angle():
    frame = _mirrored_broadband()
    assert np.array_equal(frame, frame[:, ::-1])
    centre = (frame.shape[1] - 1) // 2
    stripes = estimate_local_stripes(frame, np.ones(frame.shape, bool), BinFactors(1, 1))

    angles = stripes.angle_deg[:, centre]
    # Every +theta stripe Angle ties its -theta mirror at the centre column, so the first of the
    # pair (the negative one) wins; 0 deg is its own mirror.
    assert set(np.unique(angles)) <= {a for a in _STRIPE_ANGLES_DEG if a <= 0}
    assert np.any(angles < 0)
