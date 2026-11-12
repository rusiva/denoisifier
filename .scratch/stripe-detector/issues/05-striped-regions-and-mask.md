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
- Approval used (orchestrator, 2026-11-11, ruling R2, weakening-class test change):
  `test_dark_area_is_never_reported_as_striped` now defines "dark" on the Profile (same seed,
  `mottle="none"`, `regions=()`, noise 0) below `DARK_FRACTION` of its max, instead of on the
  Mottled envelope. Reason (ruling): the ticket says "the dark area *outside* the envelope", and
  AC 3's truth mask is geometric and includes interior Mottle holes, so the Mottled-envelope
  assertion contradicts AC 3. The detector does not clip low-light pixels; the Glossary's
  Envelope is unchanged.
- Deviations, implementers 4 and 5 (rulings R1, R3, R4; none loosens a test or tolerance):
  8. Size rule: the depth peak is climbed to (steepest ascent) from the top candidate's core, and
     the extent is the widest row (column) run of the connected half-peak component holding it,
     instead of the run through the peak. R1: at sharp edges the ratio peaks in the skirt outside
     the stripes, so the column through it started low (P20 wide_short 0.8x measured 3.34 P tall,
     now 1.69 P). R4: borderline (22, 20) had its depth peak at the light's edge, so the row
     through it gave 0.449 P wide (a width-measure bug; now 12.15 P, score 217.1).
  9. Leakage test (R1), new knob `_LEAK_FRACTION = 0.5`: a size-qualifying group near a stronger
     candidate (higher peak ratio, qualifying or not, deeper than the group) is dropped when
     taking that candidate's stripes out (its grown extent set to the local mean) drops the
     group's seed depth below 0.5x.
  10. Period/Angle refined on each survivor's settled pixels with a filter re-tuned to the
      current estimate, `_REFINE_STEPS = 2` (R3; T-free, after settling).
  11. `tests/regions.two_regions` takes per-region depths, edge and gap (existing calls unchanged);
      `calibrate_regions.py` gains the `size_low` and `neighbour` kinds on the last 40 tuning
      seeds (R1: every size shape unmottled at `edge_px=1`, and genuine weak regions beside strong
      ones).
- Lockfile lines added (implementer 5, under the "Lockfile approval": new ticket-05 module
  numbers): `denoisifier.analysis._LEAK_FRACTION` (0.5) and `_REFINE_STEPS` (2). No existing
  line changed.
- Second freeze (implementer 5): constants above plus `region-calibration.json` from the tune on
  90_000-90_399 at this tree (default knobs). Single IoU worst 0.873; two 30/30 and two_low
  30/30 separate and correct; full frame 60/60, 0 mis-measured; `size_low` (every shape, no
  Mottle, `edge_px=1`): 0 below reported, 0 above not exactly one; probe 0 mis-measured.
  R1 guard (genuine weak neighbours): with the leak test disabled (`--set _LEAK_FRACTION=0.0`)
  the `neighbour` misses are the same 7 (typical noise, 6 at depth 0.15, 1 at 0.3); every
  low-noise weak neighbour is found either way, so the fix adds no misses. `_LEAK_FRACTION` not
  tuned. The fresh-range driver `tests/evaluate_regions.py` is committed with the freeze,
  before it is run.
- Acceptance after the second freeze (`2107a40`): `uv run --locked pytest -q -p no:randomly
  --durations=12 tests/test_analyse.py tests/test_cli.py`, exit 0, `318 passed in 421.99s`
  (not a gate quote). A first run of the same command died on the 60 s per-test timeout in
  `test_verdict_is_striped_exactly_when_a_region_is_reported[two-region]` under another
  project's load (load average 7-9); alone it took 59.05 s then, 40.55 s in the green run (42.30 s
  at `ce42580`). The R1/R3 additions cost about 0.4 s of a 9.4 s analyse (profiled); the timeout
  is unchanged.
- **Fresh-range evaluation (one run, no tuning): STOPPED, two criteria missed.**
  `uv run --locked python tests/evaluate_regions.py --out ...` at `2107a40`, exit 0; record in
  `.scratch/stripe-detector/region-evaluation.json`. Results: AC2 39/40; AC3 IoU >= 0.8 40/40
  scorched (worst 0.881) and 40/40 multiscale (worst 0.896); AC4 30/30; AC5 below 96/96, above
  72/72; AC6 flank 10/10, dark area **29/30**; full frame 20/20; stripe-free 20/20; strong 20/20;
  weak neighbour (R1 guard) 12/12. Misses (diagnosis only):
  - AC2, seed 93024 (P20, A -10, scorched): one region, Period 19.998, Angle -9.91, bbox within
    0.45 P, but depth 0.383 against 0.5 (`DEPTH_TOL` 0.1). The multiscale seed 93048 (P10, A 3,
    not counted for AC2) is the same: depth 0.394. This depth tail predates the rulings: 4/100
    calibration single frames have depth error below -0.1 both at `ce42580` and now (-0.102 to
    -0.121, P12/P16 scorched); the calibration summary did not count depth misses.
  - AC6 dark, seed 93130, full-frame typical: 2 mask pixels at the frame corner (row 0,
    cols 0-1) where the Profile is 4.86-4.94% of its max, just under `DARK_FRACTION` (5%).
  Not done after the stop: slice-7 `info`, gates (`make check`, `make measure`, stored
  thresholds, `make check-slow`).
- Rulings A, B and "Evaluation" (orchestrator, 2026-11-11, `handoffs/05-orchestrator.md`,
  "Rulings on the fresh-range misses"), taken up by implementer 6. 93_000-93_999 is consumed
  (kept in `USED_SEEDS`; its record stays in `.scratch/stripe-detector/region-evaluation.json`).
  **Predeclared before any fix:** a second fresh range `REGION_EVALUATION_2_SEEDS =
  range(94_000, 95_000)` in `tests/protected.py`, registered in `USED_SEEDS` (lockfile: one new
  line plus the `USED_SEEDS` line; a reservation, loosens nothing, under the ruling). Cases: the
  same job list of `tests/evaluate_regions.py` (now `jobs(seeds)`, `--range second`, the
  default). **Pass rule: every frame meets every criterion, same as before** (every count n/n,
  every single-region IoU >= `MASK_IOU_MIN`; the driver's `summary["pass"]`). Run once after the
  third freeze, no tuning on it, no retry; a miss stops the work and goes to the owner as a
  tolerance question. 93024 and 93048 (depth) and 93130 (dark corner) become regression tests.
- Fixes A and B (implementer 6; code fixes per the rulings, no test or tolerance changed; both
  developed on calibration seeds 90_000-90_299 inside `seed_guard.calibrating`):
  12. **A, depth:** a region's reported depth is the median of the re-tuned depth over its
      interior, the settled pixels at least `_INTERIOR_FRACTION = 0.5` of the region's largest
      edge distance from its edge (`_interior_depth`), instead of over the top candidate's seed
      area. Growth reference, `_A0` qualification and the leakage test keep the seed-area median.
      On 556 calibration regions (depths 0.2/0.35/0.5/0.8, scorched and multiscale, typical
      and low noise; full frames at 0.2/0.5/0.8; two regions) the error was -0.044..+0.023,
      0 beyond `DEPTH_TOL`; the seed median was -0.177..+0.018 with 33 beyond; the core median
      (Codex's suggestion) -0.304..+0.058 with 12 beyond (scratch `i6/depth.json`).
  13. **B, dark surround:** the light is `G10(frame) > _MASK_FRACTION x max(G3(frame))`: the
      level is taken from the frame smoothed at `_LIGHT_PEAK_SIGMA = 3.0` px rather than at 10.
      Diagnosis: smoothing at 10 flattens the Mottle's bright spots (lowering the max 1.2-2x)
      and raises the surround near steep edges, so the light reached Profile 4-5%. On 300
      full-frame calibration frames: light pixels at Profile < 5% in 29 frames before, 0 after
      (< 6%: 81 -> 5); lit share of Profile >= 20% 99.8% -> 96.6%; no truth-region pixel left
      out of the light (400 single/two-region frames). `_MASK_FRACTION` unchanged.
  The calibration driver gains the `depth` kind (those depth/Mottle/noise variants on
  90_000-90_099) and a `depth_errors` summary (median, worst, misses beyond `DEPTH_TOL`) per
  kind. Lockfile lines added under the "Lockfile approval" (new ticket-05 module numbers):
  `_LIGHT_PEAK_SIGMA` (3.0), `_INTERIOR_FRACTION` (0.5), and `tests/protected.py`'s
  `REGION_EVALUATION_2_SEEDS`, `DEPTH_REGRESSION_CASES`, `DARK_REGRESSION_CASES` (the rulings'
  regression cases 93024, 93048, 93130 as `test_depth_is_measured_on_the_region_interior` and a
  `test_dark_area_is_never_reported_as_striped` case). No existing line changed.
- Third freeze (implementer 6): fixes 12-13 plus `region-calibration.json` from the tune on
  90_000-90_399 at this tree (default knobs, no knob re-tuned). Single IoU worst 0.873, 0
  Period/Angle misses; two 30/30 and two_low 30/30 (worst IoU 0.882 / 0.896); full frame 60/60,
  0 mis-measured; `size_low` 0 below reported, 0 above not exactly one; `size_mottle` 0 below
  reported, 7/30 1.4x "both" missed (detection, as before); probe score min 96.2, 0
  mis-measured; stripe-free score max 48.1; **depth: 0 misses beyond `DEPTH_TOL` in every kind**
  (worst -0.043 single scorched, +0.019 two/full); R1 guard: `neighbour` weak misses 7 (same as
  the second freeze), none mis-measured; N9: cap 20, cap-hit frames 64 (19 from the new `depth`
  kind), reach_top_max 11, uncapped max 14.
- Acceptance after the third freeze (`c99a069`): `uv run --locked pytest -q -p no:randomly
  --durations=12 tests/test_analyse.py tests/test_cli.py`, exit 0, `321 passed in 517.03s`
  (not a gate quote; load average 5-9). The two-region threshold sweep took 52.70 s against the
  60 s timeout. Deviation 14 (test construction, per the ruling "speed up the code or the
  test's construction"; nothing loosened, timeout unchanged): the verdict and lowering-threshold
  tests are parametrized per threshold kind (and per pair of kinds), each analysis cached per
  (frame, threshold), so no test item runs more than three analyses. Every assertion is kept per
  report (same score as at `THRESHOLD`, `threshold == t`, `striped == bool(regions) == score > t`,
  labels; every pair: regions at the higher threshold present unchanged at the lower); the new
  `test_sweep_thresholds_are_the_planned_ones` checks the kinds give the planned set. Slowest
  item now 18.07 s.
- **Second fresh-range evaluation (one run, no tuning): PASS** (predeclared rule: every frame
  meets every criterion). `uv run --locked python tests/evaluate_regions.py --range second
  --out ...` at `e70d99d` (detector as frozen at `c99a069`), exit 0; record in
  `.scratch/stripe-detector/region-evaluation-2.json`. AC2 40/40; AC3 IoU >= 0.8 40/40 scorched
  (worst 0.905, median 0.935) and 40/40 multiscale (worst 0.904, median 0.938); AC4 30/30; AC5
  below 96/96, above 72/72; AC6 flank 10/10, dark area 30/30; full frame 20/20; stripe-free
  20/20; strong 20/20; weak neighbour (R1 guard) 12/12; failures none.
- `make measure` at `317744b` (background, exit 0; `tests/test_feasibility_gate.py` 14 passed):
  gate PASS. Detection 500/500 (CI 0.993-1.000); held-out False Alarms 12/1000 (tolerance
  3-18); full frame median 5.73 s; probe 100/100, probe False Alarms 2/200. Thresholds: gate
  49.7159577445053 (was 74.1185), probe 85.17105365821853 (was 105.8027).
  `feasibility-gate.md` updated. Approval used (advance approval "stored thresholds after
  `make measure` per the CLAUDE.md procedure"): `GATE_STORED_THRESHOLD` and
  `PROBE_STORED_THRESHOLD` in `tests/protected.py` and their two lockfile lines set by hand to
  the new JSON values. Pass counts untouched. `make check-slow` not yet run.
- **STOPPED (implementer 6): `test_regression_plan_meets_the_operating_rule` is red** after
  the stored thresholds were updated: `P(any false red) 8.4262%` > `REGRESSION_MAX_FALSE_RED`
  1% (`{'detection': 2.2e-14, 'false alarms': 0.0804, 'full frame': 0.0042}`). The new baseline's
  held-out False Alarms (12/1000, exact CI up to 2.09%) make `REGRESSION_MAX_FALSE_ALARMS = 22`
  of 800 too tight at the pessimistic end. Per CLAUDE.md, re-deriving the pass counts is the
  owner's decision; pass counts untouched. Committed as is (measurement + stored thresholds, the
  procedure's outcome); `make check-slow` and the final `make check` not run.
- **STOPPED (implementer 7), owner ruling B not carried out: a detector fix cannot lower held-out
  False Alarms.** The gate Threshold is the 20th largest of 2000 calibration Stripe-free scores,
  so any detector's held-out rate is 20/2001 (about 1.0%, expected 10/1000,
  `betabinom(1000, 20, 1982)`). The operating rule needs at most 8/1000 at the unchanged pass
  counts, which a measure meets about 38% of the time whatever the detector. Ticket 03's 7/1000
  was a lucky draw. Re-measuring after a "fix" would only re-roll the held-out draw. The brief's
  premise ("free score max about 2 to 48") is the `region-calibration.json` *median* (2.1 to 15);
  the max was 47.9 at the first freeze. No code changed. Owner options (a)-(c) and the numbers:
  `handoffs/05-implementer-7.md`.
- **Owner approval (weakening-class gate-design change), carried out by implementer 8.** Reason:
  the stored gate threshold is a calibration rank (k = 20 of n = 2000), so the held-out False
  Alarm count is `betabinom(1000, 20, 1981)` for any detector, and the old false-alarm term
  (the held-out count's own Clopper-Pearson end) passed the operating rule on only about 38% of
  measures (implementer 7). Codex adversarial review: pooled-binomial framing wrong, the
  rank-based bound sound. Approved scope (orchestrator log, last entry): in
  `test_regression_plan_meets_the_operating_rule`, `fa0 = beta.ppf(0.975, k + x, n + 1 - k + N - x)`
  with k, n, x, N read from `feasibility-gate.json` (`gate.k`, `gate.calibration_n`,
  `gate.false_alarms`, `gate.free_n`); today Beta(32, 2969), 1.4636%, false-red term 0.209%.
  Changed interpretation: the bound holds averaged over calibration draws, not for one fixed
  threshold, and assumes i.i.d. continuous Stripe-free scores. Pass counts, sample sizes,
  `REGRESSION_MAX_FALSE_RED`/`_PASS_BAD`, the bad rates, the detection and probe terms and the
  held-out 3-18 band are unchanged; no re-measure, no detector change (measurement at `317744b`
  stands). Added: `test_stored_threshold_rank_is_untied` (calibration scores are not saved, so it
  guards what is: `gate.calibration_above == k - 1`, i.e. no tie with ranks above k; a tie below
  k is not visible) and `test_free_rate_bound_covers_the_true_rate_for_continuous_scores`
  (uniform scores, 4000 trials, coverage within 0.01 of 0.975; 0.976 now). Protected numbers
  added under this approval (`tests/protected.py` and four lockfile lines):
  `REGRESSION_FREE_RATE_BOUND_QUANTILE = 0.975`, `FREE_RATE_BOUND_COVERAGE_TEST_SEED = 41`,
  `FREE_RATE_BOUND_COVERAGE_TRIALS = 4000`, `FREE_RATE_BOUND_COVERAGE_TOL = 0.01`. Gate quotes:
  `handoffs/05-implementer-8.md`.
