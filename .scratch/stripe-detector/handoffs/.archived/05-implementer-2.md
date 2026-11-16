# 05 implementer handoff 2 (paused on coordinator request)

Ticket: `.scratch/stripe-detector/issues/05-striped-regions-and-mask.md`. Plan: `05-plan.md` (binding). BASE 87005b9. Previous handoff: `05-implementer-1.md` (read it first; this one only adds to it).

## Committed

Nothing new. HEAD is still `146102c` (slice 1, the generator). No work in the tree is verified green, so none was committed (the lockfile lines for the new names are still missing, so `test_protected_numbers` is red by construction). No gate has been run.

## Stopped

- The final tuning run (`uv run --locked python tests/calibrate_regions.py tune`, default `--out`, which is `.scratch/stripe-detector/region-calibration.json`) was stopped part-way with `kill -INT -- -1314383`. Its spawn workers outlived two INTs, so I then sent `kill -TERM -- -1314383` to the same group. No calibration or worker processes are left. Log: `<scratch>/impl/tune_final.log` (EXIT=130). **`region-calibration.json` was not written.** The current knobs have been tuned, so rerunning this exact command is the freeze run.
- `<scratch>` = `/tmp/claude-1000/-home-rusiva-dev-denoisifier/72618a23-dbd5-4573-9e6c-b83c3532a4a4/scratchpad`

## Done since handoff 1 (uncommitted, in the working tree)

- `src/denoisifier/analysis.py`, tuned on 90_000-90_399 only:
  - `_SEED_FRACTION` 0.5 -> **0.1**. The 0.5 seed areas were 36-361 px, so the full-frame Angle came out 2 deg off and depth 0.26.
  - `_GROW_FRACTION` 0.5 -> **0.6**. Worst single-region IoU rose from 0.822 to 0.853.
  - `_MAX_CANDIDATES` 16 -> **20**: twice the largest reach (10, at g = 0.6).
  - Merge knobs stay at the plan's start values: 1.2, 2.0 deg, 2.0 P.
  - Two new knobs (deviation 4 below): `_CORE_FRACTION = 0.5` and `_ABSORB_FRACTION = 0.5`. A `core` field on `_Candidate` and `top_core` on `_Group`, plus `_absorbed()` in `_merge`. The size rule now finds its peak on `top_core`.
- `src/denoisifier/_local_stripes.py`: only the `LocalStripes` docstring (it pointed at `analyse` taking the max and at `_measure`). The file is stamped.
- `GLOSSARY.md`: added the **Mask** entry (plan 7.10). Its Avoid line is "region image, segmentation", not "map", which is already an avoided term for Frame.
- `tests/calibrate_regions.py`: removed every `noqa: E402`; the thread variables are now set in `main()` before the spawn pool. Added `_ABSORB_FRACTION` and `_CORE_FRACTION` to `KNOBS`. The two-region envelope check now uses the Profile (`mottle="none"`), and the summary gained `size_mottle.above_not_qualifying`.
- `tests/protected.py`: `TWO_REGION_SHAPE` is now (640, 1024); `range(95_000, 95_300)` added to `USED_SEEDS` (the scratch seeds of handoff 1). There are still **no lockfile lines** for any new name.
- `tests/test_cli.py`: all the plan's AC 7 CLI tests are written (mask layout, all-zero mask, transpose, Solis crop layout, missing mask directory, aliasing parametrized over 6 cases without a skip). `test_cli_writes_json_report_for_striped_csv` and the borderline CLI test now read `regions`. The Solis transpose equality test handles `transposed` and the swapped bboxes. **None of them has been run.**
- Ticket Comments: the `_PERIOD_SPREAD` removal and deviations 1-7 are recorded. The `_PERIOD_SPREAD` lockfile line is **not removed yet**.

## Tuning results (tuning range 90_000-90_399, 12 workers, loaded machine)

Logs and JSON in `<scratch>/impl/`. The summary helper is `summ.py <json>`.

| run | knobs | single IoU worst | full-frame mis-measured / not striped | two-region separate & correct | cap hits / reach max |
|---|---|---|---|---|---|
| tune1 | plan start values | 0.774 (multiscale P16) | 12 / 1 of 60 | 30/30 (1 frame with 3 regions) | 220 / 7 |
| tune_sf01 | sf 0.1 | 0.822 | 8 / 1 | 30/30 | 25 / 8 |
| tuneB_g0.5/0.6 | sf 0.1, merge 1.3 / 6 deg | 0.822 / 0.873 | 1 / 1 | 27, 26 /30 (looser merge biases the P8 Angle) -> rejected | |
| tuneC_g0.5 | sf 0.1 + core + absorb | 0.822 | 0 / 0 | 30/30, two_low 30/30 | 25 / 3 |
| **tuneC_g0.6** (chosen, + cap 20) | sf 0.1, grow 0.6, core, absorb | **0.873** (all mottles/Periods >= 0.873; two-region per-region worst 0.887, two_low 0.853) | **0 / 0** | **30/30, two_low 30/30** | 58 (cap 16 then) / **10**; uncapped max 17 |

Other numbers from tuneC_g0.6:
- Stripe-free scores: max 47.9, median 2.1 (THRESHOLD 154).
- Probe m = 0.2: 18/20 reported. One of those, 90328 (P10, A3), measures A 1.8, so the probe has 1 mis-measured frame (Angle 1.2 deg off; informational).
- Times: under 12-way load, 512² single region frames take about 12 s and 400x1600 probes about 35 s. **Idle, one process:** 400x1600 takes 6.2 s at m = 0.5 and 6.9 s at m = 0.2, and the region stage is only about 0.15-0.2 s of that; the filter bank dominates. These idle times were measured with the knobs before cap 20 and grow 0.6.

## Findings for the orchestrator

1. **Mottle at low noise (plan slice 4, early check):** in every run, 7/30 "both"-shape 1.4x regions in scorched Mottle at low noise were not reported (P5, P8 and P12). The cause is detection, not the size rule: each frame still has a size-qualifying group (score > 0), but its peak ratio is 44-117, below THRESHOLD 154. The 0.8x shapes: 0/30 reported (tuneC). The AC 5 tests themselves use `mottle="none"` (ruling O2), so they are not affected. This is a risk to record, not a blocker.
2. The two-region truth masks at (512, 1024) reached 2% outside the Profile's half maximum for the (8, 16) pair, so the shape is now (640, 1024) (deviation 5). Recheck it in the freeze run's `two.truth_inside_half_envelope`.

## Next steps

1. Rerun the freeze tune (`uv run --locked python tests/calibrate_regions.py tune`, background, alone). Check that it matches tuneC_g0.6 apart from the shape change and the cap of 20. Confirm `cap_hit_frames` and `reach_top_max` (the cap must stay at least twice the reach).
2. Add the lockfile lines (approved). In `analysis`: the size constants, `_PEAK_FOOTPRINT_PX`, `_SEED_FRACTION`, `_MAX_CANDIDATES`, `_SPLIT_LOG_STEPS`, `_GROW_FRACTION`, the three `_MERGE_*`, `_ABSORB_FRACTION`, `_CORE_FRACTION`, `_EIGHT`(?) and `_LOG_BANK_STEP` if the lock check counts them. In `protected`: every new name and the updated `USED_SEEDS` / `CALIBRATION_SEEDS` lines. Remove the `_PERIOD_SPREAD` line. Run `pytest tests/test_protected_numbers.py` to see which lines it asks for.
3. Commit the constants plus `region-calibration.json` (the freeze). Only then run `tests/test_analyse.py` as acceptance. If a new test is red, stop and report; do not re-tune.
4. Run `calibrate_regions.py info` for the slice-7 numbers.
5. Run `pytest tests/test_cli.py` and fix the CLI code (not the tests) where needed. Then do the docs left in slice 9: the module and `analyse` docstrings, which may need the core and absorb steps.
6. Run the gates in plan section 6 order: `make test-fast`, `make check`, commit, `make measure` (background), the stored thresholds (approval), `make check-slow`, `make check`. The borderline seeds may need a re-pick (advance approval only if `make measure` shows a seed is no longer borderline).

## Open questions

- Deviation 4 (the two new knobs `_CORE_FRACTION` and `_ABSORB_FRACTION`) departs from the plan's merge and size-rule text. Its numbers fall under the lockfile-addition approval, but the orchestrator may want a Codex read of the absorb rule. That rule drops a non-merged candidate whose grown extent lies more than 50% inside an earlier group's.
- The B6 all-zero frame: `analyse` rejects it, so the verdict test leaves it out (deviation 3).

## Deviations from the plan

All seven are listed in the ticket Comments:
1. Seeds exclude already-grown pixels.
2. A merged group is re-grown from the top member's level.
3. A group must reach the `_A0` depth floor (no all-zero frame).
4. The core and absorb knobs.
5. The two-region shape is (640, 1024).
6. The sweep uses `MOTTLED_TEST_SEEDS[:5]`.
7. The calibration driver uses no noqa.

## File pointers

- `src/denoisifier/analysis.py`, `report.py`, `cli.py`, `frame_io.py`, `__init__.py`, `_local_stripes.py` (docstring)
- `tests/test_analyse.py`, `tests/test_cli.py`, `tests/regions.py`, `tests/calibrate_regions.py`, `tests/protected.py`
- `GLOSSARY.md`
- Tuning logs and JSON: `<scratch>/impl/{tune1,tune_sf01,tuneB_g0.5,tuneB_g0.6,tuneC_g0.5,tuneC_g0.6,tune_final}.{log,json}`, plus `summ.py`, `dbgfull.py` and `prof.py` beside them.
- Not mine and left alone (uncommitted from before): `.scratch/stripe-detector/issues/02-*.md`, `07-*.md`, `.scratch/agent-gates/handoffs/`.
