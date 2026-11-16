# 06 critic: adversarial read of the plan and its review

Read at BASE `4e40bdd`, plan and review uncommitted. No tracked file was edited.

**Bottom line:** no item needs the owner. Three things change the plan beyond what the review asks:

1. The AC 4 start configuration has no teeth, and the D9 mechanism looks unable to pass a configuration that has them (Q4).
2. The AC 3 test is close to vacuous (Q6).
3. The review's O1 option B and its B1 fix are right in direction but mis-specified (O1, B1).

One fact for the whole ticket: the only "real" frames in the repo are from an Andor Zyla sCMOS (`tests/data/solis/NOTICE.md:5`), not an EMCCD. Nothing in the repo shows how the owner's camera saturates, what its pedestal is, or what its spikes look like.

## Checks I ran

Scratch scripts outside the repo. Seeds 700_000-700_005 and 700_100-700_139 are in no list in `tests/protected.py`; avoid them or reserve them in `USED_SEEDS`. Seeds 10-29 were only scored with the BASE detector, as the existing tests do. The machine was loaded (1-min load 14), so the timings are rough.

**Clip at the plan's start value (0.8 x 100 photons), typical m = 0.5, 256x256, six frames:**

| Measure | Result |
|---|---|
| Clipped pixels per frame | 44-162 |
| Of those, pixels whose clean value is at or above the level | 9-45 (the rest are noise excursions) |
| Clipped 8-connected components of 3 px or fewer | 353 of 376 (94%) |
| Depth bias from the clip (centre median of `gabor_at` depth) | 0.005 or less |
| Pixels the D9 guard removes at P = 20 | none (1% of a 121x81 box is 98 px) |

**Deeper clips, three frames (P = 3, 8, 20), emulating D9 with the lit area as the region:**

| Clip (x clean max) | Flattened depth P3 / P8 / P20 | D9 depth P3 / P8 / P20 | Valid part of the light | Median clean level where D9 measures |
|---|---|---|---|---|
| 0.6 | 0.478 / 0.489 / 0.489 | 0.497 / 0.488 / 0.467 | 59-75% | 10-12 of 100 photons |
| 0.5 | 0.453 / 0.472 / 0.468 | 0.494 / 0.490 / 0.448 | 44-65% | 9-11 |
| 0.4 | 0.403 / 0.440 / 0.431 | 0.484 / 0.456 / 0.334 | 24-46% | 7-9 |
| 0.3 | 0.298 / 0.378 / 0.371 | 0.461 / 0.459 / 0.400 | 5-30% | 6-9 |

Truth is 0.5 and `DEPTH_TOL` is 0.1. The flattened depth leaves the tolerance only at about 0.4 (P = 3) or 0.3 (P = 8, 20). There D9 measures on the dim rim, and at P = 20, clip 0.4 it is worse than no exclusion (0.334 against 0.431). This emulation is crude (lit area as the region, filter at the true Period), so treat it as indicative.

**Other checks:**

- AC 3 frames at BASE (seeds 10-29, typical m = 0): scores are 0, 0, 0, then 6.7 to 31.1. The test's thresholds are 49.7 and 154.
- Integer-valued frames (`em_gain=1, read_noise_e=0`): 4 or more ties at the maximum in 1 of 40 frames at 30 photons, 0 of 40 at 100 and at 1000.
- Timing at 400x1600: column median (6 neighbours) 0.06 s, 3x3 median 0.11 s. The 0.3 s budget looks reachable.

## Planner open questions

### Q1. Where the code lives: agree with (a), new `_data_quality.py`
- Against: it touches a protected surface (`tests/slow_stamp.py`) where (b) touches none.
- Evidence: `test_stamped_files_cover_the_slow_tier` (`tests/test_slow_stamp.py:249`) forces a classification, and `STAMPED_FILES` is the stricter one. `analysis.py` is already 632 lines.
- Human: no. The orchestrator can approve a move that only widens the stamp.

### Q2. How the constants are tuned: agree with (a), with one change
- Against: seven lockfile constants would rest on a throwaway script. `handoffs/` is untracked (`git status`: `?? .scratch/stripe-detector/handoffs/`) and ticket 05's handoffs went to an untracked `.archived/`. So plan step 5, "commit `06-prototype.md`", does not keep the evidence unless the file moves.
- Change: put the script and its results under the tracked `.scratch/stripe-detector/evidence/`, as ticket 03 did (`03-prototype-p1.py`, `.md`, `.json`). Cite seeds and measured numbers in the constants' comments, as `analysis.py:89-101` does.
- Evidence for (a) itself: prototype seeds reserved only in `USED_SEEDS` already back protected constants (`tests/protected.py:205-213`, `MIN_HALF_DEPTH_*`). `spec.md:112` (separate seeds) is met by the disjointness test.
- Human: no.

### Q3. Report the clip level: agree with (a), counts only
- Against: the user cannot see which level auto-detection chose, so a false plateau cannot be audited.
- Evidence: `spec.md:106` lists only the two counts. A field can be added later.
- Human: no.

### Q4. Scope of the exclusion: agree on scope (depth only), disagree on the mechanism
- Against the mechanism: see the tables above. At the start value the AC 4 tests pass with no exclusion at all. At a level with teeth, D9 either measures the dim rim or falls back to the flattened depth without saying so. On a partial region the rim is the soft edge, where the depth is lower, so the bias gets worse.
- The rejection of normalised convolution on budget grounds (plan:58) is weak. The path runs only when `clipped.any()`, and only for reported regions. The 10 s timing frame is unclipped (`tests/protected.py:44-45`), so that gate never measures the clipped path either way.
- Alternative: a weighted fit of mean, cos and sin at the region's known Period and Angle, with clipped pixels at weight 0, on the region's bounding box. The prototype compares it with D9 at a level that has teeth.
- Quiet drift: the plan lowers `CLIP_LEVEL_FRACTION` "until they do, with enough valid pixels left" (plan:94). That tunes the test stimulus to the detector. Fix the fraction first by a generator-side rule: the highest fraction at which the depth of `np.minimum(clean, C)` misses `DEPTH_TOL` with a margin. Assert the same rule as a test precondition, so AC 4 can never pass on a mild clip. `truth.clipped_pixels >= CLIPPED_MIN_PIXELS` does not ensure that.
- Human: no. The prototype decides.

### Q5. Spike and clip overlap: disagree with (a)
See O1.

### Q6. AC 3 strength: disagree with (a) as written
- Against: the ticket says "at the same rate". Every one of the 20 BASE scores is 31.1 or lower, so a verdict flips only if spikes raise a score by 60% (to 49.7) or five times (to 154). Rejection could be badly broken and the test stays green.
- Better, without a slow-tier change:
  - Assert a paired score tolerance per seed in the fast test (17 of the 20 scores are non-zero), plus the verdicts.
  - Record a paired count on all 400 prototype seeds at `GATE_STORED_THRESHOLD` in the handoff.
  - Option (b), the slow-tier rate, stays with ticket 07.
- Review note N3 points the same way but only records the score change. It should be asserted.
- Human: no.

### Q7. Constant frames: agree with (a), no clipping
- Against: a fully saturated frame reports `clipped_pixels == 0`.
- The real reason is that there is no evidence of the level without the override. The plan's "keeps the test simple" is not a reason.
- Related: `_MIN_CLIPPED_PIXELS = 4` gave a false plateau in 1 of 40 integer frames at 30 photons. The prototype must cover that case.
- Human: no.

### Q8. Spike brightness range: agree with (a) for now
- Against: the generator and the detector are designed around each other. The dimmest spike is 2.0 x the clean peak and the floor is 0.5 x the peak (plan:27, :44), so no test ever goes near the decision boundary. Start the generator's range near the floor, or add a boundary case.
- Missed risk: the column median can erase real structure at a Phase Break (tickets 09-11). With m = 1, a pixel next to the break has three out-of-phase neighbours. Whether it is flagged depends on scipy taking the upper of the two middle values for a 6-pixel footprint. Add a hand-made break frame (half the frame shifted sideways, noise 0) to the prototype and to `test_spike_free_frames_report_no_spikes`.
- Human: no, not blocking. The real brightness and length of spikes is external knowledge (class b), but GLOSSARY.md:37-39 and `spec.md:129` already fix the model. Worth asking the owner for one real frame with cosmic rays when convenient.

### Q9. Glossary: agree with adding **Clipped Pixel**, with two edits
- Drop "saturated pixel" from the _Avoid_ line. `spec.md:58` and the plan's own CLI help (plan:66) say "clipped (saturated)", and `synthetic.py:166` uses "saturated" for Mottle.
- Define it by what the code does: a pixel at or above the clip level, whose true value the frame does not show. The override can set a level that is not the sensor's.
- Human: no. It is mild wording taste, and only the curated terms are enforced (`tests/test_glossary_terms.py:26`).

## Owner items

### O1. How a saturated spike is counted: agree with the direction of B, not its rule
- Against the review's rule ("small clipped component, column median below the level"): 94% of the clipped components on typical frames are noise excursions of 3 px or fewer. A size rule would call them spikes. Use the same per-pixel spike test on every pixel, clipped or not, and no component rule.
- Against B's truth ("would not be clipped without the hit"): it cannot be observed where the level is close to the local light. The residual is capped at the level minus the column median, so it cannot pass 8 x the local scale or the floor. With the clip at 0.8, roughly 40% of saturated spikes would be counted as clipped (my estimate, not measured), far outside a 5% tolerance.
- B also breaks the exact identity `clipped_pixels == (f >= C2).sum()` that the plan's AC 5 tests assert (plan:87, :91), and the help text "pixels at or above LEVEL are clipped".
- Proposal:
  - Count by what the detector did: `spike_pixels` are the pixels it replaced, `clipped_pixels` are the pixels at or above the level that it did not replace.
  - Test saturated spikes with a level far above the light (for example 3 x the clean maximum, a detector ceiling). There every spike saturates, the auto-detected plateau is the spikes, and the expected report is the spike count with 0 clipped. This is the B1 case.
  - For a peak-level clip with spikes, assert the total of the two counts, and state the limit in the docstring.
- Human: no. Stories 25 and 27 (`spec.md:57`, `:59`) decide against A: saturated cosmic rays must not read as "lower the EM gain". Whether real cosmic rays saturate is external (class b), but this counting is right either way. The fields are new in 0.1.0, so the meaning is cheap to change.

### O2. "Left out of the analysis" narrowed to the depth: agree with A
- Against: `spec.md:105` puts clipped-pixel exclusion before envelope estimation, and the ticket's line 3 says "out of the analysis". D9 drifts from both.
- For: story 26's purpose clause is the depth, AC 4 tests only the depth, and holes in the Mask would work against the mask criterion (`tests/protected.py:157`).
- Record the ruling in the ticket's Comments and say "left out of the modulation depth" in the docstrings.
- Add to the prototype:
  - Clipped stripe-free frames must not score higher than unclipped ones.
  - The second harmonic of clipped stripes (Period 6 or more gives P/2 inside the 3-20 band) must not become a region. `assert_every_region_matches` (`tests/test_analyse.py:83`) would catch it in AC 4.
- Human: no.

## Breaks

### B1. Saturated spikes are never rejected: agree, confirmed
- Every spike adds at least 200 on a frame clipped at 80, so `truth.spike_pixels == 0` and the three tests named in the review pass on 0 == 0.
- Fix as in O1: the per-pixel spike test also on clipped pixels, no component-size rule.
- Human: no.

### B2. The dark-subtraction test cannot run: agree, confirmed
- `analysis.py:210-211` raises on a frame that is negative everywhere. Subtracting C/2 is right.
- Human: no.

### B3. The spike floor is measured from zero: agree
- Caveats:
  - The pedestal evidence is from an sCMOS crop with no dark surround. A low percentile there is dim light, not bias. That is acceptable, because the sigma test is sound where the frame is lit.
  - `_light` makes the same zero-level assumption (`analysis.py:213`). It predates this ticket and should be noted, not fixed here.
- Human: no. The real pedestal is external, but a floor measured above a baseline is right either way.

### B4. The partial-region precondition: agree
- Count the clipped pixels inside `truth_pixels(region)` (`tests/regions.py:31`).
- Human: no.

## Other drifts and weakened checks

- **Tolerances fitted to the detector.** `SPIKE_PIXELS_ABS_TOL` and `SPIKE_PIXELS_REL_TOL` are "set from the prototype" (plan:96, :124). AC 2 says "a small tolerance". Fix 2 px and 5% as the requirement now and tune the detector to them. Any larger value is an escalation, not a prototype output.
- **Review P1 and P2 are likely breaks, not checks.** P2 is confirmed above. For P1, give step 2 a pass mark at 30 photons, the low end of `spec.md:141`.
- **An expected-red gate.** Gate step 1, "`make check` (green except the stale stamp)" (plan:135), adds a red run that CLAUDE.md's end sequence does not have. Use `make test-fast` before the commit, then measure, `check-slow`, `check`.
- **`make measure` is required**, as the plan says: the detector changes, though 06 is not in CLAUDE.md's milestone list (05, 07, 13). The prototype should report false spike flags on spike-free typical frames. Zero flags means identical thresholds.
- **Review notes N1 and N2 are correct.** N2 interacts with the upper-median point in Q8.
