# 05 fixer handoff: code-review fixes F1-F6 (DONE, gates green)

Ticket: `.scratch/stripe-detector/issues/05-striped-regions-and-mask.md` (Comments: last entry,
"Code-review fixes F1-F6"). Plan `05-plan.md`. BASE 87005b9. Fix list: last entry of
`05-orchestrator.md`. Previous: `05-implementer-8.md`.

## Commits

- `0c7caae`: F1-F6 code, tests, `docs/regression-plan.md`, `region-calibration.json` at cap 60.
- `91a7ea0`: `make measure` at `0c7caae` (`feasibility-gate.json`) and the ticket Comment.
- this handoff.

## What changed

- **F1.** `tests/calibrate_regions.py` `_candidate_reach` now measures plan 2.3 (N9) threshold-free
  on every tuning frame: uncapped grown candidates needed to reach the last qualifying group after
  the `_A0` floor, the size rule and the leakage test (`reach_last_member`; `reach_last_top`).
  Max **30** (neighbour; two_low 28, depth 26, two 24, single 22; probe 8, free 11, full 4); 22
  frames reached past cap 20. Rule cap >= 2x -> **`_MAX_CANDIDATES` 20 -> 60** (one lockfile line).
  At cap 60: 0 cap hits; score and region count unchanged on all 689 tune frames; 3 frames' region
  measurements moved slightly. New `test_candidate_cap_has_headroom_over_the_calibration_reach`
  (+ `CANDIDATE_CAP_HEADROOM = 2`). `make measure` at `0c7caae`: all counts and both thresholds
  identical to `317744b`, so the stored thresholds are unchanged. Speed: the timing frame grows 4
  candidates, so the cap doesn't affect it (6.19 s vs 6.55 s back to back under load 7-12). The
  measure's median of 7.47 s (was 5.73 s) reflects machine load. `make bench` was not run.
- **F2.** The old overlap frame did not overlap: it gave one merged region plus a noise region.
  Rebuilt it as Periods 8/16 at -6/+6 deg, with the ellipses overlapping by 40 px (2 groups, 2125 px
  of overlap). New `test_overlapping_extents_frame_settles_an_overlap` (a spy on `_settle_overlaps`).
- **F3.** Moved the derivation to `docs/regression-plan.md` (tracked) and pointed every docstring and
  comment at it. The coverage test reads the rate from `run_info`.
- **F4.** Moved the test_synthetic region-mask tolerances to `tests/protected.py`, keeping their
  values (6 lockfile lines added).
- **F5.** Renamed `_MASK_FRACTION` to `_LIGHT_FRACTION` (renamed lockfile line, value 0.1). Removed
  the "light mask" and "outlier" wording.
- **F6.** Inlined `_period_and_angle`, renamed `_seed_depth` to `_median_depth`, and added
  `regions.TRUTH_LEVEL` / `truth_pixels`.

Approvals used (recorded in the ticket Comments): the F1 ruling under the ticket-05 knob lockfile
approval (cap line), the orchestrator's approval to add protected numbers (7 lines), and the F5
ruling (rename).

## Gate quotes (HEAD `91a7ea0`; src/tests/docs clean; other agents' `.scratch` notes dirty)

- `make test-fast`: EXIT=0, `732 passed, 4 deselected in 451.10s (0:07:31)`.
- `make check-slow` (background, alone): EXIT=0, `4 passed, 732 deselected in 343.11s (0:05:43)`,
  `make check-slow: green; wrote .gate/check-slow-stamp.json`.
- `make check`: EXIT=0, `732 passed, 4 deselected in 549.89s (0:09:09)`, slow-stamp check passed.
- `make measure` at `0c7caae`: EXIT=0, `14 passed in 0.83s` (`tests/test_feasibility_gate.py`).
- `git rev-parse --short HEAD`: `91a7ea0`.

## Open (for the orchestrator)

- Finding, not fixed: the old overlap frame (two Period-8 regions 12 deg apart, 8 px gap) was
  merged into one region at Angle 1.15 deg. The seed-area Angles evidently fell within
  `_MERGE_ANGLE_DEG`. This may be a spec miss for close regions that differ only in Angle.
- Nothing is running in the background.
