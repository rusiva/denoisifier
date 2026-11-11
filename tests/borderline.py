"""m = 0.2 frames whose Stripe Score lands just over THRESHOLD.

Picked from test seeds, Periods {3, 5, 8, 20}, Angle 0, scorched Mottle,
EMCCD, with THRESHOLD = 154. The measured area is small: on (13, 5) and
(13, 8) it has too few neighbour pairs to measure local phase (8 and 14 pixels
when picked), so the bank Period and Angle are reported. The first entry was
(0, 20) until seeds 0-9 became A0_CALIBRATION_SEEDS; it was re-picked as the
lowest Period 20 seed in test seeds 10-99, from 20 up, that scores in the
window (ticket agent-gates/04, ruling O3). The seeds are protected numbers.
"""

from denoisifier.synthetic import Emccd, generate
from protected import BORDERLINE_TEST_CASES

BORDERLINE = BORDERLINE_TEST_CASES


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
