# 09 implementer 1: handoff (paused by the coordinator)

BASE `b7c6731`. Plan: `09-plan.md`. Paused after plan steps 0-3, at the start of step 4.

## Done (committed: see "Commit" below)

- **Step 0, protected numbers.** `tests/protected.py` gains every number of plan section 7
  (`PHASE_BREAK_TEST_SEEDS` .. `BREAK_VALIDATION_SEEDS`; `BREAK_PROTOTYPE_SEEDS` and
  `BREAK_VALIDATION_SEEDS` appended to `USED_SEEDS`; `import math` for the π values). Lockfile:
  21 new `protected ::` lines plus the extended `USED_SEEDS` line (pre-approved; still to be
  recorded in the ticket Comments, plan step 9). No detector constants yet.
- **Step 0, BASE outputs** (before any detector edit; scratch, not committed):
  `/tmp/claude-1000/-home-rusiva-dev-denoisifier/85ad64ff-6979-496b-bc0d-89a93d20c47a/scratchpad/base_output.py`
  wrote `to_json()` + `labels.npy` to `.../scratchpad/base09/` for: clear (1 region), two_regions
  5/12 (2), spikes_clipped (1), free 400x1600 (0), bin2x1_p8 400x1600 frame (1), region_emccd P5
  (1), two_compatible 8/8 Angles 4/4 gap 1 window (2: live for the bridge). Step 6 re-runs this
  script and diffs. The scratchpad can be cleared by a reboot: if it is gone, regenerate the BASE
  outputs from a `git worktree` at `b7c6731` with the same script (the script itself is quoted
  in this file's history only by path; recreate from the frame list above if lost).
- **Step 1, generator** (`src/denoisifier/synthetic.py`): `PhaseBreakLine`, `BreakTruth`,
  `GroundTruth.phase_breaks`, `generate(..., phase_breaks=())`, `_canonical_break`,
  `_break_truth`, `_break_phase`; docstring states B1's three claims and the full-frame extent.
  Tests in `tests/test_synthetic.py` (AC 1 rows of 5.2 plus on-line, zero-jump, invalid-field
  tests). Green.
- **Step 2, report** (`src/denoisifier/report.py`, `__init__.py`): `PhaseBreak` (with
  `transposed()` and `to_dict()`), `Report.phase_breaks`, `to_dict` key after `regions`, `UNITS`
  `line` / `jump_rad`, `in_file_layout` swap+reverse; exported. Tests in `tests/test_analyse.py`:
  key list and `REPORT_UNITS` extended; `test_report_lists_phase_breaks_as_plain_json`,
  `test_phase_break_in_file_layout_swaps_and_reverses_its_points`. Green.
- **Step 3, helpers.** `tests/truth_match.py`: `break_problems`, `assert_break_matches`,
  `assert_region_covers_both_sides` (empty side fails), `truth_lit_mask`. `tests/breaks.py`:
  `break_region_case` (also `period`/`angle_deg`/`height_periods`/`noise` for the sign, small and
  Gaussian tests), `break_full_frame_case` (offsets in Periods, bins), `break_pair`,
  `two_break_case`/`two_break_layout`, `ac2_line`, `full_frame_jump`. Unit tests:
  `tests/test_break_helpers.py` (13, green). `breaks.py` is not exercised by any test yet.

## In flight (uncommitted)

- `tests/test_local_phase.py` (step 4's unit tests, written test-first, red: the module does not
  exist yet). Parked outside the tree at
  `/tmp/claude-1000/-home-rusiva-dev-denoisifier/85ad64ff-6979-496b-bc0d-89a93d20c47a/scratchpad/hold/test_local_phase.py`
  so the commit's `make test-fast` is green; move it back to `tests/` to resume.
- `.scratch/stripe-detector/issues/13-speed-budget.md` was already modified before I started; not
  mine, left unstaged.
- No background job left running after the commit's `make test-fast`.

## Next step

Step 4: write `src/denoisifier/_local_phase.py` (`break_response`, `FoundBreak`, `frame_period`,
`find_phase_breaks`, section 10 constants) against the parked tests; add it to `STAMPED_FILES`
(approved); lockfile lines for its constants (`sync_lock.py` in the scratchpad adds missing lines
for a module and a name regex: `cd tests && PYTHONPATH=. uv run --locked python
<scratchpad>/sync_lock.py denoisifier._local_phase '_BREAK'`). Prototype reference
`finder.py` at `3768dd2` (read via `git -C .claude/worktrees/agent-a89346810ac6ef538 show
3768dd2:prototypes/p09_breaks/finder.py`); note it crashes if the fine scan returns None (guard
it). Then steps 5-9.

## Finding for the orchestrator (B7, plan 5.4: "if not, stop")

The refusal-test frame at BASE `analyse` (generator with breaks, detector untouched) reports
**2 regions, not 1**: 2x1, 400x1600 frame (sensor 400x3200), sensor P 4.7, Angle 0, depth 0.5,
scorched Mottle, EMCCD, horizontal π break through the sensor centre (199.5, 1599.5),
`BINNING_TEST_SEEDS[0]` = 10: areas 108308 and 102890 (BASE splits at the break). The same frame
without the break: 1 region. For information only (not a re-pick): the same recipe on a 256x256
frame gives 1 region with and without the break. The plan's test would still pass with 2 regions
(no breaks; a refusal warning for each region), but plan 5.4 says to stop and ask. Decision
needed before step 7: keep the 400x1600 frame (and assert a warning per region), or another frame.

## Open questions

- The finding above.
- `make test-fast` earlier failed once on `test_cli_clip_level_flag_overrides_detection[override]`
  because I edited `report.py` during that run (CLI subprocess saw the new key, the in-process
  report did not); it passes on rerun and in the commit's run.

## Commit

`3bacb9d` "Ticket 09 steps 0-3: protected numbers, generator phase breaks, PhaseBreak report,
test helpers". Gate, run on the tree as committed (`tests/test_local_phase.py` parked outside):
`make test-fast` exit 0, `717 passed, 482 deselected in 237.00s (0:03:57)`, at `3bacb9d`
(tree dirty only with the pre-existing `13-speed-budget.md` and untracked files). `make check`
not run (slow-tier stamp stale by design; the fixer runs `make check-slow` then `make check`).
This handoff file itself is untracked.
