# 06 fix list (code review from 4e40bdd to 2eab806)

These are orchestrator dispositions. Fix everything under **Fix**; leave everything under **Pass** alone.

## Fix

Standards:

- **F1.** `tests/test_synthetic.py::test_streaks_cover_their_length` defines its own seed range in the test (`range(SPIKE_GENERATOR_TEST_SEED, +6)`) and reuses seeds 35-37, which other tests already own (CLI_CLIP, SPIKE_BOUNDARY, PHASE_BREAK).
  - Give it its own protected seed range in `tests/protected.py`, with fresh seeds reserved in `USED_SEEDS`.
- **F2.** `tests/test_analyse.py` takes a seed subset in the test (`CLIP_TEST_SEEDS[:5]`).
  - Give the subset a protected name in `tests/protected.py`.
- **F3.** `tests/test_data_quality.py` has an unprotected tolerance: `0.2 * frame.max()`.
  - Move it to `tests/protected.py` as a named number.
- **F4.** "baseline" clashes with the `_Avoid_: baseline` line in GLOSSARY.md (term Envelope).
  - Rename to a glossary-consistent word for the bias level, e.g. "pedestal" or "bias level": `_SPIKE_BASELINE_PERCENTILE`, `BASELINE_OFFSET`, `test_spike_count_ignores_the_baseline`, and the prose ("peak-over-baseline").
  - If the word is a domain term, add it to GLOSSARY.md.
- **F5.** Two constants do not cite evidence, which breaks the `analysis.py` convention (cite the evidence file, its seeds and its numbers):
  - `_NOISE_TILE_PX`;
  - `_SPIKE_BASELINE_PERCENTILE`, which cites only "plan B3".
- **F6.** `MILD_CLIP_LEVEL_FRACTION` is reused in `test_clip_level_saturates_the_frame_and_is_in_the_truth` for a second purpose. The plan had that test at `C(CLIP_LEVEL_FRACTION)`.
  - Switch the test to the frozen `CLIP_LEVEL_FRACTION`, as planned.
- **F7. Duplicated Code.**
  - Extract one shared test helper (e.g. in `tests/cases.py` or a similar existing module) for the "typical frame from `CASES[seed % N]`" builder, now in three copies: `_case_frame`, `_typical`, `_spiked_clipped_csv`.
  - Extract one helper for "generate for `clean.max()`, then regenerate with `clip_level = fraction * top`", now used in about 6 places.
- **F8. Repeated Switches.** In `synthetic.generate`, `if spikes > 0` and `if clip_level is not None` each appear twice.
  - Fold them into one helper that returns `(frame, spike_mask, clipped_mask)`, keeping the order explicit: the clipped mask is taken on the spike-free frame (D4).
  - The digests must stay green untouched.
- **F9. Misplaced constant.** `_CLIPPED_WEIGHT_MAX` lives in `_data_quality.py`, but only `analysis._interior_depth` uses it.
  - Move it next to `_INTERIOR_FRACTION` in `analysis.py`.
  - Move its lockfile line with it. The value does not change.

Spec:

- **F10.** The runtime stimulus precondition (plan section 3) is missing: no 8-connected component of `truth.spike_mask` may have a vertical extent above `_SPIKE_MAX_LENGTH`.
  - Assert it in `test_report_counts_spike_pixels`, `test_saturated_spikes_are_counted_as_spikes` and the totals test.
- **F11.** `test_streaks_cover_their_length` cannot catch the 45° repeated-pixel bug (D1/N1), because it compares the extent with `hit.sum()`.
  - Assert that each streak's pixel count equals the drawn length `L` (from the generator's draw, or a deterministic hand-built call).
  - Check that the test fails on the old rounding.
- **F12.** The AC 5 CLI tests have no teeth:
  - `test_cli_clip_level_flag_overrides_detection[inf]` gives the same report as auto (seed 35: 11/0 and 11/0);
  - `test_cli_reports_spike_and_clipped_pixels` compares `clipped_pixels` 0 == 0.

  Build the CLI frame so that auto-detection finds clipped pixels (> 0), for example a clip near the light peak, so that `inf` and the override both change the report. Each param must fail if `--clip-level` is not wired through. Check this by temporarily unwiring the flag.

## Pass

- The string-param switch in `test_clip_level_override`: it is readable as a parametrised test, and each param has a clear purpose.
- The Data Clumps in `(spike_mask, clipped_mask)` and `(spike_pixels, clipped_pixels)`: the pairs are small and have one meaning each. A new type would be speculative.
- Spec 4, `test_clip_level_override[level]` asserting `analyse(f, clip_level=C) == analyse(f)`: the `below` and `inf` params give the teeth, and this one documents that the identity holds.
- Spec 6 (docstrings): no overclaim found.
- The `FULL_FRAME_CASES` extraction: a harmless refactor.

## Approvals for the fix

Orchestrator approval, recorded in the ticket-06 Comments with this list as the reason:

- New protected names and seed reservations: F1, F2, F3.
- Renaming protected names, values unchanged: F4.
- Moving a lockfile line between modules, value unchanged: F9.

Changing any value, or loosening a test, is not approved. Stop and report.
