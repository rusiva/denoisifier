Plan: .scratch/stripe-detector/handoffs/09-plan.md @ uncommitted (BASE b7c6731)

## Findings

- [ ] B1 break: the identity claim is false for EMCCD noise. Plan 2.1 ("every pixel off the shifted side is bit-identical too") and the AC 1 identity row in 5.2 ("Gaussian and EMCCD noise; the RNG stream is unchanged") do not hold on the EMCCD path. `synthetic.py:318` rescales `clean / clean.max() * photons_peak`, and a break changes `clean.max()`, so every pixel moves. `rng.poisson` and `rng.gamma` (`synthetic.py:429,433`) also take a varying number of draws per pixel. Checked: with 5% of the lambdas changed, only 5.8% of the later Poisson draws, 0% of the Gamma draws and none of the following `normal` draws matched. `_spikes` brightness uses `clean.max()` too (`synthetic.py:347`). → Limit the off-`shifted` bit-identity claim and test to Gaussian noise, with `spikes=0` and no clip. For EMCCD, assert only that `phase_breaks=()` keeps `_BASE_DIGESTS`. State this in the `generate` docstring.

- [ ] B2 break: the plan contradicts itself on canonicalising and `shifted`. 2.1 says that when the direction flips, "the jump changes sign" and "the positive side is the same set of pixels either way, so `shifted` does not depend on how the caller wrote the line". It is not the same set: `side = cross(d, p - p0)` changes sign with `d`. A caller who writes `a = 100°, j` and one who writes `a = -80°, -j` get frames that differ by a global phase of `j` on the complementary side. One of them is not "shifted unchanged". `test_phase_break_truth_is_canonical` (5.2) cannot be written until the plan says which. → Pin one rule. Either (A) apply the jump literally on the caller's positive side, so `shifted` is the caller's side and the truth records the canonical angle with `-j` while `shifted` stays the caller's side (then the truth's `shifted` is the canonical *negative* side, and the docstring must say so). Or (B) canonicalise first and apply `-j` to the canonical positive side, so the frame changes by a global phase of `j` and `shifted` is always the canonical positive side. B keeps truth and the Report convention aligned. Also say what happens to pixels with `side == 0`: they lie on integer grid lines, for example a horizontal line through an integer row.

- [ ] B3 break: under `in_file_layout` the documented `jump_rad` sign is wrong. 2.4 defines the positive side as `cross(end - start, p - start) > 0` on the reported points. `in_file_layout` swaps (row, col), which is a reflection and flips the sign of that cross product. It also keeps the point order and `jump_rad` (2.4; the 5.2 CLI row asserts "`jump_rad` is equal"). So in file layout a reader who applies the docstring formula to the points gets the opposite side. Col-increasing order also becomes row-increasing. → Make `in_file_layout` also reverse the point order. A reflection plus a reversal keeps the cross-product sign, so the formula and `jump_rad` hold in both layouts. State the file-layout order in the docstring and `UNITS`. The CLI test then checks the side on a pixel, not only "points swapped".

- [ ] B4 break: the provisional threshold makes the AC suite fail on fakes at seed level. 5.1 says "No other reported break may be in that region". `test_defect_free_region_frames_report_no_phase_breaks` asserts zero fakes on 10 frames. Q5 tunes for a fake rate of "at most 1 in 40". At 1/40, P(≥1 fake) is about 22% over the 10 guard frames and about 50% over the roughly 30 AC 2/3/4, binned and pair frames. Q5 rules out a re-pick after a red, so the likely result is a red `make check` with no allowed remedy. → In P1(b), freeze `_BREAK_MIN_EVIDENCE` with a stated margin above the largest fake evidence on all of P1's defect-free frames. Report the fake/true evidence gap, and require zero fakes in P1. Ticket 11 lowers it to the calibrated rate later. If P1 finds no such gap at π/2, escalate before step 4.

- [ ] B5 break: step 2 cannot land green. Its "helper unit tests on hand-built `PhaseBreak` objects" and `assert_break_matches(found, ...)` need `report.PhaseBreak`, which step 3 creates (4, steps 2-3). → Swap steps 2 and 3, or move the helper tests into step 3.

- [ ] B6 break: some docstrings would use avoided glossary terms. "amplitude" is a curated avoided term (`tests/test_glossary_terms.py:24`), and 2.2 writes "amplitude-weighted phase contrast" and `_BREAK_MIN_AMPLITUDE_FRACTION`. Any docstring or comment that explains them fails `test_glossary_terms`. "defect" is on Fork's `_Avoid_` line (`GLOSSARY.md:81`), and the plan names `_defects.py` and `_defect_phase`. → Use "magnitude" or "depth" in the prose. Rename the module and helper to something like `_local_phase.py` and `_break_and_fork_phase`, or record why "defect" is acceptable, since the spec uses "defect false-alarm rate".

- [ ] P1 prototype: does the angle grid hold the position tolerance on the longest chords? 5.1 requires *every* point within 1 P. At P = 3 the region floor gives about a 120 px chord (`tests/regions.py:36`), so the angle error must stay under about atan(3/60) ≈ 2.9° including noise. → Add to P1(b): the worst endpoint distance in Periods per Period, and whether sub-grid angle refinement is needed. If a 1° grid without refinement misses at P = 3, step 4 needs a refinement stage and P1(c) must re-time it.

- [ ] O1 owner: should break line positions be in frame px or sensor px? The spec's "Pixel geometry" says "all periods, angles, region-size minimums and **positions** in the report are in sensor pixels", and ticket 08's opening text says the same. Ticket 08 AC 4 kept the bboxes and mask in frame px. The plan picks frame px (2.4 `UNITS["line"]`) without flagging it, and ticket 10's fork `point` will follow whatever is chosen. That makes it a public schema choice that is hard to reverse. Options: A frame px, consistent with bbox and mask; ticket 12 can draw the lines directly; the spec sentence is read as covering measurements only / B sensor px, the literal spec; it needs a conversion in `to_dict` and makes overlays harder. Recommend A, with `UNITS` saying so and one line in the spec.

- N1 note: 2.2 step 2, "normalised by the band means' magnitudes", cancels the `|z+||z-|` weighting, which leaves `1 - cos Δ` and no measure of how coherent each band is. Define E exactly (for example, normalise by the mean `|z|` per band) before P1 freezes constants on it.
- N2 note: `filters` exists only inside `_qualifying_regions` (`analysis.py:438-454`), and `analyse` holds no `_Spectrum`. The 2.3 "return it from `_refined`, or recompute" choice also has to thread `_Filters`, or the response, out to `analyse`, or build a second FFT.
- N3 note: the step-5 "identity test" has no BASE fixture it can read. Step 0 saves its outputs to the scratchpad. Say whether it is a pytest test with committed fixtures or only the diff script.
- N4 note: these details are left open:
  - the shape of the AC 2 full-frame test;
  - the meaning of "step-6 frame" (5.2, AC 5);
  - the binned tolerance "P / v (or /h)" (it should say "the sensor Period across the line, converted with `frame_px`");
  - the full-frame chord "inside the lit area (`light`)". That uses `analysis._light`, the code under test, as truth. Use a truth-side lit mask instead.
- N5 note: P1's 600 seeds are used up exactly by (a): 3 × 5 × 10 × 4 = 600. Say that (b)'s defect-free frames, the pair frames and (d) reuse those seeds without the break, or widen the range.
- N6 note: `test_phase_break_does_not_add_regions_to_full_frame_stripes` checks `len(with) <= len(without)`. It would pass if a split and a merge happened in the same frame. Consider also asserting that the largest region's bbox is unchanged within `BBOX_TOL_PERIODS`.

## Closing check (plan "final", uncommitted)

- [x] B1: 2.1 "Identity claims (B1)" 1-3 (lines 71-74); 5.2 row "1 (identity)": no EMCCD pixel claim.
- [x] B2: 2.1 "Canonicalise first (B2, option B)" + strict side test, on-line pixels not shifted (lines 67-68); 5.2 row "1 (truth)".
- [x] B3: 2.4 "`in_file_layout` (B3): swap ... and reverse the point order; keep `jump_rad`" (line 160); docstring and UNITS state it; CLI row checks the side of a pixel in file layout.
- [x] B4: 5.4 "Zero fakes is required (B4)"; `_BREAK_MIN_EVIDENCE` 0.1 between the break-free max of 0.082 and the true minimum of 0.18 (section 10); fakes 0 on every P1 break-free set (section 3).
- [x] B5: step 2 is now Report, step 3 the test helpers (section 4).
- [x] B6: `_local_phase.py`, `_break_phase`; 2.2 prose rule ("avoids amplitude, defect, contrast").
- [x] P1: 2.2 step 4 golden-section refinement down to `degrees(_BREAK_LINE_TOL_PERIODS · P / L)`; validation Angle and line results in section 3.
- [x] O1: ruled frame px (2.4 "Frame px (O1)"); the owner gets the proposed spec.md line at close (step 9, step 10).
- [x] N1: E defined exactly (2.2 step 3, GLRT formula).
- [x] N2: `_qualifying_regions` also returns its `_Filters` (2.3).
- [x] N3: step 0/6 scratchpad diff script, no committed fixture; plus 5.4's identity test on the real path.
- [x] N4: full frame 400x1600; AC 5 on `PHASE_BREAK_TEST_SEEDS[0]`'s AC 2 frame; 5.1 sensor geometry with the half-pixel centre formula; `truth_lit_mask` on the generator side.
- [x] N5: `BREAK_VALIDATION_SEEDS` range(109_600, 110_460) reserved (section 7).
- [x] N6: 5.3 side-cover reading replaces the region-count comparison.

New:
- [ ] B7 break: `test_phase_breaks_are_not_searched_under_the_frame_period_limit` (5.4) uses sensor P 4, Angle 0, 2x1, which gives a frame Period of exactly 2.0, the frame Nyquist. Summing pairs of a P 4 cosine gives `(-1)^c · (cos φ0 - sin φ0)`, a frame-wide depth of `√2·|cos(φ0 + π/4)|` that depends on the seed's `phase0`. At `BINNING_TEST_SEEDS[0]`, BASE may report no region, and then the test has no "region 1" refusal to assert. The plan also does not say this frame was measured. → Use a sensor Period strictly between the two limits, for example 4.6-4.8 (frame 2.3-2.4, under the 2.5 gate and away from Nyquist). Before step 7, confirm at BASE that this seed reports exactly one region.
- N7 note: 5.2 "2 (sign end to end)" gives no seed, noise or Period. Pin them in protected.py like the other rows.
- N8 note: `_BREAK_SEGMENT_HALF_WIDTH_FRAME_PX` is used as `0.75 · max(pixel_size(bins))` sensor px (2.3 step 8), so the "FRAME_PX" in its name is misleading. Rename it before it gets locked, for example `_BREAK_SEGMENT_HALF_WIDTH_PIXELS`.
- N9 note: the B4 margin is narrow. The evidence threshold is 0.1 against a break-free maximum of 0.082, so a fake on the 14 or more break-free test frames is unlikely but possible. Step 9's after-a-red rule covers it.

Open: B7.
