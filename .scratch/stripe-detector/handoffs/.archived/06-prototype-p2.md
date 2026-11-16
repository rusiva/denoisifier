# 06 prototype P2: handoff summary

Full write-up, tables and per-frame data: `.scratch/stripe-detector/evidence/06-prototype-p2.md` (with `.py`, `-summary.py`, `.json`, `.txt`, `-first-pass.py/.txt`). BASE 4e40bdd, seeds 396_000-396_099 only (none are calibration seeds or the critic's 700_*). Script: `.scratch/stripe-detector/evidence/06-prototype-p2.py` (modes rule / guard / free).

## Answers

- **P2 at the plan's 0.8:**
  - Full frames keep enough valid pixels (0 fallbacks).
  - Partial regions fall back on 8/11 frames at 10 photons and 3/19 at 30 photons.
  - Plain (no exclusion) is within DEPTH_TOL everywhere (worst error 0.031 at 30 photons and above). **D9 as planned adds misses on partial regions** (3/11, 3/19 and 3/20 at 10, 30 and 100 photons; errors to -0.23), because it measures the soft-edge rim.
  - 0.8 has no teeth: the flattened clean depth error is 0.015 or less.
- **Generator-side rule (critic Q4):** no single fraction gives teeth on all frames.
  - With depth <= 0.35 (0.05 margin), the fraction is 0.10 for full frames and 0.20 for partial ones.
  - Per frame, the rule gives f = 0.12-0.36 (full) and 0.23-0.45 (partial).
- **At teeth levels (rule, 0.4, 0.3):**
  - No mechanism holds DEPTH_TOL on partial regions: 6-20 misses per 20, because the clipped core is the region's core.
  - The weighted fits are the worst: global fit over the region or bbox 34-40/40 misses on full frames at 100 photons; local normalised convolution 12-19/40. They are biased even noise-free, through the envelope gradient correlated with the clipped phase.
  - The best variant is **d9_inner_g10**: the region's own interior minus pixels with `gaussian_filter(clipped, (1.5P, P)) >= 0.10`. On full frames it misses 0/40 at 0.3 and 0.4 for 100 and 5000 photons, 0/39 at 0.4 for 30 photons, and 3/40 at the rule level for 100 photons. At 0.8 it is never worse than plain.
- **Stripe-free (critic O2):** clipped frames score higher than unclipped ones on 7-22 of 40 frames, by up to +41.
  - One frame crosses GATE_STORED_THRESHOLD (49.7) at a clip of 0.6 or below (100 photons) and 0.3 or below (30 photons).
  - None reaches 154, and there are 0 regions.
  - "Never higher" fails as a strict statement.
- **Second harmonic:** 0 regions at P/2, 0 Period or Angle failures, and 0 extra regions on 960 clipped frames.
- **B4:** every partial frame at 0.8 has clipped pixels inside the truth region (at least 10, mostly noise excursions).

## Recommendation

1. **Replace D9 with d9_inner_g10.** Take the region's own interior, drop window-contaminated pixels (Gaussian local_mean window, weight >= 0.10), and fall back to plain when nothing is left. The 0.10 cutoff is one tried value, a start value.
2. **AC 4 cannot both have teeth and pass on partial regions.** Orchestrator or owner call:
   - Full-frame AC 4 at a fixed 0.3 or 0.4: 0/40 vs plain's 3-4/40, but the generator rule holds there on only 0-12% of frames. At the per-frame rule level, 3/40 still miss.
   - Partial AC 4: either a mild clip labelled "no teeth", or "not worse than flattened" plus a documented limit (a saturated core loses its depth).
3. **The stripe-free AC needs a tolerance,** not "never higher".
