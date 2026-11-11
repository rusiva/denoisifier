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
