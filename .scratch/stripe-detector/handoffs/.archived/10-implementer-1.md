# 10 implementer-1 handoff (paused by the coordinator)

Main checkout, branch `main`, HEAD `ca48498` (BASE). **Nothing committed**: steps 0-4 are written but `make test-fast` has not run green on them (one run was started, then stopped because I kept editing files under it; its result is void). Per the pause rule the work stays uncommitted.

## Done (uncommitted, in the working tree)

- **Step 0.** `tests/protected.py`: the section 7 numbers (`FORK_TEST_SEEDS` ... `FORK_VALIDATION_SEEDS`), and `USED_SEEDS` extended by `FORK_PROTOTYPE_SEEDS`, `FORK_VALIDATION_SEEDS` with the comment on unused 111_200-111_599 / 111_733-111_999. `tests/protected_numbers.lock`: 15 `protected :: FORK_*` lines after `BREAK_VALIDATION_SEEDS`, the `USED_SEEDS` line updated, and 6 `denoisifier._local_phase :: _FORK_*` lines after `_BREAK_MIN_FRAME_PERIOD_PX` (A1, A2). `protected_lock.check` returns `[]`.
  - BASE outputs saved at `ca48498` (before any source edit) by `/tmp/claude-1000/-home-rusiva-dev-denoisifier/a5c31385-01e3-4bc0-bce8-a97c1d5a1f5a/scratchpad/base_diff.py save` into `.../scratchpad/base/` (27 frames: the 4 `_identity_frame` kinds, binned 2x1 at `BINNING_TEST_SEEDS[2]`, 3 region frames, AC 2 break frames 10-19, `two_break_case` and `compatible_pair_frame` 10-13, the refusal frame with a break). Step 6: run `uv run --locked python <scratchpad>/base_diff.py compare <scratchpad>/base` from the repo root; it drops `forks`, checks `forks == []`, labels equal, and tolerates only the A4 refusal-sentence rewording. Scratchpad may be cleared by a reboot; if so, re-save from a `ca48498` checkout (e.g. `git worktree add`).
  - Not covered by the BASE script: a bridged frame where the pass merges regions (plan step 0's "09 bridged two-region-crossed frame"; I used `two_break_case`, the crossed frame, plus `compatible_pair_frame`). Add one if the reviewer wants it.
- **Step 1.** `synthetic.py`: `ForkPoint`, `ForkTruth`, `GroundTruth.forks`, `generate(forks=)`, `_checked_fork`, `_fork_phase`; the break and fork terms combined in `added_phase` (fork-free path unchanged, no RNG). Module and `generate` docstrings. Tests in `tests/test_synthetic.py` (sign via Hilbert phase, phase term, truth, invalid input, identity): 127 passed in that file.
- **Step 2.** `report.py`: `Fork` (to_dict, transposed), `Report.forks`, `to_dict` key after `phase_breaks`, `UNITS["point"]`, `UNITS["direction"]`, `in_file_layout`, docstrings; `Fork` exported in `__init__.py`. `tests/test_analyse.py`: key list and `REPORT_UNITS` extended (A3), `test_report_lists_forks_as_plain_json`, `test_fork_in_file_layout_swaps_its_point_and_keeps_its_direction`. Green in a `-k` run.
- **Step 3.** `tests/forks.py` (`big_region`, `fork_region_case`, `ac2_case`, `fork_full_frame_case`, `fork_near_break_case`, `fork_pair_case`, layouts; every point half-integer); `tests/truth_match.py` `fork_problems` / `assert_forks_match`; `tests/test_fork_helpers.py` (7 passed). The frame helpers in `forks.py` have not been run yet.
- **Step 4.** `_local_phase.py`: the six `_FORK_*` constants, `FoundFork`, `fork_domain`, `find_forks`, `_box_sum`, `_stepped_across`, ported from `3922e33` `finder.py` / `forks.py` (full-frame inputs, crop inside; same arithmetic). Limits docstring as measured. `tests/test_local_phase.py`: 13 new fork tests (24 params on the generated-frame test); the file is 61 passed. The module docstring still says "Nothing here is fork-specific" (step 8 drops it).

`make fix` was run; `ruff check` was clean before step 4. mypy was not run after step 4.

## Next

1. `uv run --locked mypy src tests` (check the Makefile for what mypy covers), `make fix`, then `make test-fast` (background, log). When it is green, commit steps 0-4 (one commit per step by file: 0 = protected + lock (the `_FORK_*` lock lines belong to step 4 if you split by hunk); 1 = synthetic + test_synthetic; 2 = report, `__init__`, test_analyse; 3 = forks.py, truth_match, test_fork_helpers; 4 = _local_phase, test_local_phase).
2. Step 5: wiring in `analysis.py` (plan 2.3), tests first; then 5b timing; then steps 6-9 per the plan.

## Open

- None needing a ruling yet. No AC seed has run (N8 not triggered).
- No background runs in flight. No pytest processes left.
