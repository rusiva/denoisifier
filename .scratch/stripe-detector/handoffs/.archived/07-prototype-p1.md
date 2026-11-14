Prototype P1 (07 plan review, B4 / Q3) @ BASE 987caec, worktree agent-a8a17091543a85483. No repo code changed; scripts in the session scratchpad /tmp/claude-1000/-home-rusiva-dev-denoisifier/a2fa25a8-066e-4035-93c8-b5e87902affb/scratchpad (`p1hook/sitecustomize.py`, `runT.sh`, `p1_fullframe.py`, `rec_summary.py`, `ff_summary.py`).

## Method

- **Part 1.** Ran the whole non-slow tier (`uv run --locked pytest -q`, the same selection as `make check`: every seed, every `wide` id) six times.
  - Baseline: unchanged default T = 154.
  - Five runs with the default moved to T = 70, 80, 90, 100, 110. A `sitecustomize` hook set `analysis.THRESHOLD` and `analyse`'s keyword default before the test modules import them, so tests that cite `THRESHOLD` follow the new value, as they will after the plan's 2.3. `PYTHONPATH` carried the hook into the CLI subprocesses and the spawn workers.
  - The hook recorded every Report: test id, generator seed and kwargs, score, threshold, and every qualifying group's peak ratio.
  - The region count at each T is therefore known too (B4 asks about two-region and minimum-size tests).
- **Part 2.** Scored stripe-free 400x1600 frames at the plan's 2.5 settings: scorched Mottle, `Emccd()`, m = 0, Period and Angle from `CASES[seed % 10]` (they have no effect at m = 0), no clip.
  - 30 spikes: seeds 104_000-104_049.
  - 293 spikes: seeds 104_000-104_019, the same seeds again, so the two counts are compared on paired frames.
  - Run with 8 spawn workers and the seed guard installed.
- **Seeds.** Part 1 generated only what the existing tests already generate (test seeds; the guard test's existing calibrating block). Part 2 used only 104_000-104_049. No range from the plan's section 4 and no `CALIBRATION_SEEDS` range was generated.

## Part 1: test outcomes

| default T | result (non-slow tier) | failures |
|---|---|---|
| 154 (baseline, hook on) | `1032 passed, 4 deselected in 572.78s` | none |
| 110 | `2 failed, 1030 passed, 4 deselected in 494.32s` | borderline [22-20]; protected-numbers lockfile |
| 100 | `6 failed, 1026 passed, 4 deselected in 500.08s` | borderline x5; lockfile |
| 90 | `6 failed, 1026 passed, 4 deselected in 501.54s` | borderline x5; lockfile |
| 80 | `6 failed, 1026 passed, 4 deselected in 491.54s` | borderline x5; lockfile |
| 70 | `6 failed, 1026 passed, 4 deselected in 548.78s` | borderline x5; lockfile |

- **Lockfile failure.** `denoisifier.analysis :: THRESHOLD changed: lockfile 154.0, live T`. This is an artefact of patching the constant; the plan removes it (W4).
- **Borderline failures.** `test_borderline_striped_frame_has_finite_measurements` asserts `score < 1.5 T` (`BORDERLINE_SCORE_WINDOW`). The plan already re-picks these entries (W4).
- **Nothing else goes red** at any T in 70-110. That includes the CLI tests, the stripe-free, profile-only, clipped, spike, two-region, minimum-size and sweep tests, and the tiny regression plan.

### Frames whose default-path verdict or region count changes (S = striped, - = not)

Every default-path analysis was checked: 494 unique (test family, frame) analyses, 592 calls. Only these frames change, at the verdict level or the region-count level:

| test id | seed | frame | score | 154 | 70 | 80 | 90 | 100 | 110 | test outcome |
|---|---|---|---|---|---|---|---|---|---|---|
| test_report_counts_spike_pixels[pass-mark-m0.5-90] (spiked frame) | 90 | 256x256, m 0.5, 30 photons, 30 spikes | 149.70 | - (0 reg) | S (1) | S | S | S | S | passes: the paired spike-free frame flips with it |
| same (spike-free pair) | 90 | same, 0 spikes | 149.70 | - (0) | S (1) | S | S | S | S | passes |
| test_regression_check_runs_on_a_tiny_plan | 60 | 40x40, m 0.2 | 84.92 | - | S | S | - | - | - | passes (the tiny plan judges scores against its own thresholds) |
| same | 61 | 40x40, m 0.2 | 132.53 | - | S | S | S | S | S | passes |
| test_borderline_striped_frame_has_finite_measurements[22-20] (also CLI borderline) | 22 | 256x256, m 0.2, P20 | 212.02 | S | S | S | S | S | S | **red at every T ≤ 141**: 212.0 ≥ 1.5 T |
| …[13-5] | 13 | m 0.2, P5 | 159.35 | S | S | S | S | S | S | red at T ≤ 106 |
| …[13-8] | 13 | m 0.2, P8 | 159.75 | S | S | S | S | S | S | red at T ≤ 106 |
| …[12-20] | 12 | m 0.2, P20 | 158.44 | S | S | S | S | S | S | red at T ≤ 105 |
| …[16-8] | 16 | m 0.2, P8 | 159.70 | S | S | S | S | S | S | red at T ≤ 106 |

- **Region counts.** No already-striped frame gains a region at T ≥ 70. Every qualifying group's peak is either > 154 or ≤ 70 on every multi-region, two-region and minimum-size frame.
- **Borderline seeds.** The pairing of borderline ids to scores follows the order of the failure lines.

### Stripe-free default-path frames: headroom (max score per test family; every seed of that family)

| test | n frames | max score (seed) |
|---|---|---|
| test_clipped_stripe_free_frames_are_not_striped | 20 | 53.3 (10) |
| test_profile_only_frame_is_not_striped | 19 | 38.3 (21) |
| test_report_converts_to_json | 1 | 38.3 (21) |
| test_report_counts_spike_pixels / test_saturated_spikes_are_counted_as_spikes (m 0) | 10 / 10 | 35.1 (84) |
| test_stripe_free_mottled_frames_are_not_striped | 20 | 31.1 (21) |
| test_spikes_do_not_change_the_verdict_on_stripe_free_frames | 20 | 31.1 (21) |
| test_spike_free_frames_report_no_spikes | 29 | 31.1 (21) |
| test_multiscale_mottle_is_handled | 10 | 26.7 (27) |
| test_report_has_score_and_threshold | 1 | 22.5 (27) |
| test_regression_check_runs_on_a_tiny_plan (m 0) | 4 | 21.9 (63) |
| constant / min-side / cache-spelling / guard frames | 1 each | 0.0 |
| CLI stripe-free frames (all-zero mask, Solis crop, axis column) | 6 | 0.0; JSON-to-stdout frame 16.1 |

- **Highest stripe-free score.** The highest score of any stripe-free test frame is 53.3, 17 points below T = 70.
- **Profile-only frames.** The `_local_stripes.py:34-37` remark ("profile-only up to ~72") does not hold for today's test frames: the maximum is 38.3.
- **Excluded from the table.** `test_modulation_depth_is_relative_to_local_envelope` records m = 0 frames with scores up to 6063. Those are its region-built frames, which are striped, so they are left out.

## Part 2: full-frame stripe-free scores (400x1600, plan settings)

| spikes | seeds | n | exact 0.0 | median | p94 | p95 | p96 | p97 | p98 | p99 | max | wall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 104_000-104_049 | 50 | 5 (10%) | 31.0 | 61.0 | 65.5 | 69.8 | 73.5 | 77.0 | 77.6 | 78.18 | 110 s (8 workers) |
| 293 | 104_000-104_019 | 20 | 1 (5%) | 31.4 | 57.9 | 59.6 | 61.6 | 63.5 | 65.5 | 67.4 | 69.40 | 49 s |

- Percentiles are numpy linear. At n = 50 the p97-p99 entries are interpolations between the top three scores: 69.55, 76.95, 78.18.
- The 30-spike top scores (69.55, 76.95, 78.18) are consistent with the unspiked probe threshold of 85.17 (rank 3 of 300). The calibrated T at 1% is therefore likely about 75-90.
- **The 0.0 atom.** About 10% of frames score exactly 0.0. The 5% rank (k = 15 of 300, the 95th percentile at about 60-65) is far from the atom, so neither k = 3 nor k = 15 lands on 0.0.
- **Q3 sensitivity (paired, 20 seeds, 30 vs 293 spikes).**
  - The median paired change is 0.00. 15 of 20 scores move by less than 0.2.
  - Four scores rise by 3-9.5 (104_010 +4.35, 104_014 +3.05, 104_019 +9.47); 104_005 falls by 2.17.
  - One score jumps: 104_004 goes from 60.48 to 8.44 (-52.0), a gating step (Comment 2).
  - The maximum of the 20 barely moves (69.55 → 69.40).
  - So the spike count shifts individual frames by gating steps but does not visibly shift the upper tail at this n. Q3's choice is unlikely to move T by more than a few points; a 20-frame sample cannot rule out a tail shift of that size.

## Conclusion

- **What flips.** For any default T in 70-110 the fast tier stays green except for two cases, both of which the plan already covers under W4:
  - the five `BORDERLINE_TEST_CASES`, which fall outside (T, 1.5 T) and need the planned re-pick;
  - the `THRESHOLD` lockfile line.
  - Three frames flip verdict at the lower T: pass-mark seed 90 at 149.7, tiny-plan seeds 60 at 84.9 and 61 at 132.5. No test asserts on those flips: the first is paired with its spike-free twin, and the tiny plan uses its own thresholds.
  - No stripe-free, profile-only, clipped, CLI, two-region or minimum-size test is near a flip. The highest stripe-free score is 53.3, against a T of about 75-90.
- **B4.** No per-test rule is needed beyond the existing one ("a flip is a finding; no seed move, no explicit `threshold=`"). The plan can say that P1 measured zero non-borderline flips for T in [70, 110] and pre-declare the W4 re-pick as the only expected change.
  - If the stored T lands below about 85, tiny-plan seed 60 becomes striped. The test passes regardless.
  - The re-pick must handle `[22-20]` (212.0) as well: it leaves the window for every T ≤ 141.
  - `test_cli_reports_borderline_frame` uses the (22, 20) frame and stays striped at every T. If the re-picked first entry is used by the CLI test, it changes with it.
- **Q3.** T is about 75-90, well above 72. The share of exact zeros (about 10%) is harmless for k = 3 and k = 15. The 30 vs 293 spike count changes the tail little on 20 paired seeds, so 30 (recommended) carries no visible risk. The choice is still an owner/external-knowledge call, not a sensitivity problem.
