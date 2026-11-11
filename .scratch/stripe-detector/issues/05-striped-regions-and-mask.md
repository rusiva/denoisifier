# 05: Striped regions and mask

**What to build:** The report says *where* the stripes are. The generator gains partial striped regions with soft edges, including several regions with different periods in one frame, and returns the true region masks. `analyse` splits the frame into striped regions and reports each one with its period, angle, modulation depth and bounding box. It also produces a mask with the same shape as the frame. Regions under 3 periods wide or 2 periods tall are not reported. The CLI writes the mask as a CSV laid out like the input.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] The generator places one or more soft-edged elliptical striped regions, each with its own period, and returns their true masks.
- [ ] The report lists each region with its period, angle, modulation depth and bounding box; the frame-level verdict is striped if any region is reported.
- [ ] Mask overlap with the true region (intersection over union) is at least the spec's tolerance at typical noise.
- [ ] Two regions with different periods in one frame are reported separately with the correct periods.
- [ ] A region just below the 3×2-period minimum is not reported; one just above it is.
- [ ] Stripes covering only part of the envelope are found; the dark area outside the envelope is never reported as striped.
- [ ] The CLI writes the mask CSV with the same rows and columns as the input frame.

## Comments

- Approval (orchestrator, 2026-11-11, `.scratch/stripe-detector/handoffs/05-orchestrator.md`, ruling B3): register REGION_CALIBRATION_SEEDS = range(90_000, 90_600) in
  tests/protected.py CALIBRATION_SEEDS, add seed_guard.install() to tests/calibrate_regions.main(),
  and use seed_guard.calibrating(...) blocks there (90_000-90_399 tuning, 90_400-90_599
  informational). Reason: the growth, seed, merge and size-rule knobs must be tuned on seeds the
  acceptance tests do not use (spec.md:112, review B3); this strengthens calibration/evaluation
  separation. The review's and prototypes' seeds (N8; P1 390_000-390_307; P1-D 391_000-391_207;
  P2 410_000-410_079, 411_000-411_003) are reserved in USED_SEEDS. Tuning is frozen (constants committed) before the
  held-out tests run.
- Approval (orchestrator, 2026-11-11, same log, "Lockfile approval" and "Height ruling"): add the ticket-05 module constants of analysis.py
  (MIN_HALF_DEPTH_WIDTH_PERIODS = 3.24, MIN_HALF_DEPTH_HEIGHT_PERIODS = 1.93,
  SIZE_ALONG_PERIODS = 0.5, and the seed/growth/merge knobs) and the new
  tests/protected.py numbers (MASK_IOU_MIN 0.8, BBOX_TOL_PERIODS 1.0, MIN_SIZE_BELOW_FACTOR 0.8,
  MIN_SIZE_ABOVE_FACTOR 1.4, DARK_FRACTION 0.05, region geometry, test seeds, USED_SEEDS
  reservations, REGION_CALIBRATION_SEEDS) to tests/protected_numbers.lock. Reason: records new
  numbers, loosens nothing. Changing or removing existing pinned numbers (borderline re-pick,
  stored thresholds after make measure, dropped constants) is not covered and is asked for
  separately with its reason.
- Approvals given in advance (orchestrator, same log, fold planner's entry), used only as stated there:
  borderline re-pick only if `make measure` shows a seed is no longer borderline, reason recorded here;
  removing pinned constants the change makes obsolete (each listed here); stored thresholds after
  `make measure` per the CLAUDE.md procedure. Pass counts are never edited.
- Removed pinned constant (advance approval "removing pinned constants the change makes obsolete"):
  `denoisifier.analysis._PERIOD_SPREAD` (1.25). `_measure`, its only user, is replaced by the
  per-region seed/grow/merge measurement; its lockfile line is removed with it.
- Deviations from the plan text (implementers 1 and 2; none loosens a test or tolerance):
  1. A candidate's seed area excludes pixels an earlier (higher) candidate grew over, and dedup
     skips peaks there. Without it, low peaks (ratio 3-6) got frame-wide seed areas and merged
     into the real region.
  2. A merged group is re-grown on its re-tuned depth with the level taken from the top member's
     seed area, and its depth is the median over that seed (a skirt fragment's low-depth seed
     pulled the level down: P20 IoU 0.51).
  3. A group qualifies only if its depth is at least `_A0` (the existing ratio floor); this gives
     the constant frame `score == 0.0` (B6). The all-zero frame of B6 is not in the verdict test:
     `analyse` rejects it ("no positive light", an existing test).
  4. Two knobs beyond the plan's list, tuned on 90_000-90_399 and added under the lockfile-addition
     approval: `_CORE_FRACTION = 0.5`: the size rule's depth peak is looked for on the top
     candidate's core (ratio >= 0.5 x its peak, prototype P1's seed area) rather than on the whole
     seed area; with the tuned `_SEED_FRACTION = 0.1` the seed area is large and its depth maximum
     is a noise or Mottle outlier, which made full-frame m = 0.5 frames fail the width rule.
     `_ABSORB_FRACTION = 0.5`: a candidate that is not merged but grows mostly over an earlier
     group's extent is dropped as a fragment of it (12/60 full-frame calibration frames had such a
     fragment, Angle 3-6 deg off, reported as a second region; 0/60 with the rule).
  5. `TWO_REGION_SHAPE = (640, 1024)` instead of the starting (512, 1024): at 512 rows a (8, 16)
     truth mask reached 2% outside the Profile's half maximum on calibration seeds.
  6. The threshold-sweep and lowering-threshold tests use `MOTTLED_TEST_SEEDS[:5]` (stripe-free
     and m = 0.5) instead of all 20, to bound the run time.
  7. `tests/calibrate_regions.py` sets the one-thread variables in `main()` before the spawn pool
     (the workers inherit them), so it needs no `noqa: E402`.
- Lockfile lines added (implementer 3, under the "Lockfile approval" above): analysis.py
  `MIN_HALF_DEPTH_WIDTH_PERIODS`, `MIN_HALF_DEPTH_HEIGHT_PERIODS`, `SIZE_ALONG_PERIODS`,
  `_PEAK_FOOTPRINT_PX`, `_SEED_FRACTION`, `_MAX_CANDIDATES`, `_SPLIT_LOG_STEPS`, `_GROW_FRACTION`,
  the three `_MERGE_*`, `_ABSORB_FRACTION`, `_CORE_FRACTION`, and `_LOG_BANK_STEP` (the bank's
  log grid step, derived from `_PERIODS`, used by the Period split; a new ticket-05 module number);
  protected.py: every new ticket-05 name, plus the new `USED_SEEDS` (N8/P1/P1-D/P2 reservations and
  implementer 1's scratch seeds `range(95_000, 95_300)`) and `CALIBRATION_SEEDS` (with
  `REGION_CALIBRATION_SEEDS`) lines. The `_PERIOD_SPREAD` line is removed (listed above).
- Freeze committed at `ce42580` (knobs plus `region-calibration.json`). Acceptance after the
  freeze is red (implementer 3, stopped and not re-tuned; details in
  `handoffs/05-implementer-handoff.md`): ghost low-depth regions around sharp-edged small regions
  (AC 5, 5 cases), dark-area test full-frame typical (3; question of which envelope defines
  "dark"), strong P12 seed 23 Angle 1.02 deg off, borderline (22, 20) now scores 0 (re-pick
  needs an approval, not covered by the measure-conditioned one). Two test bugs fixed in `b9f4a88`.
- Rulings R1-R4 and "Evaluation hygiene" (orchestrator, 2026-11-11, `handoffs/05-orchestrator.md`,
  "Rulings on the post-freeze reds"), taken up by implementer 4. Evaluation range predeclared
  **before any fix**: `REGION_EVALUATION_SEEDS = range(93_000, 94_000)` in `tests/protected.py`,
  registered in `USED_SEEDS` (lockfile: one new line plus the `USED_SEEDS` line; this adds a
  reservation and loosens nothing, under the ruling). Not looked at until after the new freeze;
  then one run of a one-off driver (`tests/evaluate_regions.py`), no tuning on its results. The
  seen reds (5 ghost, 3 dark-area, P12 seed 23, borderline (22, 20)) stay as regression tests.
