# 03: Feasibility gate: weak stripes at 1% false alarms

**What to build:** A measured answer to the project's biggest open question: can the basic detector find weak stripes (m = 0.2) against stripe-size mottle without false alarms, fast enough? Set a provisional threshold on **calibration seeds** of stripe-free frames (scorched mottle, about 100 photons at the peak, EM gain 300) for 1% false alarms. Then measure the detection rate for m = 0.2, with stripes covering the profile core, on **separate held-out seeds**. Also time one 1600×400 frame. The ticket produces a short written result (numbers, setup, seeds) next to the spec. If the gate fails, do **not** push on: record the measured numbers and set this ticket's status to `ready-for-human`, so that the experimenter can decide (accept a lower rate, raise the minimum m, or change the method).

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] The threshold is set only on calibration seeds; all rates are measured on held-out seeds that were never used for calibration.
- [ ] The false-alarm rate on held-out stripe-free frames is about 1% (within binomial tolerance for the batch size used).
- [ ] The detection rate for m = 0.2 at that threshold is reported, with batch size and confidence interval. **Gate:** at least 90%.
- [ ] Time to analyse one 1600×400 frame on a laptop CPU is reported. **Gate:** 10 s or less.
- [ ] Results are written down next to the spec (setup, seeds, numbers, pass or fail).
- [ ] The measurement runs as a repeatable test or script (marked slow), not a one-off notebook.
- [ ] If either gate fails: status set to `ready-for-human`, with the numbers and the most likely causes recorded.
