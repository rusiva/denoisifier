# 06 critic 2: AC 4's test and the clipped stripe-free score

Read at BASE `4e40bdd` plus the uncommitted plan, critic and P2 prototype. No tracked file was edited. The only file written is this one.

**Bottom line:** no item blocks on the owner. Two of the prototype's statements are wrong or incomplete and must not go into docstrings or the ticket as written:

1. "The information is gone" on partial regions is **not** true. At clips of 0.3-0.4 the troughs survive in almost every cycle (check below). The limit is the estimator's, not the sensor's.
2. "Clipped stripe-free frames score higher" leaves out that about as many score **lower**. The mean change is near zero.

## Checks I ran

**Recount of `evidence/06-prototype-p2.json`** (no generator code): every miss count I recomputed matches the prototype's tables (full and partial, plain and d9_inner_g10, all levels).

Extra numbers from the same file, full frames, 100 photons:

| Clip | Mean abs depth error, plain | Same, d9_inner_g10 | g10 better by > 0.01 | g10 worse by > 0.01 | Three largest g10 errors |
|---|---|---|---|---|---|
| 0.4 | 0.047 | 0.020 | 27/40 | 0 | 0.043, 0.052, 0.081 |
| 0.3 | 0.044 | 0.028 | 22/40 | 0 | 0.053, 0.095, 0.100 |
| per-frame rule | 0.061 | 0.040 | 26/40 | 0 | 0.108, 0.113, 0.124 |

- At 0.3 the "0/40" has no margin: the worst error is 0.100 against `DEPTH_TOL` 0.1.
- At 0.4 the margin is 0.019 on 40 seeds. At 30 photons and 0.4 it is 0.005 (worst 0.095).
- Over every level and geometry, d9_inner_g10 is worse than plain by more than 0.01 on 0 regions at 100 and 5000 photons (largest 0.007).
- Share of a region's pixels that are clipped (median): 6% on full frames at 0.4, 22-35% on partial regions at 0.4, 0.3 and the rule level. The misses on partial regions start at about a fifth of the region clipped.

**Is the depth destroyed on partial regions?** Six noise-free `single_region` frames, seeds 396_400-396_405 (asserted not calibration seeds; reserve them in `USED_SEEDS`). Each pixel of the truth region's interior is classed by the clean minimum and maximum over one Period along the row:

| Clip | No clipped pixel in the cycle | Peaks clipped, troughs intact | Whole cycle saturated |
|---|---|---|---|
| 0.8 | 96-99% | 1-4% | 0% |
| 0.4 | 0-26% | 74-100% | 0% |
| 0.3 | 0-11% | 87-100% | 0-2% |

- So at the levels where every mechanism fails, the frame still shows the troughs of nearly every cycle. This is exactly the ticket's "clipped stripe peaks".
- What fails is the method: any exclusion guard has no clean window left, and the linear weighted fit is biased by Mottle inside its window (the prototype's noise-free 0.33).
- A censored model fit (trough level plus curvature at the known Period) is not ruled out. It is also not shown to work, it is badly conditioned under scorched Mottle and EMCCD noise, and it is research, not this ticket.
- Limits of this check: noise-free, six frames, the window ignores the tilt.

**Stripe-free, recounted from the `free` run (40 pairs per row):**

| Photons, clip | Higher | Lower | Mean change | Median change |
|---|---|---|---|---|
| 100, 0.8 | 7 | 7 | -0.28 | 0.00 |
| 100, 0.6 | 13 | 10 | +1.70 | 0.00 |
| 100, 0.4 | 18 | 14 | +2.83 | 0.00 |
| 100, 0.2 | 17 | 18 | -0.47 | 0.00 |
| 30, 0.8 | 12 | 16 | -1.84 | 0.00 |
| 30, 0.3 | 20 | 15 | +3.37 | +0.60 |

- The crossings of 49.7 are one frame per signal level: 396_085 (32.3 unclipped, 54.7 at 0.6-0.3, 0.0 at 0.2) and 396_078 (20.2, then 60.7 at 0.3).
- One crossing in 40 does not show a higher false-alarm rate: at a true 1% rate, one or more in 40 happens a third of the time. It does not rule a rise out either.

## 1. AC 4's test

**Decision: option (a) in a changed form. Reject (b).**

**Why not (b), the per-frame rule with a miss allowance:**

- A miss allowance on a new test is a tolerance fitted to the detector (3/40 misses becomes "allow 1 in 10").
- The rule needs `analysis._light`, `_Filters` and `_interior_depth` in the test's precondition. `spec.md:136` forbids tests that check internals, and the stimulus would depend on the detector's own depth operator.
- The prototype's own finding: the rule's teeth are not the detector's teeth (`_grow` already leaves the flattened core out).

**The tests (all at the unchanged `DEPTH_TOL`, no allowance):**

1. **Full frame, typical, clip fixed at 0.4 of the clean maximum.**
   - Assert `assert_every_region_matches(report, truth)` on every seed.
   - Teeth through the public seam, not the generator rule: analyse the same frames with `clip_level=inf` (no exclusion). Assert per seed that the depth error is not larger than the `inf` error plus a small epsilon, and over the seed set that the mean absolute depth error is strictly smaller than with `inf`. A no-op or harmful exclusion fails this. On the prototype seeds the means are 0.020 against 0.047.
   - Precondition on the stimulus only: a minimum clipped share of the frame (the prototype's minimum at 0.4 is 2.3%, the median 5.2%), so the test cannot pass on a mild clip.
   - Not 0.3: zero margin (0.100).
2. **Partial region, mild clip (0.8).** Assert the depth within `DEPTH_TOL`, with B4's precondition. Name it for what it guards: the exclusion must not harm a region whose centre has clipped pixels (plan D9 failed this on 3/20). Say in the docstring that it has no teeth against flattening.
3. **Partial region, clip 0.4.** Assert only that the depth error is not larger than the `clip_level=inf` error plus the same epsilon. It asserts an inequality, so it pins no bad value.

**Before the freeze (small prototype, about 40 full frames at one level, on reserved seeds 396_100 and up):**

- Sweep the cutoff (0.05, 0.10, 0.20). The 0.10 is one tried value and becomes a lockfile constant.
- Confirm the 0.4 margin on fresh seeds. If the worst error on 40 fresh seeds is above about 0.08, the test will go red on some later seed, and the pressure will then be on the check. In that case move the fraction (0.5), keeping the `inf` comparison as the teeth.
- Record 30 photons in the evidence, do not assert it (margin 0.005).

**Is it a weakening that needs the owner? No, with conditions.**

- The ticket's AC 4 names no clip level and no geometry. Partial regions came from the plan (B4). Tests 1 and 2 assert the AC at the unchanged tolerance. None of CLAUDE.md's listed moves is made: the new fraction, epsilon and minimum share are lockfile additions, which the orchestrator approves.
- But the AC's own words, "clipped stripe peaks", cover the regime that fails: a partial region at 0.4 has clipped peaks and intact troughs, and the best mechanism misses on 6/20. So AC 4 is met only in part. Ticking the box without saying so would be a false claim.
- Required: the ticket's Comments record that AC 4 holds up to a clipped share of a region of about a tenth, and that above about a fifth the reported depth is low, toward the flattened value. The final handoff says the same to the owner.

**Wording of the limit (docstring, ticket, glossary):**

- Do not write "a saturated core loses its depth" or "the information is gone". Write that this detector does not recover the depth when a large share of the region is clipped, and that `clipped_pixels` is the warning (story 27).
- The fallback is silent per region: a region can report 0.28 for a true 0.5 with only the frame-level count as a hint. State this.

**Follow-up issue (new, `needs-triage`):** depth of heavily clipped regions. Content: the trough check above, the failed variants, a censored fit as the untested candidate, and a per-region warning as the cheap alternative.

**Human needed: no (not blocking).** One non-blocking question for the owner goes into the follow-up issue, class (b) external knowledge: do real frames ever have a fifth or more of a Striped Region saturated? Nothing in the repo answers it (`06-critic.md`: the only real frames are sCMOS). The answer sets the follow-up's priority. It does not change what ticket 06 ships, because d9_inner_g10 is never worse than no exclusion and is cheap to replace.

## 2. The clipped stripe-free score rise

**Decision: out of ticket 06's criteria. No fix, no score tolerance. One cheap test, and a recorded item for ticket 07.**

- **Scope:** no AC of ticket 06 covers clipped stripe-free frames. "Must not score higher" came from the first critic's prototype list (O2), and as a strict paired statement it was badly posed. Any change to a frame moves the score both ways.
- **No fix now:** leaving clipped pixels out of the score reverses the O2 ruling (depth only), puts holes into the filters, and has no evidence behind it. The data shows a spread around zero, not a clear rise in the rate.
- **No paired score tolerance:** the rises come in jumps (0 to 24, 20 to 61). A tolerance wide enough to pass (over 41) checks nothing.
- **Test to add in 06:** stripe-free typical frames (the AC 3 seeds), clipped at test 1's fraction: `striped` is False and there are no regions, at the default `THRESHOLD`. The prototype has 0 regions and no score near 154 on 400 clipped frames. Do not assert at `GATE_STORED_THRESHOLD`: at 1 crossing in 40 the test would be red on about a third of 20-seed sets.
- **Ticket 07:** its text says the threshold is calibrated "using the full pipeline (regions, spike rejection, clipping)" on frames with spikes present, and names no clipped frames. Add a line to 07: either measure the stripe-free rate on clipped frames (a few hundred, at test 1's fraction) or state that the 1% rate holds for unclipped frames. Cite frames 396_085 and 396_078.
- **Human needed: no.** It is not taste, needs no outside knowledge, and nothing is hard to revert.

## Other points

- The plan's "teeth" paragraph (plan:94) lowers `CLIP_LEVEL_FRACTION` until `inf` misses "on most frames". That cannot be met on full frames (plain misses 3-5/40 at any level). Replace it with test 1's `inf` comparison.
- `handoffs/06-prototype-p2.md` and the evidence write-up should get the two corrections at the top of this file before they are committed as evidence.
