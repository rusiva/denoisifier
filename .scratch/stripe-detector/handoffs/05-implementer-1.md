# 05 implementer handoff 1 (paused on coordinator request)

Ticket: `.scratch/stripe-detector/issues/05-striped-regions-and-mask.md`. Plan: `05-plan.md` (binding). BASE 87005b9.

## Committed

- `146102c` (on main): slice 1, the generator. `StripedRegion`, `RegionTruth`, `GroundTruth.regions` (with `period`/`angle_deg`/`modulation_depth` as single-region properties), the tanh masks, validation, and an unchanged RNG stream. New tests in `tests/test_synthetic.py`: digests taken at BASE, soft-edge masks, per-region Period and Angle, truth lists, invalid regions. `tests/protected.py` gains `DIGEST_TEST_SEEDS = range(30, 33)` and `REGION_GENERATOR_TEST_SEED = 33`, each with its own lockfile line. The ticket Comments record the plan's section 8 approvals plus the advance approvals.
- Checked on the committed tree only (exported index): `pytest tests/test_synthetic.py tests/test_protected_numbers.py tests/test_feasibility_gate.py::test_seed_sets_are_disjoint_and_unused`: `66 passed in 13.15s`. That is not a gate quote. `make test-fast` / `make check` have not been run on 146102c.

## Uncommitted in the working tree (in flight, not green)

- `src/denoisifier/report.py`: rewritten per plan 2.2. It has `BoundingBox`, `Region`, `Report(striped, score, threshold, regions, labels, transposed, reader_notes)`, `mask()`, `in_file_layout()`, and the new `to_dict` key order. `__init__.py` exports `Region` and `BoundingBox`.
- `src/denoisifier/analysis.py`: rewritten per plan 2.3. It has the T-free candidates, the `analyse(frame, *, threshold=)` validation, one shared `_Spectrum`, `_Filters` (local mean cached per Period, plus the `SIZE_ALONG_PERIODS` size filter), the period split, growth, the complete-linkage merge, the width and height size rule, overlap settling, score, and labels. `_measure` and `_PERIOD_SPREAD` are removed. Removing `_PERIOD_SPREAD` is covered by the advance approval, but it is not yet listed in the Comments and its lockfile line is not yet removed. The knobs are still at the plan's start values (`_PEAK_FOOTPRINT_PX=9`, `_SEED_FRACTION=0.5`, `_MAX_CANDIDATES=16`, `_SPLIT_LOG_STEPS=2`, `_GROW_FRACTION=0.5`, merge 1.2 / 2.0 deg / 2.0 P). None of them has a lockfile line yet. There are three deliberate deviations from the plan text, to record in the Comments and the handoff:
  1. A candidate's seed area excludes pixels already grown over by a higher candidate, and dedup skips peaks inside those pixels. Without this, low peaks (ratio 3-6) got seed areas covering the whole frame and merged into the real region.
  2. A merged group is re-grown on its re-tuned depth, with the level taken from the top member's seed area. Its depth is the median over the top member's seed. Otherwise a skirt fragment's low-depth seed pulled the level down (P20 IoU 0.51).
  3. A group qualifies only if its depth is at least `_A0` (the existing ratio floor). This is what gives a constant frame `score == 0.0` (B6); the constant frame scored 3e-12 without it. No new constant.
  The plan also says "all-zero frame: score 0.0", but `analyse` rejects all-zero frames ("no positive light", an existing test), so the verdict test uses only the constant frame.
- Sanity numbers on scratch seeds 95_000-95_003, 95_100-95_102 and 95_200 (outside every registry; add `range(95_000, 95_300)` to `USED_SEEDS`):
  - IoU 0.94/0.95/0.94/0.98 at P 3/8/20/5 (512², typical).
  - Stripe-free 256² scores 15-18 (the old max ratio gave about 84-106).
  - Full-frame m 0.5 gives one region, matched.
  - Probe 400x1600 m 0.2 took 5.3 s.
- `src/denoisifier/cli.py` (`--mask`, the alias refusal, `in_file_layout()` under `--transpose`, docstring and help) and `frame_io.write_mask_csv`: written but untested. None of the CLI tests from plan section 3 is written yet.
- `tests/protected.py` (working copy; ahead of the committed version): `REGION_CALIBRATION_SEEDS = range(90_000, 90_600)` in `CALIBRATION_SEEDS`, the `USED_SEEDS` reservations (N8, P1, P1-D, P2), `MASK_IOU_MIN`, `BBOX_TOL_PERIODS`, the `MIN_SIZE_*` factors, `DARK_FRACTION`, `REGION_SEMI_AXES_*`, `REGION_EDGE_PX`, `REGION_FRAME_SHAPE`, `TWO_REGION_PAIRS`/`SHAPE`/`GAP_WINDOWS`, `REGION_TEST_SEEDS = range(66, 76)`, `TWO_REGION_TEST_SEEDS = range(76, 78)`, `MIN_SIZE_TEST_SEEDS = range(78, 80)`, `CLI_MASK_TEST_SEED = 80`. **The lockfile lines for these are not added yet**, so `test_protected_numbers` is red until they are. The approval covers them.
- `tests/regions.py` (new): the geometry helpers, `iou`, `match`, `truth_bbox`, `assert_labels_consistent`, and a cached `single_region_case`.
- `tests/test_analyse.py`: existing tests migrated to `regions` (full-frame tests assert that **every** region matches), the JSON test rewritten, and all the new AC tests for analysis appended. That covers partial region, IoU (scorched and multiscale), two regions, below and above the minimum (4 and 3 shapes), flank, dark area, the threshold sweep verdict test, the lowering-threshold test (including an overlapping-extents frame), and threshold validation. **None of the new tests has been run.** One deviation from the plan: the sweep uses `MOTTLED_TEST_SEEDS[:5]` (free and m 0.5) rather than all 20, to keep the run time bounded.
- `tests/calibrate_regions.py` (new): the calibration driver. It calls `seed_guard.install()`, opens `calibrating(TUNE | INFO)`, and runs a spawn pool with the `install_worker` initializer. `tune` mode covers 90_000-90_399; `info` mode covers 90_400-90_599. `--set KNOB=V` runs sweeps and `--only KIND` restricts the run to some kinds. It records cap hits, candidate reach (the N9 count), unmerged or mis-measured full-frame fragments, the two-region outcomes, and whether each truth mask lies inside half the envelope.
- Earlier, `pytest tests/test_analyse.py` against an intermediate analysis.py (before fixes 1-3) gave 15 failures. I looked only at the failure kinds, not at the seeds, and did no tuning on them.

## Running in the background

- The calibration driver's first tuning run (current knobs, no overrides) is still running. It is not a gate job.
  - Command: `uv run --locked python tests/calibrate_regions.py tune --out <scratch>/impl/tune0.json`
  - Log: `/tmp/claude-1000/-home-rusiva-dev-denoisifier/72618a23-dbd5-4573-9e6c-b83c3532a4a4/scratchpad/impl/tune0.log` (gets `EXIT=` at the end)
  - pgid: about 1254404
  - Stop it with `kill -INT -- -1254404` if needed.
- No gate job (`check-slow`, `measure`, `bench`) is running.

## Next steps

1. Read `tune0.log` / `tune0.json`. Check the two-region leak and the low-noise Mottle size results (plan slice 4, early check). Bring any miss to the orchestrator. Then tune the knobs on 90_000-90_399 only, record the N9 counts, and size `_MAX_CANDIDATES` (twice the largest reach).
2. Add lockfile lines for all the new protected.py names and the analysis knobs. Remove the `_PERIOD_SPREAD` line and list it in the Comments.
3. Freeze: commit the constants plus `.scratch/stripe-detector/region-calibration.json` (a `tune` run with `--out` at its default path). Only then run the new acceptance tests in test_analyse.py (plan slice 6). If one goes red, stop and report it.
4. Run `info` mode (slice 7) for the informational numbers.
5. Write the CLI tests (plan section 3, AC 7 rows), then update `test_cli.py` (`report["regions"]`), the docs, GLOSSARY Mask, the `LocalStripes` docstring note, and BORDERLINE (a re-pick may be needed after measure; approval rules apply).
6. Run the gates in the order of plan section 6, including `make measure`.

## Open questions

- None blocking yet. To watch: the B6 all-zero frame point above, and whether deviations 1-3 need an orchestrator nod. They are internal and do not loosen anything, but they depart from the plan's text.
