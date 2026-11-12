# 05 implementer handoff 8: operating rule's false-alarm baseline from the rank-based bound (DONE, gates green)

Ticket: `.scratch/stripe-detector/issues/05-striped-regions-and-mask.md`. Plan `05-plan.md`. BASE 87005b9.
Previous: `05-implementer-7.md`. Brief: the owner's approval (weakening-class gate-design change), last
entry of `05-orchestrator.md`.

## What changed (commit `5559ef9`)

- `tests/test_slow_regression_plan.py`
  - `test_regression_plan_meets_the_operating_rule`: `fa0 = beta.ppf(0.975, k + x, n + 1 - k + N - x)`
    via `_free_rate_bound`, with k, n, x, N read from `feasibility-gate.json` (`gate.k`,
    `gate.calibration_n`, `gate.false_alarms`, `gate.free_n`). Today Beta(32, 2969), 1.4636%, so the
    false-alarm false-red term is 0.209%. The detection and probe terms are unchanged (exact CI ends).
    A comment states the new interpretation: averaged over calibration draws, i.i.d. continuous scores,
    and a pointer to the approval.
  - New `test_stored_threshold_rank_is_untied`: the calibration scores are not saved, so it guards
    what is saved. `gate.k == threshold_rank(calibration_n, rate)` and `gate.calibration_above == k - 1`
    rule out a tie with the ranks above k. A tie with ranks below k cannot be seen in the saved data.
  - New `test_free_rate_bound_covers_the_true_rate_for_continuous_scores`: uniform scores at the
    saved sizes, `threshold_for_false_alarm_rate`, 4000 trials. Coverage must be within 0.01 of
    0.975 (it was 0.976 when checked by hand). The test takes about 1 s.
- `tests/protected.py` + `tests/protected_numbers.lock` (4 lines, covered by the approval):
  `REGRESSION_FREE_RATE_BOUND_QUANTILE = 0.975`, `FREE_RATE_BOUND_COVERAGE_TEST_SEED = 41` (in
  `TEST_SEED_BLOCK`), `FREE_RATE_BOUND_COVERAGE_TRIALS = 4000`, `FREE_RATE_BOUND_COVERAGE_TOL = 0.01`.
  The comment on the operating rule is updated.
- Unchanged: pass counts (280/22/26), sample sizes, `REGRESSION_MAX_FALSE_RED`, `REGRESSION_MAX_PASS_BAD`,
  the bad rates, the held-out 3-18 band, and the detector. No re-measure: the measurement at `317744b` stands.
- The ticket 05 Comments record the approval and its reason.
- The derivation note was added to `.scratch/agent-gates/handoffs/.archived/05-plan.md`, before
  "Timing frames (O2)". That directory is **untracked** (not committed by me). `tests/protected.py`
  and the test docstring still point to the old path `.scratch/agent-gates/handoffs/05-plan.md`,
  which no longer exists.

## Gate quotes (tree at `5559ef9`; dirty only in others' `.scratch` notes, no src/tests changes)

- `make test-fast` (before the commit, same content): EXIT=0, `730 passed, 4 deselected in 597.84s (0:09:57)`.
- `make check-slow` (background, alone): EXIT=0, `4 passed, 730 deselected in 381.44s (0:06:21)`,
  `make check-slow: green; wrote .gate/check-slow-stamp.json`.
- `make check`: EXIT=0, `730 passed, 4 deselected in 532.76s (0:08:52)`, slow-stamp check passed.
- `git rev-parse --short HEAD`: `5559ef9`.

## In flight

Nothing. No background jobs are running.

## Next step

The orchestrator runs code-review from BASE 87005b9, then closes the ticket.
