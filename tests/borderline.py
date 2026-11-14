"""m = 0.2 frames whose Stripe Score lands just over the default threshold.

Test seeds, Periods {5, 8, 20}, Angle 0, scorched Mottle, EMCCD, 256x256; each
scores in (T, BORDERLINE_SCORE_WINDOW x T) at the default threshold T (the
stored calibration at 1%). Re-picked at ticket 07 step 6 by the frozen W4(c)
rule (keep a seed still in the window, else the first seed from 10 up in the
window at that Period not already chosen for it); the earlier picks were made
at THRESHOLD = 154 (ruling O3 for the first entry). The seeds are protected
numbers.
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
