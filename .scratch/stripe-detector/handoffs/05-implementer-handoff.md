# 05 implementer handoff 3: STOPPED, acceptance tests red after the freeze

Ticket: `.scratch/stripe-detector/issues/05-striped-regions-and-mask.md`. Plan: `05-plan.md`. BASE 87005b9.
Previous handoffs: `05-implementer-1.md`, `05-implementer-2.md`.

## Commits (main)

- `146102c` slice 1, the generator (implementer 1).
- `ce42580` **freeze**: region detector, Report regions/labels/mask, CLI `--mask`, calibration driver
  and range, the lockfile lines for every new number (`_PERIOD_SPREAD` line removed), and
  `.scratch/stripe-detector/region-calibration.json` (the freeze tune run). It also adds the
  orchestrator's untracked `05-*.md` handoffs (plan, review, prototypes, log) to git.
- `b9f4a88` fixes two test bugs found on first run (no assertion loosened): the flank test passed
  `mottle` twice (TypeError); the CLI transpose test compared with `analyse` on the in-memory
  frame instead of on the frame the CLI reads (`%.9g` CSV), so the values differed by 1e-11.

## Freeze run (tune, 90_000-90_399, at `ce42580`'s knobs)

`uv run --locked python tests/calibrate_regions.py tune`, exit 0. Same as tuneC_g0.6:
- single-region IoU worst 0.873 (scorched P10); two-region 30/30 separate and correct (worst per-region
  IoU 0.882), two_low 30/30 (0.896); `truth_inside_half_envelope` true at (640, 1024);
- full-frame 60/60 striped, every frame one region, 0 mis-measured (N9 angle-unmerged count: 0);
- N9 candidate counts: cap 20, `reach_top_max` 10 (cap = 2x reach), `cap_hit_frames` 31 (frames
  where the cap left peaks unvisited; none dropped a qualifying group), uncapped max 17;
- stripe-free score max 47.9, median 2.1; probe m = 0.2: 18/20 reported, 1 mis-measured (90328);
- size with Mottle at low noise: 7/30 1.4x "both" regions missed (detection, as in handoff 2), 0 below reported.

## Acceptance (held-out tests after the freeze): RED, stopped as instructed

`uv run --locked pytest -q tests/test_analyse.py` at `ce42580`: exit 1,
`13 failed, 279 passed in 366.13s (0:06:06)`. Three of them were the flank test bug (fixed in
`b9f4a88`; `-k flank` now 3 passed). `tests/test_cli.py` at `b9f4a88`: 1 failed (borderline), 25 passed.
None is a gate quote; no `make` gate was run. No re-tuning was done.

Remaining reds (10 in test_analyse, 1 in test_cli), by cause:

1. **Ghost low-depth region next to sharp-edged small regions (AC 5, 5 reds).** Low noise, `edge_px = 1`, m 0.6:
   - `test_region_above_the_minimum_is_reported[78-8-+-10-narrow_tall]`: two regions, the true one
     (P 7.9, A -9.9, depth 0.16) plus a ghost (P 9.3, A -5.9, depth 0.031, bbox 80x62 around it).
   - `test_region_below_the_minimum_is_not_reported[78-8-10-narrow_tall]`: the true region is
     rejected, but a ghost (P 9.15, A 9.0, depth 0.024, score 420) qualifies.
   - `...below...[78-20--10-wide_short]`, `[79-20--10-wide_short]`: a region P 20.4, A -8.9, depth
     0.085 with a 127x110 bbox around a 32x80 truth region (a halo of the sharp edge).
   These look like the edge's spectral leakage making a wide, shallow candidate that passes the
   size rule. The plan's risk list (slice 4) named "tilted cores" and frames other than P1's; this
   is a detector finding.
2. **Dark-area test, full-frame typical, seeds 20-22 (3 reds).** The mask reaches pixels where the
   *Mottled* clean envelope is < 5% of max. All of them have Profile (no Mottle) >= 7% of max
   (median 17-19%), and 30-60% lie in interior Mottle holes inside the spot. So the detector's
   `light` (blurred frame > 10%) covers them. Question for the orchestrator: is "dark" defined on
   the Profile, or on the Mottled envelope as the test does now (plan row 6 says "envelope from the
   same seed with regions=() / m=0 and noise 0", which is ambiguous about Mottle)? Changing the
   test's definition is a test change, so I left it.
3. **`test_strong_stripes_are_measured[12-23]`**: one region, Angle 4.98 vs truth 6 (1.02 deg off,
   tolerance 1.0). Period and depth fine.
4. **Borderline (22, 20) (2 reds: `test_borderline_striped_frame_has_finite_measurements[22-20]`,
   `test_cli_reports_borderline_frame`)**: score 0.0, no qualifying group, so the frame is no longer
   borderline. A re-pick changes `BORDERLINE_TEST_CASES`. The advance approval covers a re-pick
   "only if `make measure` shows a seed is no longer borderline"; this showed up in `analyse`
   directly, so I did not take it as covered.

## Not done (blocked by the reds)

- Slice 7 `info` run (90_400-90_599).
- Gates: `make test-fast`, `make check`, `make measure`, stored thresholds, `make check-slow`.
- Docs: the module docstring now names the core and absorb steps; the CLI docstring/help, the
  `THRESHOLD` comment, GLOSSARY Mask and the LocalStripes note were already done (handoff 2).

## Deviations

Deviations 1-7 are in the ticket Comments (handoff 2). New this round: none in code. The
lockfile also gains `_LOG_BANK_STEP` (a derived ticket-05 module number), recorded in the Comments.

## Pointers

- Logs: `/tmp/claude-1000/-home-rusiva-dev-denoisifier/72618a23-dbd5-4573-9e6c-b83c3532a4a4/scratchpad/impl/{tune_freeze.log,accept.log,reds.py,dark.py}`
- Calibration: `.scratch/stripe-detector/region-calibration.json`
