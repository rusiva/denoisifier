# 06 implementer 2: handoff (stopped before 5c)

Plan `06-plan.md` section 7, steps 5-6.

## Done

- **5a** (commit `a1948ad`): stimulus check on the generator only. Seeds 82 and 87 (and 96, 98 in the free block) have a spike component taller than `_SPIKE_MAX_LENGTH` in some spike-count configuration, so no contiguous ten-seed range works. `SPIKE_TEST_SEEDS = (81, 83, 84, 85, 86, 88, 89, 90, 91, 92)`, `CLIP_TEST_SEEDS = SPIKE_TEST_SEEDS`. Lockfile lines updated; recorded in the ticket Comments.
- **5b**: P3 run, evidence `evidence/06-prototype-p3.{py,json,txt,md}`. **`SPIKE_SCORE_TOL` would be 49, above the ceiling 15 → stopped, escalated.** Everything else is within its rule: `_CLIPPED_WEIGHT_MAX = 0.05`, `CLIP_LEVEL_FRACTION = 0.4`, `CLIP_MIN_SHARE = 0.02`, `CLIP_DEPTH_EPS = 0.01`, timing 0.144 s. Test-seed stimulus preconditions (clipped share, B4 count) pass, generator only.
- **6** (docs): the `analysis` module docstring (data-quality paragraph, depth step) and `analyse` docstring (spike rejection, `clip_level`, counts), plus the `synthetic` module docstring (forward model with spikes and clip). `Report`, `GroundTruth`, `Synthetic`, `generate`, `_data_quality` and the CLI help already had lanes A-C's wording.

## Not done (5c)

- No constants frozen: `_CLIPPED_WEIGHT_MAX` is still 0.10 in `_data_quality.py`; `CLIP_LEVEL_FRACTION`, `CLIP_MIN_SHARE`, `SPIKE_SCORE_TOL`, `CLIP_DEPTH_EPS` are not in `tests/protected.py` or the lockfile.
- The AC 2-5 tests are drafted, never run: `06-implementer-2-ac-tests.patch` (applies to `tests/test_analyse.py` at `a1948ad`; imports the four freeze names, so it needs them first; ruff `--fix` sorts the imports). AC 3's test asserts `abs(score change) <= SPIKE_SCORE_TOL` and equal verdicts at `THRESHOLD` and `GATE_STORED_THRESHOLD` (as `score > T`, the pinned verdict rule, to avoid a second analysis).

## The decision needed (AC 3)

P3's 100 paired frames: no verdict change at either threshold, for both parameters. But |score change| reaches 39.0 (13/100 above 15) because weak sub-threshold groups appear or vanish (score 0 <-> 15-39). The ceiling rule assumed a smooth score. Options for whoever decides (each a new ask, not mine to choose): drop the per-seed score tolerance and keep the verdict assertions; apply the tolerance only when both scores are non-zero (not enough alone: 396_633 goes 22.4 -> 4.3, and 396_664 5.0 -> 30.8); or accept a tolerance near 49 (above the 18 headroom, so weaker than the verdict assertions).
