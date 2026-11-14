# 07 implementer handoff 1 (paused on coordinator request, 2026-11-14)

Plan: `.scratch/stripe-detector/handoffs/07-plan.md` (section 9 steps). HEAD `2e995ec`. No background run is in flight (no PID); the step-5 calibration run has **not** started.

## Done (committed, each with a green `make test-fast`, log `07-stepN-test-fast.log`)

| Step | Commit | What |
|---|---|---|
| 0 | `6957c83` | Ticket Comment: owner W7 approval + plan 8.1 verbatim + section 13 by reference + test-seed allocations. Seed ranges, `CALIBRATION_SEEDS` entry (W1), section-7 numbers and test seeds in `tests/protected.py`; lockfile lines. Pre-ticket `.gate/check-slow-measurement.json` saved as `07-pre-ticket-check-slow-measurement.json` (commit `3f09325`, `free.max_score` 101.51738269624258). Plan, ticket edit and `07-*` handoffs committed. 559 passed, 478 deselected. |
| 1 | `41751bf` | `src/denoisifier/calibration.py`: `DEFAULT_FALSE_ALARM_RATE`, frozen `Calibration` (`from_scores`, `threshold` with rate checks and 0.0-atom docstring, `digest()` for W4(b), `to_json`/`from_json`; `run_info` is `compare=False`, settings/run_info JSON-normalised at construction). Added to `STAMPED_FILES`. Lockfile line. Unit tests in `tests/test_calibration.py`. 576 passed. |
| 2 | `5fb26b9` | `stripe_free_score`, `calibrate`, `calibrate_folder` (spawn pool for `workers > 1`, errors name the file), `src/denoisifier/recalibrate.py` (`python -m denoisifier.recalibrate`, stamped). AC 5 tests (a)-(d), (f). 583 passed. |
| 3 | `2e995ec` | `analyse(frame, *, false_alarm_rate=None, calibration=None, threshold=None, clip_level=None)` via `_resolve_threshold` (`is None`; `threshold=` excludes the other two). Default still `THRESHOLD` until step 6. `stored_calibration()` (`functools.cache`, `importlib.resources`, file `stripe_free_calibration.json`, not yet present). Tests in `test_analyse.py` and AC 5 (e) round trip. 592 passed, 478 deselected in 199.10s. |

Import-cycle choice (plan 2.1): everything stays in `calibration.py`; `analysis` imports it at module level, and `stripe_free_score` imports `analyse` inside the function.

## In flight (uncommitted, untracked, not yet run)

- `tests/test_threshold_calibration.py`: step-4 fast tests, written first: `test_run_pool_matches_serial_scoring` (written against `feasibility.score_batch`, must be green **before** the `run_pool` refactor; it has not been run yet), tiny-plan repeatability, frame settings, `test_slow_calibration_checks_run_on_a_tiny_plan` (B3), clipped `evaluate`, AC 6 marker test, false-red budget, full-plan constants.
- `tests/threshold_calibration.py`: the driver draft (settings, `synthetic`, `calibration_from_seeds` core, `calibrate_synthetic` with the one `calibrating(STRIPE_FREE_CALIBRATION_SEEDS)` block (W2), `reproduction_check`/`reproduction_problems`, `evaluate`, `HeldOutPlan`/`HELD_OUT`, `held_out_free`/`held_out_striped`/`held_out_check`/`record`, `false_alarm_problems`/`other_rate_problems`/`detection_problems`, `clipped_measurement`, `main()` with `seed_guard.install()` first (W3)). It calls `feasibility.run_pool`, which does not exist yet.

## Next

1. Run `test_run_pool_matches_serial_scoring` alone (green on today's `score_batch`), then refactor `feasibility.score_batch` into `run_pool(fn, jobs, workers)` (same spawn context, initializer, allowance snapshot, `chunksize=4`, order) and keep `score_batch` on it; `test_seed_guard.py`/`test_feasibility_gate.py` unchanged and green (W3).
2. Get `test_threshold_calibration.py` green (ruff/format both files), then write `tests/test_slow_calibration.py` (AC 7, `pytestmark = [pytest.mark.slow]`, per-test `pytest.mark.timeout(CALIBRATION_TIMEOUT_S)`) and `tests/test_held_out_calibration.py` (AC 2a/2b/3, slow + held_out, module fixtures writing `.gate/held-out-calibration.json` via `record`). Do not run them. Add the driver and both modules to `STAMPED_FILES` (W5).
3. W7: Makefile (`check-slow` → `-m "slow and not held_out"`, help text; `check-held-out` target + `.PHONY`), `held_out` marker in pyproject, hook `_LONG_TARGETS` + docstring + `tests/test_require_background_gate.py`.
4. Step 5 run, then steps 6-8 as in the plan.

## Open questions for the orchestrator

1. **`tests/test_slow_stamp.py::test_check_slow_runs_the_slow_tier_under_the_runner`** asserts `last.endswith("pytest -m slow")`. W7's recipe change makes it red; the planned fix changes that expected string to the new marker expression `-m "slow and not held_out"`. Not listed in section 8/8.1: please confirm it is covered by W7 (I read it as a direct consequence, not a loosening).
2. **`PACKAGE_CALIBRATION_DIGEST` as a hex string would not be pinned by the lockfile**, which pins numbers only (`protected_lock.holds_number`). Proposal: store it as an int (`int(sha256_hex, 16)`) so the lockfile pins it and the W4(b) claim holds. Confirm.

## File pointers

- `src/denoisifier/calibration.py`, `src/denoisifier/recalibrate.py`, `src/denoisifier/analysis.py` (`_resolve_threshold`)
- `tests/test_calibration.py`, `tests/test_analyse.py` (Threshold-option tests before `test_constant_frame_is_not_striped_and_has_finite_score`)
- `tests/threshold_calibration.py`, `tests/test_threshold_calibration.py` (uncommitted)
- `tests/protected.py` (ticket 07 block), `tests/protected_numbers.lock`, `tests/slow_stamp.py`
- Ticket Comments: `.scratch/stripe-detector/issues/07-calibrated-stripe-score.md`
- Lockfile helper (scratch, not in the repo): `/tmp/claude-1000/-home-rusiva-dev-denoisifier/a2fa25a8-066e-4035-93c8-b5e87902affb/scratchpad/lockupd.py ANCHOR_KEY [--remove]`
