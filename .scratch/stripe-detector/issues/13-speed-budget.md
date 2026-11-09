# 13: Speed budget

**What to build:** An experimenter can analyse frames while the experiment is running. The full pipeline (reading, spike and clipping handling, detection, regions, breaks, forks, report) analyses a full 1600×400 frame in about 5 s or less on a laptop CPU, without a GPU. Find the slow spots and fix them without changing the results.

**Blocked by:** 07, 11

**Status:** ready-for-agent

- [ ] A marked performance test analyses a generated 1600×400 frame (scorched mottle, stripes, breaks and forks, spikes) in about 5 s or less.
- [ ] All calibration and accuracy tests still pass after optimisation; stored thresholds are re-calibrated if the detector's output changed.
- [ ] Timings for each stage are recorded next to the spec.
