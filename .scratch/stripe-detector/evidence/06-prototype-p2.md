# 06 prototype P2: clipped pixels and the modulation depth

**Corrections (2026-11-13, from `.scratch/stripe-detector/handoffs/06-critic-2.md`; the tables below are unchanged and were recounted there):**
1. "The information is gone" on partial regions (section "Answer and recommendation") is wrong. At clips of 0.3-0.4 the troughs survive in nearly every cycle (74-100% of interior pixels have clipped peaks and intact troughs at 0.4, seeds 396_400-396_405, noise-free). The limit is the estimator's, not the frame's.
2. "Clipped stripe-free frames score higher" (section 4) leaves out that about as many score lower: the mean paired change is near zero (-1.84 to +3.37 per level, median 0.00 except +0.60 at 30 photons, 0.3).

Questions: plan-review P2 and B4 (`handoffs/06-plan-review.md`), and the coordinator's additions from the critic's Q4/O2 (`handoffs/06-critic.md`).

1. With D7 auto clip detection and the D9 guard, are enough unclipped pixels left?
2. Does the depth then stay within `DEPTH_TOL` (0.1) of the truth (AC 4)?
3. Is there a clip fraction with teeth, fixed on the generator side?
4. D9 compared with weighted fits of mean, cos and sin.
5. Do clipped stripe-free frames score higher than unclipped ones?
6. Does the second harmonic become a region?

BASE `4e40bdd`, nothing in `src/` edited (D9 and the alternatives are monkeypatched into `analysis._settle_overlaps`).

- **Seeds:** 396_000-396_099 only (plan reservation `range(396_000, 396_400)`). The script asserts that none is a calibration seed or one of the critic's 700_000-700_005 / 700_100-700_139.
- **Run:** idle machine, 12 workers, about 20 min for the guard grid.
- **Clipping:** EMCCD frames are clipped as plan D3 does it, `np.minimum(frame, frac * photons_peak)`, where `photons_peak == clean.max()`. There are no spikes.

## Files

All under `.scratch/stripe-detector/evidence/`:

- `06-prototype-p2.py`: modes `rule`, `guard`, `free`.
- `06-prototype-p2-summary.py`: prints the tables.
- `06-prototype-p2.json`: every frame of the rule, guard and free runs (the first pass keeps only its summary).
- `06-prototype-p2.txt`: the full summary tables.
- `06-prototype-p2-first-pass.py` / `.txt`: first pass at the plan's fractions 0.6-0.9, with D9 box and Gaussian variants.

```
uv run --locked python .scratch/stripe-detector/evidence/06-prototype-p2.py rule  rule.json
uv run --locked python .scratch/stripe-detector/evidence/06-prototype-p2.py guard guard.json 0 0.4 0.3 0.8   # 0 = per-frame rule level
uv run --locked python .scratch/stripe-detector/evidence/06-prototype-p2.py free  free.json 0.8 0.6 0.4 0.3 0.2
python .scratch/stripe-detector/evidence/06-prototype-p2-summary.py guard.json free.json rule.json
```

## Frames

- **Full:** 256x256 typical (scorched, EMCCD), m = 0.5, `CASES[seed % 10]`, seeds 396_000-396_039.
- **Partial:** the `regions.single_region` geometry (512x512, B4's case), seeds 396_040-396_059.
- **Signal levels:** `photons_peak` 10, 30, 100 and 5000.
- **Stripe-free:** seeds 396_060-396_099 at 30 and 100 photons.

## Depth variants (per reported region)

| Name | What |
|---|---|
| plain | today's `_interior_depth` on the clipped frame (no exclusion; the "flattened" depth) |
| d9_plan | plan D9: interior of `pixels & (box mean of clipped < 0.01)`, box 2σ (121x81 at P = 20) |
| d9_gauss02 | as D9, weight = `gaussian_filter(clipped, (1.5P, P))` (the local_mean window), < 0.02 |
| d9_inner_box | the region's **own** interior first (as today), then drop pixels with box weight >= 0.01 |
| d9_inner_g10 | the region's own interior, then drop pixels with Gaussian-window weight >= 0.10 |
| fit_region / fit_bbox | critic's proposal: global weighted LSQ of mean, cos, sin at the reported Period and Angle, clipped weight 0, over the region's pixels / its bounding box; depth = hypot(b, c) / a |
| local_fit | the same fit per pixel with the local_mean window (normalised convolution); median over the region interior where the unclipped share of the window is >= 0.5 |
| local_cens | local_fit that also drops pixels whose fitted value is within 2 local σ of the level (censoring correction), 3 passes |

Fallback means no pixel is left, and the plain (flattened) depth is reported.

## 1. Generator-side rule (no detector)

Depth of `np.minimum(clean, f * clean.max())` on the noise-free frame, Gabor at the true Period and Angle, median over the interior (light, or truth region ∩ light). The error is against 0.5.

| f | full: median err, worst | full: frames <= -0.15 | partial: median err, worst | partial: frames <= -0.15 |
|---|---|---|---|---|
| 0.8 | -0.001, -0.008 | 0% | -0.002, -0.015 | 0% |
| 0.6 | -0.007, -0.024 | 0% | -0.016, -0.040 | 0% |
| 0.5 | -0.016, -0.062 | 0% | -0.052, -0.102 | 0% |
| 0.4 | -0.037, -0.123 | 0% | -0.113, -0.218 | 45% |
| 0.3 | -0.092, -0.205 | 12% | -0.237, -0.365 | 65% |
| 0.25 | -0.141, -0.250 | 47% | -0.325, -0.438 | 85% |
| 0.2 | -0.205, -0.304 | 75% | -0.414, -0.488 | 100% |
| 0.15 | -0.277, -0.373 | 95% | -0.474, -0.500 | 100% |
| 0.1 | -0.359, -0.468 | 100% | -0.498, -0.500 | 100% |

- **No single fraction gives teeth on every frame.** With a 0.05 margin (depth <= 0.35), the fraction is 0.10 for full frames and 0.20 for partial ones. The spread comes from Mottle: the clean maximum sits on one bright spot.
- **The rule is therefore applied per frame**: the highest f, found by bisection, with flattened clean depth <= 0.35. It gives f = 0.12-0.36 (median 0.24) on full frames and 0.23-0.45 (median 0.36) on partial ones.
- **The plan's start value of 0.8 has no teeth.** The flattened depth error is 0.015 or less.

## 2. Plan's fraction (0.8): P2 as asked

Table cells are misses, where a miss is |err| > 0.1, out of reported regions, with fallbacks in parentheses.

| photons | full plain | full d9_plan | partial plain | partial d9_plan | partial d9_inner_g10 |
|---|---|---|---|---|---|
| 10 | 0/27 | 0/27 (0) | 0/11 | **3/11 (8)** | 0/11 (1) |
| 30 | 0/39 | 0/39 (0) | 0/19 | **3/19 (3)** | 0/19 (0) |
| 100 | 0/40 | 0/40 (0) | 0/20 | **3/20 (0)** | 0/20 (0) |
| 5000 | 0/40 | 0/40 (0) | 0/20 | 0/20 (0) | 0/20 (0) |

- **Enough pixels left:**
  - Full frames: always (no fallback at any level).
  - Partial regions at 10 photons: D9 falls back on 8 of 11 frames. At 30 photons it falls back on 3 of 19.
- **Depth:**
  - The plain depth is within tolerance everywhere. At 30 photons and above the worst error is 0.031.
  - D9 as planned **adds** misses on partial regions, with errors to -0.23. It measures the interior of `pixels & valid`, which on a partial region with a clipped centre is the soft-edge rim. That rim sits in the across-window skirt, where the depth is low.
- **The first pass at 0.6, 0.7 and 0.9** shows the same picture (`06-prototype-p2-first-pass.txt`). The plain depth is never a miss on full frames, and there are 2 partial misses at 10 photons, 0.6. Every D9-style variant adds partial misses: up to 10/19 at 30 photons, 0.6.
- **B4:** every partial frame at 0.8 has clipped pixels inside `truth_pixels(region)`. The minimum is 10 px at 5000 photons and 37 at 100. The B4 precondition is satisfiable, but these are mostly noise excursions, not flattened peaks.
- **D7 detection:**
  - Exact (equal to `frame >= level`) on every frame at <= 0.8, except 1/40 at 5000 photons.
  - At 0.9 and 5000 photons, fewer than 4 pixels reach the level, so nothing is detected. That is 13/40 frames, and the depth is unaffected.

## 3. Levels with teeth: rule level, 0.4, 0.3

Misses out of reported regions:

| geometry, photons | level | plain | d9_plan | d9_gauss02 | d9_inner_g10 | fit_region | fit_bbox | local_fit | local_cens |
|---|---|---|---|---|---|---|---|---|---|
| full 10 | rule | 24/24 | 24/24 | 22/24 | 16/24 | 24/24 | 24/24 | 24/24 | 24/24 |
| full 30 | rule | 17/38 | 15/38 | 15/38 | **6/38** | 38/38 | 38/38 | 34/38 | 37/38 |
| full 100 | rule | 5/40 | 8/40 | 8/40 | **3/40** | 40/40 | 40/40 | 19/40 | 21/40 |
| full 5000 | rule | 2/40 | 6/40 | 2/40 | **1/40** | 40/40 | 40/40 | 10/40 | 10/40 |
| full 30 | 0.4 | 13/39 | 4/39 | 0/39 | **0/39** | 38/39 | 39/39 | 31/39 | 30/39 |
| full 100 | 0.4 | 4/40 | 2/40 | 1/40 | **0/40** | 34/40 | 35/40 | 16/40 | 16/40 |
| full 100 | 0.3 | 3/40 | 6/40 | 4/40 | **0/40** | 40/40 | 40/40 | 12/40 | 12/40 |
| full 5000 | 0.3 | 2/40 | 3/40 | 2/40 | **0/40** | 36/40 | 40/40 | 9/40 | 10/40 |
| partial 30 | rule | 20/20 | 20/20 | 20/20 | 18/20 | 20/20 | 20/20 | 20/20 | 18/20 |
| partial 100 | rule | 19/20 | 20/20 | 20/20 | 13/20 | 20/20 | 20/20 | 20/20 | 16/20 |
| partial 100 | 0.4 | 13/20 | 15/20 | 16/20 | **6/20** | 20/20 | 20/20 | 15/20 | 13/20 |
| partial 5000 | 0.4 | 11/20 | 17/20 | 14/20 | **6/20** | 16/20 | 20/20 | 13/20 | 10/20 |

All rows are in `06-prototype-p2.txt`.

**The weighted fits:**

- **The global fits** (critic's proposal) are the worst variant everywhere. Error medians run from -0.12 to -0.30. Over a region or a bounding box the envelope (profile and Mottle) varies a lot. Clipping removes the bright peaks, so the pixels left are troughs in bright areas and full cycles in dim ones. The envelope is then correlated with cos φ, and a, b, c come out biased.
- **The bounding-box fit** adds the region's unstriped surround and misses even at 0.8: 15/20 partial at 100 photons.
- **The local fit** (normalised convolution, the plan's rejected option (b)) is better than the global fit but worse than plain at every teeth level.
  - It is biased even noise-free. On partial 396_041 at f = 0.4 it gives 0.33 (global fit 0.25). On full 396_003 at f = 0.25 it gives 0.44.
  - So the loss is not noise censoring. The censoring correction (`local_cens`) did not help either.
  - The cause is the envelope gradient inside the window, together with whole clipped cycles.

**The guards:**

- **D9 as planned** is about as good as plain on full frames and worse on partial ones. At the rule level it mostly falls back.
- **d9_inner_g10** is the best variant at every level, and at 0.8 it is never worse than plain. It holds `DEPTH_TOL` on full frames at 0.3-0.4 for 30 photons and up, and at 100 photons and up at the per-frame rule level (3/40).
  - It fails at 10 photons, where the depth noise is already large.
  - It fails on **partial regions at any level with teeth** (6-18 misses per 20). The clipped core is the region's core, so nothing unflattened is left in the interior, and the 12-18 fallbacks are flattened depths.
- **The detector's grown region already avoids the clipped core.** On full frames at the rule level, plain misses only 5/40 at 100 photons, although the generator rule (median over the whole light) puts every frame <= 0.35. The clipped core has a low depth, so `_grow` leaves it out. This is why full-frame teeth are weak for the real detector: the rule's teeth are not the detector's teeth.

## 4. Stripe-free frames, clipped and unclipped (paired, 40 seeds per level; "higher" = rise > 0.001)

| photons | clip | score higher than unclipped | max rise | max score | > GATE_STORED_THRESHOLD 49.7 | regions |
|---|---|---|---|---|---|---|
| 30 | none | - | - | 31.4 | 0 | 0 |
| 30 | 0.8 | 12/40 | +24.1 | 31.4 | 0 | 0 |
| 30 | 0.6 | 22/40 | +24.0 | 36.8 | 0 | 0 |
| 30 | 0.4 | 16/40 | +26.6 | 39.4 | 0 | 0 |
| 30 | 0.3 | 20/40 | +40.6 | 60.7 | **1** | 0 |
| 30 | 0.2 | 22/40 | +34.6 | 54.2 | **1** | 0 |
| 100 | none | - | - | 36.2 | 0 | 0 |
| 100 | 0.8 | 7/40 | +21.0 | 36.2 | 0 | 0 |
| 100 | 0.6 | 13/40 | +27.1 | 54.7 | **1** | 0 |
| 100 | 0.4 / 0.3 | 18/40 / 19/40 | +34.2 / +36.3 | 54.7 | **1** | 0 |
| 100 | 0.2 | 17/40 | +31.0 | 43.8 | 0 | 0 |

- **"Must not score higher" fails as a strict paired statement.** About 20-55% of clipped frames score higher (7-22 of 40), by up to +41, with no exclusion before detection.
  - Nothing reaches `THRESHOLD` (154), and no frame gets a region.
  - One frame per level crosses the 1% working point (49.7), at 0.6 or below at 100 photons and at 0.3 or below at 30 photons.
  - The plateau's straight edges are the likely source; this was not separated here.
- At the plan's 0.8 the maximum score does not move. The rises are among low scores.

## 5. Second harmonic

Across all 960 guard frames (every level, both geometries): **0** regions at P/2, **0** Period or Angle failures, and **0** frames with more than one region. The stripe-free clipped frames give 0 regions. The second harmonic does not become a region.

## Answer and recommendation

- **P2:** at the plan's 0.8, enough pixels are left on full frames.
  - On partial regions at 10 photons the D9 guard falls back on 8/11 frames (3/19 at 30 photons).
  - More important, D9 itself causes AC 4 misses on partial regions (3/20 at 100 photons, errors to -0.19), where plain has none.
  - 0.8 has no teeth: the flattened depth is within 0.03.
- **At levels with teeth, no tested mechanism holds `DEPTH_TOL` on partial regions.** The clipped core is the region's core, and the information is gone. Normalised convolution and the global weighted fit are worse than doing nothing. The weighted fit is not the answer.
- **Smallest change to D9:**
  - Measure on the region's own interior (as today) minus pixels whose local_mean-window weight `gaussian_filter(clipped, (1.5P, P))` is >= 0.10, and fall back to the plain interior when nothing is left (d9_inner_g10).
  - It is one `gaussian_filter` per reported region and needs no new box geometry.
  - It is never worse than plain at 0.8, and it is the best variant at every level.
  - It was tried at one cutoff only (0.10), so the cutoff is a start value, not a tuned one.
- **AC 4 as the plan words it cannot have teeth and pass on partial regions.** Proposal for the orchestrator:
  - **Full-frame AC 4:** typical (100 photons), with a per-frame generator-side precondition that the flattened clean depth is <= 0.35. d9_inner_g10 misses 3/40 there and plain misses 5/40, so the test would be red on some seeds. A fixed 0.3 or 0.4 gives 0/40 for d9_inner_g10 against 3-4/40 for plain, but the generator rule holds there only on 0-12% of full frames.
  - **Partial-region AC 4:** either keep it at a mild clip, honestly labelled "no teeth", or assert only that the depth is not worse than the flattened depth, and state the limit (a saturated core loses its depth) in the docstring.
  - Either way this changes the ticket's AC 4 and so is an owner or orchestrator decision.
  - Any stripe-free AC must be a tolerance (for example, the verdict at `GATE_STORED_THRESHOLD` unchanged on most seeds), not "never higher".
