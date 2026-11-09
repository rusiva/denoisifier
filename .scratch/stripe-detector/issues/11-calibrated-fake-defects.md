# 11: Calibrated fake breaks and forks

**What to build:** Reported phase breaks and forks can be trusted. The break and fork thresholds are calibrated on generated **striped frames with no breaks or forks**, at typical settings with spikes present, so that fake breaks and forks occur at most about once per 20 frames. The rate can be changed. Calibration and evaluation use separate seeds, and the thresholds are stored with the package next to the stripe threshold.

**Blocked by:** 06, 09, 10

**Status:** ready-for-agent

- [ ] A repeatable calibration routine sets the break and fork thresholds from calibration seeds.
- [ ] On held-out striped frames with no breaks or forks (scorched mottle, about 100 photons at the peak, spikes present), the number of fake breaks and forks is about 1 per 20 frames or less.
- [ ] After calibration, breaks with jumps of π/2 or more and forks are still found at the rates required by 09 and 10.
- [ ] The rate can be set through the library option and a CLI flag.
- [ ] The statistical tests are marked slow.
