# 09 critic: verdicts on Q3-Q9, B1-B6, O1

Read against the code at `b7c6731` (plan uncommitted). Q1, Q2 and P1 belong to the prototype; only risks are flagged for them (last section).

"Owner?" is yes only for (a) taste between equivalent options, (b) knowledge not in this repo, (c) a hard-to-revert architectural decision.

**Summary: no item needs the owner before work starts.** Two items carry a non-blocking note to the owner at close (O1, Q4). One becomes an owner question only if P1 fails it (Q8).

## New findings (neither planner nor reviewer has them)

- **C1 break: the sign of `jump_rad` is undefined until the phase direction is stated.** "Phase on the positive side minus the negative side" needs a convention for which way the phase grows. In the generator it is fixed: `_phase = 2π/P (x cos t + y sin t) + phase0` (`synthetic.py:398-400`), so the phase grows with the column. The detector's filter selects the same sign (`_local_stripes.py:177`, `across = fx cos t + fy sin t - 1/period`). The plan's 2.4 docstring and `UNITS["jump_rad"]` never say this. → State it in terms a reader can check on a picture: "a positive jump means the stripes on the positive side sit toward column 0 by `jump / 2π` Periods (toward row 0 in file layout when transposed)". Add one noise-free test that pins the sign end to end (generator jump `+π/2` → reported `+π/2`).
- **C2 break: 2.3 contradicts itself on which response is used.** It says the finder runs "at the region's final refined Period and Angle", and also "pass the response `_refined` last computed". `_refined` computes `gabor(period, angle_deg)` and then updates both (`analysis.py:789-796`), so the last response it computed is tuned to the estimate *before* the final one. With N2 (no `_Filters` in `analyse`), the fix is one rule: `_qualifying_regions` also returns its `_Filters`, and `analyse` recomputes `filters.spec.gabor(...)` at the final values for reported regions only. `_Survivor` is untouched, so the score path stays as it is. P1(c) must time this extra filter per reported region.
- **C3 risk for P1: the reported Angle of a broken region may be biased.** `_phase_steps` sums neighbour products (`analysis.py:606-607`); it is a weighted mean, not a median. The filter blurs a break over about 1.5 Periods along the stripes (`_ALONG`), so the rows near a horizontal break add a phase ramp of about `jump` to the vertical products. Rough size: a frequency error of `jump / (2π H)` cycles per px for a region `H` px tall; at P = 20, `jump = π/2` and H = 60 that is several degrees. A jump of π mostly dims the response instead, so the worst case is near π/2. The plan claims "nothing upstream changes" and no AC asserts Period or Angle on break frames, so this would ship unseen. → P1(a) must also report the Period and Angle errors of the broken region against the existing protected tolerances, and AC 4's test must assert them. If they fail, the fix is in `_refined` / `_phase_steps`. That does not move the score (`peak_ratio` is set before `_refined`), but it does change reported Period and Angle, so the "byte-identical to BASE" claim of 2.3 would go, and that is an orchestrator ruling like Q2.
- **C4 note: "contrast" is on Modulation Depth's `_Avoid_` line (`GLOSSARY.md:31`).** The plan writes "two-sided phasor contrast" in the docstrings and in the ADR sentence of step 7. It is not in `CURATED`, so no test fails, but it is the same drift B6 is about. Use "phase difference between the two sides".
- **C5 note: typical noise is EMCCD** (`tests/regions.py:24`, `TYPICAL = dict(noise=Emccd())`). With B1, every "same seed, with and without the break" pair on AC frames is two independent noise draws. See B1.

## Reviewer items

### B1: bit-identity under EMCCD. Reviewer is right; verdict below. Owner: no.

Verified: `clean = clean / clean.max() * noise.photons_peak` (`synthetic.py:318`); `rng.poisson` then `rng.gamma(n[lit], ...)` (`:429-433`), whose draw counts depend on the values; `_spikes(..., clean.max())` (`:347`). Gaussian noise is `clean + rng.normal(0, noise * peak, size)`, independent of `clean`, so identity holds there.

What the plan should claim instead:
1. `phase_breaks=()` is bit-identical to BASE for all kinds. `_BASE_DIGESTS` already has a `scorched-emccd` entry (`tests/test_synthetic.py:174`), so the existing digest test covers it. The implementation must branch (`if phase_breaks:`) so the empty path does no arithmetic.
2. With breaks, Gaussian noise, `spikes=0`: `frame` and `clean` are bit-identical off `shifted`.
3. With breaks, EMCCD: no pixel-level claim on `frame`. If a check is wanted, `clean / clean.max()` is equal off `shifted` to rounding. The `generate` docstring says the break changes the noise realisation everywhere.
4. Consequence (C5): `test_phase_break_does_not_add_regions_to_full_frame_stripes` and P1's defect-free twins compare different noise draws. They stay valid as statistical checks, but the plan must not describe them as "the same frame plus a break". For a true paired check, add a Gaussian-noise variant.

Do scores "move"? **No, and `make measure` is still not required.** The no-move claim rests on (1) and on `analyse` not touching the score path. Neither depends on frames that contain breaks, and no calibration, slow-tier or feasibility frame passes `phase_breaks`. B1 removes a false test claim; it does not touch section 6's conclusion. Section 6 should cite its evidence correctly: the digest test, `make check-slow`'s exact rescoring, and the step-5 BASE diff, which must include one typical EMCCD frame.

Rejected alternative: scaling EMCCD by the break-free maximum to rescue identity. It still fails (Poisson draw counts) and adds a second code path.

### B2: canonicalising and `shifted`. Reviewer is right; take B, reworded. Owner: no.

Verified by algebra: `side = d_x (y - y0) - d_y (x - x0)` changes sign with `d`, so the plan's "same set of pixels either way" is false.

Verdict: option B, and define the input as a *difference*, not as "which side is moved". `PhaseBreakLine.jump_rad` is "the stripe phase on the positive side of the directed line minus the other side". The generator canonicalises first (angle into (-90, 90], jump sign flipped with the direction, wrapped to (-π, π]) and adds the canonical jump on the canonical positive side. Then `shifted` is always the canonical positive side, the truth and the Report share one convention, and the off-`shifted` identity test has one form. The two spellings of one line differ only by a global phase, which `phase0` randomises anyway. The 2.1 docstring line "added to the stripe phase of every pixel on the positive side" must go.

`side == 0`: use strict `> 0`, so pixels exactly on the line are not shifted; say so in the docstring. Tests place `point` at half-integer coordinates where the tie matters.

Decided by: correctness plus the simplest invariant. Not taste: A leaves `shifted` meaning two different things.

### B3: `jump_rad` under `in_file_layout`. Reviewer is right; take the fix. Owner: no.

Verified: swapping (row, col) in both vectors turns `a_col b_row - a_row b_col` into its negative. `in_file_layout` today only transposes `labels` and bboxes (`report.py:220-230`).

Verdict: `in_file_layout` swaps each point and reverses the point order. `jump_rad` is then equal in both layouts (like Period and Angle), and the cross-product rule is the single normative definition of the positive side in both. Checked on a horizontal line: "below" in the analysed frame becomes "right" in file layout, and the reversed points give exactly that. The docstring states the order per layout (col increasing analysed; row decreasing in file layout) as a consequence, not as the definition. The CLI test checks the side on a pixel. Combine with C1.

The alternative (negate the jump and keep "col increasing") makes `jump_rad` differ between layouts for no gain.

### B4: provisional threshold. Reviewer is right; extend it. Owner: no.

The arithmetic holds: `1 - (39/40)^10 = 22%`, `1 - (39/40)^30 = 53%`. Q5's "at most 1 in 40" and "a failing seed is never a re-pick" together give a likely red with no remedy.

Verdict: P1 freezes `_BREAK_MIN_EVIDENCE` with zero fakes on all its defect-free frames and a stated margin over the largest fake evidence, and reports the gap to the smallest true evidence at π/2. Two additions:
- Fakes on *break* frames are a different population (side maxima and duplicates next to a true break). 5.1's "no other reported break in that region" depends on them, so P1 must count extras on its break frames too, not only on defect-free ones.
- The plan and the `analyse` docstring must say the value is conservative on purpose and that ticket 11 sets the calibrated rate. No rate is claimed in this ticket.

Keep Q5's "never a re-pick". If P1 finds no gap at π/2, that is the escalation (to the orchestrator; to the owner only if the AC itself has to give).

### B5: step order. Reviewer is right. Owner: no.

Verified: `grep PhaseBreak src/denoisifier` is empty at BASE. Swap steps 2 and 3.

### B6: glossary terms. Reviewer is right on "amplitude", half right on "defect". Owner: no.

- "amplitude" is in `CURATED` (`tests/test_glossary_terms.py:24`). Docstrings and comments are scanned; identifiers are not. So `_BREAK_MIN_AMPLITUDE_FRACTION` would pass the test, but rename it anyway (`_BREAK_MIN_DEPTH_FRACTION`); the prose must say "depth" or "magnitude".
- "defect" is on Fork's `_Avoid_` line (`GLOSSARY.md:81`) but not in `CURATED`, so the reviewer's "fails `test_glossary_terms`" applies to "amplitude" only. The glossary avoids "defect" as a synonym for Fork. Using it as an umbrella for breaks and forks is a new sense, and nothing in the package uses it today (grep: only the glossary line). Do not introduce it. `_defect_phase` → `_break_phase` (ticket 10 renames or adds beside it). Test names say "break-free", not "defect-free".
- Also C4 ("contrast").

## Owner item

### O1: frame px or sensor px for break lines. Verdict: frame px (A). Owner: no to blocking; one confirmation line at close.

The two sources do conflict. spec.md:114 and ticket 08's opening both say "positions in the report are in sensor pixels", and spec.md:162 uses "break and fork positions", so the literal spec covers exactly this field. But ticket 08 AC 4, the owner's own criterion and now resolved, split the report in two: things that say *where in the frame* (bbox, mask) are in frame coordinates, and *measurements* are in sensor px. `Report.UNITS` at BASE follows that (`report.py:191-201`). A break line is a location in the frame, so A follows the rule the owner already accepted. No new rule is needed.

The reviewer's "hard to reverse" is overstated:
- the conversion is exact and lossless (`bin_factors` is in the report), so no information is fixed by the choice;
- `units` describes each field, and nothing consumes `phase_breaks` yet (ticket 12 is not built);
- at 1x1 the two are the same numbers.

Reasons A is better beyond consistency:
- a line in the same coordinates as `bbox` and the mask can be drawn and intersected with them without conversion;
- sensor-px positions would bake a sub-pixel origin convention into the public schema (a frame pixel `r` covers sensor rows `v r .. v r + v - 1`, centre `v r + (v - 1) / 2`), which frame px avoids.

Conditions on A, which the plan must add:
- The *tolerance* is a measurement: "within one Period" is checked in sensor geometry (scale the frame-px offsets by `pixel_size(bins)` before taking the distance). This replaces the plan's "P / v (or /h)" (reviewer N4).
- The binned test's truth line is in sensor px (the frame is generated at sensor size and block-summed, `tests/binning.py`), so the helper converts it with the half-pixel centre offset above. State the formula in the plan.
- `UNITS["line"]` says frame px; ticket 10's fork `point` follows.
- Record in the ticket Comments that this departs from the literal spec.md:114, and propose the one-line spec edit ("positions" → "measurements; locations such as bbox, mask, break lines and fork points are in frame px") for the owner to confirm at close. This does not block.

Decided by: the precedent of ticket 08 AC 4. It would be an owner question only if the owner had not already ruled on bbox and mask.

## Planner questions

### Q3: schema and sign. Accept with B3, C1 and O1. Owner: no.

`{"region", "line", "jump_rad"}` after `regions` matches spec.md:106; `region` is an additive field and makes Q7 checkable. A polyline with two points is fine. The gaps are B3 (file layout) and C1 (phase direction). Decided by spec plus correctness.

### Q4: generator API; straight lines only. Accept. Owner: no; note at close.

The line-angle convention checks out against `_phase` and the glossary: the across-stripes direction is `(cos t, sin t)` in (x, y), so a line at `line_angle_deg == t` is perpendicular to stripes of Angle `t`. Apply B2's rewording.

Curvature: the ticket's "straight-ish" describes real breaks; AC 1 asks only for "any line angle and jump", and spec.md:124 models a line. Deferring it meets every AC. It is a scope reading, so record it in the ticket Comments and name it in the close note (section 8 already lists the risk). Not blocking: adding a bow later is additive (`line` is already a polyline).

### Q5: provisional threshold. Replaced by B4. Owner: no.

`_BREAK_MIN_JUMP_RAD = π/4` is a detector constant from P1 and a lockfile addition; the orchestrator approves it with the rest.

### Q6: new module and the `STAMPED_FILES` edit. Accept the module; change the name. Owner: no.

- **Is it a weakening move?** Yes, by the letter. CLAUDE.md lists "editing `tests/slow_stamp.py`" itself, without regard to direction, so adding a file needs an approval recorded in the ticket Comments. It is the easy kind: it strengthens the stamp, and `test_stamped_files_cover_the_slow_tier` (`tests/test_slow_stamp.py:249`) forces a classification for every new package file. The orchestrator approves it; no escalation.
- **Do not choose the module layout to avoid the approval.** Putting the finder in `analysis.py` or `_local_stripes.py` (both already stamped) to skip the edit lets the gate rule drive the design. Ticket 08's case was different: `BinFactors` was data only.
- **Is a new module premature before ticket 10?** No. This ticket alone justifies it: about 200 lines with one job, unit-testable on hand-built phasor fields without a frame (step 4), next to an 862-line `analysis.py`. What is premature is designing for forks: the name `_defects.py`, and docstrings that promise a shared interface. Name it for what exists now and is the stated foundation (ADR 0001): `_local_phase.py`, holding `demodulated` and `find_phase_breaks`. Ticket 10 then adds to the same file with no second `slow_stamp.py` edit. No fork-specific parameter or hook in this ticket. The "±1 winding returns `[]`" unit test stays: it is a negative test of the break finder.

### Q7: breaks only in reported regions. Accept. Owner: no.

Verified: `reported = [g for g in survivors if g.peak_ratio > threshold]` (`analysis.py:286`); running after it cannot change the score, labels or regions. Apply C2 for the response. Decided by report consistency (every break names a reported label).

### Q8: meaning of "within one period". Accept the strict reading. Owner: no, unless P1 fails it.

"Every sampled point within 1 P of the true line, plus coverage" is the strictest sensible reading of the AC, and the coverage rule closes the stub loophole. Additions:
- measure the distance in sensor geometry (O1);
- the full-frame chord uses a truth-side lit mask, not `analysis._light` (reviewer N4 is right: that is the code under test);
- `BREAK_CHORD_COVER_MIN` is a new acceptance limit that P1 freezes before the test seeds are run.

If P1 shows the every-point reading cannot hold at P = 3 (reviewer P1), first add angle refinement. Loosening the reading (midpoint or mean distance) relaxes the ticket's own AC wording, and spec.md:162 leaves tolerances to the user: that, and only that, goes to the owner.

### Q9: GLOSSARY "Phase Jump". Accept with edits. Owner: no.

Add the term with C1's direction sentence. Keep the `_Avoid_` line to real synonyms ("phase step, shift size"); "offset" is an ordinary word the code needs for the line offset. No registration is needed: `test_glossary_terms.py` reads the `_Avoid_` lines and flags only `CURATED` terms. Keep the definition consistent with **Phase Break**, which already says "shifted sideways".

## Risks for the prototype (Q1, Q2, P1): flagged only

- C3 above: Angle and Period bias on broken regions; P1(a) must measure it.
- B4's extra: count extra breaks on break frames.
- Jumps near ±π flip sign under noise; 5.1's wrapped difference handles it, but any test that asserts a sign must avoid `|jump| = π`.
- N1 (reviewer) stands: define E exactly before constants are frozen.
- A break changes `clean.max()` and so the EMCCD light level slightly; it does not matter for detection, but it is why twins differ (B1).

## Count

| Item | Verdict | Owner |
|---|---|---|
| B1 | Gaussian-only identity; EMCCD claims only the empty-breaks digests; no score move, no `make measure` | no |
| B2 | Option B, input defined as a difference; strict `> 0` | no |
| B3 | swap and reverse points; cross rule is the definition | no |
| B4 | zero fakes plus margin in P1; also count extras on break frames | no |
| B5 | swap steps 2 and 3 | no |
| B6 | drop "amplitude", "defect" and "contrast" | no |
| O1 | frame px, by ticket 08 AC 4; tolerance in sensor geometry | no (confirm spec line at close) |
| Q3 | accept with B3 and C1 | no |
| Q4 | accept; straight only | no (note at close) |
| Q5 | superseded by B4 | no |
| Q6 | new module `_local_phase.py`; stamp edit needs the orchestrator's approval | no |
| Q7 | accept; recompute the response (C2) | no |
| Q8 | strict reading | only if P1 forces a looser one |
| Q9 | accept; shorter `_Avoid_` | no |
