# 11: Calibrated fake breaks and forks

**What to build:** Reported phase breaks and forks can be trusted. The break and fork thresholds are calibrated on generated **striped frames with no breaks or forks**, at typical settings with spikes present, so that fake breaks and forks occur at most about once per 20 frames. The rate can be changed. Calibration and evaluation use separate seeds, and the thresholds are stored with the package next to the stripe threshold.

**Blocked by:** 06, 09, 10

**Status:** ready-for-agent

- [ ] A repeatable calibration routine sets the break and fork thresholds from calibration seeds.
- [ ] On held-out striped frames with no breaks or forks (scorched mottle, about 100 photons at the peak, spikes present), the number of fake breaks and forks is about 1 per 20 frames or less.
- [ ] After calibration, breaks with jumps of π/2 or more and forks are still found at the rates required by 09 and 10.
- [ ] The rate can be set through the library option and a CLI flag.
- [ ] The statistical tests are marked slow.

## Comments

- 2026-11-15, from ticket 10 (Forks). The held-out frames here have no Forks, so the fake-defect rate will not see the fake Phase Breaks on Fork frames (close opposite Fork pairs, Forks near a region edge: ticket 10 Comments, ticket 18). The fork evidence scalar is yours to calibrate: E = winding-component area / (2R)², R = `_FORK_LOOP_PERIODS` = 2 P; gate `_FORK_GATE_EVIDENCE` = 0.2, reported `_FORK_MIN_EVIDENCE` = 0.3; true-Fork E min 0.31 (P2 explore), largest fork-free candidate 0.000. A fake region gets fake Forks too (09's 109797 kind).
