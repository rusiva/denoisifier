# 13: Speed budget

**What to build:** An experimenter can analyse frames while the experiment is running. The full pipeline (reading, spike and clipping handling, detection, regions, breaks, forks, report) analyses a full 1600×400 frame in about 5 s or less on a laptop CPU, without a GPU. Find the slow spots and fix them without changing the results.

**Blocked by:** 07, 11

**Status:** ready-for-agent

- [ ] A marked performance test analyses a generated 1600×400 frame (scorched mottle, stripes, breaks and forks, spikes) in about 5 s or less.
- [ ] All calibration and accuracy tests still pass after optimisation; stored thresholds are re-calibrated if the detector's output changed.
- [ ] Timings for each stage are recorded next to the spec.

## Comments

- 2026-11-12, owner ruling after ticket 05: the heavy gates run once, at the end of the ticket, after the code review's fixes (CLAUDE.md, Gates, "When"). A second `make measure` is only for a detector fix that the final measure forces, and its reason goes here.
- 2026-11-14, from ticket 09 (`.scratch/stripe-detector/handoffs/09-prototype-p1.md`, "v2 speed"): the phase-break pass was accepted as is in ticket 09: single process, idle, 400x1600, it adds up to ~1.4 s on a single-break frame at P 3 (~0.3 s at P 10), ~2.5 s on P 3 two-break frames, ~0.1 s on break-free frames. At P 3-4 the time is the finder's samples (~230k at a 0.5 P stride over a full frame, re-binned for every coarse, fine and golden-section angle and again per greedy round); the FFT filters add a flat 0.17-0.20 s per region (a crop-local spectrum would cut it). Speedup for this ticket (not implemented or measured): run the coarse angle scan on strided (capped) samples, then the fine scan, golden-section refinement and fit on full-density 0.5 P samples within the ±4 P fit window of the coarse line; expected ~0.3-0.6 s worst case. It must not move results: check found / line error against ticket 09's tests and the P1 v2 explore set before adopting (the coarse scan must still pick the right basin). A plain sample cap is not an option: it moved line error at P 3-5 (full P 4 max 0.17 -> 0.75 P).

