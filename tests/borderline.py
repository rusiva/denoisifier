"""m = 0.2 frames whose Stripe Score lands just over THRESHOLD.

Picked from test seeds 0-19, Periods {3, 5, 8, 20}, Angle 0, scorched Mottle,
EMCCD, with THRESHOLD = 154. The measured area is small: on (0, 20), (13, 5)
and (13, 8) it has too few neighbour pairs to measure local phase (3, 8 and
14 pixels when picked), so the bank Period and Angle are reported.
"""

from denoisifier.synthetic import Emccd, generate

BORDERLINE = [(0, 20), (13, 5), (13, 8), (12, 20), (16, 8)]


def borderline_frame(seed, period):
    return generate(
        seed=seed,
        shape=(256, 256),
        period=period,
        angle_deg=0,
        modulation_depth=0.2,
        mottle="scorched",
        noise=Emccd(),
    ).frame
