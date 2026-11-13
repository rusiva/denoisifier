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

## Comments

- 2026-11-12, owner ruling after ticket 05: the heavy gates run once, at the end of the ticket, after the code review's fixes (CLAUDE.md, Gates, "When"). A second `make measure` is only for a detector fix that the final measure forces, and its reason goes here.
- 2026-11-13, from ticket 06 (`.scratch/stripe-detector/handoffs/06-critic-2.md` item 2): clipped stripe-free frames score both higher and lower than unclipped ones (mean change near zero), and one frame per signal level crossed 49.7 (seeds 396_085, 396_078); either measure the stripe-free rate on clipped frames (a few hundred, at ticket 06's `CLIP_LEVEL_FRACTION`) or state that the 1% rate holds for unclipped frames.
- 2026-11-13, from ticket 06 (`.scratch/stripe-detector/handoffs/06-critic-3.md`): the hard group gating (size and leakage rules on the best surviving group) makes the score jump under small pixel changes: replacing about 0.3% of a stripe-free frame's pixels with their column median moves it between 0 and 15-39, and once from 39.0 to 79.4, across `GATE_STORED_THRESHOLD`.
