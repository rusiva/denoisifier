# 09 P1 prototyper handoff 3 (paused, v2 in progress)

The task is to apply the critic-3 rulings (`09-critic-3.md`; the orchestrator's "critic-3 done" bullet, items 1-5) and to diagnose 109797 and 109765. After that, re-freeze on explore and validate once on 110_000-110_399.

- **Status:** the rulings are partly done. **The explore re-freeze is not finished. The v2 validation (110_000-110_399) has NOT started**, and no BASE was run for it.
- **Code:** commit `108e150` on `worktree-agent-a89346810ac6ef538`, worktree `/home/rusiva/dev/denoisifier/.claude/worktrees/agent-a89346810ac6ef538`, in `prototypes/p09_breaks/`.
- **Copy this file** to `/home/rusiva/dev/denoisifier/.scratch/stripe-detector/handoffs/09-prototyper-3.md`. The isolation guard put it in the worktree.
- `09-prototype-p1.md` is not yet updated with a v2 section. The old validation stays as is.

## Running background job (left running)

`bash <P3>/run_ablate.sh`, where `<P3>` = `/tmp/claude-1000/-home-rusiva-dev-denoisifier/85ad64ff-6979-496b-bc0d-89a93d20c47a/scratchpad/p3`. Started 15:54. It runs in sequence:

1. explore eval `v2`: the current defaults, every tag.
2. `off`: `{"absorb":"off"}`.
3. `old`: `{"absorb":"old"}`, the P1-2 rule.
4. `capoff`: finder `{"max_samples":0}`, on the full_break, fullcap, pair and bin tags.
5. The gate frames with finder `min_frame_period` 2.0 (`g2.0`) and 2.5 (`g2.5`).

Logs are `<P3>/ev_<name>.log`. Each log ends with an `EXIT=` line. Results are `<P3>/explore_v2.pkl.<name>.eval.pkl` and `<P3>/base_gate.pkl.g2.0.eval.pkl` / `.g2.5.eval.pkl`.

**When `<P3>/ablate.done` exists, the job is finished.** About 15-20 min in total.

Caveat: post.py's warning string was edited while `v2` was running. That edit is text only, with no effect on behaviour.

## Rulings: what is done

### 1. Absorb (code done, numbers pending)

- `post.py` has `absorb` = "constrained" (the default) | "off" | "old".
- Constrained form:
  - **(a)** A region **with no break of its own** joins a region with a break when at least `absorb_frac` 0.6 of its pixels lie in that region's fill bins (`r["slit"]`: the both-sides bins within the fill reach), and the Period ratio is at most 1.2.
  - **(b)** The `same_line` branch is replaced by a **second bridge round after the re-measure**: `_compatible` on the re-measured Period and Angle, then the same finder-on-the-union rule and side shares as round 1, up to 3 rounds. The merged group is re-processed.
  - Neither can fire without a found break.
- Break-present negative (`two_break`): two regions, equal Period, Angles 3° or 10° apart, gap 2 or 3 P, one frame-wide horizontal break. 20 explore frames (109_120-139). It is in the validation layout too.
- First explore run, `e1`. This was before the re-measure and depth changes below, but the absorb code was the same:
  - two_break: the pass merged **0/20** (absorbed 0, bridge2 0). 17/20 end with 2 regions. The 3 others are BASE's own counts, unchanged by the pass: 109128 and 109136 have `n_base` 3, and 109137 has `n_base` 1.
  - bin1x2: AC 4 16/18. 109509 and 109515 lost AC 4 compared with the old absorb. That is the critic's prediction.
  - pair3: 15/20.
  - split: 10/10. splitx (50 new P 3 split-type frames): 50/50 found and AC 4, 6 merged.
- **Pending:** the `v2`/`off`/`old` comparison in the running job. Rule: if constrained does not recover the 4 frames (bin1x2 109503, 109509; pair3 109446, 109448), set `absorb` = "off" and list those seeds for ticket 17. Use `summary2.py <v2.eval.pkl> <off.eval.pkl>` (the per-frame DIFF lines).

### 2. Overshoot (done)

- **Diagnosis** (`diag_over.py`, explore pair6 109450/109455, pair8 109440, full_break 109400/109405):
  - The full frames are not fully lit: scorched illumination makes a blob.
  - The segment ends where the final region ends. On the second break's row that is the fill region, bounded by `_light`. The truth lit mask (`gaussian(clean, σ = P) >= 0.1 max`) ends up to 7 px (2.3 P at P 3) earlier on that row. Example: pair6 109450 break 2 has segment x 455..1290, truth-lit 462..1303, `_light` 450..1300.
  - So the pair overshoot is the fill reaching `_light`'s edge, past a truth mask whose smoothing narrows with P. It shows at P 3-4 and on pairs only because the extra rows sample more of the lit boundary.
  - Single-break full frames at P 3-4 (2 each on explore) happened to stay inside it.
  - The validation frame 109910 (P 3) is the same mechanism (over 1.0 P).
- **Change** (`eval2.py`): on full frames, overshoot is measured against the frame-clipped true line, so it is vacuous there, as critic 3 says. Coverage is measured against a generator-side lit mask with one fixed σ (`LIT_SIGMA_PX` = 10 sensor px, `LIT_LEVEL` 0.1). Region frames are unchanged.
- Also changed: `both_sides` now returns 0 for an empty side instead of 1.0.

### 3. Tests: no prototype work.

### 4. Frame-period gate and sample cap

- **Warning (done):** `o.warnings` gets one string per reported region under the limit, in the style of `_unresolved_warning`:
  > `region {label} (Period {P} px): phase breaks were not searched at {h}x{v} binning: its stripes fall under 2.5 frame pixels along their normal ({pf})`

  Labels follow the BASE order (area, peak, first pixel). `eval2` records `warnings` per frame. On explore `e1`, bin2x1 was warned on 2 frames (P 4).
- **Derivation (for the constant's comment):** the finder's across window is s_across = 1 P, so the passband's upper edge at k σ is `(1/P)(1 + k/2π)`. It reaches the frame Nyquist at a frame Period of `2(1 + k/2π)`: 2.32 at k = 1, **2.5 at k = π/2** (response exp(−k²/2) = 0.29 there), and 2.64 at k = 2.
- **Measurement (job running):** `jobs_gate()`, fresh seeds 110_400-110_459 (unused, checked). Full frames under 2x1, Angle 0, P 4.0/4.2/4.5/4.8/5.0/5.5, which is a frame Period of 2.0-2.75. 10 break frames and 10 break-free frames each. BASE is done (`<P3>/base_gate.pkl`). Read the evals with `gate_summary.py <P3>/base_gate.pkl.g2.0.eval.pkl <P3>/base_gate.pkl.g2.5.eval.pkl`. Pick the limit where fakes stop or finds hold. Then state the rule; there is no fitting.
- **Sample-cap ablation (job running, `capoff`):** compare line error by P and time against `v2` on full_break, fullcap (40 new full frames at P 3-6, seeds 109_200-299), pair* and bin*. Keep the cap only if line accuracy is unchanged. Otherwise set `max_samples` 0, so the stride stays 0.5 P, and leave speed to ticket 13.
  - `v2` reference from `e1`: line error max P5 1.03 (p95 0.81), P6 0.85 (p95 0.77), against P8-20 at 0.44-0.68. fullcap was found 39/40.

### 5. Re-measure, owned, depth

- **owned:** done. Updated in place after each fill.
- **Minimum area:** `remeasure_min_p2` = **9.4 P²** of region outside the exclusion. That is one bank Gabor footprint, 2π · 1.0 · 1.5. It is a floor, never hit on explore: the minimum area was 14.7 P² on small8 and 25.4 on ac2.
  - Measured: small-region area does **not** predict the bad cases. The 4 small8 frames over 1° have areas 17-27 P², inside the range of the good ones.
- **Guard, measured on explore** (`<P3>/explore_v2.pkl.rmnone.eval.pkl`, guard "none", BASE depth):

  | Tag | BASE Angle > 1° | Re-measure, no guard | `_compatible` guard (critic) | Energy guard |
  |---|---|---|---|---|
  | ac2 (300) | 204, max 3.43 | 0, max 0.76 | **109, max 3.43** (refused 109) | 0, max 0.76 (refused 7) |
  | ac3 (300) | 39, max 1.75 | 0, max 0.30 | 0 | 0, max 0.45 (refused 83) |
  | small8 (20) | **20/20, 2.8-3.3°** | 4, max 1.34 | 19 (refused 16) | 4, max 1.34 |
  | weak (52) | 39 | 1, max 1.19 | 21 | 1 |
  | full_break, split, splitx | | all fine | | |

  - So **critic 3's `_compatible` guard is harmful**. BASE's break-biased Angle is up to 3.4° off, which is more than the 2° it allows.
  - Also, critic 3's small8 reading was wrong: BASE is over 1° on all 20 small8 frames, and the re-measure brings 16 of them under 1°. "Keep BASE under a minimum area" would make small regions worse.
  - **Chosen:** `remeasure_guard` = "energy". The mean |bank Gabor| over the re-measure pixels must not drop: the result must fit the stripes on those pixels at least as well. This needs the orchestrator's OK, since it departs from the critic's form.
- **Depth:** `diag_depth.py` on 90 explore break frames, depth minus the true 0.5:

  | Method | Mean | Within 0.1 |
  |---|---|---|
  | BASE | −0.062 | 73/90 |
  | Recomputed at the final Period and Angle, interior of pixels outside k·σn (k = 0/2/3/4) | −0.090 / −0.098 / −0.149 / −0.294 | worse at every k |
  | True Period and Angle on the truth core | −0.099 | |

  - The phase jump lowers the bank depth well beyond 2σn. BASE free frames: −0.003.
  - From `e1`: break frames within 0.1 were 432/620 recomputed against 549/620 BASE.
  - **Decision:** `depth_all` = False. BASE depth is kept for break-only regions, and recomputed only for merged regions, as before.

## Diagnoses

- **109797 (fake breaks):**
  - The false region (P 4.28, A −0.65, 944 px, rows 440-511) is a **BASE false positive**: peak 118 against threshold 100.8, depth 0.19.
  - It does not appear in the break-free frame of the same seed. Its BASE has 1 region and its second survivor has peak 19. The break changes the Poisson/gamma draws downstream, so the noise differs everywhere. The break itself sits far from that region.
  - The finder then accepts 3 breaks there (E 0.80/0.76/0.54). One of them is at Y0 511.9, the frame edge.
  - **Candidate guard measured and rejected:** per-side phase coherence |Σw|/Σ|w| over the fit windows (added as `coh`; `min_coherence` defaults to 0, so it is off). The fakes have 0.80-0.89. Matched true breaks on explore have min **0.793**, p1 0.911, p5 0.987. There is no separation, so no principled finder guard was found.
  - Verdict: BASE (ticket 17) territory, plus a general point for ticket 11: a fake region gets fake breaks.
- **109765 (6.4° line):**
  - With the line fixed at each angle, E is flat: 0.714-0.759 over −6° to +12°. The maximum is at 8°, and the true line is at 1°.
  - An exhaustive 0.5° grid gives the same 7.44° as coarse-to-fine, so it is not a search error.
  - The line is 5° from the stripe direction (an AC 2 ±5° shape) in a P 4 region about 29 P long. A jump across a line nearly parallel to the stripes has almost no angular signature.
  - Verdict: a resolution limit of the finder, not BASE. The only guard would be an angle-uncertainty refusal, and that would still fail AC 2. It is a risk for AC 2 at small P with near-parallel lines; it was 0/300 on explore.

## Next step

1. Wait for `<P3>/ablate.done`. Then run:
   - `summary2.py` on `explore_v2.pkl.v2.eval.pkl`, with the off/old pickles as the diff argument;
   - `gate_summary.py` on the two gate evals;
   - a capoff vs v2 line-error comparison by P: summary2 prints `line_err by P`; use `--` and filter the tags.
2. Decide absorb (constrained or off), the gate value and the cap, all on explore only. Then commit, and write down the frozen v2 constants.
3. Run BASE for validation once:
   ```
   cd <worktree>/prototypes/p09_breaks
   uv run --locked python harness2.py <P3> validate2
   ```
   That is 1276 frames, about 22 min idle; it writes `<P3>/base_validate2.pkl`. Then:
   ```
   eval2.py <P3>/base_validate2.pkl '{}' '{}' '' v2val
   summary2.py <P3>/base_validate2.pkl.v2val.eval.pkl
   ```
   No retuning after this.
4. Add a "v2" section to `/home/rusiva/dev/denoisifier/.scratch/stripe-detector/handoffs/09-prototype-p1.md`: explore and v2 validation reported separately, the constants diff, the guard table, depth, the gate table, the cap ablation, and the diagnoses above.

## Current v2 constants (not frozen) against P1-2

- `post.POST`, new or changed:
  - `absorb` "constrained" (was the old rule);
  - `remeasure_min_p2` 9.4;
  - `remeasure_guard` "energy" (new);
  - `update_owned` True;
  - `depth_all` False (unchanged behaviour).
  - `same_line_*` are used only by "old".
- `finder.FINDER`: unchanged so far (`min_frame_period` 2.5, `max_samples` 40000), pending items 4 and 5 of the job. New `coh` output; `min_coherence` is unset, so it is off.
- `eval2`: `LIT_SIGMA_PX` 10, `LIT_LEVEL` 0.1, full-frame overshoot against the frame, and an empty side fails.

## Open questions for the orchestrator

1. **Energy guard instead of the critic's `_compatible` guard** (table above). The critic's guard puts 109/300 ac2 frames over 1°.
2. **The critic's small8 premise was wrong:** BASE is 20/20 over 1° there, and the re-measure fixes 16. The minimum area is kept only as a floor (9.4 P²).
3. **Depth:** keep BASE depth. Every recompute measured was worse.
4. **109797:** no principled guard found; the coherence test was rejected by measurement. BASE / ticket 17, and a ticket-11 note.

## Files

- Scripts in `prototypes/p09_breaks/`:
  - `post.py`, `finder.py`, `eval2.py`, `harness2.py`: v2. The layouts are `jobs("v2extra" | "gate" | "validate2")`.
  - `summary2.py` (v2 headline, with an optional diff), `gate_summary.py`, `diag_over.py`, `diag_765.py`, `diag_depth.py`.
- Scratch, `<P3>`:
  - `explore_v2.pkl`: explore BASE, 1796 frames = `p2/all_explore.pkl` + `base_v2extra.pkl`;
  - `base_gate.pkl`;
  - `explore_v2.pkl.e1.eval.pkl`: the first v2 run, with the `_compatible` guard and depth recomputed;
  - `explore_v2.pkl.rmnone.eval.pkl`: the guard study;
  - the job outputs above.
- The P1-2 data is still in `p2/` (handoff 2). A reboot clears the scratchpad.
