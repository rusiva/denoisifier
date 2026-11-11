# 05 implementer handoff 5: STOPPED, fresh-range evaluation misses AC2 and AC6

Ticket: `.scratch/stripe-detector/issues/05-striped-regions-and-mask.md`. Plan: `05-plan.md`. BASE 87005b9.
Previous: `05-implementer-1.md`, `-2.md`, handoff 3 (the reds; superseded by this file, in git history at
`138ffb3`), `05-implementer-4.md`. Rulings: `05-orchestrator.md`, "Rulings on the post-freeze reds".

## Commits (main)

- `f72c427` (implementer 4) fresh evaluation range `REGION_EVALUATION_SEEDS = range(93_000, 94_000)`
  predeclared before any fix.
- `2107a40` **second freeze**: R1 leakage test (`_LEAK_FRACTION = 0.5`) and climbed widest-run size measure
  (R1, R4), Period/Angle refinement on settled pixels (`_REFINE_STEPS = 2`, R3), dark area on the Profile
  (R2, approved test change), lockfile lines for the two knobs, `region-calibration.json` from the tune at
  this tree, `tests/evaluate_regions.py` (committed before its run), calibration kinds `size_low` and
  `neighbour`, ticket Comments (R2 approval, deviations 8-11, lockfile lines, freeze numbers).
- The next commit (this handoff): the evaluation record `.scratch/stripe-detector/region-evaluation.json`,
  the ticket Comment on the stop, and this file.

## Calibration at the freeze (tune, 90_000-90_399, default knobs)

Single IoU worst 0.873, 0 Period/Angle misses; two 30/30 and two_low 30/30 (worst IoU 0.882 / 0.896);
full frame 60/60, one region each, 0 mis-measured; stripe-free score max 48.1 (median 15.4; 2.1 at
`ce42580`, still far below T = 154); size_mottle 0 below reported, 7/30 1.4x "both" missed (as before:
detection); **size_low (every shape, no Mottle, edge 1): 0 below reported, 0 above not exactly one**; probe
m = 0.2 score min 96.2, 0 mis-measured (1 at `ce42580`); N9: cap 20, cap-hit frames 38, reach_top_max 9,
uncapped max 17.

**R1 guard:** `neighbour` misses 7/24 (all typical noise: six at weak depth 0.15, one at 0.3). With the
leak test disabled (`--set _LEAK_FRACTION=0.0`) the misses are the same 7, so the fix erases no genuine weak
neighbour; every low-noise weak neighbour is found. `_LEAK_FRACTION` was not tuned.

R4: borderline (22, 20) now scores 217.1 (one region, 12.15 P wide); it was a width-measure bug. No re-pick
was needed, and its tests are green.

## Acceptance after the freeze (held-out tests, not a gate quote)

`uv run --locked pytest -q -p no:randomly --durations=12 tests/test_analyse.py tests/test_cli.py` at
`2107a40` (tree had only others' `.scratch` edits): exit 0, `318 passed in 421.99s (0:07:01)`. Every seen
red from handoff 3 is green.

**Timeout margin (open):** a first run of the same command died on the 60 s per-test timeout in
`test_verdict_is_striped_exactly_when_a_region_is_reported[two-region]` while another project's tests
loaded the machine (load average 7-9). Run alone under that load it took 59.05 s (`ce42580`'s detector
took 53.61 s under the same load); in the green run 40.55 s (42.30 s at `ce42580`). Profiled, one analyse of
that 640x1024 frame takes 9.4 s, 6.6 s of it the pre-existing bank (`estimate_local_stripes`). The R1/R3
additions cost about 0.4 s (refinement 0.34 s, leakage 0.01 s). The test runs analyse 6 times. Not
touched: the timeout is a protected move. `make check` may be flaky on a loaded machine.

## Fresh-range evaluation: STOPPED (brief: "the fresh-range evaluation misses an acceptance criterion")

`uv run --locked python tests/evaluate_regions.py --out <scratch>/i5/eval.json` at `2107a40`, exit 0, one
run, no tuning. Record: `.scratch/stripe-detector/region-evaluation.json`.

| Criterion | Result |
|---|---|
| AC2 partial region (scorched) | **39/40** |
| AC3 IoU >= 0.8 scorched / multiscale | 40/40 (worst 0.881, median 0.933) / 40/40 (worst 0.896, median 0.939) |
| AC4 two regions | 30/30 |
| AC5 below not reported / above reported | 96/96 / 72/72 |
| AC6 flank found | 10/10 |
| AC6 dark area never reported | **29/30** |
| full frame, every region matches | 20/20 |
| stripe-free not striped | 20/20 |
| strong stripes measured | 20/20 |
| weak region beside a strong one (R1 guard) | 12/12 |

The misses, diagnosed only (`<scratch>/i5/diag.py`):

1. **AC2, seed 93024 (P20, A -10, scorched): depth 0.383 vs truth 0.5** (`DEPTH_TOL` 0.1). One region;
   Period 19.998, Angle -9.91, bbox within 0.45 P on every side, IoU 0.925. The multiscale frame 93048
   (P10, A 3) fails the same way (depth 0.394) but is not counted for AC2. The depth tail predates rulings
   R1-R4: on the calibration range 4/100 single frames have depth error below -0.1 at both `ce42580` and
   `2107a40` (-0.102 to -0.121, P12 and P16 scorched). The calibration summary only counted Period/Angle
   misses, so the tail was never flagged. The held-out `REGION_TEST_SEEDS` test passes.
2. **AC6 dark, seed 93130, full-frame typical m = 0.6:** 2 mask pixels at the frame corner (row 0,
   cols 0-1) where the Profile is 4.86-4.94% of its max, just under `DARK_FRACTION` (5%). The noise-free
   and spilling-region cases of that seed pass.

Questions for the orchestrator: is the depth under-measurement at typical noise (about 4% of single-region
frames off by 0.10-0.12) a detector finding to fix (and how is the evaluation then re-run, given that the
fresh range has now been looked at), or a tolerance question for the owner? Is a 2-pixel mask graze at
Profile 4.9% a miss of "never", or within the smoothing margin that `DARK_FRACTION` 0.05 vs the detector's
`_MASK_FRACTION` 0.1 was meant to leave?

## Not done (after the stop)

- Slice 7 `calibrate_regions.py info` (90_400-90_599): informational numbers.
- Gates: `make test-fast`, `make check`, `make measure`, stored thresholds, `make check-slow`, `make check`.
  **No gate was run; there is no gate quote.**
- Optional guard test `test_weak_region_beside_a_strong_one_is_reported` (not added; the fresh-range
  driver's R1 guard is 12/12).

## Approvals used and deviations (all in the ticket Comments)

- R2 (weakening-class test change, dark area on the Profile); "Lockfile approval" for `_LEAK_FRACTION`
  and `_REFINE_STEPS`; the evaluation-range reservation (implementer 4).
- Deviations 8-11: climbed widest-run size measure; leakage test; refinement; `two_regions` per-region
  depth/edge/gap plus the new calibration kinds.

## Pointers

- `src/denoisifier/analysis.py`; `tests/evaluate_regions.py`; `tests/calibrate_regions.py`
- `.scratch/stripe-detector/region-calibration.json`, `.scratch/stripe-detector/region-evaluation.json`
- Scratch (`/tmp/claude-1000/-home-rusiva-dev-denoisifier/72618a23-dbd5-4573-9e6c-b83c3532a4a4/scratchpad`):
  `i4/tuneR.json`, `i4/nb_leak0.json` (R1 guard), `i4/accept.log` (timeout run), `i4/accept2.log` (green),
  `i5/eval.json`, `i5/diag.py`, `i5/timing.py`, `i5/prof.py`.
- No background jobs are left running.
