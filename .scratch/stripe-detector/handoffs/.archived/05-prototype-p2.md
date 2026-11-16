# Ticket 05 prototype P2: real-pipeline IoU at geometry in Periods

Answers review item P2 (with B2 and N4) of `05-plan-review.md`, against plan section 2.3. BASE 87005b9. This is throwaway code and changes no source.

## Scripts and seeds

- `/tmp/claude-1000/-home-rusiva-dev-denoisifier/72618a23-dbd5-4573-9e6c-b83c3532a4a4/scratchpad/p2_proto.py`: the IoU sweep. Raw output is in `p2_out.txt` in the same directory.
- `/tmp/claude-1000/-home-rusiva-dev-denoisifier/72618a23-dbd5-4573-9e6c-b83c3532a4a4/scratchpad/p2_timing.py`: the timing run. Raw output is in `p2_timing_out.txt`.
- Seeds used: **410_000-410_079** for the sweep (8 per CASE, in CASES order) and **411_000-411_003** for timing. The EMCCD rng is seeded with `seed + 7_000_000`, which is a `default_rng` and not a `generate` seed. Both ranges are outside USED_SEEDS, CALIBRATION_SEEDS, every other range in `tests/protected.py`, and the reviewer's N8 list. Add them to `USED_SEEDS`, or avoid them, when B3's calibration range is picked. These seeds are not a registered calibration range, so the numbers below are evidence for the plan. They are not the calibration itself.

## Setup

- **Frames.** Each frame is 512x512 and built the way p7/p8 build them: the m=0 scorched envelope from `generate(...).clean`, one centred tanh-mask region (edge_px 6) with m 0.5, then `_emccd` at 100 photons peak with the default Emccd (typical noise). The truth is soft mask >= 0.5. The 10 CASES Periods and Angles were used, with 8 seeds each.
- **Region semi-axes (rows x cols).**
  - `4Px5.3P`, as B2 proposed.
  - `5Px6.6P`, for P >= 12 only.
  - `floor45x60` = `max(4P,45) x max(5.3P,60)`. For P >= 12 this is the same geometry as 4Px5.3P.
- **Pipeline (plan 2.3, steps 1-3).**
  1. Cores are the 8-connected components of `ratio > THRESHOLD` (154).
  2. Each core is split by bank Period at log gaps of 2 or more grid steps.
  3. Size test: the core's bbox must be at least 3P wide and 2P tall, with P = the core's median bank Period.
  4. For each passing core:
     - Measure Period and Angle on the core with the neighbour-product sum (N5).
     - Re-tune one filter from **one shared `_Spectrum` per frame** (N4).
     - Grow: take the connected part of `{depth >= FRAC * median core depth} & light & (EDT from core <= CAP * P)` that touches the core.
- **Growth-rule parameters tried:**
  - FRAC 0.5 with CAP 2P (the plan's rule), 4P, and no cap.
  - FRAC 0.4 and 0.6, each with CAP 2P.
- **IoU measures.** "Union" is the IoU of all reported regions together against the truth. "Best" is the best single region. They differ only where the region breaks into fragments.

## Results (m 0.5, typical noise, scorched, 512x512, 8 seeds per row)

Union IoU, given as median / worst.

| P | geometry | FRAC 0.5 CAP 2P (plan) | FRAC 0.5 CAP 4P | FRAC 0.5 no cap | FRAC 0.6 CAP 2P | FRAC 0.4 CAP 2P |
|---|---|---|---|---|---|---|
| 3 | 4Px5.3P | 0 / 0 (detected 1/8) | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| 3 | floor45x60 | 0.34 / 0.05 | 0.57 / 0.11 | **0.97 / 0.95** | 0.33 / 0.05 | 0.34 / 0.05 |
| 4 | 4Px5.3P | 0.68 / 0 (missed 3/8) | 0.90 / 0 | 0.91 / 0 | 0.65 / 0 | 0.66 / 0 |
| 4 | floor45x60 | 0.64 / 0.31 | 0.84 / 0.54 | **0.97 / 0.93** | 0.63 / 0.31 | 0.64 / 0.31 |
| 5 | 4Px5.3P | 0.67 / 0 (missed 1/8) | 0.90 / 0 | 0.91 / 0 | 0.62 / 0 | 0.69 / 0 |
| 5 | floor45x60 | 0.87 / 0.69 | 0.96 / 0.91 | **0.97 / 0.97** | 0.84 / 0.67 | 0.85 / 0.69 |
| 6 | 4Px5.3P | 0.78 / 0.64 | 0.92 / 0.85 | 0.93 / 0.91 | 0.72 / 0.61 | 0.76 / 0.61 |
| 6 | floor45x60 | 0.91 / 0.74 | 0.96 / 0.87 | **0.96 / 0.94** | 0.88 / 0.73 | 0.89 / 0.74 |
| 8 | 4Px5.3P | 0.90 / 0.84 | 0.90 / 0.88 | 0.90 / 0.88 | 0.89 / 0.81 | 0.84 / 0.82 |
| 8 | floor45x60 | 0.95 / 0.90 | 0.95 / 0.93 | 0.95 / 0.93 | 0.92 / 0.88 | 0.89 / 0.87 |
| 10 | 4Px5.3P | 0.89 / 0.76 | 0.91 / 0.87 | 0.92 / 0.87 | 0.89 / 0.76 | 0.82 / 0.70 |
| 10 | floor45x60 | 0.91 / 0.82 | 0.93 / 0.91 | 0.93 / 0.91 | 0.88 / 0.78 | 0.84 / 0.76 |
| 12 | 4Px5.3P | 0.87 / 0.66 | 0.90 / 0.86 | 0.90 / 0.86 | 0.90 / 0.66 | 0.82 / 0.62 |
| 12 | 5Px6.6P | 0.92 / 0.76 | 0.93 / 0.85 | 0.93 / 0.85 | 0.90 / 0.76 | 0.87 / 0.72 |
| 14 | 4Px5.3P | 0.88 / 0.86 | 0.88 / 0.86 | 0.88 / 0.86 | 0.90 / 0.89 | 0.80 / 0.79 |
| 14 | 5Px6.6P | 0.90 / 0.87 | 0.90 / 0.87 | 0.90 / 0.87 | 0.91 / 0.88 | 0.84 / 0.82 |
| 16 | 4Px5.3P | 0.88 / **0.79** | 0.88 / 0.79 | 0.88 / 0.79 | 0.87 / 0.83 | 0.82 / 0.73 |
| 16 | 5Px6.6P | 0.90 / 0.83 | 0.92 / 0.84 | 0.92 / 0.84 | 0.89 / 0.85 | 0.85 / 0.78 |
| 20 | 4Px5.3P | 0.88 / **0.80** | 0.88 / 0.80 | 0.88 / 0.80 | 0.87 / 0.84 | 0.82 / 0.74 |
| 20 | 5Px6.6P | 0.88 / 0.84 | 0.90 / 0.86 | 0.90 / 0.86 | 0.89 / 0.84 | 0.82 / 0.80 |

The core alone (`ratio > T`) has a median IoU of 0.10-0.48 at P <= 6 and 0.53-0.77 at P >= 8. The core is too small to serve as the mask (Q4), and growth is necessary.

## Findings

1. **At P 16-20 (B2's question) the real pipeline matches the oracle.**
   - At 4Px5.3P with the plan's rule (FRAC 0.5, CAP 2P), the median is 0.88 at both Periods. That is above the 0.85 escalation line, and the oracle gave 0.83-0.92.
   - The **worst seeds sit right at 0.8**: 0.793 at P16 (seed 410_053) and 0.796 at P20 (seed 410_033).
   - Two changes clear 0.8 on all 8 seeds:
     - 5Px6.6P semi-axes: worst 0.83 at P16 and 0.84 at P20.
     - FRAC 0.6: worst 0.83 at P16 and 0.84 at P20 at 4Px5.3P.
   - Estimated Periods were within 0.3% of truth. The cap does not bind at long Periods.
   - Conclusion: an AC that requires IoU >= 0.8 on **every** frame needs about 5P x 6.6P semi-axes (200 x 264 px at P20, which fits in 512x512), or FRAC about 0.6, and the margin is still thin (0.83). At 4Px5.3P with FRAC 0.5 it fails on about 1 frame in 16.
2. **The plan's 2-Period dilation cap breaks short Periods.**
   - At P <= 6 and typical noise, the core is a small fragment, often several pieces (2-8 passing cores per frame at P 3-4).
   - A cap of 2P is only 6-12 px, so the grown mask cannot reach the region edge. The union IoU is 0.34-0.87 at floor45x60, and FRAC makes no difference.
   - Without a cap the union is 0.96-0.97 (worst 0.93), and so is the best single region. Once uncapped, the fragments grow into the same full region.
   - So the cap must be **much larger at short Periods or absent**. A cap in pixels (for example about one region size, or an absolute floor of about 30-40 px) is a candidate. This was not tried. Removing the cap is safe only if overlapping grown regions are deduplicated (O3-B merge, or step 5's label rule followed by dropping duplicates). With no cap, single-region frames came out as several identical copies, which is fine for union IoU but not for the region count.
   - Not tested: whether no cap leaks into a neighbour in the two-region frames (gap 14 px). A cap is needed for that case, so the pixel cap has to be tuned on the two-region pairs.
3. **Short Periods at 4P x 5.3P are below detection.**
   - At P3 the region is 24x32 px and is detected in 1/8 frames. At P4 7 of 16 frames are missed and at P5 1 of 8 (the zeros in the table).
   - This is B1/O2's typical-noise effect.
   - So the geometry needs a floor in pixels. With `max(4P,45) x max(5.3P,60)`, every frame at P3-P20 had a passing core.
4. **The per-region view at short Periods depends on the O3 decision.**
   - The best single region at P3-P6 with CAP 2P is 0.09-0.76, because the region breaks into fragments.
   - An AC measured "per region" and not on the union needs fragments merged (O3-B), or no cap with deduplication.
5. **IoU >= 0.8 is reachable on single-region 512x512 frames** with the following settings. In the table, every Period has worst >= 0.83 on 8 seeds, except P12, which is 0.85 under these settings:
   - semi-axes `max(5P, 45) x max(6.6P, 60)`;
   - FRAC 0.5;
   - a cap that does not bind at short Periods (no cap shown here).

   The margin is about 0.03-0.05 above 0.8 at P 12-20 on these seeds, so the tolerance should stay 0.8, with no tighter value. The two-region frames (256x800 or 400x1600) were not tried. They need the cap question (item 2) settled first.

## Timing (N4): growth step, one shared `_Spectrum` per frame

Single process, `p2_timing.py`. The **machine was loaded** (load average about 15, from other agents). The bank took 7.1-9.7 s here against 7.4 s idle in `bench.json`, so scale the numbers below by about 0.8 to estimate idle times.

| frame | passing cores | growth total | one region | shared spectrum | `gabor_at` (own FFT) |
|---|---|---|---|---|---|
| 512x512, P8, m 0.5 | 6 | 0.40 s | 0.084 s | 0.011 s | 0.040 s |
| 400x1600, P8, m 0.5 | 3 | 0.27 s | 0.077 s | 0.019 s | 0.078 s |
| 400x1600, P8, m 0.2 | 1 | 0.09 s | 0.076 s | 0.019 s | 0.067 s |
| 400x1600, P20, m 0.2 | 6 | 0.52 s | 0.081 s | 0.019 s | 0.067 s |

- Each region costs about 0.08 s at 400x1600.
- Sharing the spectrum saves only the forward FFT, about 0.02 s per region. Most of the per-region cost is the two full-frame inverse FFTs (`gabor` plus `local_mean`) and the full-frame EDT and label.
- Six passing regions add about 0.5 s on top of the 7.4 s bench median. That is within the 10 s limit, but the probe at m 0.2 has up to 6 passing cores.
- If the cost matters, there are two cheap wins:
  - compute the EDT and label on the core's bbox padded by the cap;
  - take `local_mean` once per distinct Period. It does not depend on Angle.
