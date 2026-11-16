# 06 prototype P1: handoff summary

Full write-up: `.scratch/stripe-detector/evidence/06-prototype-p1.md`. Script, raw output and JSON are next to it (`06-prototype-p1.py`, `.txt`, `.json`; not committed).

- **Answer.** The plan's 8 sigma / floor 0.5 / max3 peak gets recall >= 0.99 at >= 30 photons, but it **misses the fixed tolerance** (max(2, 5%)).
  - At 30 ph m 0.5, 11/40 frames are over, from dim-halo EM-gain excursions: 2.5 false px per spike-free frame, max 10.
  - Typical and Gaussian frames have 1-4/40 over, because overlapping hits raise the 3x3 maximum and so the floor.
  - Phase Break frames get 37 false px.
  - At 10 ph nothing on the grid passes. Bright-pixel recall at k 8 is 0.85, as P1 predicted, but false flags dominate. This is a documented limit below the 30-photon pass mark.
- **Recommended constants:**
  - `_SPIKE_SIGMAS = 8.0` (unchanged) and `_SPIKE_FLOOR_FRACTION = 1.0`.
  - Peak = the 10th-largest value of `median3`, as the new `_SPIKE_PEAK_RANK = 10`. Scale = peak minus the 5th percentile of `median3` (B3).
  - Column window of 6 neighbours, upper median, **shifted inward** in the 3 edge rows.
  - `_SPIKE_NEIGHBOUR_ROWS = 3` and `_NOISE_TILE_PX = 16` unchanged.
- **With them, at >= 30 ph:**
  - 0/40 frames over tolerance in every configuration.
  - Boundary spikes (2.0-2.2x) pass.
  - Clip at 3x: spikes are counted as spikes and 0 as clipped, except 1 frame with an out-of-model 4-px vertical overlap.
  - 0 false px on 180 Phase Break frames and on 80 typical spike-free frames, so the stored thresholds are not expected to move.
  - 0 flags on the Solis crop at any offset.
- **Timing:** 0.29 s at 400x1600, measured under load 16. This needs an idle re-measure against the 0.3 s budget.
- Seeds: only 396 000-396 399.
