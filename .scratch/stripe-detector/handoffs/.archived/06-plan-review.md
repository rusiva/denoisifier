Plan: .scratch/stripe-detector/handoffs/06-plan.md @ uncommitted (BASE 4e40bdd)

## Findings

- [ ] B1 break: **saturated spikes are never rejected, and the clipped-spike tests are vacuous.** D4/D6 (plan:31, :49) say a clipped pixel is never a spike and stays at its value in the working copy. The plan itself says real cosmic rays under EM gain usually saturate (plan:28). On a real frame, 4 or more saturated spike pixels form the plateau D7 looks for (plan:55). They are then counted as clipped, never replaced, and go into `_light` and the bank. Teeth check (ii) (plan:94) shows unrejected streaks raise the score, so AC 3 fails on exactly these frames. The tests cannot see this: spike brightness is >= 2 x `clean.max()` (plan:27) and the clip is 0.8 x `clean.max()` (plan:96), so every spike in a clipped test frame is clipped and `truth.spike_pixels == 0`. That makes AC 2 "with spikes=30" (plan:82), the CLI test with spikes 5 (plan:90) and `test_clipped_spike_pixels_are_clipped_not_spikes` (plan:77) pass 0 == 0. → Plan change: in `reject_spikes`, also test clipped pixels against their column neighbours. Replace small clipped components (<= `_SPIKE_MAX_LENGTH` px, column median below the level) in the working copy; how they are counted is O1. Add an AC 3 case: stripe-free frames with spikes that saturate, analysed with auto clip detection. Give the AC 2 and CLI clip-with-spike frames a level that leaves some spike pixels below it. Real path: `generate(spikes=, clip_level=)` -> `analyse`.
- [ ] B2 break: **the dark-subtraction test cannot run.** `test_clipping_is_detected_after_a_constant_dark_subtraction` (plan:88) analyses `frame - 2*C`. The frame's maximum is C, so every pixel becomes <= -C, not just the ones near the edge. `_light` then raises "envelope max <= 0" (analysis.py:210-211; pinned by `test_frame_with_no_positive_light_is_rejected`, test_analyse.py:146). → Subtract a constant that leaves positive light but drives the dark surround negative, e.g. `C/2`. Assert the clipped count is unchanged and the surround has negative values.
- [ ] B3 break: **the spike floor is measured from zero, not from the frame's baseline.** The D5 floor `_SPIKE_FLOOR_FRACTION * median_filter(frame, 3).max()` (plan:44) assumes a zero dark level. On real data it moves:
  - With a bias offset it is too high. The Solis crop has min 713, median 1132, max 2022 (checked with `read_frame`), so the floor is about 1011 counts, roughly 0.8 x the lit excess over the bias.
  - After dark subtraction (story 28) the floor gets small or <= 0, so the sigma test runs alone. That flags spurious charge in the dark surround, the failure plan:46 itself describes.
  → Take the scale above a baseline, e.g. the peak minus a low percentile or the dark surround's median. Add a fast test: on a typical frame with spikes, the spike count is unchanged after adding +1000 and after subtracting C/2. Run the prototype on the Solis crop with its bias.
- [ ] B4 break: **the partial-region AC 4 test can pass with no stripe peak clipped.** Its precondition counts clipped pixels anywhere in the frame (plan:85-86). The region is small and centred in 512x512 (tests/regions.py:4), and scorched Mottle (log-std 0.4) can put `clean.max()` and the whole clip on a bright Mottle spot outside the region. → Count the precondition on clipped pixels inside `truth_pixels(region)`. The full-frame test's precondition is fine.
- [ ] P1 prototype: **spike recall at the spec's low light (30 photons; the plan also checks 10).** At 10 photons the noise at the peak is about 4.5, so 8 s is about 36 or more, while a spike at the minimum 2 x peak adds only 20. About a fifth of the spikes on bright pixels would be missed, which contradicts D1's "far above it everywhere" (plan:28). Every AC test runs at 100 photons, so none of them would catch this. Step 2 lists low light but sets no pass mark. → Record recall by brightness at 10 and 30 photons. If it is below the AC 2 tolerance, change `_SPIKE_SIGMAS` or the brightness model before step 4, and record the low-light limit in the docstring.
- [ ] P2 prototype: **how many pixels D9 leaves valid.** With EMCCD noise (σ about 14 at 100 photons), a clip at 80 also catches pixels whose clean value is about 55 or more, scattered across the lit core, not only stripe peaks. The guard box is up to 121x81 px at P = 20 (plan:57). On 256x256 AC 4 frames the valid set may vanish, which means falling back to the flattened depth. → Measure the fraction of frames with a non-empty valid interior, and the depth error on each path. If most frames fall back, rework D9 before slice 4: weight the clipped mask with the `local_mean` window itself instead of a ±2σ box, or use a smaller guard.
- [ ] O1 owner: **how a saturated spike is counted** (plan Q5; it changes the meaning of the public `spike_pixels` and `clipped_pixels` fields, which is hard to reverse). Story 27 says the clipped count tells the user when to lower the EM gain; saturated cosmic rays should not trigger that. Options:
  - A: as the plan has it, every clipped pixel counts as clipped. Saturated cosmic rays inflate `clipped_pixels` and are never counted as spikes.
  - B: a small, isolated clipped component that passes the spike test counts as a spike pixel. Generator truth: a hit pixel counts as a spike if it would not be clipped without the hit, i.e. `frame_without_spikes < clip_level`. The bulk plateau stays clipped.

  Recommend B.
- [ ] O2 owner: **"left out of the analysis" narrowed to "left out of the depth".** The ticket (line 3) and story 26 say clipped pixels are left out of the analysis. D9 (plan:57) keeps them for detection, Period, Angle and the Mask, and leaves them out only of the reported depth. The ACs test only depth, but this changes the agreed wording. Options:
  - A: depth only, as the plan proposes. Mask unchanged, cheap.
  - B: also leave them out of the growth and depth medians. Holes in the Mask, costs time.

  Recommend A, with the ruling recorded in the ticket's Comments.
- N1 note: rounding `t*(cos, sin)` repeats a pixel near 45° (t = 1 and 2 both give (1, 1)), so a streak of `L` can cover fewer than `L` pixels. Step along the dominant axis, Bresenham-style.
- N2 note: scipy's `mode="reflect"` repeats the edge pixel, so a spike in row 0 is one of its own neighbours. Vertical streaks within 2 rows of the top or bottom edge are missed. Use `mirror`, and have the prototype count edge misses against `SPIKE_PIXELS_ABS_TOL`.
- N3 note: AC 3 (plan:84) compares only verdicts, on 20 seeds. Also record the score change in the prototype, so a frame near `GATE_STORED_THRESHOLD` (49.7) does not make the result a coin flip.
- N4 note: story 46 and the forward model (spec:129) put spikes in the EMCCD chain. The plan adds them for Gaussian noise too, through `generate`. That is fine; say so in the `generate` docstring, together with `clip_level=inf` being rejected by `generate` but accepted by `analyse`.
- N5 note: checked and confirmed:
  - `Report.labels` has no default and `compare=False` (report.py:85), so the new required fields fit before it and `analyse(f, clip_level=C) == analyse(f)` works.
  - `test_stamped_files_cover_the_slow_tier` (test_slow_stamp.py:249) exists, and seeds 34-39 and 81-90 are free in protected.py.
  - The P = 3, 10° column-median bound r <= 0.26 x the excess (plan:45) holds.
  - The `local_mean` window is σ P in columns and 1.5 P in rows (_local_stripes.py:87-97), as the guard box assumes.

## Closing check (plan revised, untracked, read at HEAD d13bfdc)

- [x] B1 closed. Every pixel is now tested, clipped or not (plan:54). The tests cover saturated spikes: `SATURATING_CLIP_FACTOR = 3.0` leaves some spike pixels at the level and some below it (plan:94, :98, :113), and AC 3 adds a spiked-and-clipped case (plan:105).
- [x] B2 closed. The dark-subtraction test now subtracts `C/2` and asserts the shifted frame has negative pixels (plan:111).
- [x] B3 closed. The spike floor uses `scale = peak - baseline` (plan:53), tested with `+BASELINE_OFFSET` and `-C/2` (plan:99). `_light`'s zero-level assumption is recorded as out of scope (plan:57).
- [x] B4 closed. The partial-region precondition now counts clipped pixels inside `truth_pixels(region)` (plan:108-109).
- [x] P1 closed. The count is stated as reliable from about 30 photons (plan:57) and asserted at `SPIKE_PASS_MARK_PHOTONS = 30` (plan:97).
- [x] P2 closed. The box guard is replaced by d9_inner_g10 with a plain-interior fallback (plan:66), and the cutoff is swept in P3 (plan:188).
- [x] O1 closed. Ruling: count by what the detector did (plan:34-36, :64). The totals test covers spikes saturated inside the plateau (plan:103).
- [x] O2 closed. Ruling: clipped pixels are left out of the modulation depth only, recorded in the ticket Comments (plan:65, plan:227).
- [x] N1 closed: streaks are drawn along the dominant axis (plan:30). N2 closed: the column window shifts inward at the top and bottom edges (plan:50). N3 closed: the per-seed score change is asserted, not just recorded (plan:105). N4 closed: both docstring points are in (plan:33).

### Values the plan picked

- [ ] B5 break: **`SPIKE_SCORE_TOL = 2.5` rests on no evidence, and the evidence on file says scores jump by far more.**
  - The plan sets 2.5 as 5% of 49.7 and fixes it at step 0 (plan:137). P3 is only to "confirm" it (plan:192), and a larger value would be an escalation.
  - No prototype measured paired score changes with spikes; P1 recorded recall, not scores.
  - P2 (evidence/06-prototype-p2.md:142-162) shows stripe-free scores rising +21 to +24 on 7-12 of 40 frames from a clip at 0.8, a change to a few hundred pixels. Critic 2 explains why: the score jumps when a group passes or fails the size rule (06-critic-2.md:101).
  - With perfect rejection, 100 spikes still change about 200 pixels from their noise value to a column median, a perturbation of the same kind. Step 5c is then likely to go red, and that ends in an escalation.
  - P3 measures the distribution on 396_000-396_399, the seeds the spike constants were tuned on.

  → Plan change:
  - Set `SPIKE_SCORE_TOL` at the freeze (5c) from P3, like `CLIP_MIN_SHARE`.
  - Measure P3's paired spike/no-spike distribution, for both AC 3 parameters (spikes only, and spikes with the 3x clip), on fresh reserved seeds.
  - Rule for the value: the largest paired change plus a margin, and only while it stays below the headroom at the working point (49.7 minus the largest stripe-free score, 31.1 at BASE on 10-29, 06-critic.md:40). If it exceeds the headroom, escalate before 5c.
- N6 note: `CLIP_DEPTH_EPS = 0.01` is backed: the largest excess of d9_inner_g10 over plain is 0.007 (06-critic-2.md:24). The margin is thin, though (0.003), and it was measured on the prototype's code and seeds 396_000-396_059 at 100 and 5000 photons. Because the value is fixed at step 0, a P3 result above 0.01 would mean an escalation; consider setting it at the freeze from P3, as B5 does. The strict mean inequality (plan:107) carries the teeth whatever the value.
- N7 note: `CLIPPED_MIN_PIXELS = 10` is consistent with the evidence (P2's minimum inside the region was 37 at 0.8, plan:142). It makes the precondition non-vacuous but weak: about 0.1% of a region of roughly 8,500 px. That is acceptable for a test labelled as a no-harm guard. Its name is easy to confuse with the detector's `_MIN_CLIPPED_PIXELS = 4`; consider `REGION_CLIPPED_MIN_PIXELS`.
- N8 note: P3 seeds 396_500-396_599 check out. They overlap no `USED_SEEDS` range, no named seed set and no `CALIBRATION_SEEDS` (tests/protected.py:194-231). No committed script generates them (the P1 and P2 scripts use 396_000-396_399). The plan reserves them at step 0, before any use (plan:146, :155). The plan's three sub-ranges are disjoint. B5's fresh AC 3 seeds need a further reservation, e.g. 396_600-396_699.

Still open: B5.
