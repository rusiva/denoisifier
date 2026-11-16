# 09 P1 prototyper handoff 1 (paused)

Paused on the coordinator's request. Nothing is running now: the last background job finished, and its output is quoted below.

- Worktree: `/home/rusiva/dev/denoisifier/.claude/worktrees/agent-a89346810ac6ef538`
- Branch: `worktree-agent-a89346810ac6ef538`, prototype commit `861fc14`, on BASE `b7c6731`. It is a throwaway branch: do not merge.
- Code: `prototypes/p09_breaks/` in that worktree.
- Data: in the scratchpad `/tmp/claude-1000/-home-rusiva-dev-denoisifier/85ad64ff-6979-496b-bc0d-89a93d20c47a/scratchpad/p1/`. It is not committed, about 3.3 GB, and can be regenerated.
- The findings file `09-prototype-p1.md` is **not written yet**. This handoff holds every result so far.
- This file was written in the worktree, because the isolation guard refused the main-checkout path. Copy it to `/home/rusiva/dev/denoisifier/.scratch/stripe-detector/handoffs/09-prototyper-1.md`.

## Setup (what was run)

- **Breaks.** They are injected by monkeypatching `synthetic._phase` (`harness.py`), using the plan 2.1 side test. The patch makes no RNG draws.
  - Frames: the `tests/regions.py` single-region geometry, 512x512, typical EMCCD noise, scorched Mottle, depth 0.5, with the line through the region centre.
  - Grid: jumps {π/2, 3π/4, π} x line angles {0, 10, -10, 45, 90}, 40 seeds per cell. Seeds 109_000-109_599 are each used once, and `CASES[seed % 10]` gives every case 4 times per cell.
- **Break-free frames.**
  - The same 600 seeds with no break (scorched Mottle).
  - Seeds 109_000-109_199 with multiscale Mottle.
- **Full frame.** 400x1600, seeds 109_400-109_419, with and without a horizontal break (jump π/2 and π alternating).
- **Reported regions.** BASE `analyse` gives them; `_refined` is wrapped to capture the final Period, Angle and `_Filters`. The saved crop is `z = 2*gabor/local_mean` at the final Period and Angle.
- **Run time.** `main.pkl` took 29 min with 15 workers.

## Q2: does BASE meet AC 4? **No.** (Stop condition hit; the detector was not changed.)

Table from `uv run --locked python prototypes/p09_breaks/q2.py <scratch>/main.pkl`:

| set (40 frames each unless noted) | striped | exactly 1 region | bbox within 1 P (AC 4) | same seeds, no break | Angle err > 1° | max Angle err | max Period err |
|---|---|---|---|---|---|---|---|
| a=0/±10, j=π/2 (120) | 120 | 120 | 120 | 120 | 93 | 2.68° | 1.6% |
| a=45, j=π/2 | 40 | 40 | 40 | 40 | 18 | 1.84° | 3.0% |
| a=90, j=π/2 | 40 | 40 | 40 | 40 | 0 | 0.41° | 3.6% |
| a=0/±10, j=3π/4 (120) | 120 | 120 | 117 | 120 | 85 | 3.91° | 2.0% |
| a=45, j=3π/4 | 40 | 40 | 38 | 39 | 22 | 1.75° | 3.3% |
| a=90, j=3π/4 | 40 | 40 | 40 | 40 | 0 | 0.35° | 2.9% |
| a=0/±10, j=π (120) | 120 | 120 | 105 | 120 | 50 | 3.18° | 1.6% |
| a=45, j=π | 40 | **38** | 37 | 40 | 0 | 0.80° | 0.9% |
| a=90, j=π | 40 | 40 | 40 | 40 | 0 | 0.14° | 0.6% |
| break-free scorched (600) / multiscale (200) | all | all | 599 / 200 | n/a | 0 | 0.16° / 0.18° | 0.3% |
| full frame with break / without (20 each) | 20 / 20 | **19** / 20 | n/a | n/a | 1 / 0 | 1.08° | 0.3% |

Totals:
- **AC 4 fails on 23 of 600 break frames.** The same seeds without a break fail on 1 of 600.
- **AC 4 full frame fails 1 of 20.** Seed 109405 (P 4, jump π) splits into an upper and a lower region.
- **The Angle misses `ANGLE_TOL_DEG = 1.0` (`tests/protected.py:16`) on 268 of 600 break frames**, against 0 of 800 break-free frames. Period stays within `PERIOD_REL_TOL = 0.05` everywhere (addendum a).

### How and why it fails

The evidence is in `prototypes/p09_breaks/why_bbox.py`, which prints the candidate seeds and growth for seeds 109404, 109244, 109494 and 109530.

1. **The region grows past the truth bbox by more than 1 P.**
   - Where: 21 frames, at P >= 5, jump >= 3π/4, near-horizontal lines.
   - Mechanism: the break dims the depth along the line, so one stripe set seeds as two candidates, one per side. Each seed area straddles the dimmed band, so its median depth drops, for example from 0.46 to 0.30 and 0.21 at seed 109404.
   - Effect: the grow level `_GROW_FRACTION * median` drops with it, so each candidate grows further into the soft edge. After the merge, the bbox is about 1.1-1.4 P too tall. Example: 109404 rows 133-381 against truth 156-356 at P 20.
2. **The region is split into two regions.**
   - Where: 2 of 4 frames at P = 3, line 45°, jump π (seeds 109530, 109550), and the full-frame seed 109405 (P 4, jump π).
   - Mechanism: the π cancellation band is wider than `_MERGE_GAP_PERIODS` (2 P), so the two half-regions do not merge.
   - Consequence: the break then lies *between* two regions, so no per-region finder can report it.
   - Related: when the halves do merge, the mask keeps a **slit** along the line, up to about 2.5 P wide (seed 109419: 36 empty rows at P 14).
3. **The Angle is biased (C3 confirmed).**
   - Size: 1-3.9° at line angles 0 and ±10, worst at 3π/4; 1-1.8° at 45°; none at 90°.
   - At 90° (a break along the stripes) the bias moves into the Period instead, up to 3.6%. That is still inside the tolerance.
   - Mechanism: `_phase_steps` takes the weighted mean of neighbour products. The blurred jump adds a phase ramp across the break, and the mean folds that ramp into the frequency. The candidates' Angle is already biased at the seed stage (cand0 −7.68° against −10°).
   - The same seeds without a break: max 0.16°.

**Both kinds of fix move upstream outputs.** Fixing failures 1 and 2 changes region growth or merging, which moves the score and the regions. Fixing failure 3 changes `_refined` and `_phase_steps`, which moves the reported Angle and Period but not the score. Either one is an orchestrator ruling (plan Q2 and the C3 escape hatch).

## Q1 (finder): preliminary, constants NOT frozen

This was done only because addendum (b) and (c) need a finder. The thresholds below are evaluated on the same 600 seeds they were explored on, so this is not a held-out claim.

1. **The plan's band contrast on the bank response fails** (`eval_default.log`).
   - Result: 138 of 600 matched.
   - Cause: the bank Gabor's along-stripe window (σ = 1.5 P) spreads a break over about ±3 P. That is most of a 10 P-tall test region.
   - Consequence: the **median carrier absorbs most of the jump**. Seed 109023 (P 12, jump π/2) shows a 0.5 rad step instead of 1.57. So the plan 2.2 claim "the median ignores it" fails at this region size.
2. **What works:**
   - **(i) Its own break-finder Gabor**, recomputed once per reported region at the final Period and Angle (C2), with window σ (across, along) = (1.0, 0.5) Periods, not the bank's (1.0, 1.5). This is `refilter.py`. On the same run, (0.75, 0.75) is about equal and (1.0, 1.0) is worse.
   - **(ii) A blur-aware two-amplitude fit** along each candidate line, in place of gap and band means. Model: `z(s) = c-(1-Φ(s/σn)) + c+Φ(s/σn)`, with `σn² = (σa·P·sin(t−a))² + (σl·P·cos(t−a))²`.
     - Evidence is the explained power: `E = [Re(c-*·B1 + c+*·B2) − |ΣZ|²/N] / (N·mean|z|²)` over a ±4 P window. It is a GLRT, and it settles N1.
     - The jump is `angle(c+·conj c-)`.
   - **(iii) Greedy "explain away"**: after each accepted break, undo its jump on the positive side, drop the ±2σn zone, and rescan. This removes duplicate tilted lines.
   - **(iv)** The reported segment is the extent of the region pixels within ±2.5 P of the line. This handles the slit.
   - Settings: angles −87..90 every 3° coarse, then ±3° every 0.5° fine; bins of 0.25 P; samples on a 0.5 P stride.
3. **Result with E >= 0.1, |jump| >= π/4, segment spread <= π/4** (`raw_rf_1.0_0.5_seg.pkl`):
   - **594/600 region break frames pass** the 5.1 metric, exactly one break per region. Every cell is 40/40 except j=π at a=0 (39), a=10 (39) and a=45 (38). That includes a = 90, 45 and ±10.
   - **Fakes: 0 of 600 scorched + 200 multiscale + 20 full-frame break-free frames.**
   - **Full frame: 19/20.**
   - Failures:
     - 3 with line error 1.01-1.21 P: π jumps where the line angle is off by about 6°;
     - the 2 split frames from Q2 failure 2.
4. **The evidence gap (B4).**
   - Break-free top E: 99th percentile 0.009, max 0.075. The max is full frame seed 109410 at P 3, and its |jump| is 0.68 < π/4, so the jump rule rejects it.
   - True breaks: 1st percentile E 0.178.
   - Second candidates on break frames: max 0.026.
   - The gap is about 2.4x at the extreme. Freezing the threshold is still pending.
5. **Sign convention at ±90° (plan Q3/5.1).** The canonical angle (−90, 90] flips direction at vertical, so a line found at −89.5° against truth 90° gets the opposite jump sign. The 5.1 metric must flip the found jump when `cos(Δangle) < 0`. Before that fix, a=90 failed about 20 of 40 frames.
6. **Not done yet:**
   - addendum (b): the worst endpoint distance per Period at P = 3, and the angle-grid sufficiency. The data is in `raw_rf_1.0_0.5_seg.pkl` (`matches[*].line_err` per frame); it needs a per-Period summary. The 3 line failures are at P 14, 4 and 6 (π jumps), not at P = 3;
   - addendum (c) and plan (c): timing. The evaluation of 1440 frames took about 11 s on 15 workers, so roughly 0.1 s per region. The C2 recompute is one Gabor plus local mean on the existing `_Spectrum`, recorded as `t_filter` in the `rf_*.pkl` regions. Neither has been summarised, and the 400x1600 one- and three-region probe has not been run;
   - two parallel breaks (`extra.py pairs`) and binning (`extra.py binning`): written, not run (`harness.py <out> pairs|binning`);
   - an explicit gradient-ridge variant. I judged it subsumed: the per-pixel phase gradient is weak at large P;
   - a split of thresholds into tune and validation halves (`evaluate.summary` supports halves).

## Next step (if resumed)

1. Summarise `line_err` by Period from `raw_rf_1.0_0.5_seg.pkl`, which answers (b). Time the finder and the C2 recompute on 400x1600 with 1 and 3 regions, which answers (c).
2. Run `pairs` and `binning` through `harness.py` (about 3-5 min each), then `refilter.py ... 1.0 0.5`, then `evaluate.py`.
3. Write `09-prototype-p1.md` from this handoff.

Per the stop rule, this waits on the orchestrator's Q2/C3 ruling: will BASE region growth, merging and Angle refinement change? If they do, re-run P1 on the new BASE before freezing constants.

## Open questions for the orchestrator

- Q2 and C3 are both breaks. Is a region-growth/merge change (it moves the score, so a measure milestone) and/or a `_phase_steps` change (it moves Angle and Period, not the score) approved?
- Should the finder use its own narrower Gabor (σ along 0.5 P) rather than the bank response? It costs one extra filter per reported region, which is C2's cost anyway.
- Is the 5.1 metric change OK: align directions before comparing jumps near vertical?
- Is the slit-aware segment OK: region pixels within ±2.5 P of the line?

## Files

- `prototypes/p09_breaks/`, one script per job:
  - `harness.py`: generation and BASE analyse;
  - `q2.py`: the Q2 table;
  - `why_bbox.py`: candidate dump;
  - `detector.py`: the finder;
  - `evaluate.py`: the 5.1 metric;
  - `thresholds.py`: the threshold study;
  - `refilter.py`: the narrow Gabor;
  - `profile_dbg.py`: the phase profile;
  - `inspect_eval.py`;
  - `extra.py`: pairs and binning jobs;
  - `nf_test.py`: noise-free check.
- Scratch, under the scratchpad `p1/`:
  - `main.pkl`: BASE frames and regions;
  - `rf_*.pkl`: the refiltered regions;
  - `raw_*.pkl`: finder candidates;
  - `eval_default.log`, `main.log`, `rf.log`.
