# 09 critic 3: the four open questions of `09-prototyper-2.md`

Read against the prototype at `994e4dc` (`post.py`, `finder.py`, `eval2.py`, `harness2.py`), the plan, critics 1 and 2, ticket 17 and `src/denoisifier` at `b7c6731`.

- Numbers marked "measured here" come from two read-only scripts over the explore evaluation `p2/all_explore.pkl.s6.eval.pkl` (last section).
- Nothing was re-run: the validation was still in flight (load 15), so every "why" below that needs a run is marked as not checked.
- I did not open any validation output.

"Owner?" is yes only for (a) taste between equivalent options, (b) knowledge not in this repo, (c) a hard-to-revert architectural decision.

**Summary: no item needs the owner.** Four things in the handoff do not hold as written:

- The absorb step is not "needed for full and binned frames". It acted alone on 4 of 1686 explore frames, none of them a planned test shape.
- The 5.1 overshoot is not shown to be a lit-mask artefact. All 20 single-break full frames have overshoot 0.00, including P 3 and P 4.
- The re-measure breaks `ANGLE_TOL_DEG` on small regions: 4 of 20 `small8` frames are 1.16-1.34° off. The handoff's Angle table leaves them out.
- 109221 passes AC 2 and the letter of AC 4. It fails only the both-sides cover (0.14) and the IoU (0.31).

## 1. Absorb step (`post.py:208-236`). Constrain; drop it if the constrained form is not needed. Owner: no.

**Can it fire with no found break? No.** It loops over `r["breaks"]` (`:211`), so the absorbing region must hold an accepted break. With no break anywhere, `changed` stays False and BASE is returned. That part is sound.

**It can merge genuinely distinct regions.** Three defects:

- **The band is the infinite line.** `band` (`:213`) has no limit along the line. A small separate region that sits beside `r`, within 4 P, on the extension of `r`'s break line passes the 0.6 share. The band is up to ±2.5 P wide (bank σn 1.5 P plus 1 P), so any region up to about 8 P across the line qualifies.
- **The Angle condition is gone.** The bridge requires `_compatible` (Period ratio 1.2 and Angle within 2°, `analysis.py:668`). Absorb keeps only the Period ratio. Its `same_line` branch has no size or share limit: two real neighbours with Periods within 20%, any Angles, crossed by one frame-wide break, become one region. That is the common real case (the ticket: breaks "usually cross the stripes roughly horizontally"), and it is the same wrong merge the handoff found on the 3-region timing frame. That frame's Periods (6/10/14) are separated by the ratio gate alone, so the gate was never tested at equal Periods.
- **It skips the ruling's evidence.** The ruling merges when the finder, run on the union, accepts a break through the gap. Absorb runs no finder on the union and never checks that the absorbed pixels carry `r`'s stripes.

**The evidence is thin (measured here).** Frames merged without an accepted bridge: 4 of 1686. They are `bin1x2` 109503 and 109509, and `pair3` 109446 and 109448. On `full_break` (20 frames) the one merge is a bridge. No planned AC test has the shape of those 4 frames. The 2°, 1 P and 0.6 constants were set on them.

**Required form, if kept:**

1. Limit the band branch to the fill's own bins: the along-line bins where `r` has pixels on both sides (`ok`, `:196-202`). A region enclosed in `r`'s slit cannot be a separate neighbour. This turns absorb into "the fill may claim a slit region", which is inside the ruling's step 3.
2. Replace the `same_line` branch with a second bridge round after the re-measure: test `_compatible` on the re-measured Period and Angle, then run the normal bridge (finder on the union, side shares). No new merge rule.
3. Add a break-present negative to the prototype: two real regions with equal Period and Angles more than 2° apart, at a 2-3 P gap, crossed by one frame-wide break. They must stay two regions. The 20 `two_free` frames only cover the no-break case.
4. If 1 and 2 do not recover the 4 frames, drop absorb and add the 4 seeds to ticket 17.

## 2. Full-frame chord for the 5.1 overshoot. Do not copy `analyse`'s light. Diagnose first. Owner: no.

**The artefact claim is not supported (measured here).** If the truth lit mask ended a few px short of `_light` at P 3-4, the single-break full frames at P 3-4 would overshoot too. All 20 `full_break` frames have overshoot 0.00. The overshoot appears only on `pair*` frames and on one `bin1x2` P 4 frame (2.5 P). So something specific to two breaks or to binning extends the segment. Candidates: a merged or absorbed region, or a fill across the second break. Not checked. Find the cause before changing any definition.

**Reject option 1** (truth lit mask closer to `analyse`'s light). The plan's N4 keeps the truth on the generator side. A truth that follows `_light` passes whatever `_light` does. That is the weakening choice.

**The faithful definition** follows from what the bound is for (critic 2, 3.3: a segment must not run outside the stripes):

- Region frames: the true chord is the line inside the truth region (`mask >= 0.5`). Unchanged.
- Full frames: the generator applies the break wherever it draws stripes, which is the whole frame (`harness2.py`, `generate` without `regions`; the implementer confirms this in `synthetic.py`). So overshoot is measured against the frame-clipped true line, and coverage stays against the generator-side lit mask.
- On full frames the overshoot bound is then vacuous. The plan must say so. The region frames carry the bound.
- The lit mask is fixed in `tests/` with protected constants before the test seeds are run. The harness's `gaussian(clean, sigma=P)` makes the truth depend on Period for no physical reason; use one fixed sigma.

This is not a weakening move under CLAUDE.md: the test does not exist yet and no tolerance changes. It does change settled plan text (5.1), so record it in the ticket Comments.

## 3. 109221-type frames and the AC tests. Keep the pre-declared seeds; no pass count, no exclusion in advance. Owner: no.

**What 109221 fails (measured here).** `found_ok` True, `striped` True, one region. So AC 2 passes, and so does the letter of AC 4 ("not split into fake separate regions"). It fails only the both-sides cover (0.14 against 0.5) and `MASK_IOU_MIN` (0.31). No bridge was attempted (`bridges` is empty): the rest is unreported, which is ticket 17's third bullet.

**The seeds are already honest.** The plan fixes `PHASE_BREAK_TEST_SEEDS = range(10, 20)`, one per case, never run, with "a red seed is a finding, never a re-pick". Keep exactly that.

The three options against CLAUDE.md:

| Option | Reading | Verdict |
|---|---|---|
| Fixed seeds picked after seeing outcomes, or re-picked after a red | Narrowing the selected tests. The seeds are protected numbers, so a later change is a lockfile edit. | Weakening move. Reject. |
| Pass count over many seeds in the slow tier | Turns "always" into a rate, which is a relaxed AC (critic 2, section 1: the owner's). It also adds about 20 min of BASE `analyse` to `make check-slow`. | Reject. Would need the owner. |
| Documented exclusion (`skip`, `xfail`, `--deselect`) | Listed weakening move. Needs an approval and a reason in the ticket Comments. | Only after a red, never in advance. |

**Shape of the tests:**

- The AC 2 and AC 3 tests assert 5.1 only.
- The AC 4 test asserts `striped`, exactly one region, and both sides covered (5.3).
- The IoU and Angle tolerances on break frames go in their own test. A ticket-17 mechanism then turns one named test red, not the AC 2 test.
- If a pre-declared seed goes red by the 109221 mechanism: it is a finding. The orchestrator may approve a `xfail(strict=True)` on that one parameter, citing ticket 17, recorded in Comments. Strict, so it goes red again when ticket 17 fixes it.
- Risk: 1 of 600 on explore. About 22 planned AC 4 frames give roughly a 4% chance of a hit.
- The rate itself is recorded from the explore and validation counts in the ticket Comments and in ticket 17, with seed 109221. It is not a test.

## 4. The new gates. Owner: no.

### `_BREAK_MIN_FRAME_PERIOD_PX` = 2.5. Keep a limit; the value is not yet justified and the refusal must be visible.

- **It is a second, stricter limit beside an existing one.** `MIN_FRAME_PERIOD_PX = 2.0` (`_local_stripes.py:61`) already decides which Periods are searched, and ticket 08 measured Period and Angle as good at 2.1 frame px. So regions with a frame Period in [2.0, 2.5) are reported, and their breaks are silently not searched. Under 2x1 that is sensor Periods 4 to 5.
- **The value rests on one point.** 2.0 gave fakes; 2.5 (P 5) works. No explore case lies between. Any value in (2.0, 2.5] fits. P 5 under 2x1 at Angle 0 sits exactly on the limit, so the `<` comparison decides it by float rounding.
- **To do:** measure P 4.2, 4.5 and 4.8 under 2x1, break-free and with a break, on fresh seeds. Or derive the limit: the finder's passband is `f0 · (1 ± k / (2π · s_across))`, and it reaches the frame's Nyquist at a frame Period of `2 · (1 + k / 2π)`, which is 2.5 at k = 1.57 and 2.64 at k = 2. State the rule in the constant's comment, next to `MIN_FRAME_PERIOD_PX`.
- **It also disables the bridge**, since the bridge calls `find`. A split at these Periods is not repaired.
- **Reporting.** `phase_breaks == ()` must not mean both "none found" and "not searched". Add a `Report.warnings` entry per affected reported region, in the style of the existing unresolved-Period warning: the region label, its Period in frame px, the limit, and "phase breaks were not searched". Put the same sentence in the `analyse` docstring. No new report field is needed (`warnings` is already in `to_dict`).
- **Tests.** One test asserts the refusal: P 4 under 2x1 gives no breaks and the warning. `test_binned_phase_break_is_found` names cases above the limit. Neither is a `skip`. The harness skipped P 3 under binning; the plan states that P 3 is unsearched there (ticket 08) and is covered by the existing warning.

### Sample cap 40 000. Not accepted as is; it may cost line accuracy at small Periods.

- On a 400x1600 frame the cap grows the stride at P <= 6 only: about 4 px, which is 1.33 P at P 3, 1.0 P at P 4, 0.8 P at P 5 and 0.67 P at P 6. The offset bin is 0.25 P and the finder's σn for a horizontal line is 0.5 P. The line offset is then sampled coarser than the transition it fits.
- Measured here on `full_break`: line error 0.89 and 0.51 P at P 5, 0.84 and 0.79 P at P 6, against 0.03-0.06 P at P 8-10, where the cap is idle. Region frames at P 5 reach 0.60 P. Two frames per Period, so this is suggestive only.
- The planned full-frame AC 2 seeds 10-13 include P 5. The margin to the 1 P tolerance is 0.11 P.
- **To do:** rerun full frames at P 3-6 with the cap off and report line error and time. If the cap costs accuracy, bound the stride in Periods (at most 0.5 P) and leave the speed to ticket 13.
- The cap hides nothing by itself, but its grid is anchored to the crop origin, so results change with the region's bbox. State that.

### Golden-section angle refinement. Accept.

- It is bounded to ±0.25°, falls back to the grid's best (`cand[0] > E`), and can only raise E. It is not a gate and cannot hide a failure.
- `line_tol` 0.1 gets a lockfile line.
- It assumes E has one peak inside ±0.25°; state that.
- The comment after `line_tol` in `FINDER` belongs to `min_frame_period`.

All three need lockfile lines. That is a lockfile edit, approved in the same way as the other `_BREAK_*` lines.

## 5. Other things the plan must change

- **Angle on small regions (measured here).** `small8`: 4 of 20 frames at 1.16-1.34° after the re-measure. The exclusion (±3 P) leaves about 1 P on each side of an 8 P region. The plan needs a minimum of pixels outside the exclusion; under it, BASE's Period and Angle are kept. Report BASE's Angle error on the same frames so the two can be compared. `weak` has one frame at 1.19°.
- **`BREAK_SMALL_REGION_PERIODS` = 5 leaves heights 6 and 7 P untested** (6 P: 0 of 20 changed; 8 P: 18 of 20 found). State which height is the limit and what happens between.
- **Fill overlap.** `owned` (`post.py:149-152`) is computed once and never updated. Two regions' fills can claim the same free pixel, which gives overlapping masks. Update it after each fill.
- **Depth is stale.** Depth is recomputed only for merged regions (`:249`). A region with a break keeps BASE's depth, measured at the biased Period and Angle and over the dim slit. `eval2.py` stores the depth and never compares it. Add the depth error against `DEPTH_TOL` to the table, then decide.
- **No guard on the re-measure.** Six free steps of `_phase_steps` (`:176-177`). Require the result to stay `_compatible` with the start; otherwise keep BASE's values. This also bounds the damage of a fake break before ticket 11.
- **Vacuous pass in the both-sides check.** `both_sides` returns 1.0 for a side with no truth pixels beyond 2.5 P (`eval2.py:86`). The real `assert_region_covers_both_sides` must fail when either side is empty.
- **Lost breaks.** A region absorbed through the band branch loses its own found breaks (`:231-235`).
- **Binned and pair misses are real.** `bin2x1` 109509 (P 14, line error 1.06 P), `bin1x2` 109515 (P 4, overshoot 2.5 P), and 3 of 20 pairs at 6 P. `BINNING_TEST_SEEDS` and the pair test are fixed; a red there is a finding. The handoff's "at 6 P every miss is at P <= 4" rests on 2 frames per Period.
- **The validation covers only the frozen code.** Every change above comes after it. Reserve one more fresh range and run the changed pass on it once before the constants go into the plan. The validation seeds are spent.
- **Ticket 17** gains seed 109221 with its numbers, the 3-region one-sided frames 109580 and 109582, and whatever absorb case is dropped.

## Count

| Item | Verdict | Owner |
|---|---|---|
| 1. Absorb | Constrain to the fill's bins plus a second bridge round after the re-measure; add the break-present two-region negative; else drop to ticket 17. Cannot fire without a found break. | no |
| 2. Chord | Reject a truth that follows `_light`. Overshoot against the generator's stripe extent (frame-clipped line on full frames), coverage against a generator-side lit mask. First explain why single-break full frames show no overshoot. | no |
| 3. 109221 and seeds | Keep `range(10, 20)` as declared. No pass count (relaxed AC, would be the owner's). No exclusion in advance; a strict `xfail` with approval only after a red. | no |
| 4. Frame-period gate | Keep a limit, justify 2.5 by measurement or derivation, report through `Report.warnings`, test the refusal. | no |
| 4. Sample cap | Ablate at P 3-6 on full frames; bound the stride in Periods. | no |
| 4. Golden section | Accept. | no |

## Checks run

Scripts in the session scratchpad `/tmp/claude-1000/-home-rusiva-dev-denoisifier/85ad64ff-6979-496b-bc0d-89a93d20c47a/scratchpad/`, run with `uv run --locked python <script> p2/all_explore.pkl.s6.eval.pkl`:

- `c3.py`: per tag, the count of merged frames with and without an accepted bridge; line error and overshoot by frame kind and Period; the largest Angle error on changed frames.
- `c3b.py`: per-frame line error and overshoot for `full_break`, `bin2x1` and `bin1x2`; Angle errors over 1° for `small8`, `weak` and `pair6`; the 109221 record.

Not checked: the cause of the pair overshoot, the cap ablation, absorb switched off, anything on validation seeds, and whether `generate` without `regions` draws stripes over the whole frame.
