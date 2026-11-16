# 09 implementer 2: handoff (paused by the coordinator)

BASE `b7c6731`. Plan: `09-plan.md`. Earlier handoff: `09-implementer-1.md` (steps 0-3 in `3bacb9d`).
Paused after plan steps 4-6, before step 7 (the AC tests).

## Done

Commit: see "Commit" at the end (steps 4-6 in one commit on top of `3bacb9d`).

- **Step 4, `src/denoisifier/_local_phase.py`.** `FoundBreak` (with `side()` and `along()`),
  `frame_period`, `sigma_n` (generic step width; `_finder_sigma_n` uses the finder's sigmas),
  `break_response`, `find_phase_breaks`. Constants are those of plan section 10. Behaviour is
  identical to the prototype `finder.py` at `3768dd2`: same output on the unit fields and, through
  the pass, on AC 2 seeds 10-13, full frame 11 and pair 12 (scratch `cmp.py`). The fine-scan
  `None` crash is guarded (the coarse result is kept). Added to `STAMPED_FILES` (approved).
  Lockfile has 23 `_local_phase` lines (approved).
  - Tests: `tests/test_local_phase.py` (25). Per the orchestrator's rulings (`09-critic-4.md`):
    - the phasor field is the blurred step (the finder's own window), not the plan's hard step;
    - new `test_the_phasor_field_is_the_finder_response_to_a_hard_step[0, 90]` (max error 0.043 at r 60);
    - the module docstring is fixed;
    - the jump is direction-aligned (`_aligned_jump`);
    - `BREAK_EXACT_POSITION_TOL_PERIODS` 0.25 -> 0.5 (APPROVED weakening; the comment at the constant gives the reason);
    - the small-region test uses a 56-px disc (ruled fine); the `find_phase_breaks` docstring says the window rule is per line angle.
  - New protected numbers `BREAK_PHASOR_FIELD_RADIUS_PX = 60.0` and `BREAK_PHASOR_FIELD_ATOL = 0.1`
    (measured 0.043) are in `protected.py` and the lockfile. They are new pins outside plan section 7:
    record them in Comments and confirm with the orchestrator.
- **Step 5, the pass in `analysis.py`.**
  - `_qualifying_regions` returns `(survivors, _Filters | None)`.
  - `analyse` calls `_with_phase_breaks(reported, filters, clipped)` between `reported` and the
    sort. It returns `[(survivor, found breaks)]`; with no found break these are the same objects.
  - `_BreakPass` holds the shared state (`find` with its response cache, `bridge`, `process`,
    `remeasure` under the energy guard, `fill` that updates `owned`, `depth`). The other helpers are
    `_absorbed_in_slits`, `_bridged_again` / `_bridge_one`, `_settled`, `_reported_breaks` (the
    segment; frame px via `frame_px`), `_refusal_warning` and `_bank_sigma_n`.
  - `_compatible` now takes a `_Tuned` Protocol. This is a type-only change; its behaviour is untouched.
  - `phase_breaks` are sorted by (region, -|jump|, first point). The refusal warnings sit after the
    unresolved-Periods warning and before the coverage note, one per final region under the 2.5 gate.
  - Pass constants (plan 10, second table) are in `analysis.py`, with 12 lockfile lines (approved).
  - Tests in `tests/test_phase_break_pass.py`:
    - same objects back when nothing is found;
    - fills never overlap;
    - absorb never takes a region with its own break, in both directions;
    - `test_phase_breaks_only_in_reported_regions`.
    Mutation-checked: removing the `owned` update reddens the fill test, and dropping the
    `q.breaks` check reddens absorb[True].
- **Step 6, BASE diff.**
  - Scripts: `scratchpad/base_output.py <out> refusal`, then `scratchpad/diff09.py base09 new09`
    (scratchpad = `/tmp/claude-1000/-home-rusiva-dev-denoisifier/85ad64ff-6979-496b-bc0d-89a93d20c47a/scratchpad`).
  - Result: every frame (bin2x1_p8, clear, free, region_emccd, spikes_clipped, two_compatible,
    two_regions) is `json equal: True`, `labels equal: True` and `phase_breaks: []`. The only
    differences are the expected new `phase_breaks` key and the new `units` entries `line` and `jump_rad`.
  - Refusal frame: 2 regions with 2 refusal warnings (labels 1 and 2, 2.35), in the right place.

## Orchestrator rulings (critic-4) applied?

- (1) Done in the code and tests, as listed above. **Not yet recorded in Comments:**
  - the approval and its reason (0.25 -> 0.5);
  - the plan deviation (blurred field);
  - the -0.125 P half-bin bias, to go in plan section 8 and ticket 17 Comments, with critic-4's
    `lo = s.min() - bin/2` trial.
- (2) Refusal frame: **not yet written** (it is a step-7 test). Assert:
  - `phase_breaks == ()` and at least one region;
  - one refusal entry per region, in label order, with its label and 2.35, between the
    unresolved-Periods warning and the coverage note;
  - do not pin the count of 2;
  - add the break-free twin (1 region, 1 warning).
  Record the AC 4 limitation (under 2.5 frame px, a split region stays split) in plan section 8,
  the `analyse` docstring and the Comments.

## In flight

- No background job is running. Nothing of mine is left uncommitted; this handoff file is untracked.
- **Unexplained single failure.** The combined run (`pytest tests/test_analyse.py tests/test_slow_stamp.py
  tests/test_protected_numbers.py tests/test_local_phase.py tests/test_phase_break_pass.py -q -x`)
  ended `1 failed, 831 passed in 472.32s`. `| tail -2` hid which test failed, and `--lf` did not
  name it.
  - The reruns are green: `pytest tests/test_analyse.py -q -x` gave `761 passed in 480.44s`, and the
    four small files gave `75 passed in 8.74s`.
  - Watch for it in `make test-fast`. Possible cause: a test sensitive to an edit made during the
    run, as in implementer-1's note.
- `.scratch/stripe-detector/issues/13-speed-budget.md` was modified before ticket 09. It is not
  mine and is left unstaged.

## Next steps

- **Step 7:** the AC tests of plan 5.2/5.4 in `tests/test_analyse.py`, plus `test_cli.py::test_cli_reports_phase_breaks`.
  - Helpers ready: `tests/breaks.py` (`break_region_case`, `break_full_frame_case`, `break_pair`,
    `two_break_case`, `ac2_line`, `full_frame_jump`, `region_breaks`) and `tests/truth_match.py`.
  - Parametrize AC 2 with `inner(PHASE_BREAK_TEST_SEEDS)` and AC 3 with
    `diagonal(PHASE_BREAK_TEST_SEEDS[0:2], [(a, j) ...])`.
  - The AC 4 and measurement tests reuse those frames (the cache is shared).
  - Pass-free analysis: monkeypatch `analysis._with_phase_breaks` with
    `lambda reported, filters, clipped: [(g, []) for g in reported]`.
  - `test_phase_breaks_only_in_reported_regions` already exists in `test_phase_break_pass.py`.
  - The handoff lists, per seed, whether a break was found on `two_break`.
- **Steps 8-9:** docs (`analyse` docstring, GLOSSARY Phase Jump, ADR 0001 line) and the ticket
  Comments (everything in plan step 9, plus the critic-4 items above and the two new pins).
- Then `make test-fast` (full), and report `make check` (expected red only on the stamp).

## Open questions

- Confirm the two new protected numbers (`BREAK_PHASOR_FIELD_*`): new pins, not in plan section 7.
- The plan names the AC tests in `test_analyse.py` (already about 1500 lines). I planned to keep
  them there, as named.

## Commit

`8a3fbc8` "Ticket 09 steps 4-6: _local_phase finder, post-threshold Phase Break pass, BASE diff clean".
Gate on the tree as committed (dirty only with the pre-existing `13-speed-budget.md` and untracked
files):
- `ruff format --check`, `ruff check` and `mypy` are clean.
- `uv run --locked pytest tests/test_analyse.py -q -x`: exit 0, `761 passed in 480.44s (0:08:00)`.
- `uv run --locked pytest tests/test_slow_stamp.py tests/test_protected_numbers.py tests/test_local_phase.py tests/test_phase_break_pass.py -q`: `75 passed in 8.74s`.

`make test-fast` was not run (left for the end of step 7). `make check` was not run: the slow-tier
stamp is stale by design.
