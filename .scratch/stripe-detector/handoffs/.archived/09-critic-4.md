# 09 critic 4: the step-4 unit-test input, the [90-π] case, the refusal frame

Tree: `3bacb9d-dirty` (`src/denoisifier/_local_phase.py`, `tests/test_local_phase.py` uncommitted).
Nothing edited but this file. Scripts (scratch, may be cleared):
`/tmp/claude-1000/-home-rusiva-dev-denoisifier/85ad64ff-6979-496b-bc0d-89a93d20c47a/scratchpad/c4/`
(`exp.py`, `sweep.py`, `sweep_p.py`, `fd.py`, `ref.py`).

## Verdicts

| Item | Verdict |
|---|---|
| 1a. Blurred field as the unit-test input | **Approve**, with two conditions (below). It is the finder's real input, not a cover-up. |
| 1b. "0.4 P bias" | Not real on the real path. A smaller bias is real: **-0.125 P (half an offset bin) on grid-aligned lines**. Not an AC risk; record it, do not fix it in 09. |
| 1c. [90-π] red | **(b)**: `BREAK_EXACT_POSITION_TOL_PERIODS` 0.25 → **0.5** (= `_BREAK_SAMPLE_STRIDE_PERIODS`). Reject (a) and (c). |
| 2. Refusal frame with 2 regions | **Accept** the frame, one warning per region; do not pin the count 2; record the limitation. |

## 1a. Is the blurred field faithful?

Yes. Measured, P 8, stripe Angle 0, 200x200, disc r 90, 6 line angles x 3 jumps x 2 points
(`exp.py`), three inputs: the hard step, the blurred step, and `break_response` of a real
noise-free frame `1 + 0.5 cos(k·r + j·[side>0])` (a hard step in the image).

- The finder's output on the blurred field and on `break_response` of the hard-step frame is
  the same line to 0.01 px in 28 of 36 cases; the other 8 (line 90°, some π cases) differ by
  which of two near-equal E peaks wins, with the same error size.
- The fields themselves: `|response/depth - blurred|` is at most 0.06 inside r 60 (0.01 on
  tilted lines); `|response/depth - hard|` is 0.64-1.0. Inside r 90 the first is up to 0.19,
  from the frame edge.
- The hard field is 2.5-3.8 px (0.31-0.475 P) off at 0° and 90° and 0.6-0.9° off in angle at
  tilted lines. `find_phase_breaks`' contract is "`z` = `break_response` at Period and Angle"
  (its docstring), so the hard field is outside the contract: `analyse` never gives it one.

So the plan's `exp(i(k·r + j·[side>0]))` was a plan error (it forgot the finder's own window).
The change of input is a correction, not a weakening move by CLAUDE.md's list. Conditions:

1. The claim "this is what the Gabor gives" must be a test, not a comment: the existing
   `test_break_response_finds_a_break_in_a_generated_frame` covers one line (10°, π/2). Add a
   direct one: `break_response` of the noise-free hard-step cosine frame, divided by the depth,
   equals `_field(...)` within a stated tolerance on a disc away from the frame edge, for at
   least line angles 0 and 90 (measured 0.06 at r 60; the implementer measures and states its
   own number).
2. The module docstring of `tests/test_local_phase.py` still says
   `z = exp(i (k . r + jump [side > 0]))`. Fix it, and record the plan deviation in the
   ticket's Comments.

## 1b. Is there a real finder bias?

Yes, a small one, and it is not the 0.4 P.

- Line 0° (horizontal: the typical break), blurred input, point moved in 0.5 px steps over one
  Period (`sweep.py`): centre error takes only the values 0, -0.5, -1, -1.5, -2 px;
  **mean -1.0 px = -0.125 P**, max 2.0 px = 0.25 P. Same pattern at 90° for π/2.
- Cause (`_Samples.scan`): `lo = s.min()` is itself a sample, and on a grid-aligned line every
  sample lies at `lo + m · stride`, i.e. exactly on the left edge of its 0.25 P bin, while the
  fitted step treats it as at the bin centre (`(rk + 0.5) * bin`). Tilted lines fill the bins
  evenly and have no bias. (Samples exactly on bin edges also make `idx` depend on float
  rounding.)
- A one-line trial on a scratch copy (`lo = s.min() - bin / 2`, `sweep_p.py`) removes the
  centre bias at 0° (mean -0.15 px) but does not cure the 90° angle error (max 1.5°, end
  0.46 P). So it is no fix for the red case.

AC relevance: AC 2 allows 1 P. This bias is ≤ 0.25 P, and it was already inside every
prototype number (v2 validation max 0.89 P, horizontal breaks included). It does not threaten
an AC beyond what the plan accepted. The finder is the prototype's validated one (860 seeds);
changing `lo` in 09 would un-validate it. **Rule: do not change the finder in 09. Add the
half-bin bias to the plan's section 8 known limitations and to ticket 17 (or 11) with the
trial above.** "Fix the code, never the check" does not bite here: no check is red because of
this bias.

## 1c. The [90-π] case: (a), (b) or (c)?

The red is not special to that parameter. On the faithful input, 10 line angles x 4 jumps x
12 random points within ±1 P of the centre (480 runs, `sweep.py`), max chord-end error:

- overall **max 0.364 P**, p95 0.208 P, **1.3 % over 0.25 P**;
- over 0.25 P: 90°/π 0.364 P (angle 1.06° off), 45°/π 0.265 P, 0°/2.0 rad 0.264 P;
- centre error never over 0.238 P; every break found, 480/480.

So 0.25 P was never a property of the finder: the plan picked it without a measurement
(section 7: "noise-free unit tests"), and 14/15 green is luck of the one test point. The 90°
line is the finder's weakest: parallel to the stripes the window is widest across the line
(σn = 1 P), E is flattest in angle, and the fine scan lands two 0.5° steps off.

- **(a) xfail(strict=True): reject.** It pins one parameter as "known bad" when the cause is
  the tolerance, leaves the other 14 one point-move from red, and is a listed weakening move
  with no good reason.
- **(c) centre plus angle check: reject.** It needs a new angle tolerance above 1.06°, a
  number fitted to the failure, and it drops the chord-end metric, which is the one AC 2 uses
  ("every segment point within tol of the true line").
- **(b): approve, 0.25 → 0.5.** Reason for the number: `_BREAK_SAMPLE_STRIDE_PERIODS` is 0.5;
  a line cannot be asked to be placed finer than the samples it is fitted to. Evidence: max
  0.364 P over 480 noise-free runs (27 % margin). It stays at half of AC 2's 1 P. What the unit
  tests guard (sign, canonical angle, transposed or mirrored coordinates, wrong offset origin)
  gives errors of many Periods, so 0.5 P loses none of it. A number between (0.3, 0.4) would
  again be fitted to one sweep.

This is a protected-number edit (`tests/protected.py` + lockfile): approval and reason go in
the ticket's Comments before the edit. Comment at the constant: "= the finder's sample
stride; measured max 0.364 P, 480 noise-free runs (09-critic-4)".

One more defect in the same test, found on the way: line 90° sits on the canonical cut. On
the real response at point (102.8, 97.8), jump +π/2, the finder returned -88.99° with jump
-1.581: correct (direction reversed, sign flipped), but
`test_a_break_is_found_on_its_line_with_its_jump` compares `found.jump_rad` with the
canonical `want_jump` without aligning directions, so it would fail there. It passes today
only because the blurred case lands at 89.7°. **Rule: align first, as plan 5.1 says: flip the
found jump iff the found direction `(cos a, sin a)` and the true direction have a negative
dot product; never "try both signs".**

## 2. Refusal frame

Reproduced (`ref.py`; 2x1, 400x1600, sensor P 4.7, Angle 0, `BINNING_TEST_SEEDS[0]`):

- no break: 1 region (216493 px), 1 refusal warning;
- horizontal π break: 2 regions (108308, 102890 px), `phase_breaks == ()`, 2 refusal
  warnings, labels 1 and 2 in order, between the unresolved-Periods warning and the coverage
  note.

Accept the proposal. The 2 regions are BASE's split at the break, and under the gate nothing
can bridge them (plan 2.2 step 0: the bridge is disabled with the finder). The frame now
tests more of 2.3 step 7 (one entry per region, label order) than the planned one-region
frame did. It is the same frame, so it is not a seed re-pick. Rules:

1. Assert `phase_breaks == ()`, and that the refusal entries are exactly one per reported
   region, in label order, each with its label and frame Period (2.35), placed between the
   two other warnings. Do not assert `len(regions) == 2`: that would pin BASE's split, which
   ticket 17 may change. Assert at least one region.
2. Add the break-free twin of the same frame (1 region, 1 warning) if it is cheap: it shows
   the warning follows regions, not breaks.
3. Record in plan section 8 and the `analyse` docstring: under 2.5 frame px a break is not
   found and the region it splits stays split (AC 4 is not held there; the warning is the
   only sign). Record the plan-5.4 deviation in the ticket's Comments.
