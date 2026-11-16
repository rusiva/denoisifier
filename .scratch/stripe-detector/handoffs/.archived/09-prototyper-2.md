# 09 P1 prototyper handoff 2 (paused, validation in flight)

Paused at the coordinator's request.

- **Validation is running in the background. Leave it running.** It started 15:09 CET. It should take about 20 min for BASE plus about 2 min for the eval, so it should finish around 15:30.
- The worktree was clean at the pause. Everything is committed in `994e4dc`.
- This file sits in the worktree because of the isolation guard. Copy it to `/home/rusiva/dev/denoisifier/.scratch/stripe-detector/handoffs/09-prototyper-2.md`.
- `09-prototype-p1.md` is **not written yet**. Every number is here.

## Where things are

- Worktree: `/home/rusiva/dev/denoisifier/.claude/worktrees/agent-a89346810ac6ef538`
- Branch: `worktree-agent-a89346810ac6ef538`. Throwaway; do not merge.
- Commits:
  - `994e4dc` "PROTOTYPE 09 P1-2: scope-C post pass, constants frozen before validation". The frozen constants are the defaults in that commit.
  - `1bf7b8d` is handoff 1, and `861fc14` is P1 v1.
- Code is in `prototypes/p09_breaks/`. The scripts that matter now:
  - `harness2.py`: generation plus BASE `analyse`, which captures every survivor.
  - `finder.py`: the break finder.
  - `post.py`: the scope-C pass.
  - `eval2.py`: the 5.1 metric, the AC 4 reading and the per-cell table.
  - `summary.py`: the headline numbers.
  - `estats.py`: the E margin.
  - `timing.py`: 400x1600 timing with 1 and 3 regions.
  - `dbg.py`: a per-frame dump.
  - The handoff-1 scripts are kept but superseded.
- Scratch data lives in `/tmp/claude-1000/-home-rusiva-dev-denoisifier/85ad64ff-6979-496b-bc0d-89a93d20c47a/scratchpad/p2/` (about 0.6 GB; a reboot clears it):
  - `all_explore.pkl`: the explore BASE cache, 1686 frames.
  - `all_explore.pkl.s6.eval.pkl` and `ev_s6.log`: the frozen-config explore evaluation.
  - `estats.log`
  - `sweep1.log`: the re-measure sweep.
  - **In flight:** `validate.log`, then `base_validate.pkl`, then `ev_val.log` and `base_validate.pkl.frozen.eval.pkl`. The background shell writes `EXIT=` to the end of `ev_val.log` when it is done.

## Next step

1. Wait for `EXIT=` at the end of `ev_val.log`, then run:
   ```
   cd <worktree>/prototypes/p09_breaks
   uv run --locked python summary.py <scratch>/base_validate.pkl.frozen.eval.pkl
   ```
   That gives the validation numbers. **Do not retune after this.** If AC 4 or bridging fails on the fresh seeds, stop and report it (owner).
2. Re-run `timing.py '{}' '{}'` on an idle machine with the frozen config (steps = 6). Only steps 4 and 8 have been timed so far (see Timing).
3. Write `/home/rusiva/dev/denoisifier/.scratch/stripe-detector/handoffs/09-prototype-p1.md` from this file plus the validation numbers. Reply to the orchestrator in 150 words or fewer.

## Setup (harness2, plan-shaped)

- **Explore seeds:** 109_000-109_599.
- **Break frames.** Single-region `tests/regions.py` geometry, 512x512, typical EMCCD noise, scorched Mottle, depth 0.5, line through the centre.
  - First 300 seeds (AC 2 shape): line angle = case Angle + {0, 5, −5}[seed % 3]; jump cycles {π/2, 2π/3, π, −π/2, −3π/4}.
  - Next 300 seeds (AC 3 shape): (line angle, jump) cycles over {45, 90, −60} x {π/2, π}.
- **Break-free frames:**
  - the same 600 seeds;
  - 100 multiscale-Mottle frames;
  - 20 full frames;
  - 20 frames with two compatible same-Period regions at a 2 P or 3 P gap (R1).
- **Full frames (400x1600):** 20 with a horizontal break through the centre, jump π/2 and π alternating (seeds 109_400-109_419, which include 109405).
- **`split`:** the handoff-1 split frames: seeds 109530 and 109550 plus 8 more P = 3 seeds, line 45°, jump π.
- **`pair{2..8}`:** full frames, two horizontal breaks `sep` P apart, jumps π/2 and π, 20 seeds each.
- **`small{3..8}`:** a region H P tall with a horizontal π/2 break.
- **`bin2x1` / `bin1x2`:** full frame, horizontal π break; P = 3 seeds skipped.
- **`weak`:** depth 0.25.
- **Validation seeds:** 109_600-109_999, with the same layout and fewer frames: 400 break frames, 400 break-free, 100 multiscale, 20+20 full, 20 two-region, pairs, small and bins. There are no split or weak frames.

## The pass (`post.py`, after `reported`; score path untouched)

1. **Bridge.**
   - Which pairs: reported regions only (R2 is ruled out), that are `_compatible` and within `bridge_gap` = 4 P of each other.
   - Domain: the union of the two regions plus the pixels within the gap of both, inside `light`.
   - The finder runs on that domain, at the Period and Angle of the higher-peak region.
   - Merge rule: a found break with the smaller region at least 0.8 on one side and the larger at least 0.5 on the other side. When the re-find on the merged region returns nothing, the bridge's own break is reported.
2. **Find** in every final region, with the finder's own narrow Gabor at the region's Period and Angle.
3. **Re-measure.**
   - Pixels: the region's pixels outside ±`excl_k` = 2.0 times the bank σn of each break.
   - Method: `_phase_steps(spec.gabor(...))`, 6 steps, starting from the reported (biased) Period and Angle.
   - No re-find afterwards (`refind` = False; re-find measured worse).
4. **Fill.** Add pixels within ±`fill_k` = 1.0 times the bank σn of the line, limited to:
   - the along-line bins (0.5 P) where the region has pixels on both sides within the band + 1 P;
   - `light`;
   - pixels not owned by another region.
5. **Absorb slit regions (new; not in the plan).** A smaller final region joins a region that has a found break when all of these hold:
   - the period ratio is at most `_MERGE_PERIOD_RATIO`;
   - it lies within `bridge_gap`;
   - either its own found break is the same line (within 2° and within 1 P at its centroid), or at least 0.6 of its pixels lie within the fill band + 1 P.

   Why: on binned and full frames, BASE grows an incompatible region along a π break; for example bin1x2 109509 had a region at A 1.27° beside A −6°. Without the Period and gap conditions it wrongly merged distinct regions crossed by one frame-wide break (found on the 3-region timing frame).
6. **Segment.** Region pixels within 0.75 x max(bins) sensor px of the line, after the fill and the absorb. A σn-wide band overshot the chord on full frames, so it was dropped.
7. **No break accepted anywhere: BASE is returned untouched.** This held by construction on every break-free frame: fakes are 0, below.

## Frozen constants (decided on explore only; commit `994e4dc`)

Finder (`finder.FINDER`), with the plan's §10 names:

| Constant | Value |
|---|---|
| `_BREAK_SIGMA_ACROSS_PERIODS` / `_ALONG` | 1.0 / 0.5 (filter and σn model) |
| `_BREAK_MIN_DEPTH_FRACTION` | 0.5 (samples where \|z\| >= 0.5 x median \|z\| on the domain) |
| `_BREAK_COARSE_STEP_DEG` | 3 |
| `_BREAK_FINE_SPAN_DEG` | ±3 |
| `_BREAK_FINE_STEP_DEG` | 0.5 |
| angle refinement (new) | golden-section search within ±0.25°, down to `line_tol` = 0.1 P at the region's length. Without it, long lines in 400x1600 frames were 1-1.7 P off at the ends. |
| `_BREAK_BIN_PERIODS` | 0.25 |
| `_BREAK_SAMPLE_STRIDE_PERIODS` | 0.5 |
| sample cap (new, speed) | `max_samples` = 40 000; the stride grows on large domains |
| `_BREAK_FIT_HALF_WINDOW_PERIODS` | 4 |
| samples per side (new) | at least 6 P² of area per side in the window |
| `_BREAK_MIN_EVIDENCE` | 0.1 |
| `_BREAK_MIN_JUMP_RAD` | π/4 |
| `_BREAK_SEGMENTS` | 3 |
| `_BREAK_JUMP_SPREAD_RAD` | π/4 |
| `_BREAK_EXPLAIN_SIGMAS` | 2 |
| `_BREAK_MAX_PER_REGION` | 4 |
| `_BREAK_MIN_FRAME_PERIOD_PX` (new) | 2.5 frame px along the stripe normal. Below it the finder returns nothing. P 4 under 2x1 aliases, and without the gate it gave fake breaks with E 0.16-0.18. |

Pass (`post.POST`):

| Constant | Value |
|---|---|
| `_BRIDGE_GAP_PERIODS` | 4 |
| bridge side shares | 0.8 smaller / 0.5 larger |
| gap domain | pixels within the gap of both regions, inside `light` |
| `_BREAK_FILL` | ±1.0 x bank σn (fill reach + 1 P, both-sides bins 0.5 P) |
| `_REMEASURE_EXCLUDE` | ±2.0 x bank σn (≈ 3 P for a horizontal line at stripe Angle ~0) |
| `_REMEASURE_STEPS` | 6 |
| `_REMEASURE_START` | the reported values |
| `_BREAK_REFIND_AFTER_REMEASURE` | False |
| absorb | 2°, 1 P, 0.6 |
| segment | 0.75 px |

Decisions:
- **Keep step 3 (fill)** and **step 4 (re-measure)**: both meet the tolerances on explore (below).
- **Protected (proposed):**
  - `BREAK_CHORD_COVER_MIN` = 0.6 (min cover over matched breaks 0.776, p1 0.799);
  - `BREAK_SIDE_COVER_MIN` = 0.5 and `BREAK_SIDE_EXCLUDE_PERIODS` = 2.5 confirmed (one-region frames min 0.785, apart from the R2 frame 109221 at 0.14);
  - `BREAK_SMALL_REGION_PERIODS` = 5 (heights 3-6 P: 0/20 changed each; 8 P: 20/20 changed, 18/20 found);
  - `BREAK_PAIR_SEPARATION_PERIODS` = 6, with the test at P >= 5 (see pairs);
  - `BREAK_VALIDATION_SEEDS` = `range(109_600, 110_000)`.

## Explore results (frozen config; `summary.py` on `all_explore.pkl.s6.eval.pkl`)

Steps 4 gave identical counts with max Angle error 0.88°.

| Check | Result |
|---|---|
| AC 2 found (5.1, with overshoot and direction alignment) | 300/300 |
| AC 2 full frame | 20/20 |
| AC 3 found | 300/300 |
| AC 4 (striped, one region, both sides >= 0.5 beyond 2.5 P), region frames | **599/600** |
| AC 4, full frames | 20/20 |
| AC 4, split seeds (109530, 109550 + 8) | 10/10, all bridged or merged |
| Angle within 1°, region break frames | **600/600, max 0.76°** (BASE: 268/600 over 1° in handoff 1) |
| Angle within 1°, full | 20/20, max 0.42° |
| Period within 5% | 620/620, max 0.8% |
| Mask IoU >= 0.8 | **599/600**, min 0.308 (BASE 497/600) |
| Fakes (any output change) | free 0/600, multiscale 0/100, full 0/20, two-region 0/20 |
| Weak (depth 0.25) | found 52/60 (information only) |
| bin2x1 | found 15/18, AC 4 18/18 |
| bin1x2 | found 17/18, AC 4 18/18 |

The single AC 4 / IoU failure is **109221** (P 5, jump π, ac2): BASE reports only a 1830 px piece (BASE IoU 0.21). The rest of the stripes are survivors below the threshold, or at P 3.97 and incompatible. That is R2 plus growth, so it belongs to ticket 17. It is a frame of the plan's AC 2 test shape, so a test seed like it would go red: risk for the orchestrator.

Binned misses:
- 109505 and 109515 are P 4 under 2x1, where the frame-period gate refuses by design (frame period 2 px).
- 109515 under 1x2 also misses.
- 109509 under 2x1 (P 14): line error 1.06 P at a found angle of −0.54°.

### (b) Line error by Period

Max over AC 2, AC 3 and full frames, in Periods:

| P | 3 | 4 | 5 | 6 | 8 | 10 | 12 | 14 | 16 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|
| max line error | 0.72 | 0.75 | 0.89 | 0.85 | 0.54 | 0.55 | 0.68 | 0.44 | 0.59 | 0.61 |

- The worst is 0.89 P at P 5. P 3 is not the worst; the 0.5° grid plus the golden refinement is enough there.
- Handoff 1's 3 line errors of 1.01-1.21 P at π are gone. They are not reproducible: the old data and geometry are gone after the reboot, so the 594/600 versus per-cell versus failure-list counts **cannot be reconciled**. The new counts all come from one script.

### Evidence margin (B4; `estats.log`, gates off, two greedy rounds)

- **Break-free top E:** n 754, p99 0.010, max 0.082.
  - The max is full-frame 109410 at P 3; its \|jump\| 0.72 fails the jump gate.
  - **No break-free candidate passes the jump and spread gates.**
- **True breaks:** min E at π/2 is 0.18.
- **Second candidate on break frames:** max E 0.034; none passes the gates.
- So E = 0.1 sits 1.22x above the largest break-free E and 1.8x below the smallest true one.

### Re-measure sweep (explore; max Angle error on AC frames)

| Steps / exclusion | Max Angle error |
|---|---|
| 4 / 1.5σn | 1.11° (8 frames over 1°) |
| 8 / 1.5σn | 0.96° |
| 4 / 2.0σn | 0.88° |
| **6 / 2.0σn** | **0.76°** (frozen) |
| 8 / 2.0σn | 0.75° |
| 8 / 2.5σn | 0.83° |
| re-find (4 / 1.5σn) | 1.11° |

### Pairs (full frames, jumps π/2 and π)

Both found, out of 20:

| Separation | 2 P | 3 P | 4 P | 5 P | 6 P | 8 P |
|---|---|---|---|---|---|---|
| Both found | 1 | 15 | 18 | 16 | 17 | 15 |

- At 6 P every miss is at P <= 4: P 3 0/2, P 4 1/2, all P >= 5 2/2.
- At P 3-4 the misses are overshoot of the segment past the truth lit-mask chord, by 1.3-2.3 P = 4-7 px. That is a metric artefact of the lit-mask definition at the frame's lit edge, and it needs the orchestrator's look (open question 2).
- At 8 P, P 14-20 lose the second break to a 1-1.7 P line error.
- In region geometry (handoff-1 style) pairs cannot work at P >= 8: the region is 10 P tall.
- Recommendation: `test_two_parallel_phase_breaks_are_both_found` on a full frame at P >= 5, separation 6 P.

### Timing

Single process, 400x1600, seeds 109_580-109_584. Measured at steps 4 and 8 only; steps 6 is not timed yet (next step 2).

| Frame | Steps | Post-pass added time | BASE `analyse` |
|---|---|---|---|
| 1 region, horizontal π break | 4 | mean 0.25 s, max 0.41 | ~5.4-6.0 s |
| 1 region, horizontal π break | 8 | mean 0.38 s, max 0.55 | |
| 1 region, no break | | 0.08 s | |
| 3 regions (P 6/10/14), π break each | 4 | mean 0.53-0.56 s, max 0.83 | ~7.2-7.7 s |
| 3 regions, π break each | 8 | mean 0.80 s, max 1.23 | |
| 3 regions, no break | | 0.16 s | |

- Steps 6 should land between the two.
- Cost drivers: full-frame FFT filters on the shared `_Spectrum`. A crop-local spectrum for the re-measure would cut it; that is ticket 13 material.
- **Finding for ticket 17:** on the 3-region frames, BASE often reports a P 6 or P 14 region on one side of its π break only, with the other side lost entirely and not even an unreported survivor (seeds 109580, 109582). No bridge can fix that.

## Open questions for the orchestrator

1. **Is the absorb step OK?** It goes beyond the ruling's "merge across a found break". It merges a region that lies on a found break's line or slit. It is needed for full and binned frames, never fires on break-free frames, and is gated by Period ratio and gap.
2. **Full-frame chord definition (5.1 overshoot).** The truth lit mask (here `gaussian(clean, P) >= 0.1 max`) ends a few px before the region at P 3-4. Either define the chord from a lit mask closer to `analyse`'s light, or accept the overshoot on full frames.
3. **109221-type frames.** In the plan's AC 2 shape, BASE reports a fragment at a π break with the rest below the threshold. That is R2 and ticket 17 territory, but a fixed test seed could hit it. One in 600 on explore.
4. **The new gates** (`_BREAK_MIN_FRAME_PERIOD_PX`, the sample cap, the angle refinement) need lockfile lines like the other `_BREAK_*`.
