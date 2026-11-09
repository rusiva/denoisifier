# 07: Calibrated stripe score

**What to build:** The stripe verdict is backed by a number. The threshold is calibrated on generated stripe-free frames using the full pipeline (regions, spike rejection, clipping), at typical settings (scorched mottle, about 100 photons at the peak, spikes present). It is stored with the package. The false-alarm rate can be changed (default 1%). Calibration and evaluation use **separate seeds**. Recalibration can be re-run, so that it can later use real stripe-free frames instead of generated ones.

**Blocked by:** 05, 06

**Status:** ready-for-agent

- [ ] A repeatable calibration routine produces the stored threshold(s) from calibration seeds.
- [ ] On held-out stripe-free frames, the false-alarm rate is about 1% (within binomial tolerance); it also matches when another rate (for example 5%) is requested.
- [ ] On held-out frames, m = 0.2 at typical noise is detected in at least 90% of frames at the default rate.
- [ ] The report includes the score and the threshold used.
- [ ] Calibration accepts a folder of frames (synthetic or real) as its stripe-free set.
- [ ] The statistical tests are marked slow so they can be skipped in quick runs.
