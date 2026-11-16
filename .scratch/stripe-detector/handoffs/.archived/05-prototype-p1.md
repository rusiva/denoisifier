# 05 prototype P1: blur-corrected size rule

Question (05-plan-review.md, P1, context B1): is there a size measure that, with a blur correction, separates a region at 0.8x the 3x2-Period minimum from one at 1.25x / 1.4x, on every Period and Angle, at mottle "none", Gaussian noise 0.01, m 0.6?

**Answer: yes for width, no for height.**
- **Width**: the sub-pixel half-peak width of the re-tuned depth map, measured in the detector's own Period, separates on every Period and Angle. Cut: **3.24 P**. It does not depend on stripe strength (m 0.3 and 0.6) or on noise (0 and 0.01), and it held on a separate set of check seeds.
- **Height** (along the stripes): no measure separates 0.8x from 1.25x with one cut. The along-stripe window has sigma 1.5 P, so its half-peak height (FWHM) is 2.355 x 1.5 P, about 3.5 P. That is wider than the 2 P minimum, so a region's half-peak height is about 3.6-4.4 P whatever its true height. The 2-Period height minimum cannot be measured with today's filter bank.

AC 5 as planned scales both axes together (`semi_axes = (f*P, 1.5*f*P)`), so a width-only rule passes it. A region 3 P wide but under 2 P tall would still be reported. That breaks the spec's "3x2 Periods" requirement, so it is **an owner decision** (see "Open" below).

## Setup

Script: `/tmp/claude-1000/-home-rusiva-dev-denoisifier/72618a23-dbd5-4573-9e6c-b83c3532a4a4/scratchpad/proto_p1_size_rule.py`. Tables come from `proto_p1_tabulate.py` and `proto_p1_perP.py` in the same directory. Logs and pickles are there too: `fit.pkl`, `hold.pkl`, `p1_none_0.0_0.6.pkl`, `p1_none_0.01_0.3.pkl`, `tab.log`. The first-pass results (no sub-pixel measure) are in `v1/`. Run it with `uv run --locked python <script> NOISE MOTTLE M SEED_START [short]` from the repo.

- **Frame**: 256x256. The profile is `generate(seed, modulation_depth=0, mottle="none", noise=0).clean`, multiplied by `(1 + m * mask * cos(phase))`. The mask is the plan's 2.1 tanh mask with `edge_px = 1` and `semi_axes = (f*P, 1.5*f*P)`, so the 0.5-contour bbox is 2fP tall and 3fP wide. Each seed gets a random stripe phase and a sub-pixel jitter of the centre. Gaussian noise is `noise * 1000`.
- **Grid**: P in {3, 5, 8, 12, 20}; Angle in {-10, 0, +10}; f in {0.6, 0.8, 0.9, 1.0, 1.1, 1.25, 1.4} for the fit set and {0.8, 1.0, 1.25, 1.4} for the others; 8 seeds per cell.
- **Pipeline**: `estimate_local_stripes`, then the `ratio > 154` component that holds the ratio peak (the core). Period and Angle come from the core with the neighbour-product sum (as in `_measure`). `gabor_at` is re-tuned to them, giving the depth map `2|tuned| / mean`. Everything is measured in units of the estimated Period.
- **Measures**:
  - `core`: bbox of the core at T (plan Q2-A).
  - `hd_med`: bbox of the core grown to depth >= 0.5 x the median depth on the core, inside a 2P dilation (plan 2.3 step 2, Q2-B).
  - `hd_pk`: the same grow with 0.5 x the peak depth.
  - `hd_sub`: the **sub-pixel** half-peak width and height, taken from linear-interpolated crossings of 0.5 x the peak depth along the row and the column through the depth peak on the core.
- **Detection**: every frame at f >= 0.8 was detected (max ratio > 154) in every set. At f = 0.6, 4 of 24 frames were missed at P 8 and at P 12.

## Results: one cut fitted on the fit set, then applied to the check sets

The cut is the geometric midpoint of max(0.8x) and min(1.25x) on the fit set.

| measure | axis | fit: max 0.8x / min 1.25x | cut | hold-out (m .6, n .01) | noise 0 (m .6) | m 0.3 (n .01) |
|---|---|---|---|---|---|---|
| core at T | w | 5.45 / 6.35 | 5.89 P | separates | separates | **26/120 1.25x fail** |
| core at T | h | 7.44 / 6.70 | overlap | | | |
| hd_med bbox | w | 4.85 / 5.43 | 5.13 P | separates | separates | **49/120 1.25x fail** |
| hd_med bbox | h | 6.71 / 6.52 | overlap | | | |
| hd_pk bbox | w | 3.14 / 3.27 | 3.21 P | **overlap** (0.8x max 3.20, 1.25x min 3.18) | separates | separates |
| hd_pk bbox | h | 4.27 / 3.79 | overlap | | | |
| **hd_sub** | **w** | **3.09 / 3.40** | **3.24 P** | **0/120 0.8x pass, 0/120 1.25x fail, 0/120 1.4x fail** | same, all 0 | same, all 0 |
| hd_sub | h | 4.25 / 3.85 | overlap | 21 pass / 79 fail | 23 / 75 | 23 / 75 |

What the table shows:
- **core at T and hd_med depend on stripe strength.** The core grows with the ratio, and hd_med's level is taken over the core. Both separate at m 0.6 but fail at m 0.3, so each would be a rule for one depth only. This confirms B1's point about Q2-A, and it also rules out the plan's Q2-B level (the median on the core).
- **The bbox version of the half-peak extent is pixel-quantised.** At P 3, one pixel is 0.33 P. Measuring it sub-pixel (`hd_sub`) removes that and makes it separate.
- **hd_sub width over all four sets** (480 frames per factor): max(0.8x) is 3.13 and min(1.25x) is 3.40. At the 3.24 cut the margins are **x1.035 below and x1.049 above**. Against 1.4x (min 3.66) the margin above is x1.13.

### hd_sub width per Period and Angle, all four sets pooled (32 frames per cell)

| P | Angle | max 0.8x | range 1.0x | min 1.25x | min 1.4x | cut/max(0.8x) | min(1.25x)/cut | h: max 0.8x, min 1.25x |
|---|---|---|---|---|---|---|---|---|
| 3 | -10 | 2.95 | 3.07-3.17 | 3.45 | 3.73 | 1.098 | 1.064 | 3.72, 3.85 |
| 3 | 0 | 2.90 | 3.03-3.14 | 3.42 | 3.73 | 1.115 | 1.055 | 3.75, 3.88 |
| 3 | +10 | 2.93 | 3.06-3.16 | 3.42 | 3.75 | 1.104 | 1.056 | 3.72, 3.84 |
| 5 | -10 | 3.01 | 2.99-3.20 | 3.40 | 3.71 | 1.078 | 1.050 | 3.70, 3.84 |
| 5 | 0 | 2.92 | 2.98-3.12 | 3.40 | 3.66 | 1.111 | 1.050 | 3.73, 3.89 |
| 5 | +10 | 2.98 | 2.99-3.20 | 3.41 | 3.72 | 1.088 | 1.053 | 3.70, 3.86 |
| 8 | -10 | 3.07 | 2.98-3.19 | 3.41 | 3.70 | 1.055 | 1.051 | 3.74, 3.90 |
| 8 | 0 | 2.94 | 2.97-3.13 | 3.40 | 3.68 | 1.102 | 1.049 | 3.78, 3.94 |
| 8 | +10 | 3.04 | 2.99-3.20 | 3.40 | 3.69 | 1.065 | 1.050 | 3.74, 3.91 |
| 12 | -10 | 3.05 | 3.01-3.23 | 3.44 | 3.75 | 1.062 | 1.061 | 3.85, 4.03 |
| 12 | 0 | 2.95 | 3.00-3.15 | 3.42 | 3.71 | 1.097 | 1.057 | 3.89, 4.05 |
| 12 | +10 | 3.04 | 2.99-3.24 | 3.42 | 3.76 | 1.067 | 1.056 | 3.85, 4.01 |
| 20 | -10 | 3.09 | 3.16-3.34 | 3.64 | 3.97 | 1.047 | 1.124 | 4.20, 4.36 |
| 20 | 0 | 3.05 | 3.13-3.28 | 3.57 | 3.95 | 1.064 | 1.103 | 4.27, 4.40 |
| 20 | +10 | 3.13 | 3.17-3.34 | 3.61 | 3.98 | 1.036 | 1.114 | 4.19, 4.34 |

At P 20 the widths run about 0.1-0.2 P higher than at P <= 12. The likely cause is the profile's curvature under a 20-30 px window in a 256 frame. The noise-free, flat-envelope reference shows the same 3.0 -> 3.1 P drift.

Two ways to correct for this, compared:
- Normalising by a per-Period reference (the median at 1.0x from the fit set: 3.10, 3.10, 3.11, 3.12, 3.20) gives margins of x1.052 on both sides.
- A single cut gives margins of x1.035 below and x1.049 above.

Not worth the extra table. Use the single cut.

The width ranges at 0.8x and 1.0x overlap. The measure's spread (about ±0.1 P, about ±0.07 in f) is too large to resolve 20%, which is why the cut sits at about f = 1.05-1.1 rather than exactly at 1.0.

## Candidate module constants

Each needs approval as a lockfile addition, batched under section 5 of the plan.

- `MIN_HALF_DEPTH_WIDTH_PERIODS = 3.24`: report a core only if the sub-pixel half-peak width of its re-tuned depth (across the frame's columns, through the depth peak on the core) is at least 3.24 x the measured Period. In correction-factor form, this is 1.08 x the spec's 3 P. On a region exactly 3 P wide this measure gives about 3.1 P (analytic, noise-free: 3.0-3.1 P), so the rule reports from about 1.05x the minimum upward.
- **Height:** no constant separates. The 0.8x maximum is 3.77 at P <= 8 and 4.27 at P 20; the 1.25x minimum is 3.84 overall. If the owner keeps a height test, the most it can do without failing 1.25x/1.4x is a permissive floor of about `3.6 P` on the same sub-pixel half-peak height. That floor rejects almost nothing, because the window's own height is about 3.5 P.
- The fraction 0.5 (half of the core's **peak** depth, not its median) is part of the measure, not a tuning knob.

## AC 5 margins that separate cleanly

- **0.8x vs 1.25x, width:** passes with the cut above. Margins are only 3.5-5%, but they held on hold-out seeds, on noise 0, and on m 0.3.
- **0.8x vs 1.4x:** width margin is x1.035 below and x1.13 above. This is the safer test pair if the owner prefers headroom.
- **Test conditions:** mottle "none", Gaussian noise <= 0.01, m 0.6 (B1 (a)). At typical (scorched, Emccd) noise, near-minimum regions are not detected at all; this was not re-tested here (see the reviewer's p4/p5, and O2).

## Open, for the orchestrator or owner

1. **Height minimum.** The spec's 2-Period height cannot be told apart from about 1.6 P with today's along-stripe window (sigma 1.5 P). The options:
   - (A) A width-only size rule. Record the along-stripe resolution limit in the docstring and the handoff. AC 5 as written passes.
   - (B) A permissive height floor of about 3.6 P on the half-peak height (practically the same as A).
   - (C) Narrow `_ALONG`. That is a detector redesign, outside ticket 05, and needs `make measure`.

   Recommend A. Because it changes an agreed requirement ("3x2 Periods"), it goes to the owner.
2. **Consistency with Q1-B / B4.** If the score must use the same component test, each candidate component needs a re-tuned `gabor_at` (two FFTs) at each level it is tested at. That makes a T-free candidate construction (B4's second option) more attractive than a descending sweep. Cost: one `_Spectrum` per frame (N4).
3. **Not covered here:**
   - the two-region case (whether a neighbour's leak widens the half-peak width);
   - estimated-Period errors at m 0.2;
   - Mottle;
   - frames other than 256x256.

   The width measure runs through the estimated Period, so a Period error scales the measured width by the same factor.
4. **Seeds used** (all passed to `generate`; the noise RNG is `default_rng(seed + 11)`): 390_000-390_007 (fit; run twice, same frames), 390_100-390_107, 390_200-390_207, 390_300-390_307. Add them to `USED_SEEDS` (or keep clear of them) when B3's calibration range is chosen. The fit set doubles as a calibration set for the 3.24 constant, so the constant was not tuned on test seeds. If the implementer re-derives it, it must be done inside a registered calibration range under `seed_guard.calibrating(...)` (B3).

No commits; throwaway code only, in the scratchpad.

## Follow-up: option D, height from a separate short-along filter

Question (coordinator): leave the detection bank as it is. For the size test only, re-tune one extra filter at the candidate's measured Period and Angle with a short along-stripe window (sigma_along = SA x P, with SA in {0.5, 0.75, 1.0}; across stays 1 P). Take the sub-pixel half-peak height along the column through that filter's depth peak on the core. Does one height cut separate 0.8x from 1.25x and 1.4x on every Period and Angle? Does width still separate?

**Answer: yes.** One cut separates at every SA tried, on every Period and Angle, at low noise with no Mottle. **SA = 0.5 is the clear choice**: its margins are about x1.10 on both sides, against x1.05 for SA 0.75 and x1.01 for SA 1.0. Width at 3.24 P still separates. Today's window (SA 1.5) fails again, as before. Cost: about 7-17 ms per candidate at 256x256 and 55-92 ms at 400x1600, with one shared `_Spectrum` per frame (27-44 ms at 400x1600).

### Setup

- **Script**: `/tmp/claude-1000/-home-rusiva-dev-denoisifier/72618a23-dbd5-4573-9e6c-b83c3532a4a4/scratchpad/proto_p1d_height.py` (`uv run --locked python <script> low|typical SEED_START`). Tables come from `proto_p1d_tab.py` in the same directory. Output is in `p1d_tab.log`, `p1d_*.log` and `p1d_*.pkl` there.
- **Pipeline**: the same as P1 (core at T=154, neighbour-product Period and Angle). The extra filter is the bank's Gabor formula with `_ALONG` replaced by SA, plus its own local mean (the same window at DC). Depth = `2|resp| / mean`. With SA = 1.5 it reproduces `gabor_at` to 1e-17.
- **Shapes**, with f in {0.8, 1.0, 1.25, 1.4}:
  - "both": `semi_axes = (f*P, 1.5*f*P)`.
  - "short": `semi_axes = (f*P, 2*P)`, so 4 P wide and 2fP tall.
- **Grid**: P {3, 5, 8, 12, 20} x Angle {-10, 0, +10}; 8 seeds per cell; `edge_px = 1`; m 0.6.
- **Regimes**:
  - low: no Mottle, Gaussian noise 0.01. Fit set 391_000-391_007, hold-out set 391_100-391_107.
  - typical: scorched Mottle, `_emccd` at 100 photons peak, `Emccd()`. Seeds 391_200-391_207.
- **Fitting**: the cut is the geometric midpoint of max(0.8x) and min(1.25x) on the fit set, with both shapes pooled (240 frames per factor).
- **Detection**: every frame was detected in both low-noise sets.

### Height, low noise (AC 5 regime)

| SA | ref h at 1.0x (median, both / short) | fit: max 0.8x / min 1.25x / min 1.4x | cut | margins | hold-out: 0.8x pass, 1.25x fail, 1.4x fail |
|---|---|---|---|---|---|
| **0.5** | 1.885 / 1.918 | 1.753 / 2.124 / 2.394 | **1.93 P** | x1.101 / x1.101 | 0/240 (max 1.762), 0/240 (min 2.135), 0/240 (min 2.391) |
| 0.75 | 2.246 / 2.267 | 2.193 / 2.411 / 2.616 | 2.30 P | x1.048 / x1.048 | 0/240 (max 2.204), 0/240 (min 2.416), 0/240 |
| 1.0 | 2.722 / 2.734 | 2.770 / 2.851 / 3.005 | 2.81 P | x1.014 / x1.014 | 0/240 (max 2.773), 0/240 (min 2.847), 0/240 |
| 1.5 (today) | 3.81 | 4.261 / 3.844 | overlap | | 48/240 pass, 148/240 fail |

With SA 0.5, an exactly 2 P tall region measures about 1.9 P, so the blur correction is almost nil. The cut 1.93 P is 0.965 x 2 P, which is about 1.0x the reference. The "both" and "short" shapes give the same height, so a region's width does not leak into its height.

**SA 0.5 per Period and Angle (hold-out set, 16 frames per cell, shapes pooled).** The last two columns are cut/max(0.8x) and min(1.25x)/cut.

| P | Angle | max 0.8x | min 1.25x | min 1.4x | cut/max | min/cut |
|---|---|---|---|---|---|---|
| 3 | -10 | 1.70 | 2.24 | 2.53 | 1.132 | 1.161 |
| 3 | 0 | 1.66 | 2.22 | 2.47 | 1.163 | 1.151 |
| 3 | +10 | 1.72 | 2.25 | 2.51 | 1.124 | 1.168 |
| 5 | -10 | 1.72 | 2.19 | 2.48 | 1.124 | 1.135 |
| 5 | 0 | 1.68 | 2.13 | 2.41 | 1.146 | 1.106 |
| 5 | +10 | 1.73 | 2.20 | 2.50 | 1.116 | 1.141 |
| 8 | -10 | 1.72 | 2.17 | 2.43 | 1.124 | 1.122 |
| 8 | 0 | 1.66 | 2.14 | 2.39 | 1.163 | 1.110 |
| 8 | +10 | 1.73 | 2.15 | 2.45 | 1.112 | 1.112 |
| 12 | -10 | 1.73 | 2.16 | 2.47 | 1.116 | 1.119 |
| 12 | 0 | 1.67 | 2.16 | 2.44 | 1.158 | 1.119 |
| 12 | +10 | 1.75 | 2.16 | 2.46 | 1.104 | 1.121 |
| 20 | -10 | 1.76 | 2.34 | 2.62 | 1.095 | 1.211 |
| 20 | 0 | 1.70 | 2.30 | 2.59 | 1.137 | 1.194 |
| 20 | +10 | 1.74 | 2.35 | 2.63 | 1.106 | 1.216 |

SA 0.75 on the same cells: the margins are x1.043-1.099 below and x1.051-1.148 above. The tightest cells are P 20 at 0.8x and P 5-8 at 1.25x.

### Width, rechecked on the new seeds (cut 3.24 P, today's window)

| set | "both" 0.8x passing | "both" 1.25x failing | "both" 1.4x failing | "short" (4 P wide) failing |
|---|---|---|---|---|
| low, fit | 0/120 (max 3.10) | 0/120 (min 3.385) | 0/120 | 0/480 (min 3.52) |
| low, hold-out | 0/120 (max 3.12) | 0/120 (min 3.38) | 0/120 | 0/480 (min 3.52) |
| typical | 0 detected | 0/19 | 0/34 | 1/80 (min 3.19) |

### Typical scorched noise (information only)

Detected out of 120 frames per shape and factor:

| shape | 0.8x | 1.0x | 1.25x | 1.4x |
|---|---|---|---|---|
| both | 0 | 2 | 19 | 34 |
| short | 5 | 13 | 23 | 39 |

This confirms O2: near the minimum, regions are mostly below detection.

With SA 0.5 and the 1.93 cut, on the detected frames:
- 1.25x: 0/42 fail on height.
- 1.4x: 0/73 fail on height.
- 0.8x: **1/5 pass on height** (h 2.30). It is a "short" region, 4 P wide, so it also passes width and would be reported. That is 1 of 240 0.8x frames.

The few 0.8x frames that are detected at all are the ones where noise inflated the response (selection bias). At typical noise the size test is therefore not clean. It is clean only in the AC 5 regime (low noise).

### Timing of the extra filter

Measured on random frames, before each run. It is noisy because other runs were loading the machine.

| frame | per candidate, on a shared `_Spectrum` (resp + local mean = 2 inverse FFTs) | `_Spectrum`, once per frame |
|---|---|---|
| 256x256 | 7-17 ms | 4-11 ms |
| 400x1600 | 55-92 ms | 27-44 ms |

Probe frames give 0-5 passing components at T (N4), so this adds roughly 0.1-0.5 s on 400x1600 against the 10 s limit (last bench median 7.4 s). Build the `_Spectrum` once per frame and share it with the width re-tune (N4).

### Candidate constants

Each is a lockfile addition and needs approval.

- `SIZE_ALONG_PERIODS = 0.5`: the along-stripe window sigma, in Periods, of the size-test filter only.
- `MIN_HALF_DEPTH_HEIGHT_PERIODS = 1.93`: the cut on the sub-pixel half-peak height of that filter's depth. This is 0.965 x the spec's 2 P; reference at exactly 2 P: about 1.90.
- `MIN_HALF_DEPTH_WIDTH_PERIODS = 3.24`: unchanged, measured with the bank's own window.

### Open

1. Option D keeps "3x2 Periods" enforceable on both axes in the AC 5 regime. That removes the need for the owner decision in Open item 1 above. It still needs approval of the new constants, and the docstring must say that the size test uses its own short-window filter.
2. Not covered:
   - the two-region case (whether a neighbour's leak raises the short filter's height);
   - Mottle at low noise;
   - frames other than 256x256;
   - whether the core-peak column misses the region's centre in elongated or tilted cores. The sub-pixel crossing runs through the depth peak of the short filter on the core.
3. **Seeds used** (all passed to `generate`; the noise RNG is `default_rng(seed + 11)`): 391_000-391_007, 391_100-391_107, 391_200-391_207.
