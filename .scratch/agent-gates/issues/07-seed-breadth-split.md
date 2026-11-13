# 07: Seed-breadth split for the inner loop

**What to build:** `make test-fast` runs every test function and every distinct case, but only the first seeds of each; `make check` keeps running every seed. Today the inner loop takes almost 10 minutes (1009 tests, 712 of them in `tests/test_analyse.py`, nearly all running `analyse` once or more), and an agent pays that after every change. The cost is the number of analyses times the frame size: about 0.8 s at 256x256, about 3 s at 512x512 and about 9 s at 640x1024 (scaled from the bench's 7.3 s at 400x1600; not measured per test). Most tests repeat one check over 10 to 20 seeds, and the threshold sweep runs 18 frames at 6 thresholds. Target: an inner loop of about 2 minutes on an idle machine.

**Evidence, gate time spent in stripe-detector ticket 06** (2026-11-13, from the workers' transcripts; seconds are pytest's summary lines; the machine was not always idle):

| Tier | Runs (s) | Total |
|---|---|---|
| `make test-fast` (full fast tier) | implementer 1: 426.10, 379.89, 360.58; implementer 2: 438.74; implementer 3: 403.67, 575.99; fixer: 571.99, 595.30, plus one stopped at about 240 | about 66 min (lower bound: runs stopped without a summary line are not counted) |
| `pytest -k "spike or clip"` (acceptance subset) | 206.31, 290.41, 268.36 | about 13 min |
| single-file pytest runs | about 15 | about 1 min |
| `make measure` | one run, 47:21 wall | 47 min |
| `make check` | `1009 passed, 4 deselected in 596.42s` | 10 min |
| `make check-slow` | `4 passed, 1009 deselected in 351.82s` | 6 min |
| **All tiers** | | **about 2 h 23 min** |

The inner loop was nearly half of it. Each fast run grew from about 6-7 min to about 10 min as ticket 06 added its tests (1009 tests at the end), and `make check` at the end re-ran the same 1009 tests once more.

**Blocked by:** none

**Status:** ready-for-agent

- [ ] Step 0, before any change: a `--durations=0` run of the fast tier on an idle machine (background, log, 1-minute load below 2). The per-test times go in Comments and set the subset below.
- [ ] A `wide` marker is registered in `[tool.pytest.ini_options]` (`strict_markers` is on). A small helper marks the extra parameters, so `parametrize("seed", inner(SEEDS))` leaves the first seeds unmarked and gives the others `pytest.mark.wide`. The number of unmarked seeds (start: 2) is a named constant in `tests/protected.py`.
- [ ] `make test-fast` selects `not slow and not wide`, and keeps `-x --ff`. `make check` and `make check-slow` select exactly what they select today: the same test ids and counts before and after, quoted in Comments.
- [ ] `make check` still runs every test that `make test-fast` runs.
- [ ] The inner loop keeps every test function, every Period/Angle case, every frame kind (the sweep frames, the spike frames, the size shapes, the dark cases) and every threshold kind. Only seed repetition and cross-products are cut:
  - seed ranges go to their first seeds;
  - the 15 threshold pairs of `test_lowering_the_threshold_keeps_reported_regions_unchanged` go to a subset in which every threshold kind appears;
  - the 640x1024 two-region frame is analysed once in the inner loop (12 times today), and the 512x512 region tests keep two or three cases.
- [ ] A collection-time check fails the run when a test function has only `wide` parameters, so no test can leave the inner loop silently. It has its own test, with a planted all-`wide` function that is not committed.
- [ ] No tolerance, expected value, timeout, seed range or pass count changes. No test is deleted or moved to the slow tier.
- [ ] `make test-fast` takes about 2 minutes on an idle machine, and its slowest test takes about 10 s or less. Comments quote the command, exit status, pytest's summary line, the wall time, the load before and after, and the `--durations` top 10.
- [ ] CLAUDE.md's Gates section says what `make test-fast` now runs, that a seed-specific failure can first appear at `make check`, and that adding `wide` to a parameter is a narrowing move that needs an approval.
- [ ] The ticket ends on the usual sequence: `make check-slow` (the `Makefile` and `pyproject.toml` are stamped files), then `make check`, both quoted.

**Out of scope**

- pytest-xdist. The prototype (`.scratch/agent-gates/xdist-prototype.md`) ruled it out while the slowest fast test takes more than about 10 s serially. Once this ticket is done, `make check` under `-n 4` is worth a new timing run, as its own ticket.
- Analysing each sweep frame once, not once per threshold. It would also shorten `make check`, but it changes how those tests reach the detector. Not decided.
- Smaller region frames. The 512x512 and 640x1024 shapes come from stripe-detector ticket 05's geometry in Periods and are protected numbers.
- Changed-file test selection (pytest-testmon or by path). Every `analyse` test depends on `analysis.py`, so detector tickets would still pay the full run.

**Risk, accepted by the owner:** a defect that shows on one seed only is found at `make check`, at the end of the work, not in the inner loop.

## Comments

### 2026-11-13 — owner approval (recorded by the session that wrote the ticket)

The owner approved the seed-breadth split in conversation, before any change, after reading the proposal and its risk. Reason: the inner loop takes almost 10 minutes after every change, which the owner called unacceptably slow. The approval covers these weakening moves, and only for this ticket's purpose:

1. Narrowing the tests that `make test-fast` selects to `not slow and not wide` (the `Makefile` recipe of `test-fast`).
2. Gate-config edits needed for it: the `wide` marker line in `[tool.pytest.ini_options]`, and the collection-time check if it goes in `tests/conftest.py`.
3. A lockfile addition for the new constant in `tests/protected.py` (no existing line changes).

Not covered: any change to what `make check` or `make check-slow` select, any tolerance, expected value or timeout, and any edit to `tests/slow_stamp.py` or the `check`/`check-slow` recipes. Those need their own approval.

Evidence behind the estimate, 2026-11-13: test counts from `pytest --collect-only`; `.gate/bench.json` (median 7.32 s at 400x1600, commit `b90b64e`); the xdist prototype's serial run (`732 passed, 4 deselected in 441.83s`, 2026-11-12, before ticket 06's tests). The full suite was not timed for this ticket, because another session's `make measure` was running; step 0 does that.

### 2026-11-13 — step 0: per-test times of the fast tier, before any change (planner)

Command (the `make test-fast` selection, without `-x` so every test is timed), at `21487c9` (tree dirty only in unrelated `.scratch/` files), background, log `.scratch/agent-gates/handoffs/07-step0-durations.log`:

`uv run --locked pytest --ff --durations=0` → `EXIT=0`, `1009 passed, 4 deselected in 852.15s (0:14:12)`. Shell clock: 21:56:46 → 22:10:35 (829 s; the VM clock and pytest's disagree by 23 s).

Load: 1-min 1.18 at the pre-check (21:56:41); **2.05** in the log's own `uptime` 5 s later, at start; 1.18 / 1.85 / 1.59 (1/5/15-min) at the end. Not a clean idle run: the same 1009 tests took 596.42 s in ticket 06's closing `make check`, so this run is about 1.43x slower. The per-test times below are used as **relative** costs; projections are given at this run's speed and scaled by 596/852 = 0.70.

Per-test time = setup + call + teardown. 686 tests are listed; 323 took under 5 ms each (hidden by pytest). Sum 848.7 s: `tests/test_analyse.py` 822.3 s, every other file 26.4 s (`test_cli.py` 14.5 s).

Top 30 tests (s):

| s | test |
|---|---|
| 25.61 | `test_analyse.py::test_two_regions_with_different_periods_are_reported_separately[77-8-16]` |
| 21.50 | `test_analyse.py::test_verdict_is_striped_exactly_when_a_region_is_reported[two-region-zero]` |
| 16.70 | `test_analyse.py::test_partial_region_is_reported_with_its_measurements[71]` |
| 16.26 | `test_analyse.py::test_two_regions_with_different_periods_are_reported_separately[77-4-10]` |
| 14.49 | `test_analyse.py::test_mask_overlaps_the_true_region[72-scorched]` |
| 12.47 | `test_analyse.py::test_mask_overlaps_the_true_region[71-multiscale]` |
| 10.42 | `test_analyse.py::test_partial_region_is_reported_with_its_measurements[70]` |
| 9.84 | `test_analyse.py::test_verdict_is_striped_exactly_when_a_region_is_reported[two-region-score]` |
| 8.75 | `test_analyse.py::test_two_regions_with_different_periods_are_reported_separately[77-5-12]` |
| 8.65 | `test_analyse.py::test_verdict_is_striped_exactly_when_a_region_is_reported[two-region-inf]` |
| 8.38 | `test_analyse.py::test_verdict_is_striped_exactly_when_a_region_is_reported[two-region-below-score]` |
| 8.16 | `test_analyse.py::test_verdict_is_striped_exactly_when_a_region_is_reported[two-region-above-score]` |
| 7.72 | `test_analyse.py::test_two_regions_with_different_periods_are_reported_separately[76-8-16]` |
| 7.29 | `test_analyse.py::test_two_regions_with_different_periods_are_reported_separately[76-4-10]` |
| 6.79 | `test_analyse.py::test_two_regions_with_different_periods_are_reported_separately[76-5-12]` |
| 6.03 | `test_analyse.py::test_report_counts_spike_pixels[typical-m0.5-84]` |
| 5.85 | `test_analyse.py::test_strong_stripes_are_measured[5-20]` |
| 5.82 | `test_analyse.py::test_heavily_clipped_partial_region_is_no_worse_than_no_exclusion[81]` |
| 5.68 | `test_analyse.py::test_heavily_clipped_partial_region_is_no_worse_than_no_exclusion[83]` |
| 5.48 | `test_analyse.py::test_heavily_clipped_partial_region_is_no_worse_than_no_exclusion[85]` |
| 5.46 | `test_analyse.py::test_report_converts_to_json[0.0]` |
| 5.43 | `test_analyse.py::test_strong_stripes_are_measured[5-22]` |
| 5.29 | `test_analyse.py::test_heavily_clipped_partial_region_is_no_worse_than_no_exclusion[86]` |
| 5.23 | `test_analyse.py::test_heavily_clipped_partial_region_is_no_worse_than_no_exclusion[84]` |
| 4.65 | `test_analyse.py::test_strong_stripes_are_measured[5-21]` |
| 4.26 | `test_analyse.py::test_clipping_does_not_harm_a_partial_region[85]` |
| 3.87 | `test_analyse.py::test_strong_stripes_are_measured[5-23]` |
| 3.61 | `test_analyse.py::test_partial_region_is_reported_with_its_measurements[66]` |
| 3.46 | `test_analyse.py::test_stripes_on_one_flank_of_the_envelope_are_found[66]` |
| 3.36 | `test_analyse.py::test_mask_overlaps_the_true_region[66-multiscale]` |

Per-function totals, every function at 1 s or more (s total / items / slowest item), all in `tests/test_analyse.py` unless named:

| total | items | max | function |
|---|---|---|---|
| 136.6 | 91 timed (108) | 21.50 | `test_verdict_is_striped_exactly_when_a_region_is_reported` |
| 92.5 | 40 | 6.03 | `test_report_counts_spike_pixels` |
| 75.6 | 20 | 14.49 | `test_mask_overlaps_the_true_region` |
| 72.4 | 6 | 25.61 | `test_two_regions_with_different_periods_are_reported_separately` |
| 50.2 | 10 | 16.70 | `test_partial_region_is_reported_with_its_measurements` |
| 46.3 | 40 | 1.36 | `test_spikes_do_not_change_the_verdict_on_stripe_free_frames` |
| 43.9 | 48 | 1.40 | `test_region_below_the_minimum_is_not_reported` |
| 36.4 | 66 | 0.73 | `test_spike_free_frames_report_no_spikes` |
| 33.7 | 36 | 1.49 | `test_region_above_the_minimum_is_reported` |
| 27.5 | 5 | 5.82 | `test_heavily_clipped_partial_region_is_no_worse_than_no_exclusion` |
| 26.4 | 30 | 1.09 | `test_profile_only_frame_is_not_striped` |
| 23.2 | 10 | 5.85 | `test_strong_stripes_are_measured` |
| 16.6 | 5 | 4.26 | `test_clipping_does_not_harm_a_partial_region` |
| 14.9 | 20 | 1.16 | `test_stripe_free_mottled_frames_are_not_striped` |
| 13.5 | 10 | 1.75 | `test_multiscale_mottle_is_handled` |
| 13.2 | 20 | 0.95 | `test_saturated_spikes_are_counted_as_spikes` |
| 11.9 | 20 | 0.77 | `test_clear_stripes_in_mottle_are_found_and_measured` |
| 11.8 | 20 | 1.00 | `test_clipped_stripe_free_frames_are_not_striped` |
| 11.4 | 10 | 1.26 | `test_report_counts_clipped_pixels` |
| 9.9 | 3 | 3.46 | `test_stripes_on_one_flank_of_the_envelope_are_found` |
| 8.2 | 14 | 0.70 | `test_clear_full_frame_stripes_are_found_and_measured` |
| 7.7 | 10 | 1.03 | `test_dark_area_is_never_reported_as_striped` |
| 6.1 | 2 | 5.46 | `test_report_converts_to_json` |
| 6.0 | 10 | 0.71 | `test_clipped_and_spike_totals_match_at_a_peak_level_clip` |
| 5.8 | 8 | 0.94 | `test_period_and_angle_extremes_are_detected` |
| 5.7 | 2 | 2.97 | `test_depth_is_measured_on_the_region_interior` |
| 3.5 | 5 | 0.76 | `test_borderline_striped_frame_has_finite_measurements` |
| 3.3 | 1 | 3.27 | `test_slow_regression_plan.py::test_regression_check_runs_on_a_tiny_plan` |
| 3.1 | 6 | 0.72 | `test_modulation_depth_is_relative_to_local_envelope` |
| 2.5 | 1 | 2.51 | `test_overlapping_extents_frame_settles_an_overlap` |
| 1.6 | 1 | 1.65 | `test_slow_regression_plan.py::test_an_unchanged_detector_passes_the_rule_on_most_measures` |
| 1.6 | 1 | 1.64 | `test_spike_count_ignores_the_pedestal` |
| 1.5 | 1 | 1.53 | `test_seed_guard.py::test_guard_reaches_the_feasibility_workers` |
| 1.5 | 3 | 0.52 | `test_clip_level_override` |
| 1.5 | 1 | 1.49 | `test_seed_guard.py::test_feasibility_script_guards_itself_and_its_workers` |
| 1.4 | 6 | 0.27 | `test_cli.py::test_cli_refuses_a_mask_path_that_aliases_the_input_or_output` |
| 1.4 | 2 | 0.70 | `test_cli.py::test_cli_clip_level_flag_overrides_detection` |
| 1.4 | 1 | 1.38 | `test_report_has_score_and_threshold` |
| 1.1 | 1 | 1.11 | `test_cli.py::test_cli_fails_cleanly_when_output_dir_missing` |
| 1.0 | 1 | 1.03 | `test_cli.py::test_cli_prints_json_to_stdout_without_output_flag` |

The totals that set the subset:

- **Cost per analysis** (from single-analysis items): about 0.6-0.9 s at 256x256; about 2.5-3.5 s at 512x512 for Periods 6-20, but 10.4 s and 16.7 s for the Period 3 and 5 cases (seeds 70, 71); 6.8-9 s for the 640x1024 two-region frame at seed 76 and 8.8-25.6 s at seed 77.
- **Cached work hides behind the first test that pays it.** `test_lowering_the_threshold_keeps_reported_regions_unchanged` (105 items) and the `THRESHOLD` items of the verdict test are all under 5 ms: they read `_sweep_report`'s cache. Likewise `test_spikes_leave_the_typical_stripe_free_score_unchanged` reads all 40 pairs that `test_spikes_do_not_change_the_verdict_on_stripe_free_frames` computed (46.3 s), and `test_clipped_stripe_peaks_keep_the_modulation_depth` reads the 10 seeds of `test_report_counts_clipped_pixels` (11.4 s). If those parametrized tests are cut, the unparametrized aggregate pays the cost itself, as one item.
- **The 640x1024 two-region frame:** 72.4 s (`test_two_regions_*`, 6 analyses) + 56.5 s (verdict test's `two-region` items, 6 analyses) = **128.9 s, 15% of the run**, for 12 analyses.
- **The 512x512 region tests:** 50.2 + 75.6 + 9.9 + 5.7 + 16.6 + 27.5 = **185.5 s, 22%**.
- **The 256x256 sweep** (verdict test less two-region): about 80 s.

Collected ids before any change (for "same ids before and after"), in `.scratch/agent-gates/handoffs/`: `07-ids-check-before.txt` (`uv run --locked pytest --collect-only -q`: `1009/1013 tests collected (4 deselected)`, 713 of them in `tests/test_analyse.py`) and `07-ids-check-slow-before.txt` (`uv run --locked pytest -m slow --collect-only -q`: `4/1013 tests collected (1009 deselected)`).

The plan: `.scratch/agent-gates/handoffs/07-plan.md`.
