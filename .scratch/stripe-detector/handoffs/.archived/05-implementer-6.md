# 05 implementer handoff 6: STOPPED at the regression plan's operating rule

Ticket: `.scratch/stripe-detector/issues/05-striped-regions-and-mask.md` (Comments carry every approval and
deviation 12-14). Plan `05-plan.md`. BASE 87005b9. Previous: `05-implementer-handoff.md` (handoff 5).
Rulings: `05-orchestrator.md`, "Rulings on the fresh-range misses".

## Stop

After `make measure`, I stored the thresholds per CLAUDE.md. `tests/test_slow_regression_plan.py::test_regression_plan_meets_the_operating_rule`
then went red:
`P(any false red) 8.4262%: {'detection': 2.2e-14, 'false alarms': 0.0804, 'full frame': 0.0042}`, `assert 0.0843 <= 0.01`.
The new baseline has 12/1000 held-out False Alarms (exact CI 0.62-2.09%; it was 7/1000). At the pessimistic
CI end, `REGRESSION_MAX_FALSE_ALARMS = 22` of 800 gives an 8% false-red chance. Re-deriving the pass counts is
**the owner's decision**. I left the pass counts untouched. `make check-slow` and the final `make check` were not run.

## Commits (main)

- `7f418cc` predeclares the second fresh range `REGION_EVALUATION_2_SEEDS = range(94_000, 95_000)` (in `USED_SEEDS`
  and the lockfile) and its pass rule, before any fix. **Pass rule: every frame meets every criterion** (every
  count is n/n and every IoU >= 0.8; the driver's `summary["pass"]`). Same cases as before:
  `tests/evaluate_regions.py --range second`.
- `c99a069` **third freeze**:
  - A: the reported depth is the median over the region's interior (`_interior_depth`, `_INTERIOR_FRACTION = 0.5`
    of the largest edge distance).
  - B: the light level comes from the frame smoothed at `_LIGHT_PEAK_SIGMA = 3.0` (`_light()`).
  - Regression tests: `test_depth_is_measured_on_the_region_interior` (93024, 93048) and a dark-area case (93130).
  - The calibration driver gains the `depth` kind and a `depth_errors` summary.
  - `region-calibration.json` was re-tuned at this tree; no knob changed.
- `e70d99d` (deviation 14): the threshold-sweep tests are split per threshold kind, with analyses cached. The
  slowest item went from 52.7 s to 18.1 s; the timeout is unchanged and the assertions are the same.
- `05f889d` second fresh-range record: `.scratch/stripe-detector/region-evaluation-2.json`.
- `317744b` renames `DARK_REGRESSION_SEED` to `DARK_REGRESSION_CASES`. An int named `*_SEED` counted as a seed range
  overlapping the consumed range.
- `3325cf2` adds the `make measure` output, the updated `feasibility-gate.md`, and the stored thresholds (gate
  49.7159577445053, probe 85.17105365821853). It also records the stop in the ticket.

## Numbers

- **Calibration at the third freeze** (90_000-90_399):
  - Single IoU: worst 0.873. Period/Angle misses: 0.
  - Two-region: two 30/30, two_low 30/30. Full frame: 60/60, 0 mis-measured.
  - Size rule: `size_low` clean. Probe score min 96.2. Stripe-free score max 48.1.
  - R1 neighbour weak misses: 7, as before.
  - N9: cap 20, 64 cap-hit frames (19 of them from the new `depth` kind), reach_top_max 11.
- **Depth error summary** (`depth_errors`): 0 misses beyond `DEPTH_TOL` in every kind.
  - single scorched: worst -0.043, median -0.004.
  - depth m0.2-0.8, both Mottles, typical and low noise: within -0.036..+0.018.
  - full: -0.019..+0.018. two: -0.023..+0.019. probe: -0.004..+0.003.
  - Before the fix: the seed-median estimator was -0.177..+0.018, with 33/556 beyond the tolerance (scratch `i6/depth.json`).
- **Dark surround**: on 300 calibration full frames, light at Profile < 5% went from 29 frames to 0 (< 6%: 81 → 5).
  The lit share of Profile >= 20% went from 99.8% to 96.6%.
- **Acceptance after the freeze** (not a gate): `uv run --locked pytest -q -p no:randomly --durations=12 tests/test_analyse.py tests/test_cli.py`,
  exit 0, `321 passed in 517.03s` at `c99a069`.
- **Second fresh range** (94_000-94_999), one run at `e70d99d`: **PASS**.

  | Criterion | Result |
  |---|---|
  | AC2 | 40/40 |
  | AC3 IoU, scorched | 40/40 (worst 0.905) |
  | AC3 IoU, multiscale | 40/40 (worst 0.904) |
  | AC4 | 30/30 |
  | AC5 below the minimum | 96/96 |
  | AC5 above the minimum | 72/72 |
  | AC6 flank | 10/10 |
  | AC6 dark area | 30/30 |
  | Full frame | 20/20 |
  | Stripe-free | 20/20 |
  | Strong stripes | 20/20 |
  | R1 weak neighbour | 12/12 |

- **Slice-7 `info`** (90_400-90_599, scratch `i6/info.json`; informational only):
  - Reported at typical noise and T = 154, by size factor:

    | Factor | "both" | wide_short |
    |---|---|---|
    | 0.8 | 0/10 | 0/10 |
    | 1.0 | 0/10 | 0/10 |
    | 1.25 | 1/10 | 0/10 |
    | 1.5 | 4/10 | 3/10 |
    | 2 | 6/10 | 3/10 |
    | 3 | 9/10 | 7/10 |

  - m = 0.2 single regions: 31/80 reported, 0 depth misses. Median IoU of the reported ones is about 0.87-0.91 at P14-20.
- **make measure** at `317744b`, exit 0 (`tests/test_feasibility_gate.py` 14 passed): detection 500/500, held-out
  False Alarms 12/1000, 5.73 s, probe 100/100.

## Gate quotes

- `make test-fast` at `317744b`: exit 0, `728 passed, 4 deselected in 350.31s`.
- `make check` at `317744b` (clean apart from others' `.scratch` notes): exit 2. Lint passed; tests
  `728 passed, 4 deselected in 359.45s`. The slow tier is stale, as expected (no check-slow yet).
- No gate has run since `3325cf2`. At that commit, `test_regression_plan_meets_the_operating_rule` is red (above).

## In flight

Nothing. No background jobs are running.

## Next step

1. The owner rules on the regression pass counts (`REGRESSION_MAX_FALSE_ALARMS` and the others) for the new baseline.
2. Then `make check-slow` in the background.
3. Then `make check`.
4. Then the final handoff (`05-implementer-handoff.md` still describes handoff 5).

## Open

- The operating-rule red above, for the owner.
- `size_mottle` 1.4× "both": 7/30 missed at low noise in scorched Mottle. This is detection, as before.

## Pointers

- Code and drivers: `src/denoisifier/analysis.py`, `tests/evaluate_regions.py`, `tests/calibrate_regions.py`, `tests/protected.py`.
- Records: `.scratch/stripe-detector/region-calibration.json`, `region-evaluation-2.json`, `feasibility-gate.{json,md}`.
- Scratch: `/tmp/claude-1000/-home-rusiva-dev-denoisifier/72618a23-dbd5-4573-9e6c-b83c3532a4a4/scratchpad/i6/`
  - Logs: `tune3.log`, `accept.log`, `eval2.log`, `info.log`, `testfast.log`, `check1.log`, `measure.log`.
  - Diagnostics: `light*.py`, `depth.py`.
