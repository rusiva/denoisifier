# 06 prototype P1: spike recall and false spike pixels (plan D5)

Question (plan review P1, then the coordinator's four additions from the critic's notes O1, Q8 and "Other drifts"): with the plan's spike model (added brightness 2-10x `clean.max()`, streaks of 1-3 px) and its rejection test (8 sigma, floor measured above the frame baseline per B3), what spike-pixel recall and false spike rate does it get? The requirement is fixed: per frame, `|spike_pixels - truth| <= max(2, 0.05 * truth)`, and the pass mark is **30 photons**.

**Verdict.** The plan's start constants (`_SPIKE_SIGMAS = 8`, `_SPIKE_FLOOR_FRACTION = 0.5`, peak = max of `median3`) **fail**. Recall is not the problem: it is >= 0.99 at 30 photons and above. The failures come from three other places:
1. False spike pixels from EM-gain excursions of 1-2 photons in the dim halo. The 10-photon frames get 58-123 per spike-free frame, and 30 ph m = 0.5 gets 2.5 (max 10), so 11/40 frames are over tolerance.
2. A 3x3 median maximum raised by overlapping spike hits. The floor then jumps up to 6x and the frame misses 10-60 spikes (1-4/40 frames in every configuration).
3. 37 false pixels on noise-0 Phase Break frames (14/180 frames, worst 15).

**Smallest change that meets the requirement at >= 30 photons** (seeds 396 000-396 399 only):
- `_SPIKE_FLOOR_FRACTION = 1.0` (was 0.5).
- **Peak = the 10th-largest value of `median3(frame)`**, not its maximum. This is one new constant, `_SPIKE_PEAK_RANK = 10`. Scale = peak minus the 5th percentile of `median3` (B3).
- `_SPIKE_SIGMAS = 8.0`, `_SPIKE_NEIGHBOUR_ROWS = 3` and `_NOISE_TILE_PX = 16` stay as they are.
- In the 3 rows at the top and bottom, the column window **shifts inward** (rows 0..6 or R-7..R-1, self excluded) instead of `mirror`. Mirror still misses vertical streaks at the frame edge (N2; 1-3 px per affected frame).
- The median of the 6 values is the upper middle (scipy's rank for an even footprint), the same everywhere.

**10 photons stays a stated limit.** No (k, floor) on the grid meets the tolerance there. Rank10 8/1.0 gives 31/40 and 40/40 frames over; the best was 8/1.25 with 8/40 and 32/40. The cause is that a 2x-peak spike (20 photons) sits inside the tail of single-photon EM excursions. The docstring should say that the spike count is reliable from about 30 photons at the peak.

## Results, recommended detector (rank10, k = 8, floor 1.0), 40 frames per row, 30 spikes per frame

| Frames | Recall | Frames over tolerance | Worst abs diff | False spike px, spike-free twin (mean / max) |
|---|---|---|---|---|
| EMCCD 10 ph, m 0 / 0.5 (below the pass mark) | 0.981 / 0.996 | 31 / 40 of 40 | 15 / 61 | 7.3 / 15, 21.0 / 62 |
| EMCCD 30 ph, m 0 | 0.9996 | 0 | 1 | 0 / 0 |
| EMCCD 30 ph, m 0.5 | 1.0000 | 0 | 2 | 0.25 / 2 |
| typical 100 ph, m 0 | 1.0000 | 0 | 0 | **0 / 0** |
| typical 100 ph, m 0.5 | 1.0000 | 0 | 0 | **0 / 0** |
| EMCCD 1000 ph, m 0.5 | 1.0000 | 0 | 0 | 0 / 0 |
| EMCCD 5000 ph, m 0.5 | 1.0000 | 0 | 0 | 0 / 0 |
| integer EMCCD (gain 1, read 0) 100 ph | 1.0000 | 0 | 1 | 0.03 / 1 |
| Gaussian 0.01, P 3 +10°, P 20 -10° | 1.0000 | 0 | 0 | 0 / 0 |
| Gaussian noise 0, m 1, P 3 ±10°, P 20 +10° | >= 0.9996 | 0 | 1 | 0 / 0 |
| **Boundary**: brightness 2.0-2.2x, 30 ph / 100 ph / 5000 ph / noise-0 P 3 | 0.999-1.000 | 0 | <= 2 | <= 0.25 / 2 |
| **Clip at 3x `clean.max()`** (spikes saturate; per-pixel test on clipped pixels too, no component rule), 30 ph / 100 ph m 0 / 100 ph m 0.5 / Gaussian P 3 | 0.998-1.000 | 1, 1, 0, 0 | 4 | 0.12 / 2 at 30 ph, else 0 |

- Clip at 3x: the reported clipped count (auto plateau pixels that were not flagged) is **0** on 158 of 160 frames. It is 3 on the remaining frame (seed 396 316, in both the 30 ph and 100 ph m 0 sets), where two hits overlap into a 4-px vertical saturated run at rows 1-4. That is longer than `_SPIKE_MAX_LENGTH` and outside the model, and it accounts for both over-tolerance frames.
- **Phase Break** (noise 0; lower half of the frame rolled sideways by 1, round(P/3) or round(P/2) px; P 3/4/5/8/12/20, Angle 0/±10°, m 1 and 0.5, no Mottle or scorched; 180 frames): **0 false spike pixels**. For comparison, floor 0.75 gives 5 and the plan's max3 8/0.5 gives 37 (worst 15, at P 3).
- **Typical spike-free frames (100 ph scorched, m 0 and 0.5, 80 frames): 0 false spike flags.** Rejection therefore changes no pixel on such frames, and the stored thresholds are not expected to move. The gate frames are spike-free typical frames, so `make measure` remains the check.
- Solis crop (bias 713 counts, raw, +1000 and minus median/2): 0 flags at every grid point. B3's baseline works.

## The plan's start constants for comparison (max3, k 8, floor 0.5; B3 baseline and edge fix included)

Frames over tolerance per 40: 10 ph 37 and 40; 30 ph 2 and 11; typical 1 and 2; 1000-5000 ph 0; Gaussian 0-2. False spike pixels on spike-free 30 ph m 0.5 frames: 2.5 mean, max 10. Phase Break: 37 px. Recall on bright pixels at 10 ph (clean above half the peak) is 0.85 at k 8, as P1 predicted. These pixels are only about 4% of the spike pixels, so the false flags dominate the count error. Lowering k does not help, because it only adds false flags.

## Setup

- Script: `.scratch/stripe-detector/evidence/06-prototype-p1.py` (throwaway; it emulates generator D1 and detector D5 outside `src/`). Raw output: `06-prototype-p1.txt`, `06-prototype-p1.json`.
  - Run: `uv run --locked python .scratch/stripe-detector/evidence/06-prototype-p1.py OUT.json`, about 200 s, run at HEAD 4e40bdd.
  - The `--mirror-edges` flag gives the run without the edge fix: the same table, with up to 1/40 extra over-tolerance frames per configuration (e.g. Gaussian P 3 clip, boundary 5000 ph) from edge streaks.
- Seeds: `generate()` saw only `range(396_000, 396_400)`, the plan's reservation. There are 40 per configuration, with overlap between configurations. The Phase Break frames use 396 300-396 371.
  - The spike positions come from a local `np.random.default_rng((seed, 6))`, never passed to `generate`.
  - No calibration seeds and no 700 000-700 005 or 700 100-700 139.
- Frames: 256x256, `CASES[seed % 10]` for Period and Angle (EMCCD rows), scorched Mottle. Each spiked frame has a spike-free twin with the same seed.
- Grid: peak in {max3, rank10} x k in {8, 6, 5} x floor in {0.5, 0.75, 1.0, 1.25}. All of it is in the `.txt`.
- Timing, 400x1600 `features + detect`: median **0.285-0.296 s**, measured on a machine that was *not idle* (load average about 16 from another session). The parts are: column median 0.10 s, `median3` 0.12 s, tile MAD 0.08 s.
  - That is at the 0.3 s budget, and it needs an idle re-measurement.
  - If it is tight: `median3` serves only the global peak scalar, so it can run on a 2x-binned frame or be restricted to rows and columns above a percentile.
