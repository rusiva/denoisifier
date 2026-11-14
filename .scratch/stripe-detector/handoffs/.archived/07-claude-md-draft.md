# 07: drafted CLAUDE.md wording (plan 2.11, 2.12), for the owner at close

Not applied: the implementer does not edit CLAUDE.md. Each item gives the current text and the proposed text, in the Gates section. Durations are the closing wall clocks (fixer, 2026-11-14, at `6405366`, 12 workers): `make check-slow` 972.80 s (16:12) pytest time, `make check-held-out` 1019.49 s (16:59); the step-5 driver run 837.8 s. The stamped docstrings and help texts carry the step-5 estimate (about 20 min).

## 1. "When": the closing sequence, the check-slow duration, check-held-out, the hook list

Current:

> A ticket ends on one sequence, after the code review's fixes: `make measure` (only when the detector changed since the last measure; then the stored thresholds), `make check-slow`, `make check`. `make check-slow` takes about 6 min idle (duration: the module docstring of `tests/test_slow_regression.py`).

Proposed:

> A ticket ends on one sequence, after the code review's fixes: `make measure` (only when the detector changed since the last measure; then the stored thresholds and, when scores moved, the package re-store below), `make check-slow`, `make check`. `make check-slow` takes about 16-20 min idle (duration: the module docstring of `tests/test_slow_regression.py`); it runs the regression check and the calibration reproduction (`-m "slow and not held_out"`). `make check-held-out` (the held-out calibration tests, about 17-20 min, background; writes `.gate/held-out-calibration.json`) runs only at stripe-detector ticket 07's close and at `make measure` milestones, between `make check-slow` and `make check`; nothing else runs it or generates its seeds.

Current:

> A PreToolUse hook (`.claude/hooks/require_background_gate.py`) refuses `make check-slow`, `make bench` and `make measure` in the foreground.

Proposed:

> A PreToolUse hook (`.claude/hooks/require_background_gate.py`) refuses `make check-slow`, `make check-held-out`, `make bench` and `make measure` in the foreground.

## 2. "Write targets": the second source writer

Append after the `make measure` sentence:

> The calibration driver (`uv run --locked python tests/threshold_calibration.py --out src/denoisifier/stripe_free_calibration.json`, background, about 14 min) rewrites the tracked package calibration: the second writer of source outside `make fix`, only at stripe-detector ticket 07 step 5 and in the re-store procedure below.

## 3. New bullet after "After `make measure`" (plan 2.12, O2)

> - **After a score-moving change** (stripe-detector ticket 07 on): when `make measure` shows the score moved, re-run `uv run --locked python tests/threshold_calibration.py --out src/denoisifier/stripe_free_calibration.json` (background), set `PACKAGE_STORED_THRESHOLD`, `PACKAGE_STORED_THRESHOLD_5PCT` and `PACKAGE_CALIBRATION_DIGEST` in `tests/protected.py` to the file's values (a lockfile edit, needs an approval), then `make check-slow` → `make check-held-out` → `make check`. A re-store is **not** allowed when the change was not meant to move scores: an AC 7 red (`tests/test_slow_calibration.py`) then is a finding, not a re-store.

## 4. Weakening moves list (optional, for consistency)

In "weakening the slow-tier stamp or the background hook", the hook's list now includes `check-held-out`; no wording change needed beyond item 1.
