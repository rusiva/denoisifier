# 13: Speed budget

**What to build:** An experimenter can analyse frames while the experiment is running. The full pipeline (reading, spike and clipping handling, detection, regions, breaks, forks, report) analyses a full 1600×400 frame in about 5 s or less on a laptop CPU, without a GPU. Find the slow spots and fix them without changing the results.

**Blocked by:** 07, 11

**Status:** ready-for-agent

- [ ] A marked performance test analyses a generated 1600×400 frame (scorched mottle, stripes, breaks and forks, spikes) in about 5 s or less.
- [ ] All calibration and accuracy tests still pass after optimisation; stored thresholds are re-calibrated if the detector's output changed.
- [ ] Timings for each stage are recorded next to the spec.

## Comments

- 2026-11-12, owner ruling after ticket 05: the heavy gates run once, at the end of the ticket, after the code review's fixes (CLAUDE.md, Gates, "When"). A second `make measure` is only for a detector fix that the final measure forces, and its reason goes here.
