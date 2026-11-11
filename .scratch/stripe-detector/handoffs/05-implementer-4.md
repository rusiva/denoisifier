# 05 implementer handoff 4 (paused on coordinator request)

Ticket: `.scratch/stripe-detector/issues/05-striped-regions-and-mask.md`. Plan: `05-plan.md`. BASE 87005b9.
Brief: rulings R1-R4 and "Evaluation hygiene" in `05-orchestrator.md` ("Rulings on the post-freeze reds"),
then the new freeze, the fresh-range evaluation, slice-7 `info`, docs, gates (plan section 6).
Previous handoffs: `05-implementer-1.md`, `-2.md`, `05-implementer-handoff.md` (handoff 3, the reds).
`<scratch>` = `/tmp/claude-1000/-home-rusiva-dev-denoisifier/72618a23-dbd5-4573-9e6c-b83c3532a4a4/scratchpad`

## Committed

- `f72c427` **evaluation range predeclared before any fix**: `REGION_EVALUATION_SEEDS = range(93_000, 94_000)`
  in `tests/protected.py`, registered in `USED_SEEDS` (by reference); lockfile: one new line plus the
  updated `USED_SEEDS` line; ticket Comment added. `test_protected_numbers.py` +
  `test_seed_sets_are_disjoint_and_unused`: 11 passed (not a gate quote). **No frame from 93_000-93_999
  has been generated yet.** (Only `jobs()` of the driver was listed, which builds no frames.)

## Uncommitted (in the working tree, not yet verified green: no pytest run on them)

`src/denoisifier/analysis.py` (stamped):
- **R1 + R4, size rule** (`_half_peak_span`): the peak is now reached by `_climb` (steepest ascent on the
  depth map from the max on `top_core`), and the extent is `_widest_run`: the widest row (column) run of
  the connected part of `depth >= 0.5 x peak` holding that peak, ends interpolated as before. Causes found:
  (a) at sharp edges the ratio peaks in the skirt outside the region (reference energy is high on the
  edge), so the core sat outside the stripes and the column through it started on a low value: P20
  wide_short 0.8x measured h 3.34 P (now 1.69, fails as it should); (b) borderline (22, 20): the depth
  peak on the core is at the light edge (row 246, light row only 9 px), so the row through it gave
  w 0.449 P (now 12.15 P; score back to 217.1). For a compact, centrally symmetric blob the widest run is
  the run through the peak, so P1/P1-D's calibration carries over (to be confirmed by `size_low` below).
- **R1, leakage** (`_is_leakage`, new knob `_LEAK_FRACTION = 0.5`): a size-qualifying group is dropped
  when, for a stronger candidate (higher peak ratio, qualifying or not, not one of its members) that is
  `_near` it and deeper than it (`own < s.depth`), setting that candidate's grown extent to the local mean
  (`filters.mean(s.period)`) and re-filtering drops the group's seed depth below 0.5x. On the seen ghosts
  the deflated depth is 0.02x and 0.03x of the original; real stripes elsewhere stay at 0.83-1.00x.
  `_Candidate` gained `depth` (median seed depth), `_Group` gained `members`, `_Filters` gained `mean()`.
- **R3, refinement** (`_refined`, new knob `_REFINE_STEPS = 2`): after overlaps are settled, each
  survivor's Period/Angle is re-measured by the neighbour-product sum (`_phase_steps`, factored out of
  `_period_and_angle`) of `spec.gabor(P, A)` re-tuned to the current estimate, over the survivor's
  settled pixels, twice. Seed 23 P12: 4.98 -> 5.97 deg (prototype: on the seed area only 5.29; on the
  grown/settled pixels 5.97-5.98; other STRONG seeds stay within 0.03 deg). T-free (after settling).
- Module docstring updated (steps 4-6). Lint, format, mypy on `src`: clean.
- `<scratch>/impl/reds.py` on the current tree: every seen red now gives the expected result
  (strong 23 P12 A 5.97; narrow_tall 1.4x one region; all below cases no region).
- **Not yet in the lockfile**: `_LEAK_FRACTION`, `_REFINE_STEPS` (new ticket-05 module constants,
  covered by the "Lockfile approval"); run `<scratch>/impl/lockfix.py` (`uv run --locked python ...`).

Tests:
- `tests/test_analyse.py`: **R2** applied: the dark-area test now defines dark on the Profile
  (`mottle="none"`, noise 0, `regions=()`) below `DARK_FRACTION` of its max, with a comment citing R2.
  Not run yet. The approval is the orchestrator's R2 ruling; **its ticket Comment is not written yet**.
- `tests/regions.py`: `two_regions(..., depth=(left, right), edge_px=, gap_windows=)`; `depth` is now a
  pair (both existing callers use the default).
- `tests/calibrate_regions.py`: KNOBS gain `_LEAK_FRACTION`, `_REFINE_STEPS`; `SIZE_SHAPES` dict (adds
  `four_by_one`); new kinds on the last 40 tuning seeds (ruling R1): `size_low` (no Mottle, Gaussian
  0.01, `edge_px=1`, all 4 shapes at 0.8x and 3 at 1.4x, P 3/5/8/12/20 x A -10/0/10; 105 frames on
  90_360-90_379, reused) and `neighbour` (genuine weak region beside a strong one: each pair, strong on
  either side, weak depth 0.15/0.3, "low" = no Mottle, edge 1, gap 0.5 window / "typical" = scorched,
  Emccd, edge 6, gap 2 windows; 24 frames on 90_380-90_399). Summaries: `size_low.below_reported`,
  `size_low.above_not_exactly_one`, `neighbour.weak_missed`, `neighbour.weak_reported_wrong`. Per-truth
  matching now only pairs a truth with a region that overlaps it.
- `tests/evaluate_regions.py` (new, untracked): the one-off fresh-range driver. 390 frames on
  93_000-93_205: AC2/AC3 single region (40 scorched, 40 multiscale), AC4 two-region (30), AC5 (96 below,
  72 above), AC6 flank (10) and dark (30, Profile definition), full-frame (20), stripe-free (20), strong
  (20), weak neighbour (12; depths 0.6/0.3, low noise, edge 1, gap 0.5 window: **confirm these settings
  from the `neighbour` calibration numbers before the run**, and adjust only before running it).
  `uv run --locked python tests/evaluate_regions.py --out <path>` (background, alone). Lint clean; mypy on
  tests not checked yet.

## In flight

- Calibration tune on the current tree (all kinds, default knobs, `_LEAK_FRACTION 0.5`, `_REFINE_STEPS 2`):
  `uv run --locked python tests/calibrate_regions.py tune --out <scratch>/i4/tuneR.json`
  - log `<scratch>/i4/tuneR.log` (gets `EXIT=` at the end); pgid **1380230**; started about 21:30,
    expected about 15 min. Stop with `kill -INT -- -1380230` if needed. Left running.
  - Writes `<scratch>/i4/tuneR.json` (not the tracked `region-calibration.json`).
- My own idle wait loops (`until grep EXIT=`) on that log are harmless and end with it.

## Next steps

1. Read `tuneR.json` summary. Check: single IoU worst (was 0.873), two/two_low 30/30, full 0 mis-measured,
   free score max, `size_low.below_reported == []` and `above_not_exactly_one == []` (R1/R4: the new size
   measure on every shape), size_mottle, probe seconds (the leakage FFTs cost time; probe
   `seconds_max`), N9 counts.
2. R1 guard against erasing real weak neighbours: rerun `--only neighbour --set _LEAK_FRACTION=0.0`
   (disables the leak test) and compare `weak_missed`; the fix must not add misses. If it does and no
   tuning on 90_000-90_399 fixes it: **stop and report** (brief's stop condition). Tune `_LEAK_FRACTION`
   there only if needed.
3. Optionally add a held-out guard test `test_weak_region_beside_a_strong_one_is_reported` with new
   `*_TEST_SEEDS` in 81-99 (lockfile addition covered), settings taken from calibration.
4. Lockfile lines for the two knobs; ticket Comments: R1-R4 approvals used (R2 is the weakening-class
   test change), deviations below; commit the freeze = constants + `tuneR` rerun to the default
   `--out` (`.scratch/stripe-detector/region-calibration.json`).
5. Run `tests/test_analyse.py` and `tests/test_cli.py` as acceptance (seen reds should be green; any red
   after the freeze: stop and report). Then the fresh-range driver once; record numbers; any AC miss:
   stop and report.
6. `calibrate_regions.py info` (slice 7), docs, then gates in plan section 6 order: `make test-fast`,
   `make check`, commit, `make measure` (background), stored thresholds (approved procedure),
   `make check-slow` (background), `make check`. Borderline re-pick only per the measure-conditioned
   approval. Rewrite `05-implementer-handoff.md` with gate quotes.

## Deviations (to record in the ticket Comments)

8. Size rule: the peak is climbed to from the core, and the extent is the widest run of the half-peak
   component instead of the run through the peak (R1 P20 halo case, R4 light-edge case).
9. Leakage test with `_LEAK_FRACTION` (R1) and the pruning `own < s.depth` (leaked depth is below its
   source's).
10. Period/Angle refined on the settled pixels with a re-tuned filter, `_REFINE_STEPS` (R3).
11. `two_regions` takes per-region depths, edge and gap (test helper; existing calls unchanged).

## Open questions

- None blocking yet. The `neighbour` comparison (step 2) is the open R1 check.

## File pointers

- `src/denoisifier/analysis.py`; `tests/test_analyse.py` (dark-area), `tests/regions.py`,
  `tests/calibrate_regions.py`, `tests/evaluate_regions.py`, `tests/protected.py`
- Diagnostics: `<scratch>/i4/{dbg.py,ghost.py,defl.py,col.py,bl.py,r3.py}`; reds: `<scratch>/impl/reds.py`;
  lockfile helper `<scratch>/impl/lockfix.py`.
- Not mine, left alone: `.scratch/stripe-detector/issues/02-*.md`, `07-*.md`, `05-orchestrator.md` edits,
  `.scratch/agent-gates/handoffs/`, `.scratch/stripe-detector/handoffs/.archived/`, the `proto_*`/`p2_*` files.
