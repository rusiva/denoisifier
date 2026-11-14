# 07 implementer handoff 2 (stopped at section 13 rule 2, 2026-11-14)

Continues `07-implementer-1.md`. HEAD after this commit; steps 0-4 committed, step 5 run done (EXIT=0), rest of step 5 waits for the orchestrator.

## Done
- Step 4 (`c20b28d`): `feasibility.run_pool`, driver, `test_slow_calibration.py`, `test_held_out_calibration.py` (not run), STAMPED_FILES (W5), `held_out` marker, `check-held-out` target, hook + hook test. `make test-fast`: 601 passed, 482 deselected in 207.18s (`07-step4-test-fast.log`).
- **Held back:** Makefile `check-slow` recipe `-m slow` → `-m "slow and not held_out"` together with `tests/test_slow_stamp.py:317` `endswith("pytest -m slow")` → `endswith('pytest -m "slow and not held_out"')`. Needs the orchestrator's yes (expected-value change not named in 8/8.1). Must land before any `make check-slow`, or check-slow also runs the held-out module.
- Step 5 run: 1% = 100.80547983306298 (k = 3), 5% = 60.91880891139576 (k = 15), untied, zeros 30/300, 2.79 s/frame. `src/denoisifier/stripe_free_calibration.json` written, **uncommitted** (copy: `07-step5-stripe_free_calibration.json`). Stopped: rule 2 "near about 110".
- CLAUDE.md draft: `07-claude-md-draft.md`.

## Next (once the orchestrator goes on)
1. Rest of step 5: `PACKAGE_STORED_THRESHOLD`, `PACKAGE_STORED_THRESHOLD_5PCT`, `PACKAGE_CALIBRATION_DIGEST = int(digest_hex, 16)` (int so the lockfile pins it; implementer-1 Q2) in `tests/protected.py`; lockfile lines (scratchpad `lockupd.py`); the stored-file tests (2.2, W4(b)); add the JSON to STAMPED_FILES; switch the slow modules from `protected.X` attribute access to direct imports. Commit.
2. Steps 6-8 as in the plan.
