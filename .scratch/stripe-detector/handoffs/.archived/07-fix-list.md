# 07 code-review fix list (orchestrator, 2026-11-14)

Review: Standards S1-S7, Spec P1-P6 (BASE 987caec .. 0e4ca79). Score path frozen since step 5 (plan section 13 rule 4): none of these fixes may touch `analysis.py`, `_local_stripes.py`, `_data_quality.py`, `synthetic.py` or the driver's generation settings.

## Fix

- **F1 (P5):** `python -m denoisifier.recalibrate DIR -o F --clip-level inf` crashes after scoring every frame (`calibrate_folder` puts `inf` into `settings`, and `from_scores` refuses non-JSON floats). Validate and normalise before scoring: record an `inf` clip level in `settings` as JSON-safe (e.g. `null` meaning "off", matching what `analyse` does with inf), or reject non-finite values up front with a clear message, whichever matches the help text "'inf' turns it off" (keep the help text true). Add a test through `recalibrate.main` and `calibrate_folder` with `--clip-level inf`.
- **F2 (P6):** add a fast test that `calibrate_synthetic()` calls `calibration_from_seeds` with `STRIPE_FREE_CALIBRATION_SEEDS` and `CALIBRATION_SHAPE` inside an active `seed_guard.calibrating(STRIPE_FREE_CALIBRATION_SEEDS)` block (monkeypatch the core; no frames generated). No change to the guard.
- **F3 (P4):** `calibrate_folder`'s `run_info` records the folder's name only, not its absolute path.
- **F4 (S1):** remove the extended `# noqa: E402` instead of approving it: move the stdlib `typing` import in `tests/feasibility.py` above the `sys.path` manipulation, so it needs no suppression. Net effect: one fewer suppressed name. If ruff then still needs a noqa on that line, stop and report.
- **F5 (S3):** `threshold_calibration.run_info` reuses `feasibility.run_info` without re-adding keys it already records. (The package's `calibrate_folder` copy stays: the package cannot import tests.)
- **F6 (S5):** `Calibration.threshold` computes the rank once and indexes the sorted scores directly (no second rank or finiteness pass). Results must stay bit-identical: the stored-file tests and `PACKAGE_STORED_THRESHOLD*` must stay green unchanged.

## Pass (reason)

- S2: the package cannot import `tests/feasibility.run_pool`, and the guard initializer is test-only, so the copy is justified.
- S4: three read options in a private job tuple; a type for them is cosmetic now. Revisit if a fourth option is added.
- S6: plan 2.1 allowed the lazy-import cycle; it is documented in the code.
- S7: renaming means lockfile churn for a naming nit.
- P3: story 2's continuous score is deferred by ruling Q4 to issue 16.

## Fixer's remaining steps (plan section 9)

- Step 10, the clipped measurement, at the frozen code after F1-F6.
- Step 11, the closing gates: Q8 skip conditions quoted; `make check-slow` → `make check-held-out` → `make check`.
- Owner item: CLAUDE.md wording (`07-claude-md-draft.md`), shown at close (P2).
- Durations (orchestrator ruling): the duration docstrings in stamped files carry the step-5-derived estimate. They are written **before** the closing `make check-slow`, never after it, so the stamp stays valid. The closing wall clocks go in the ticket Comments and in `07-claude-md-draft.md` only.
- The stale "about 6 min" text in `tests/slow_stamp.py`: a docs-only text update is approved under W7 (the duration help text). It too is made before the closing check-slow; no code change in that file.
