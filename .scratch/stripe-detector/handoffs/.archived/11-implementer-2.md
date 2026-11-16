# 11 implementer-2 handoff (paused by the coordinator, mid step 6)

BASE `e06a902`. Plan `11-plan.md` §7; rulings `11-rulings.md`; P1 `11-prototype-p1.md`;
predecessor `11-implementer-1.md` (steps 2-5 committed: `7ec6451`, `172b879`, `7d05e6c`).

## Leftovers checked at start

No leftover pytest/driver processes from implementer-1. Its step-2 `test_analyse.py` run
(`<scratchpad>/step2-analyse.log`) had been killed at 84 % with no failure; not rerun (step 6's
full suite covers it). `<scratchpad>` = `/tmp/claude-1000/-home-rusiva-dev-denoisifier/82f6a58c-c50e-48db-bf95-5f3223ba7872/scratchpad`.

## In flight

- **Background driver run** (approved, plan §10 O3), started ~16:10, ~13 min idle, 12 workers:
  `uv run --locked python tests/break_fork_calibration.py --out src/denoisifier/break_fork_free_calibration.json`,
  log `<scratchpad>/driver.log` (ends with `EXIT=<n>`; its summary line prints thresholds, S_b/S_f
  max, digest). If you need to stop it: kill its process group (spawn workers outlive the parent;
  check `ps aux | grep multiprocessing.spawn`). It was started on the driver as written (formatting
  changes since then do not affect output; `settings()` content must stay as is, else rerun).
  Expected: S_b = S_f = 0 on (nearly) all frames → thresholds = floors 0.1 / 0.3.

## Uncommitted (step 6, nothing committed this session; not yet green)

- `tests/protected.py`: ticket-11 block after `FORK_VALIDATION_SEEDS` (seed ranges of plan §5,
  `BREAK_FORK_REPRODUCTION_PREFIX = 60`, shape/depth/rate, `BREAK_FORK_MAX_FAKES = 29`,
  `BREAK_FORK_CASE_ALARM_FRAMES = 6`, min detection 0.95, 100/100 frames, tiny test seeds
  40-43 / 44-47 / 10-11 / 12-13); `USED_SEEDS` += prototype and the two `_2` ranges;
  `CALIBRATION_SEEDS["BREAK_FORK_FREE_CALIBRATION_SEEDS"]`. **Missing:**
  `PACKAGE_BREAK_FORK_BREAK_THRESHOLD`, `PACKAGE_BREAK_FORK_FORK_THRESHOLD`,
  `PACKAGE_BREAK_FORK_CALIBRATION_DIGEST` (int of the hex digest, like
  `PACKAGE_CALIBRATION_DIGEST`) — set from the driver output. **Lockfile not yet edited**: add a
  `protected :: NAME :: value` line for every new name and update `USED_SEEDS` /
  `CALIBRATION_SEEDS` lines (approved A1/A2; `test_protected_numbers.py` prints the canonical
  values). Record the A1/A2/A3/A4 edits (and implementer-1's `DEFAULT_BREAK_FORK_FALSE_ALARM_RATE`
  line) in the ticket Comments.
- `tests/break_fork_calibration.py` (new driver): `settings`, `synthetic`, core
  `break_fork_calibration_from_seeds(..., depth=)` (raises on non-striped), `calibrate_break_forks(
  workers, *, prefix=None)` with the one `calibrating` block, `reproduction_check/_problems`
  (prefix-aware: thresholds of stored with the fresh prefix spliced in), `FakesPlan`/`held_out_fakes`/
  `implication_violations`/`fake_problems`, `DetectionPlan`/`held_out_detection` (paired floor run
  via `mock.patch.object(analysis, "_stored_break_fork_calibration", _floor_calibration)` in the
  worker)/`detection_problems`, `fake_count_bound`, `record = tc.record`, `main`. Smoke-tested core
  on tiny seeds (ok; depth 0 raises).
- `tests/test_slow_break_fork_calibration.py` (prefix 60 reproduction, slow) and
  `tests/test_held_out_break_fork.py` (slow+held_out: AC 2 fakes, AC 3(c) breaks/forks, full-300
  reproduction; JSON `.gate/held-out-break-fork.json`). Not run yet.
- `tests/test_break_fork_calibration.py`: imports rewritten; appended tiny-plan, spy, recipe,
  refusal, false-red budget (AC 2 bound 29; AC 3 at 09 199/200 and 10 133/133 validated rates,
  literals in the test), full-plan, AC 5 marks, stored-file and stripe-digest tests,
  `test_default_thresholds_are_the_stored_calibrations_at_the_default_rate`. Not run yet.
- `src/denoisifier/analysis.py`: `_resolve_break_fork_thresholds(None)` now uses the stored file at
  `DEFAULT_BREAK_FORK_FALSE_ALARM_RATE` (no floor fallback); unused `_BREAK_MIN_EVIDENCE` /
  `_FORK_MIN_EVIDENCE` imports removed from analysis.
- Lint: 2 errors left (E501 + I001 in the new test/driver files): `make fix` resolves them.

## Next

1. Wait for `driver.log` `EXIT=0`; set `PACKAGE_BREAK_FORK_*`; lockfile lines; `make fix`, `make lint`.
2. Run `tests/test_break_fork_calibration.py` (fast; tiny-plan test spawns pools), then
   `tests/test_feasibility_gate.py tests/test_protected_numbers.py tests/test_seed_guard.py`.
3. `tests/slow_stamp.py` `STAMPED_FILES` (A3): add `src/denoisifier/break_fork_free_calibration.json`,
   `tests/break_fork_calibration.py`, `tests/test_slow_break_fork_calibration.py`,
   `tests/test_held_out_break_fork.py`, and their imports `tests/breaks.py`, `tests/forks.py`,
   `tests/regions.py`, `tests/truth_match.py`, `tests/shared_cache.py`, `tests/binning.py`
   (`test_stamped_files_cover_the_slow_tier` lists any missed).
4. Still to write: `test_analyse.py::test_default_break_fork_thresholds_are_the_stored_ones` (AC 3b,
   hand calibration above floors, spy sees them); `test_cli.py` in-process
   `test_cli_break_fork_false_alarm_rate_reaches_analyse`, `test_cli_zero_break_fork_false_alarm_rate_is_an_error`,
   subprocess `test_cli_break_fork_false_alarm_rate_flag_is_accepted`. Implementer-1's T8 test passes the
   rate explicitly; fine either way now.
5. Commit step 6, then full `make check` in background (only the stamp step red expected; a red
   09/10 seed is a stop). Then step 7 docs (analyse docstring claim with scope and measured
   numbers, ADR 0003, spec.md note, CLAUDE.md + Makefile help strings, `test_slow_regression.py`
   docstring durations: check-slow ~22-23 min, check-held-out ~ +12.5 (full repro) +~25 (AC 2)
   +~4 (detection) min).

## Open questions

- None blocking. AC 3 false-red budget uses point validated rates (09 199/200, 10 133/133);
  a reviewer may prefer a stated lower bound (at 0.98 the bar's false red is 1.5 %).
