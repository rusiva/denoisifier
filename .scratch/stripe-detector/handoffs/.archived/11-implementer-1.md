# 11 implementer-1 handoff (paused by the coordinator)

BASE `e06a902`. Plan `11-plan.md` §7; rulings `11-rulings.md`; P1 `11-prototype-p1.md`.

## Done (committed on main)

- `7ec6451` step 2: `find_phase_breaks(..., *, min_evidence, max_lines=_BREAK_MAX_PER_REGION)`,
  strict `E > min_evidence` in `_accepted`; `_region_forks` returns every candidate and each
  caller filters: pre-break gate `>= _FORK_GATE_EVIDENCE`, reported `> threshold`. Doubles and the
  9 direct finder calls in `tests/test_local_phase.py` updated; new tests
  `test_a_line_is_accepted_only_above_min_evidence`, `test_max_lines_caps_the_greedy_sequence`.
- `172b879` step 3: `calibration.py`: `DEFAULT_BREAK_FORK_FALSE_ALARM_RATE = 0.05` (lockfile line
  added, A1), `_BREAK_FORK_EVIDENCE_VERSION = "break-fork-v1"`, `_BreakForkThresholds`,
  `_BreakForkCalibration` (`from_evidence`, `thresholds(rate)` = r/2 marginal order stats with
  floors, rate error names 2/(n+1), `digest`, `to_json`/`from_json` with format + evidence
  version), `_STORED_BREAK_FORK_CALIBRATION_FILE`, `_stored_break_fork_calibration()`. Tests in
  `tests/test_break_fork_calibration.py`. (That commit had 4 PT011 lint errors in the test file;
  fixed in the steps 4-5 commit.)

## Steps 4-5 (committed `7d05e6c`)

Steps 4-5 together (they share `analysis.py` hunks):
- `analysis._FrontHalf` + `_front_half(frame, *, false_alarm_rate, calibration, threshold,
  clip_level, bin_factors)`: `analyse` and `_break_fork_evidence` both call it (pure refactor).
- `analyse(..., break_fork_false_alarm_rate=None)` → `_resolve_break_fork_thresholds(rate)`.
  **Temporary:** `rate is None` returns the floors (the stored file does not exist yet); a given
  rate uses `_stored_break_fork_calibration().thresholds(rate)`. Step 6 must switch None to the
  stored calibration at `DEFAULT_BREAK_FORK_FALSE_ALARM_RATE` (plan: no floors fallback shipped).
- `_with_phase_breaks(..., *, break_threshold)` → `_BreakPass(..., break_threshold)` → `find`
  (`max_lines` param); `_post_break_forks(..., *, fork_threshold)`.
- `_BreakPass.bridge` factored into `bridge_domain(a, b) -> _BridgeDomain | None` (`pixels`,
  `splits(brk, y, x)`), reused by the evidence pass.
- `_BreakForkEvidence(breaks, forks, striped)` (striped added for the driver's "every calibration
  frame striped" check) and `_break_fork_evidence(frame, *, clip_level, bin_factors)` per plan §2.
- CLI flag `--break-fork-false-alarm-rate` (help text per plan step 4), docstring line in
  `cli.py`. CLI tests not written yet (step 6, N6).
- Tests: `tests/test_analyse.py` end: `_hand_break_fork_calibration`, `_ThresholdSpy`,
  `test_break_fork_false_alarm_rate_option_sets_the_finder_thresholds`,
  `..._out_of_range_is_an_error` (4 params), `..._changes_the_report`; test doubles of
  `_with_phase_breaks` take `**kwargs`. `tests/test_break_fork_calibration.py`: T7
  (`test_break_evidence_is_where_the_first_break_is_found`,
  `test_fork_evidence_is_where_the_first_fork_is_found`, 5 frames each), T8
  (`test_evidence_bounds_the_public_report`, N10 precondition asserted),
  `test_analyse_and_evidence_share_the_front_half`. All pass (see Commit state).

## Checks run

- `make lint` green at pause.
- Step 2 tie check (R3): `uv run --locked pytest tests/test_analyse.py -q` (all params, wide
  included) on the step-2 tree, log `/tmp/claude-1000/-home-rusiva-dev-denoisifier/82f6a58c-c50e-48db-bf95-5f3223ba7872/scratchpad/step2-analyse.log`;
  at 77 % with no failure when paused (no `EXIT=` line yet). If it ends red on a 09/10 seed:
  stop rule (B4/R3).
- `tests/test_local_phase.py tests/test_phase_break_pass.py` 74 passed; `test_phase_break_pass.py
  tests/test_cli.py` 52 passed; fork/gate/pass subset of test_analyse green (exit 0).

## Findings

- T7 bridge: no real-path frame found where a bridge domain carries a break. Probe
  (`compatible_pair_frame` 10-13, `two_break_case` 10-13, AC 2 frames 10-19): compatible pairs
  give an empty bridge sequence; two-break frames are not `_compatible` (by design). So T7's
  bridge case checks only "nothing at S_b = 0". The bridge `g` formula is covered only by
  reasoning; a reviewer may want a synthetic bridge frame (e.g. a break the score path splits).
- S_b on AC 2 frames 10-19: 0.267-0.998 (min seed 18, matches P1's 0.267).

## Next (step 6 onward)

1. `protected.py`: seed ranges of plan §5 (`BREAK_FORK_*`), registry (`CALIBRATION_SEEDS`,
   `USED_SEEDS`), `BREAK_FORK_REPRODUCTION_PREFIX = 60` (P1: prefix branch),
   shape/depth/rate/min-detection/frame counts, AC 2 bound **29** (computed: betabinom(300, 15,
   286), P(X > 29) = 0.0090 <= 0.01, P(X > 28) = 0.0128), held-out per-case alarm 6 of 30;
   `PACKAGE_BREAK_FORK_*` after the driver run. Lockfile lines for each (A1, approved).
2. `tests/break_fork_calibration.py` driver (shape of `threshold_calibration.py`): frames =
   `threshold_calibration.synthetic(seed, PROBE_SHAPE, 0.5)`; core raises on a non-striped frame;
   one `seed_guard.calibrating(BREAK_FORK_FREE_CALIBRATION_SEEDS)` block; reproduction (prefix 60 in
   check-slow, full 300 `held_out`); held-out fakes (count, frames-with-fakes, Clopper-Pearson
   upper, per-case, implications at scale via `_break_fork_evidence`, JSON
   `.gate/held-out-break-fork.json`); detection (100 break frames via `breaks.break_region_case`
   + `ac2_line`, 100 Fork frames via `forks.fork_region_case`/`ac2_direction`/`ac2_offset`;
   matching via `truth_match.break_problems` / `fork_problems`; paired floor run needs the floors
   inside spawned workers, e.g. `unittest.mock.patch.object(analysis,
   "_stored_break_fork_calibration", ...)` in the job; `feasibility.run_pool` always spawns).
3. AC 3 budget: 09/10 "validated rates" not yet located (`.archived/09-prototype-p1.md`,
   `10-prototype-p2.md`); binom(100, 0.99) false red at 95/100 = 0.00053, at 0.98 = 0.0155.
4. Slow modules, `STAMPED_FILES` (A3), CLI tests (in-process `cli.main`), fast tiny-plan tests,
   `test_statistical_break_fork_tests_are_slow`, `test_stored_break_fork_calibration_*`.
5. Driver run (background) → JSON → wire `analyse` default → `PACKAGE_BREAK_FORK_*` → `make check`
   (only stamp step red expected). Then step 7 docs (ADR 0003 etc.).
6. Record the lockfile edits in the ticket Comments (A1 line for
   `DEFAULT_BREAK_FORK_FALSE_ALARM_RATE` not yet recorded there).

## Commit state

Steps 4-5 committed as `7d05e6c` after `pytest tests/test_break_fork_calibration.py
tests/test_phase_break_pass.py tests/test_cli.py`: `69 passed in 261.33s`, and `pytest
tests/test_analyse.py -k break_fork_false_alarm`: `6 passed, 1027 deselected in 18.74s`; `make
lint` green. Tree clean apart from this file and the pre-existing ticket-file edit. The step-2
full test_analyse run was at 84 % with no failure at handoff (log path above); if it did not
finish, rerun it (or rely on step 6's `make check`).
