# 09 critic 2: scope ruling on Q2 / C3 and the prototype's four questions

Read against the code at `b7c6731`, the ticket, the plan, the review, critic 1 and `09-prototyper-1.md`. Three checks were run on the prototype's own data (scripts and commands in the last section; nothing in the repo was edited).

"Owner?" is yes only for (a) taste between equivalent options, (b) knowledge not in this repo, (c) a hard-to-revert architectural decision.

**Summary: no item needs the owner before work continues.** Recommended scope is C: the detector's score path stays untouched, and AC 4 is met by a report-level pass that runs after the score is fixed. One follow-up ticket is filed for the score-moving part. Two notes go to the owner at close.

## Three findings the handoff does not have

- **F1: the premise "fixing `_phase_steps` moves Angle and Period but not the score" is wrong as written.** `_phase_steps` has three callers: the candidate step (`analysis.py:537`), the merge step (`:641`) and `_refined` (`:790`). The first two feed `filters.depth(period, angle_deg)` → `_grow` → the size rule and the leakage test → the survivors → `score = max(peak_ratio)` (`:285`). So a change to the body of `_phase_steps` can move the score. Only a change confined to `_refined`, or made after `reported` is settled (`:286`), is score-neutral.
- **F2: the mask misses the spec's IoU tolerance on break frames, and the bbox test does not see it.** On the prototype's 600 break frames, IoU against the truth is under `MASK_IOU_MIN = 0.8` on 123 frames: 0 of 200 at π/2, 4 of 200 at 3π/4, 119 of 200 at π (minimum 0.541; break-free minimum 0.842). The cause is the slit along a π break. Of the frames with IoU under 0.8, most pass the bbox check (for example seed 109419, bbox OK, IoU 0.551). So "bbox within 1 P" is both too strict (it fails 21 frames that are one unsplit region) and too weak (it passes a region with a hole 2.5 P wide).
- **F3: both the Angle bias and the slit can be repaired after the score, using the found break.** Measured upper bounds, with the *true* line standing in for the found one:
  - Angle: re-running `_refined`'s loop on the region's pixels farther than `k` Periods from the line, starting from the biased values. Frames over 1° out of 40:

    | cell | reported | k = 2.5, 4 steps | k = 2.5, 8 steps | k = 3.5, 4 steps | k = 3.5, 8 steps |
    |---|---|---|---|---|---|
    | a = 0, j = 3π/4 | 29 (max 3.91°) | 2 (1.15°) | 0 (0.94°) | 0 (0.94°) | 0 (0.78°) |
    | a = 10, j = π/2 | 31 (2.62°) | 0 (0.73°) | 0 (0.66°) | 0 (0.60°) | 0 (0.44°) |
    | a = 0, j = π | 18 (3.18°) | 0 (0.55°) | 0 (0.38°) | 0 (0.71°) | 0 (0.57°) |

    Two steps (today's `_REFINE_STEPS`) are not enough from a biased start: 15-17 of 40 stay over 1° in the worst cell. Without the exclusion, more steps do not help (29 of 40 at any step count).
  - Slit: adding the band within ±1.5 P of the line, over the region's extent along it, gives IoU ≥ 0.8 on all 600 frames (minimum 0.800, so the margin is nil; ±2.5 P leaves one frame at 0.797).

  These are feasibility bounds, not results: the real pass uses the found line (up to 1 P off), and the constants were not chosen on held-out seeds.

## 1. What AC 4 requires

Ticket text: "A frame with phase breaks is still recognised as striped, and its region is not split into fake separate regions." Spec story 23: "so that defects never hide the effect itself."

- **Required:** `report.striped`, and one true region gives exactly one reported region.
- **"bbox within `BBOX_TOL_PERIODS`" is not a faithful reading.** It is a ticket-05 accuracy limit for break-free regions. The spec's tolerance list (spec.md:162) has no bbox item, and the same seeds fail it 1 of 600 times with no break. The plan added it "to prove the region spans both sides of the break". That intent is right; the instrument is wrong (F2).
- **The 21 overgrowth frames (1.1-1.4 P against 1 P) are not AC 4 failures.** Each is one unsplit region. They are a ticket-05 accuracy miss on a new frame type.
- **The 2 of 600 region splits and the 1 of 20 full-frame split are AC 4 failures by the letter.** The ticket gives no rate, the tests use fixed seeds, and plan Q5 says a failing seed is never a re-pick. So "accept splits at some rate" cannot be written as a test without loosening the AC. That loosening would be the owner's. It is not needed (section 2).
- **Faithful test for AC 4:** `striped`; exactly one region; and that region covers both sides of the true line: on each side, at least half of the truth pixels farther than 2.5 P from the line are in the region. On the prototype data every one-region frame has at least 0.75 on its weaker side, and the split frames have 0.00, so the limit of 0.5 separates them with room. This is a new acceptance limit in `tests/protected.py`, a lockfile addition.
- **Angle on break frames is not in AC 4's text, but it is in scope for the ticket's close.** Spec.md:139 and :162 put the angle tolerance (±1°) on every reported region. Spec.md:7 says the stripes' structure "is broken by phase breaks", and the ticket says breaks "usually cross the stripes roughly horizontally": the worst case for the bias is the common case in real frames. Ticket 09 is the first ticket that can generate such a frame. Shipping `phase_breaks` while the same report's Angle is 2-4° off on 45% of those frames, with no test and no ticket, is the "ships unseen" case critic 1 named in C3. It must be either fixed or recorded; it must not be silent. The same holds for F2.

Owner: no. The reading follows the ticket text and spec story 23. Dropping the bbox line removes nothing that exists: the test is not written yet. Record the change of reading in the ticket Comments.

## 2. Scope

### Verdict: C. No change to the score path in ticket 09.

**C = B plus a report-level pass after the score.** Everything below runs after `reported` is settled (`analysis.py:286`), so `score`, `striped` and the calibration cannot move.

1. **Find breaks** in each reported region (the plan's 2.3, with C2's recompute).
2. **Bridge.** For each pair of reported regions that are `_compatible` and closer than a stated gap, run the finder on the union plus the pixels between them. If it accepts a break whose line runs through the gap, the two regions become one region and the break is reported in it. This is the only step AC 4 strictly needs. The prototype's finder takes `interior = pixels & ...` (`detector.py`), so its domain must be widened for this; the response in the gap is valid, only dim.
3. **Fill the slit** along each accepted break (F3), so the mask and the reported segment agree.
4. **Re-measure Period and Angle** of a region with an accepted break on its pixels away from the break (F3).
5. **Record what C does not fix**, in a follow-up ticket (below).

Steps 3 and 4 are conditional: keep each only if the successor prototype shows, with the *found* line and on fresh seeds, that it meets the existing protected tolerance (`MASK_IOU_MIN`, `ANGLE_TOL_DEG`). If one does not, drop it, do not assert that tolerance on break frames, and add it to the follow-up ticket. Do not reach into `_grow`, `_merge` or the body of `_phase_steps` to rescue it.

### Why not A (fix growth, merging or `_phase_steps` in ticket 09)

- **It reopens ticket 05.** `_GROW_FRACTION`, `_MERGE_GAP_PERIODS` and the grow level's reference were tuned on `REGION_CALIBRATION_SEEDS` 90_000-90_599 and frozen (ticket 05 Comments). A change means re-tuning on those seeds and re-proving ticket 05's criteria, before any break work.
- **It makes 09 an unplanned measure milestone.** CLAUDE.md names 05, 07 and 13. The sequence is `make measure` (39 min), stored thresholds, the calibration driver (14 min), three lockfile edits, `make check-slow` (16-20 min), `make check-held-out` (17-20 min), `make check`: about two hours on an idle machine, with the feasibility gate, the pass counts and the borderline seeds all able to go red. Ticket 07's calibration (`T 1% = 100.805`) was stored one day ago.
- **The gain is small.** A fixes 21 frames that are 0.1-0.4 P over a tolerance the spec does not list, and 3 splits that step 2 fixes without it. It does not fix F2 (the slit is a property of the filter at a π jump, not of the grow level) and it is not needed for the Angle (F3).
- **Widening `_MERGE_GAP_PERIODS` is the wrong cure for the splits.** It merges on distance alone, so it also merges genuinely separate neighbours on break-free frames. Bridging merges only on evidence of a break.
- **A score-moving fix has a planned home.** Ticket 16 (needs-triage) is already an explicit detector change with `make measure` and a re-store. Ticket 13 says "without changing the results" and re-calibrates only if they changed, so it is the weaker host.

### Why not plain B (finder between regions, no merge)

- A break reported between two regions still leaves two regions: AC 4 fails by the letter on 2 of 4 frames at P 3, 45°, π.
- It needs a schema answer that C avoids: which `region` does a break between two regions carry?
- It leaves F2 and the Angle bias with neither a fix nor a test.

### Risks of C, and what the plan must add

- **R1: the "nothing upstream changes" claim becomes conditional.** Reports stay byte-identical to BASE only on frames with no accepted break. A fake break now has side effects: a slightly different Angle, a few added mask pixels, or a wrong merge of two real neighbours. Until ticket 11 the rate is uncalibrated. → Section 6 of the plan must say so. The step-5 BASE diff runs on break-free frames and must include a frame with two compatible neighbouring regions if `tests/regions.py` can make one (ticket 05's two-region frames have different Periods, so they never reach the finder).
- **R2: a half below the threshold.** If only one half of a split region scores over the threshold, the report has one region covering one side. AC 4's letter holds, the "both sides" test fails. → Let the bridge consider any survivor next to a reported region. It still cannot change `score` or `striped`. The prototype counts how often this happens.
- **R3: order and labels.** Bridging and filling change `area_px`, so the sort (`:287`) and the labels are settled after the pass. `phase_breaks[*].region` refers to the final labels.
- **R4: speed.** Step 4 costs up to 8 extra Gabor filters per region with an accepted break, on the existing `_Spectrum`. Ticket 13's budget is 5 s for 400x1600 with breaks. → The prototype times it and tries a better start (the bank's estimate, or per-side estimates) to cut the step count.
- **R5: weak breaks stay biased.** A break under the finder's limits (`|jump| < π/4`, or low evidence) is not found, so its Angle bias stays. The bias scales with the jump. → Follow-up ticket.
- **R6: nil margin in F3's fill** (minimum IoU 0.800 at ±1.5 P with the true line). → If the found line cannot hold `MASK_IOU_MIN`, state the measured IoU in the ticket Comments rather than asserting it.

### Follow-up ticket (file at this ticket's close, `needs-triage`)

"Region growth and phase steps under phase breaks":
- the grow level drops when the seed area straddles a break (bbox 1.1-1.4 P over on 21 of 600);
- `_phase_steps` is a weighted mean and folds a blurred jump into the frequency at the candidate and merge steps (candidate Angle −7.68° against −10°), including for breaks the finder does not accept (R5);
- whatever of steps 3 and 4 the prototype dropped.

It is score-moving: `make measure`, a re-store and the held-out tests. Suggest it rides with ticket 16.

### Owner?

**No.**
- Not hard to revert: the pass is private code after the score, the report schema is as critic 1 ruled it, and no stored number changes.
- Not taste: A costs a milestone and reopens ticket 05 for a smaller gain than C; plain B fails the AC's letter.
- No outside knowledge is needed.

Notes for the owner at close, non-blocking: (i) the follow-up ticket and its numbers; (ii) the change of AC 4's reading from "bbox within 1 P" to "one region covering both sides".

The owner would be needed only if the successor prototype shows bridging cannot remove the splits on its fresh seeds. Then the choice is between A (a milestone) and a stated split rate (a relaxed AC), and that is the owner's.

## 3. The prototype's four open questions

### 3.1 The finder's own Gabor, σ along = 0.5 P. Accept. Owner: no.

- The plan's premise failed by measurement (138 of 600): the bank's along window (`_ALONG = 1.5`) smears a break over about ±3 P of a 10 P region. The cost is the one filter per reported region that C2 already requires.
- Conditions:
  - It was picked from three settings on the seeds it was scored on. Freeze it, then confirm on fresh seeds.
  - The window sigmas enter the fit's `σn`. Use one pair of constants for the filter and the model.
  - A window three times shorter passes more noise. All 600 frames have depth 0.5. Report the detection rate at a weaker depth (0.2-0.3) as information; no AC asks for it.
  - Check P = 3, where σ along is 1.5 px.
  - Step 4 above changes the final Angle. The finder's response is then re-tuned once more, or the plan states which Angle the finder uses.

### 3.2 Aligning directions before comparing jumps. Accept; it is a correctness fix, not a loosening. Owner: no.

- An undirected line has two spellings: (angle, jump) and (angle ± 180°, −jump). The canonical range (−90°, 90°] has its seam at vertical, so a line found at −89.5° against a truth at 90° is the same break with the other sign. Comparing without alignment fails correct answers (about 20 of 40 at a = 90).
- Conditions:
  - Flip the found jump if and only if the two direction vectors have a negative dot product (as `evaluate.py` does with `cos(found.angle − a) < 0`). Never "try both signs and keep the smaller error": that would pass a wrong-sign π/2 jump.
  - In the real test the direction comes from the reported points' order and the cross-product rule (critic 1, B3), not from an angle field.
  - `UNITS["jump_rad"]` says that near vertical the point order and the sign flip together.
  - Sign-pinning tests avoid lines within a few degrees of vertical and `|jump| = π` (critic 1, C1).

### 3.3 Slit-aware segment, region pixels within ±2.5 P. Accept the aim; change the form. Owner: no.

- 2.5 P is the largest slit seen on the tuning sample (seed 109419), with no margin and no derivation. Tie the band to the model: a multiple of the fit's `σn`.
- With step 3 (fill) the question disappears: the segment is the line's run through the filled region.
- **Gap in metric 5.1:** it bounds the distance to the true *infinite* line and the coverage from below, so a segment that overshoots the region is never penalised, and a wider band makes overshoot more likely on tilted lines. → Add: neither end of the reported segment lies more than `BREAK_POSITION_TOL_PERIODS * P` beyond the true chord.

### 3.4 Replace the band-contrast finder with the two-amplitude fit and greedy explain-away. Accept. Owner: no.

- The plan's method was measured and failed; the replacement reaches 594 of 600 with 0 fakes on 820 break-free frames. It is still "from the local phase" (ADR 0001): it works on the demodulated complex response. It lives in a private module, so it is not an architectural commitment. Critic 1's N1 (define E exactly) is met by the explained-power formula.
- Conditions before the constants are frozen:
  - **Fresh seeds.** Every number so far is in-sample. Zero fakes in 820 bounds the rate under about 0.4% per frame, but the selection was made on those frames. Validate once on a new range reserved in `USED_SEEDS`; `evaluate.summary`'s halves do not count, both halves were looked at.
  - **The margin is thin.** Largest break-free E is 0.075 against a limit of 0.1 (1.33x); only the jump rule rejects that frame. The break-free frames have no Spikes, one depth and no forks. Ticket 11 calibrates on frames with Spikes. → E is the one scalar that ticket 11 calibrates; the jump and spread rules stay fixed gates. Say so in the `analyse` docstring (critic 1, B4).
  - **Explain-away is untested for its purpose.** `pairs` was written, not run. The second break is found on data altered by the first, so an error in the first carries over. Run it before the plan relies on `test_two_parallel_phase_breaks_are_both_found`. Keep the cap on breaks per region and state it.
  - **Small regions.** The fit needs a ±4 P window, and a region may be 2 P tall. State what is reported there (no break) and test it.
  - **Fixed-seed red risk.** If bridging removes the 2 splits, the listed residual is 3 line errors of 1.01-1.21 P, all at π jumps. (The handoff's totals do not agree: "594/600" is 6 misses, the per-cell counts give 4, the failure list gives 5. The successor reconciles them.) With "never a re-pick", a red AC test is a finding to fix in the finder (the found line's angle is about 6° off in those three). Check whether step 4's better Angle removes them before freezing.
  - **Unfinished P1 items stay required:** `line_err` by Period at P = 3, the timing on 400x1600 with one and three regions, `binning`.
  - Rename in the plan: the method is no longer a "contrast" (critic 1, C4, is then moot).

## Count

| Item | Verdict | Owner |
|---|---|---|
| 1. AC 4 reading | striped, exactly one region, covering both sides; bbox line dropped (over-strict, and blind to the slit) | no |
| 1. Angle on break frames | not in AC 4's text; in scope to fix score-neutrally or record, never silent | no |
| 2. Scope | C: score path untouched; bridge across a found break (required), fill and re-measure if the prototype confirms; follow-up ticket for growth and `_phase_steps` | no (yes only if bridging fails on fresh seeds) |
| 3.1 Own Gabor | accept, with conditions | no |
| 3.2 Direction alignment | accept; flip by direction only | no |
| 3.3 Segment | accept the aim; band from `σn` or the filled region; add an overshoot bound to 5.1 | no |
| 3.4 Fit and explain-away | accept; fresh-seed validation, `pairs`, E as ticket 11's scalar | no |

## Checks run (read-only on the repo; scripts in the session scratchpad)

Scratchpad: `/tmp/claude-1000/-home-rusiva-dev-denoisifier/85ad64ff-6979-496b-bc0d-89a93d20c47a/scratchpad/c2/`. Data: the prototype's `p1/main.pkl`.

- `iou.py main.pkl`: IoU and two-side coverage per cell (F2, section 1). In the per-cell output, IoU under 0.8 on the largest region: 0/0/0/0/0 at π/2; 2/1/1/0/0 at 3π/4; 28/29/26/27/11 at π. Weaker-side coverage at least 0.75 on every one-region frame, 0.00 on seeds 109530 and 109550.
- `fill.py main.pkl`: IoU after adding a band along the true line (F3). Frames under 0.8: π/2 0 → 0; 3π/4 4 → 0; π 119 → 0 at ±1.5 P (minimum 0.800), 1 at ±2.5 P (0.797). These counts use the union of reported regions, so they differ slightly from `iou.py`'s largest-region counts.
- `iter.py`: regenerates 3 cells of 40 frames through the prototype's `harness.py` (seeds 109_200-109_239, 109_040-109_079, 109_400-109_439, already used by P1) and iterates `_phase_steps` on `filters.spec.gabor` with the true line's zone excluded (F3 table).
- `angle.py main.pkl`: one step on the stored response. It under-states the fix (22 of 40 still over 1° in the near-horizontal cells), because the stored response is tuned to the biased Angle. This is why step 4 needs more than `_REFINE_STEPS = 2` steps or a better start.

Not checked: bridging itself (no finder run on a union of two regions), the fill and the re-measure with the *found* line, timing, and anything on fresh seeds.
