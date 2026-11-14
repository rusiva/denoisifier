# 07 plan: calibrated stripe score (settled)

**Status: settled 2026-11-14.** Not a draft. Every open question is ruled (section 12, "Rulings") and every review item is folded into the body. Sources: `07-orchestrator.md` "Decisions" (including the owner's Q2 ruling of 2026-11-14 and codex items C1-C3), `07-plan-review.md` (B1-B5, P1, O1, O2, N1-N8), `07-critic-plan.md` (Q1-Q9, E1-E6, smaller points), `07-codex-review.md` (C1-C3, B4 refinement), `07-prototype-p1.md` (P1 results). Implementers follow this file; a departure from it is a finding for the orchestrator, not a silent fix.

Ticket: `.scratch/stripe-detector/issues/07-calibrated-stripe-score.md`. The working-tree version is authoritative: it adds the `make check-slow` reproduction criterion. BASE `987caec`.
Spec: `.scratch/stripe-detector/spec.md` stories 2, 4, 5, 34, 52 and 53. Also "Analysis" (option "stripe false-alarm rate (default 0.01)"), "Report" (`score`, `threshold`), "Calibration" (spec.md:112, separate seeds, "stored with the package, can be recalibrated later on real frames"), Testing Decisions spec.md:140 and spec.md:157 (real-frame calibration must be possible; it happens later).
GLOSSARY: **Stripe Score**, **Threshold**, **False Alarm**, **Stripe-free**, **Verdict**. ADR 0001 (the Threshold is calibrated on synthetic stripe-free frames, not on an analytic model). CLAUDE.md Gates.
Inputs read: 06 critics 2 and 3 (the two 2026-11-13 Comments); 05 and 06 plans and orchestrator logs; `docs/regression-plan.md`; `feasibility-gate.json` at `fd59d0c`; `.gate/check-slow-measurement.json` (310 s wall clock).

## 1. Where things stand (BASE)

- `analysis.analyse(frame, *, threshold=THRESHOLD, clip_level=None) -> Report`. `THRESHOLD = 154.0` is provisional: it was set on ticket 03's old score and is a lockfile line (`denoisifier.analysis :: THRESHOLD :: 154.0`).
  - `score` = highest peak ratio over the surviving size-qualifying groups, 0.0 when there are none. The threshold changes only which regions are reported, never the score; this is tested (sweep tests in `test_analyse.py`).
  - Spike rejection and clip detection always run.
- `Report` already carries `score` and `threshold` (`to_dict` order pinned by `test_report_converts_to_json`). The CLI writes both.
- `_calibration.py` (private, stamped) has the order-statistic threshold (`threshold_for_false_alarm_rate`, k = floor(rate·(n+1))), `threshold_rank`, `false_alarm_tolerance` (betabinom central interval) and `rate_interval`.
- Feasibility gate (`tests/feasibility.py`, `make measure`) calibrates on spike-free, unclipped frames. Results:
  - 256x256: `GATE_STORED_THRESHOLD = 49.72`, k = 20 of 2000.
  - 400x1600: `PROBE_STORED_THRESHOLD = 85.17`, k = 3 of 300.
  - These values live only in `tests/protected.py`. The slow regression check (`test_slow_regression.py`) scores fresh seeds at them.
- **The score depends on frame size.** It is a maximum over a larger light area on a bigger frame, so the 1% threshold is 49.7 at 256x256 and 85.2 at 400x1600 (02 plan:270: "ticket 07 calibrates at the real frame size").
- Throughput: the runtime basis is **2.75-3.5 s of pool wall clock per full 400x1600 frame**, derived from `make measure` (600 full + 3500 small frames in 39 min per CLAUDE.md, 47 min in ticket 06), the only long measured run dominated by full frames (critic E1). The older 2.4 s figure (from check-slow's 310 s with 27 full frames) and the review's serial ratio (N2, about 8.6) both understate the pooled cost. Step 5 measures the real rate on 300 full frames in the same pool, and that number replaces the estimate in the duration docstring.
- Seed guard: `CALIBRATION_SEEDS` registry plus `seed_guard.calibrating(range)` blocks. The guard is installed in conftest, `feasibility.main`, `bench.main` and the `score_batch` initializer.
- Slow-tier stamp: `STAMPED_FILES` in `tests/slow_stamp.py`. `test_stamped_files_cover_the_slow_tier` fails on any unclassified file in `src/denoisifier/`, data files included, and on any unstamped module that uses `pytest.mark.slow` or is imported by one.
- The lockfile pins live values of every module- and class-level number in the package and in `tests/protected.py`. A computed value counts too.
- Detector code since the last measure: `git diff --stat fd59d0c HEAD -- src tests/feasibility.py` is empty (critic number checks).

## 2. Design

### 2.1 Public module `denoisifier.calibration` (new, stamped)

This module promotes the statistics behind a public interface. 03 plan-review O2 kept them private "until 07 fixes its interface". `_calibration.py` stays as the private maths (feasibility imports it).

- `DEFAULT_FALSE_ALARM_RATE = 0.01` (lockfile addition).
- `@dataclass(frozen=True) class Calibration`:
  - `ids: tuple[str, ...]`: `"seed:100000"`, or file names.
  - `scores: tuple[float, ...]`: in `ids` order.
  - `shape: tuple[int, int]`.
  - `settings: Mapping[str, object]`: how the Stripe-free set was made (generation and analysis parameters only), recorded and never interpreted by the library. Compared by the checks (2.2, AC 7) after JSON normalisation on both sides (`json.loads(json.dumps(x))`), because JSON turns tuples into lists (B1).
  - `run_info: Mapping[str, object]`: commit, CPU, versions, loadavg, wall clock. Recorded, **never compared** by any check (B1): the commit differs on every later commit and cannot be the commit that contains the file.
  - `threshold(rate: float) -> float`: `threshold_for_false_alarm_rate(scores, rate)`. Raises `ValueError` unless `0 < rate < 1` and `1 <= k <= n` (the existing "too few scores" message, plus a new "rate too high for n" message). The docstring states the 0.0 atom (Q4): a requested rate above the share of positive scores gives a threshold of 0 or a tie, and the realised rate is then below the request; the smallest requestable rate is 1/(n+1) (0.33% at n = 300).
  - `from_scores(...)` constructor.
  - `to_json()` / `from_json()` (`allow_nan=False`); scores must be finite.
- `stripe_free_score(frame, *, clip_level=None) -> float` = `analyse(frame, threshold=inf, clip_level=clip_level).score`. This is the one scoring rule for every calibration path: the full pipeline (spike rejection, clip detection, regions). `threshold=inf` means it never needs the stored calibration.
- `calibrate(frames: Iterable[tuple[str, np.ndarray]], *, clip_level=None, settings=None) -> Calibration`, serial. It refuses an empty input, frames of differing shapes (the rate depends on shape, 2.7), and non-finite scores.
- `calibrate_folder(folder, *, drop_axis_column=False, transpose=False, clip_level=None, workers=1) -> Calibration`:
  - Reads every `*.csv` and `*.asc` file in `folder` (not recursive, hidden files skipped, sorted by name) with `read_frame`, the same options for all. Ids are the file names.
  - `workers > 1` scores the files in a spawn process pool. Each worker reads and scores one path; no generator is involved, so the seed guard is not concerned. The docstring says that a user script calling it with `workers > 1` needs the `if __name__ == "__main__":` guard (N5), and that evaluation must use frames other than the Calibration Set.
  - Raises `ValueError` on: no matching files, a reader error (naming the file), mixed shapes.
- `stored_calibration() -> Calibration`: loads the package file (2.2) once, cached through `functools.cache`, not stored at module level. Otherwise the lockfile would pin every score; 2.2 pins the thresholds instead.
- Import cycle: `analysis` imports `calibration` for the default. `calibration`'s `stripe_free_score` imports `analyse` inside the function. The alternative is to keep `calibrate*` in `calibration.py` and have only the loader and the dataclass in a tiny `_stored.py`; the implementer picks one and states it in the handoff.

### 2.2 The stored calibration (package data, stamped)

- File: `src/denoisifier/stripe_free_calibration.json`. `uv_build` ships non-Python files inside the package directory (N7: the wheel already ships `py.typed`); a fast test loads it through `importlib.resources`.
- Content: `format: 1`, `shape`, `settings` (source `"synthetic"`, mottle, `Emccd` fields, spikes, `modulation_depth: 0`), `run_info` (generator and analysis commit, CPU, versions, loadavg, wall clock), and `frames: [{id, score}]` for all 300 calibration seeds in seed order.
- It stores **every per-seed score, not one threshold**. So any false-alarm rate is an order statistic of the same set (AC 2 at 5%), and check-slow can name the seed whose score changed.
- Protected copy, the same pattern as `GATE_STORED_THRESHOLD`. `tests/protected.py` gets `PACKAGE_STORED_THRESHOLD` (1%) and `PACKAGE_STORED_THRESHOLD_5PCT` (5%). A `make check` test asserts:
  - the file's `threshold(0.01)` and `threshold(0.05)` equal them exactly;
  - `ids == [f"seed:{s}" for s in STRIPE_FREE_CALIBRATION_SEEDS]`;
  - `shape == CALIBRATION_SHAPE`, and the JSON-normalised `settings` equal the driver's JSON-normalised settings. `run_info` is not compared.

  So any edit to the file forces a lockfile edit, which needs an approval.
- Rank sanity test (`make check`), mirroring `test_stored_threshold_rank_is_untied`: at k(1%) = 3 and k(5%) = 15, the k-th largest score is strictly above the (k+1)-th, and it is > 0. P1 measured about 10% exact zeros on 50 full frames, far from both ranks.

### 2.3 `analyse` options

`analyse(frame, *, false_alarm_rate=None, calibration=None, threshold=None, clip_level=None)`.

- `threshold` given: used as is (today's semantics; the sweep and invariant tests keep it). Passing `false_alarm_rate` or `calibration` as well raises `ValueError`.
- Otherwise, resolved with `is None`, never `or` (B2/E3):
  - `cal = stored_calibration() if calibration is None else calibration`;
  - `rate = DEFAULT_FALSE_ALARM_RATE if false_alarm_rate is None else false_alarm_rate`;
  - threshold = `cal.threshold(rate)`. An invalid rate, including `0.0`, gives the `Calibration.threshold` `ValueError`.
- `analysis.THRESHOLD` is **removed** (lockfile line removal, W4). Docstrings and comments citing it are updated: analysis.py:74-82, `_local_stripes.py:39` (and its "profile-only up to ~72" remark at :34-37, which P1 measured at 38.3 max on today's test frames), `borderline.py`, `test_analyse.py`.
- The sweep kind `"THRESHOLD"` in `test_analyse.py` (`SWEEP_THRESHOLDS`, lines 632-700) is **renamed `"default"`** and resolves to `stored_calibration().threshold(DEFAULT_FALSE_ALARM_RATE)`. `tests/test_inner_loop.py:272` (`assert verdict == ["THRESHOLD"]`) changes to `["default"]` (B5, W8).
- No score change: the score path is untouched. That is why `make measure` is skipped, on the conditions in Q8 (section 12).

### 2.4 Report and CLI (Q6)

- **No new Report field.** `Report.threshold` stays "the threshold used" (AC 4); `Report.score` unchanged. `Report.false_alarm_rate` is not added: the spec's Report list does not have it, AC 4 does not need it, and on a frame of another shape it would state a rate that is not the true one (Q9).
- CLI flags:
  - `--false-alarm-rate RATE` (`0` raises the same `ValueError`, reported as a CLI error, B2);
  - `--calibration FILE` (a JSON written by `Calibration.to_json`).
- Recalibration from the shell: `python -m denoisifier.recalibrate FOLDER -o FILE [--drop-axis-column] [--transpose] [--clip-level LEVEL] [--workers N]`. `src/denoisifier/recalibrate.py` is a module **nothing in the package imports** (E4: `python -m denoisifier.calibration` would re-execute an already-imported module and warn). No `pyproject.toml` edit, no console script.
- `cli.py` and `report.py` stay not stamped. `recalibrate.py` is stamped (W5; an addition to `STAMPED_FILES`, so no loosening question arises).

### 2.5 Synthetic calibration driver (`tests/threshold_calibration.py`, new, stamped)

- Settings, all constants or protected numbers:
  - `CALIBRATION_SHAPE = PROBE_SHAPE` (400, 1600) (Q1);
  - scorched Mottle; `Emccd()` (100 photons at the peak, EM gain 300, read noise 50 e, CIC 0.005);
  - `spikes = CALIBRATION_SPIKES` = 30 per frame (Q3; a synthetic assumption, not `SPIKE_TEST_COUNT`: same value, different density);
  - `modulation_depth = 0`; no clip (`clip_level=None` in `generate`), and the analysis auto-detects clips as on real frames.
- `calibrate_synthetic(seeds=STRIPE_FREE_CALIBRATION_SEEDS, shape=CALIBRATION_SHAPE, workers=None) -> Calibration`:
  - **inside `seed_guard.calibrating(seeds)` (W2)**, scores the seeds in the guarded pool;
  - then calls `Calibration.from_scores`, with the ids, shape, settings and run_info above.
  - The tiny-plan test calls it with test seeds and a small shape, outside any calibrating block.
- `evaluate(seeds, *, depth, clip_fraction=None, option_rate=None, calibration=None, workers=None)`: per seed, the default-path `Report`'s `(score, striped, threshold)` from `analyse(frame)`, at the stored calibration and default rate. `calibration` (B6) is passed to `analyse` only when set (and must be picklable for the pool); `held_out_check(plan, calibration=None)` forwards it. The gate passes None, so AC 2a and AC 3 stay on the real default path; only the fast tiny-plan test passes its own tiny calibration. With `option_rate`, the job also runs `analyse(frame, false_alarm_rate=option_rate)` on that seed and returns its `(score, striped, threshold)` (N3; used on a handful of frames only). With `clip_fraction`, the clip level is `clip_fraction × clean.max()` of the same seed: two `generate` calls, same RNG stream, as in `test_analyse.clipped_at`.
- **Plan-taking check functions (B3).** As `feasibility.regression_check(plan)` does, the slow modules' fixture logic lives in functions that take a plan (seeds, shape, workers, depth) and return a result dict:
  - `reproduction_check(plan) -> dict` (AC 7): runs `calibrate_synthetic` on the plan and compares with a given stored `Calibration`;
  - `held_out_check(plan) -> dict` (AC 2a, 2b, 3): the Stripe-free and striped evaluations, counts, per-case results, posterior interval, wall clock.

  The slow modules only build the full plan and assert on the dict. So the gate differs from the fast tiny-plan test only in seed ranges, shape and sizes.
- Pool: refactor `feasibility.score_batch` into a generic guarded runner, `feasibility.run_pool(fn, jobs, workers)`, with the **same spawn context and initializer** (`seed_guard.install_worker`, `worker_allowance()`), so the existing gate frames stay bit-identical (W3). A fast **serial-vs-pool equivalence test** (`test_run_pool_matches_serial_scoring`, C2) runs a small set of test seeds through `run_pool` with 2 workers and through serial `analyse`, and asserts equal per-seed scores, ids and order. It is written before the refactor and stays as a permanent test; it is also primary evidence for Q8.
- `main()` (script): `uv run --locked python tests/threshold_calibration.py --out PATH`, and `--clipped` for step 10. It installs the guard first (W3, a new install) and writes the Calibration JSON with its `run_info`.

### 2.6 Folder input (AC 5)

`calibrate_folder` reads synthetic CSVs (`write_frame_csv`) and Solis-layout exports. The real export `tests/data/solis/xpos_ypos_crop.asc` reads as **64x64** with `drop_axis_column=True` (E2), above `MIN_SIDE` = 40, so it is used as a real frame in the folder test, beside generated 64x64 frames written in the verified real Solis layout (axis column 1..N, a trailing comma on every row, two blank lines, `Key: value` metadata, as `test_read_frame.py` builds). The reader-error case uses `tests/data/solis/kinetic.asc`, which the reader refuses; the error names the file.

### 2.7 Frame size (Q1, Q9)

- Ship **one** calibration, at the full sensor frame of 400x1600. That is what real frames are (spec story 34; Newton 971).
- Frames of another shape get the same threshold, and the docs say so. Wording (Q1): on crops and smaller frames the false-alarm rate is **expected to be lower** than the requested one (smaller light area); this is an expectation, not a guarantee, since a generated 256x256 frame is not a crop of a 400x1600 one. Frames with a larger light area than 400x1600 (for example 640x1024) and binned frames (ticket 08) are **not covered** by the rate claim.
- The `Calibration` format records its shape, and a user can recalibrate on their own frames at their own shape (story 53).
- Not chosen: per-shape tables, or an area-corrected (extreme-value) score.
- Ticket 08 Comments get one line (Q9): decide there whether a shape or binning mismatch with the calibration is noted in the Report.

### 2.8 Comment 1: clipped stripe-free frames (Q5)

**Choice: measure once, at the frozen code, and state the scope.**

- The calibrated 1% is stated, in the `analyse` docstring, ADR 0002 and the ticket Comments, as holding for **unclipped** frames at typical settings.
- One pre-declared, one-off measurement: `CLIPPED_FREE_EVALUATION_SEEDS`, 200 full frames, clipped at `CLIP_LEVEL_FRACTION` (0.4) × each seed's clean max, analysed on the default path.
  - It runs once, **after the code-review fixes** (step 10), at the code that ships, by `threshold_calibration.py --clipped`, and is never tuned on.
  - It reports the count of False Alarms out of 200 and its exact (Clopper-Pearson) 95% interval, into Comments and the docstring. It is **a measurement, not a pass/fail**: clipped frames are not exchangeable with the Calibration Set, so no tolerance applies.
  - Cost about 9-12 min, once.
- If the interval sits clearly above 1%, the docs say clipped frames raise the rate (by the measured amount), and a follow-up issue is filed. No result changes code or checks.

### 2.9 Comment 2: score jumps from hard group gating (Q4)

**Choice: keep the score for this ticket; document the jumps; file a follow-up.**

- The calibration is distributional. The Stripe-free scores include the jumps (the atom at 0, the jumps of 15-39 points), so the order-statistic threshold has its stated rate over frames whatever the score's per-frame continuity. The held-out test (AC 2) measures exactly that.
- What the jumps do break is story 2's reading of the score as "how close a borderline frame was". Two nearly identical frames can sit at 39 and 79 (critic 3, seed 396_698 with another fill); P1 saw one paired frame go from 60.5 to 8.4 between 30 and 293 spikes.
- Record:
  - in the `analyse` docstring and `Report.score`: the score can change in steps under small pixel changes, because a group appears or vanishes at the size and leakage rules;
  - in the `Calibration.threshold` docstring: the 0.0 atom and its tie consequence (2.1);
  - the 06 critic 3 numbers in the ticket Comments;
  - a new `needs-triage` issue, "continuous stripe score", with options: a smooth size and leakage weight on the peak ratio, or the score of the best group before gating.

### 2.10 Domain docs

- **ADR 0002**, "The Threshold is an order statistic of stored per-frame Stripe-free scores at full frame". It covers the sizes, the scope (unclipped, typical settings, 400x1600, expected lower on crops, larger area not covered), `CALIBRATION_SPIKES` = 30 as a stated assumption ("above the expected real rate; chosen so that spike rejection is exercised"), recalibration on real frames, the reproduction gate and where the held-out tests run (Q2). It also notes (N8) that at the new default more groups are reported as Regions, so region outputs at the new default are not the ones ticket 05 evaluated at 154. Its reason: hard to reverse once users hold calibration files, and surprising without the reason.
- GLOSSARY: add **Calibration Set**: "The Stripe-free frames a Threshold is set on; generated or real; never the frames it is evaluated on." _Avoid_: training set, reference frames. The **Threshold** entry adds "at the requested false-alarm rate (default 1%)". The edit goes through the domain-modeling skill.

### 2.11 Held-out tests outside `make check-slow` (owner ruling Q2, 2026-11-14)

The owner ruled "Reproduce only": `make check-slow` runs the regression check and the reproduction (AC 7); the held-out statistical tests (AC 2a, 2b, 3) are marked slow **and** carry their own marker, and run once at this ticket's close and at measure milestones. The Makefile and marker edit is owner-approved (W7; record in the ticket Comments).

- **Marker:** `held_out`, registered in `[tool.pytest.ini_options] markers` as `"held_out: held-out statistical calibration tests (ticket 07); slow too; excluded from make check-slow, run by make check-held-out at a ticket's close and at make measure milestones"` (`strict_markers = true` requires the registration).
- **Modules:** two, so each fixture's cost is paid inside one module's timer:
  - `tests/test_slow_calibration.py`: AC 7 only. `pytestmark = [pytest.mark.slow]`.
  - `tests/test_held_out_calibration.py`: AC 2a, 2b, 3. `pytestmark = [pytest.mark.slow, pytest.mark.held_out]`.
- **Exclusion from `make check` / `make test-fast`:** unchanged `addopts = ["-m", "not slow"]` (and `-m "not slow and not wide"`), because the held-out tests are also `slow`.
- **Exclusion from `make check-slow`:** the recipe becomes `$(UV) python tests/slow_stamp.py run -- $(PYTEST) -m "slow and not held_out"`. The stamp logic is unchanged; the stamp still covers both modules' files (they use `pytest.mark.slow`, so `test_stamped_files_cover_the_slow_tier` demands them in `STAMPED_FILES`).
- **How they run:** a new Makefile target
  ```
  check-held-out: lock-check  ## held-out calibration tests (~19-24 min): ticket 07 close and measure milestones only, background; writes .gate/held-out-calibration.json
  	$(PYTEST) -m held_out
  ```
  (added to `.PHONY`). It does not stamp and does not read the stamp. `check-held-out` is added to `_LONG_TARGETS` in `.claude/hooks/require_background_gate.py` (a tightening; docstring and `tests/test_require_background_gate.py` updated with it), so it cannot run in the foreground.
- **When:**
  - **this ticket's close**: once, in the closing sequence `make check-slow` → `make check-held-out` → `make check` (step 11);
  - **measure milestones** (stripe-detector 13, or any later `make measure`): after `make measure`, the stored gate and probe thresholds, and, when scores moved, the driver re-run and package re-store (O2 procedure), run `make check-slow` → `make check-held-out` → `make check`. It is **not** added to the `measure` recipe: at a milestone where scores move, the held-out run must use the re-stored package calibration, which exists only after the re-store.
- **Not run elsewhere:** no prototype, scratch run, worktree build or code-review fix runs `make check-held-out` or generates its seeds. The fast tiny-plan test (B3) exercises its code on test seeds.
- **Measurement:** the held-out fixture writes `.gate/held-out-calibration.json` (counts, per-case results, Beta(3 + x, 598 - x) posterior interval, wall clock); its numbers go into the closing Comment.
- **CLAUDE.md** (owner text, shown at close with W7): the check-slow duration line, `make check-held-out` in "When" and in the hook's list, and the O2 re-store procedure (draft in 2.12).

### 2.12 Re-store procedure (O2, fold A): draft CLAUDE.md wording, shown to the owner at close

- Gates, after "After `make measure`": "**After a score-moving change** (stripe-detector ticket 07 on): when `make measure` shows the score moved, re-run `uv run --locked python tests/threshold_calibration.py --out src/denoisifier/stripe_free_calibration.json` (background), set `PACKAGE_STORED_THRESHOLD` and `PACKAGE_STORED_THRESHOLD_5PCT` to the file's values (a lockfile edit, needs an approval), then `make check-slow` → `make check-held-out` → `make check`. A re-store is **not** allowed when the change was not meant to move scores: an AC 7 red then is a finding, not a re-store."
- Write targets: add the driver's `--out` write of `src/denoisifier/stripe_free_calibration.json` next to `make measure`'s tracked JSON, as the second writer of source outside `make fix`.

## 3. Acceptance criteria → tests (real code paths)

| AC | Test (file) | Path |
|---|---|---|
| 1. Repeatable routine produces the stored threshold(s) from calibration seeds | fast: `test_calibrate_synthetic_tiny_plan_is_repeatable` (`test_threshold_calibration.py`). Two runs, at test seeds, 1-2 workers and a small shape, give equal `Calibration`s (run_info excluded), the same per-id scores as serial `stripe_free_score`, and `threshold(r)` = k-th largest. fast: `test_run_pool_matches_serial_scoring` (C2). slow: AC 7 row. | `calibrate_synthetic` → `run_pool` → `analyse(threshold=inf)` → `from_scores` |
| 2a. Held-out FA ≈ 1% | slow + held_out `test_held_out_false_alarms_at_the_default_rate` (`test_held_out_calibration.py`): False Alarms counted from `Report.striped` of `analyse(frame)` (default path) on `CALIBRATED_FREE_SEEDS` (300 full frames) are within `false_alarm_tolerance(300, 300, 0.01, CALIBRATION_TOLERANCE_LEVEL)` = (0, 13); also every `report.threshold == PACKAGE_STORED_THRESHOLD`. | default `analyse` → `stored_calibration().threshold(0.01)` |
| 2b. …and at 5% | slow + held_out `test_held_out_false_alarms_at_five_percent`: on the same frames, the count of `score > stored.threshold(0.05)` is within (3, 33). On the first `HELD_OUT_OPTION_FRAMES` (20) of those seeds, the same pool job also runs `analyse(frame, false_alarm_rate=0.05)`; the test asserts its score equals the default-path score, its threshold equals `stored.threshold(0.05)` and its verdict equals the counted one (N3). fast `test_false_alarm_rate_option_sets_the_threshold_and_verdict` (`test_analyse.py`, test seed): `analyse(f, false_alarm_rate=0.05).threshold == stored_calibration().threshold(0.05)`, `striped == (score > threshold)`, score equals the default-path score. | `false_alarm_rate` option |
| 3. m = 0.2 ≥ 90% at the default rate | slow + held_out `test_weak_stripes_detected_at_the_default_rate`: `Report.striped` of `analyse(frame)` on `CALIBRATED_STRIPED_SEEDS` (100 full frames, m = `WEAK_DEPTH`, `CASES[seed % 10]`, 10 per case, spikes as in calibration): detected/100 ≥ `MIN_DETECTION_RATE` (0.90), with a per-case breakdown in the message. The criterion is **pooled, accepted in words**: 90 of 100 passes even with one whole case (10 frames) lost; the per-case breakdown is reported, not asserted. | default `analyse` |
| 4. Report has score and threshold used | fast (`test_analyse.py`, `test_cli.py`): default → `threshold == stored.threshold(0.01)`; option 0.05 → its threshold; `calibration=` a custom one built by `Calibration.from_scores` with **≥ 99 scores** (k ≥ 1 at 1%, C3) → its `threshold(0.01)`; explicit `threshold=` → that value; `false_alarm_rate=0.0` → `ValueError` through `analyse`, and `--false-alarm-rate 0` → CLI error (B2); `threshold=` with `false_alarm_rate=` or `calibration=` → `ValueError`. CLI JSON carries `score` and `threshold` with `--false-alarm-rate` and `--calibration`. `test_report_converts_to_json` is unchanged (no new field). | `analyse`, `Report.to_dict`, `cli.main` |
| 5. Folder of frames | fast (`test_calibration.py`): (a) 12 generated 64x64 frames (test seeds) as CSV → `calibrate_folder` equals `calibrate` on the same arrays (ids are the file names, sorted); `threshold(0.1)` (k = 1) is the max. (b) 11 generated 64x64 frames in real Solis layout `.asc` plus the real `xpos_ypos_crop.asc` (64x64), `drop_axis_column=True` → equals `calibrate` on the arrays as read (E2). (c) `workers=2` → same result. (d) errors: empty folder, mixed shapes, `kinetic.asc` (reader refuses, naming the file). (e) round trip of the 12-frame calibration: `to_json` → `from_json` → `analyse(f, calibration=c, false_alarm_rate=0.1)` uses `c.threshold(0.1)`; `analyse(f, calibration=c)` at the default 1% raises the "too few scores" `ValueError` (C3). (f) `python -m denoisifier.recalibrate FOLDER -o FILE` writes the same JSON (run_info excluded). | `calibrate_folder` → `read_frame` → `stripe_free_score` |
| 6. Statistical tests marked slow | `test_slow_calibration.py`: `pytestmark = [pytest.mark.slow]`; `test_held_out_calibration.py`: `pytestmark = [pytest.mark.slow, pytest.mark.held_out]`; per-test `pytest.mark.timeout(2400)` (W6). `addopts -m "not slow"` keeps both out of `make check` and `make test-fast`; `-m "slow and not held_out"` keeps the held-out module out of `make check-slow` (2.11). fast `test_statistical_calibration_tests_are_slow` (`test_threshold_calibration.py`) collects both modules and asserts every item has `slow`, every held-out item has `held_out`, and the reproduction item does not. | markers |
| 7. check-slow reproduces the stored threshold(s) | slow `test_calibration_reproduces_the_stored_thresholds` (`test_slow_calibration.py`): the module fixture runs `reproduction_check` on the full plan (`STRIPE_FREE_CALIBRATION_SEEDS`, `CALIBRATION_SHAPE`). It asserts ids, shape and JSON-normalised `settings` equal the stored file (`run_info` not compared, B1); every per-seed score equal (exact, Q7); `threshold(0.01) == PACKAGE_STORED_THRESHOLD` and `threshold(0.05) == PACKAGE_STORED_THRESHOLD_5PCT`. On a mismatch the message reports the number of differing seeds, the first few seeds, and the largest relative difference (Q7: tiny everywhere = platform; tens of points = detector), and says: follow the re-store procedure only when the change was meant to move scores (2.12), never edit the check. | the routine itself |

Fast `make check` tests on the stored data (no analysis):
- `test_stored_calibration_is_the_protected_one`: section 2.2.
- `test_stored_threshold_ranks_are_untied_and_positive`.
- `test_calibration_plan_meets_its_false_red_budget`: from the protected sizes and level it recomputes the AC 2a and AC 2b false-red terms (section 5); their sum is ≤ `CALIBRATION_MAX_FALSE_RED`; the 5% lower bound is ≥ 1. It encodes **no AC 3 term** (C1) and none of the corrected power figures' old values (E6).
- `test_stored_calibration_ships_with_the_package`: `importlib.resources`.

Fast tiny-plan test of the slow assertions (B3): `test_slow_calibration_checks_run_on_a_tiny_plan` (`test_threshold_calibration.py`) runs `reproduction_check` and `held_out_check` on `TEST_SEED_BLOCK` seeds (protected `CALIBRATION_TINY_*_TEST_SEEDS`) at a small shape, against a tiny calibration made in the test and passed through `calibration=` (B6), and runs every slow assertion's code (count, tolerance, per-case breakdown, option-path comparison, mismatch message, JSON write to a tmp path). Only seeds, shape and sizes differ at the gate.

Unit tests (`test_calibration.py`, extended):
- `Calibration.threshold` for 1% and 5% at n = 300 (k = 3, 15);
- the rate-validation messages (0, 1, too small, too high);
- tie behaviour (realised rate ≤ requested), including a 0.0 atom;
- `from_scores` refuses non-finite scores;
- JSON round trip, including that `run_info` survives and is not part of equality checks' compared keys.

Seed-parametrised fast tests use `inner_loop.inner(...)` (agent-gates/07).

## 4. Seeds and their separation

New module-level ranges in `tests/protected.py`, disjoint from every existing range (checked by `test_seed_sets_are_disjoint_and_unused`; nothing is in use between 95_300 and 300_001):

| Name | Range | Use |
|---|---|---|
| `STRIPE_FREE_CALIBRATION_SEEDS` | `range(100_000, 100_300)` | the Calibration Set; **registered in `CALIBRATION_SEEDS` (W1)**; generated only inside `calibrating(...)` in `calibrate_synthetic` (W2) |
| `CALIBRATED_FREE_SEEDS` | `range(101_000, 101_300)` | AC 2 held-out, Stripe-free |
| `CALIBRATED_STRIPED_SEEDS` | `range(102_000, 102_100)` | AC 3 held-out, m = 0.2, 10 per case |
| `CLIPPED_FREE_EVALUATION_SEEDS` | `range(103_000, 103_200)` | one-off clipped measurement (2.8) |
| (USED_SEEDS) | `range(104_000, 104_100)` | scratch range; P1 used 104_000-104_049 and the review's N6 timing used 104_000. Anything else looked at is reserved before it is looked at |

`THRESHOLD_CALIBRATION_SEEDS` (100-199) **stays registered** in `CALIBRATION_SEEDS` when `analysis.THRESHOLD` is removed: removing a registered range is a weakening move, and those seeds stay spent.

How the separation holds:
- **Runtime.** The guard raises on any `STRIPE_FREE_CALIBRATION_SEEDS` seed outside the one calibrating block. The held-out tests and the clipped driver run with no block, so a calibration seed there is a `SeedGuardError`.
- **Structure.** The disjointness test fails on any overlap.
- **Hygiene** (05 "Evaluation hygiene"):
  - The held-out ranges are predeclared here and looked at only by the closing `make check-held-out` (2.11).
  - The clipped range is looked at once, by step 10.
  - No prototype or scratch run touches them.
  - The tiny-plan and fast tests use `TEST_SEED_BLOCK` seeds only.
  - The calibration run (step 5) generates only calibration seeds.
- **Real frames.** Separation is the user's job; the `calibrate_folder` docstring says to evaluate on other frames.

## 5. Statistics: tolerances and sample sizes

The held-out count of an order-statistic threshold is `betabinom(N, k, n + 1 - k)` for **any** detector whose calibration and held-out scores are exchangeable (`_calibration.false_alarm_tolerance`; the same fact that drove 05's operating-rule fix). So AC 2 tests **the calibration routine**, not detector quality: it tests the rate→rank mapping, that the default path uses the stored file at the right rate, and that the Calibration Set matches the held-out settings. AC 3 carries the detector's teeth.

Sizes (Q2, kept by the owner): n = 300 calibration, N = 300 held-out Stripe-free, N = 100 striped; all 400x1600.

| Quantity | 1% | 5% |
|---|---|---|
| k = floor(r·301) | 3 | 15 |
| true rate of the stored threshold, Beta(k, 301 - k), central 95% | 0.21%-2.39% | 2.83%-7.71% |
| held-out tolerance at level 0.995, betabinom(300, k, 301 - k) | **0-13 of 300** | **3-33 of 300** |
| false-red probability of that assertion | 0.19% | 0.29% |
| P(pass) if the true rate were … | 3%: 93%; 4%: 68%; 5%: 36% | 10%: 75%; 12%: 34%; 14%: 7.5%; 15%: 2.8% |

(5% column corrected per N1/E6.)

- Level: `CALIBRATION_TOLERANCE_LEVEL = 0.995` per assertion. `CALIBRATION_MAX_FALSE_RED = 0.01` bounds the union of the two **AC 2** assertions (Bonferroni): 0.19% + 0.29% ≈ 0.48%. Reproduction (AC 7) is deterministic: 0.
- **AC 3 is outside that bound (C1).** Its false-red probability depends on the true detection rate of spiked full frames at the new threshold, and no baseline for that population and threshold exists: the probe's 100/100 (lower 95% end 0.964) was spike-free at 85.17. Conditional figures only: false red 1.15% at a true 0.95, 0.10% at 0.964, 0.02% at 0.97; pass-bad 9.9% at 0.85, 0.57% at 0.80. No combined false-red figure for the held-out run is claimed. The 90/100 rule is pre-declared and not tuned after the look.
- Overall bounds by gate, after Q2: **`make check-slow`** keeps the regression check's 1% (reproduction adds 0); the critic's "check-slow becomes 2%" no longer applies because the held-out tests left check-slow. **`make check-held-out`**: AC 2 ≈ 0.48% plus AC 3's conditional term.
- At the existing convention (level 0.95) the two AC 2 assertions alone would be red about 1.8% + 3.7% of the time per detector change, with fixed seeds.
- Teeth of 2b: a request for 5% that silently got the 1% threshold gives a count ≥ 3 with probability about 50%, a coin flip, so 2b gives no protection there. A "got 10% instead of 5%" bug passes 2b 75% of the time. Both are caught by the fast `false_alarm_rate` option test, the N3 option-path frames and the unit test of k, not by 2b. A wrong rank (rounding, descending vs ascending) is caught by the unit tests.
- Weak point, stated: at k = 3 the shipped "1%" threshold is only known to be 0.2-2.4% (95%), and the smallest requestable rate is 1/301 = 0.33%. The held-out count narrows it: Beta(3 + x, 598 - x) is reported in `.gate/held-out-calibration.json` and the closing Comment. Halving that width needs n ≈ 1000 (Beta(10, 991): 0.48%-1.70%), which would add about 46-58 min to every check-slow for the reproduction alone; not worth it for a synthetic calibration that real frames are meant to replace.
- One-off clipped (2.8): N = 200, reported as a count with its Clopper-Pearson interval, not against a tolerance.

## 6. Runtime

At 2.75-3.5 s of pool wall clock per full frame (section 1), idle:

| Part | Frames (400x1600) | Minutes, idle |
|---|---|---|
| Reproduction (AC 7), in `make check-slow` | 300 | 14-18 |
| Existing regression check, in `make check-slow` | | 5-6 |
| **`make check-slow` total** | | **~20-24 min** (today about 6) |
| Held-out Stripe-free (AC 2a, 2b; one analysis each, plus 20 option-path analyses) | 300 (+20) | 15-19 |
| Held-out striped (AC 3) | 100 | 5-6 |
| **`make check-held-out` total** (this ticket's close, measure milestones) | 400 | **~19-24 min** |
| One-off: calibration run (step 5) | 300 | 14-18, once |
| One-off: clipped measurement (step 10) | 200 | 9-12, once |

- Timeouts (E1, W6): three module-scoped fixtures (reproduction; held-out Stripe-free; held-out striped), each paid by the first test that uses it, so each test's timer covers at most about 320 frames. Each test in both modules carries `pytest.mark.timeout(2400)`: about twice the 18-19 min upper estimate, so a machine at twice the idle time (CLAUDE.md: another project's load can double gate times) stays under it. As in `test_slow_regression.py`, the timer covers the fixture setup of the first test.
- Each pool session is one spawn per set (a few seconds each).
- Fast tier: new tests analyse about 30 small frames (64x64 to 128x128) plus the tiny plans; well under 10 s added to `make test-fast` (190 s at BASE). The stored-file tests do no analysis.
- Step 5 measures the real per-frame rate (300 full frames in the same pool). The closing `make check-slow` and `make check-held-out` wall clocks replace these estimates.
- Docs to update afterwards (W7):
  - `test_slow_regression.py` module docstring, CLAUDE.md's named duration source: "about 20-24 min idle with `test_slow_calibration.py`" (the measured closing wall clock); it names `test_held_out_calibration.py` and `make check-held-out` as separate. One source for the duration.
  - Makefile `check-slow` help text "~6 min" → the measured value; the new `check-held-out` help text; the hook docstring's "about 6 min"; CLAUDE.md's "about 6 min" (owner text).

## 7. Protected numbers (lockfile)

Additions, approved by the orchestrator as lockfile additions:
- `denoisifier.calibration :: DEFAULT_FALSE_ALARM_RATE :: 0.01`.
- `protected`:
  - `STRIPE_FREE_CALIBRATION_SEEDS`, `CALIBRATED_FREE_SEEDS`, `CALIBRATED_STRIPED_SEEDS`, `CLIPPED_FREE_EVALUATION_SEEDS`, the new `USED_SEEDS` entry;
  - `CALIBRATION_SHAPE = PROBE_SHAPE`;
  - `CALIBRATION_SPIKES = 30` (Q3);
  - `OTHER_FALSE_ALARM_RATE = 0.05`;
  - `CALIBRATION_TOLERANCE_LEVEL = 0.995`;
  - `CALIBRATION_MAX_FALSE_RED = 0.01`;
  - `HELD_OUT_OPTION_FRAMES = 20` (N3);
  - `CALIBRATION_TIMEOUT_S = 2400` if the mark reads a constant (else the literal in the mark, still W6);
  - `PACKAGE_STORED_THRESHOLD`, `PACKAGE_STORED_THRESHOLD_5PCT`, both set from the step 5 run;
  - the updated `CALIBRATION_SEEDS` dict (`THRESHOLD_CALIBRATION_SEEDS` kept);
  - the folder-test, tiny-plan and serial-vs-pool test seeds (`CALIBRATION_TINY_*_TEST_SEEDS` and the like, from `TEST_SEED_BLOCK`).
- No `REPRODUCTION_REL_TOL` (Q7: exact).

Removals or changes:
- `denoisifier.analysis :: THRESHOLD` (removed).
- `BORDERLINE_TEST_CASES` (re-picked, step 6).

Both are W4.

## 8. Weakening moves and approvals (all asked before the change, recorded with reason in the ticket Comments)

| ID | Move | Why it is needed | Who |
|---|---|---|---|
| W1 | Add `STRIPE_FREE_CALIBRATION_SEEDS` to the `CALIBRATION_SEEDS` registry (keep `THRESHOLD_CALIBRATION_SEEDS`) | new calibration range must be guarded | orchestrator (registry edit) |
| W2 | New `seed_guard.calibrating(seeds)` block in `threshold_calibration.calibrate_synthetic` | the one place the Calibration Set is generated | orchestrator |
| W3 | Refactor of `feasibility.score_batch`'s pool into `run_pool` (same initializer); new `seed_guard.install()` in `threshold_calibration.main()` | share the guarded pool; guard the script | orchestrator |
| W4 | Lockfile: additions (section 7); remove `analysis.THRESHOLD`; set `PACKAGE_STORED_THRESHOLD*` from the run; re-pick `BORDERLINE_TEST_CASES` by a mechanical rule (lowest unused test seed per entry, from 10 up, scoring in (T, 1.5 T) at the new T, as ruling O3 did; it must replace `[22-20]` too, which P1 found outside the window for every T ≤ 141); if `test_cli_reports_borderline_frame` uses the first entry, it follows the re-pick | the provisional threshold is replaced; borderline frames are defined relative to T | orchestrator; the re-pick rule is fixed here, before any analysis at the new T |
| W5 | Edit `tests/slow_stamp.py`: add `src/denoisifier/calibration.py`, `src/denoisifier/recalibrate.py`, `src/denoisifier/stripe_free_calibration.json`, `tests/test_slow_calibration.py`, `tests/test_held_out_calibration.py`, `tests/threshold_calibration.py` to `STAMPED_FILES` (only additions; nothing moved to `NOT_STAMPED_SRC`) | the stamp must cover the new detector-output and slow-tier files | orchestrator |
| W6 | `pytest.mark.timeout(2400)` on each test of `test_slow_calibration.py` and `test_held_out_calibration.py` | module fixtures of up to about 320 full frames | orchestrator |
| W7 | **Q2 gate-config edit, owner-approved 2026-11-14** ("Reproduce only"): Makefile `check-slow` recipe → `-m "slow and not held_out"` and its help text duration; new `check-held-out` target (+ `.PHONY`, help text); `pyproject.toml` `[tool.pytest.ini_options] markers` gains `held_out`; `.claude/hooks/require_background_gate.py` `_LONG_TARGETS` gains `check-held-out` (tightening) with its docstring and `tests/test_require_background_gate.py`; CLAUDE.md duration line, `make check-held-out` and the 2.12 re-store wording | owner ruling Q2: held-out tests leave check-slow, run at the close and at measure milestones; stale durations mislead gate planning | **owner, approved 2026-11-14** (Makefile/marker edit); CLAUDE.md wording shown to the owner at close |
| W8 | Sweep kind `"THRESHOLD"` → `"default"` in `test_analyse.py`, and the expected value at `tests/test_inner_loop.py:272` (`["THRESHOLD"]` → `["default"]`) | the constant it names is removed | orchestrator (expected value change by rename) |
| W9 | Writing the package data file from a script (`--out src/denoisifier/stripe_free_calibration.json`): a source write outside `make fix` | the stored threshold is produced by the routine | orchestrator, once at step 5 |
| W10 | B4 rule 2: a named property test (spike or clip pairing, two-region, minimum size, on a small frame) passes `threshold=GATE_STORED_THRESHOLD` explicitly | only if a flip appears on such a test | orchestrator, **only on a list approved before step 5**; P1 predicts the list is empty |

### 8.1 Orchestrator approvals, 2026-11-14 (from codex `07-codex-approvals.md` + orchestrator reading; binding; record verbatim in ticket Comments at step 0)

- **W1, W5, W8: approved.**
- **W2: approved with condition.** Split the driver: a core `calibration_from_seeds(seeds, shape, ...)` with **no** guard block, and `calibrate_synthetic()` = `with seed_guard.calibrating(STRIPE_FREE_CALIBRATION_SEEDS): calibration_from_seeds(STRIPE_FREE_CALIBRATION_SEEDS, CALIBRATION_SHAPE, ...)`. The block covers generation and scoring of the Calibration Set only and closes before any evaluation. The tiny-plan and reproduction-on-test-seeds tests call the core with test seeds (outside any block). The guard itself is not loosened; `calibrating()` still accepts only registered ranges.
- **W3: approved with condition.** Keep spawn context, initializer, allowance snapshot, result order and exception propagation. `test_run_pool_matches_serial_scoring` and the existing guard-negative tests (`test_seed_guard.py`, `test_feasibility_gate.py`) stay green **unchanged**.
- **W4: approved as amended.**
  - (a) Fixed additions, `THRESHOLD` removal and the stored values derived solely from the step-5 run.
  - (b) **Complete-payload protection:** `tests/protected.py` gains `PACKAGE_CALIBRATION_DIGEST`, the SHA-256 of the canonical JSON (`sort_keys=True, separators=(",", ":")`, floats via `repr`) of `{ids, scores, shape, settings}` (no `run_info`). A `make check` test asserts the shipped file matches it, plus a unit test that changing any one score (not just ranks 3/15) fails it. So any change to the stored data needs a lockfile approval.
  - (c) **Borderline re-pick rule, frozen now:** for each `BORDERLINE_TEST_CASES` entry in its current order, keep its Period and `borderline_frame`'s settings. If its current seed satisfies the existing predicate `T < score < BORDERLINE_SCORE_WINDOW * T` at the new stored T, keep it. Otherwise scan seeds 10..99 ascending and take the first that satisfies the predicate at that Period and is not already chosen for another entry of the same Period. The predicate is the only criterion. Exhaustion or an analysis error stops the step and goes to the orchestrator. A later failure of any other assertion on a picked frame stays red, never a re-pick. The full scan table goes in Comments.
  - (d) No permission to refresh expectations after a red check.
- **W6: approved with condition.** `timeout(2400)` only on the tests that consume the new heavy fixtures; existing timeouts untouched.
- **W7:** owner approval stands for the Makefile, marker, target and hook edits. **2.12 (standing re-store/source-write policy and its CLAUDE.md wording): approved by the orchestrator**, keeping its rule that an unexpected score change is a finding, never a re-store. The CLAUDE.md text is still shown to the owner at close.
- **W9: approved with condition.** One initial write at step 5 from the frozen settings and seeds, under W4(b). No rewrite during any check, and no standing permission to overwrite a failed reproduction baseline.
- **W10: approved as an explicitly empty list.** Any explicit-threshold override found later needs a new named approval.
- **W11 (new): inner-loop `wide` marks on new parameter sets.** Seed-parametrised **new** fast tests may use `inner_loop.inner()` (wide after the first `INNER_LOOP_SEED_COUNT` seeds) with `INNER_LOOP_SEED_COUNT` unchanged, every test case still covered in the inner loop, and full `make check` selection. Never applied to an existing parameter or to silence a failure.
- **Section 7:** approved as listed, plus `PACKAGE_CALIBRATION_DIGEST`. Exact tiny, folder and pool test-seed allocations are fixed at step 0, before use.

Apart from W7 (owner-approved), no pass count, tolerance of an existing test, marker selection, `addopts`, regression seed, or stored gate or probe threshold is changed.

## 9. Steps (test-first)

0. **Approvals and seeds.** The orchestrator approves W1-W6 and W8-W10 (W10's list, expected empty) and records them, with the owner's W7 approval of 2026-11-14, in the ticket Comments. Save a copy of the pre-ticket `.gate/check-slow-measurement.json` (from `3f09325`'s green check-slow) as `.scratch/stripe-detector/handoffs/07-pre-ticket-check-slow-measurement.json` before any run overwrites it (Q8 supporting evidence). Add the seed ranges, registry entry and lockfile lines (section 7, without the two stored thresholds). Then `make test-fast` and commit. No analysis yet.
1. **`Calibration` core.** Write the unit tests first (section 3, unit list), red; then the dataclass (with `settings`/`run_info` split), `threshold`, JSON and validation; green. Add `calibration.py` to `STAMPED_FILES` now (W5), or `test_stamped_files_cover_the_slow_tier` goes red.
2. **`stripe_free_score`, `calibrate`, `calibrate_folder`, `python -m denoisifier.recalibrate`.** Write the AC 5 tests (a)-(f) first; then the code. Add `recalibrate.py` to `STAMPED_FILES`.
3. **`analyse` options with an injected calibration.** Tests first: `calibration=` (≥ 99 scores), `false_alarm_rate=` with `calibration=`, `false_alarm_rate=0.0` raises, mutual-exclusion errors, `threshold=` unchanged. Resolution with `is None`. The default path still uses `THRESHOLD` until step 6, so the fast tier stays green.
4. **Driver, pool, slow modules, Q2 gate edit.**
   - Write `test_run_pool_matches_serial_scoring` first (green against today's `score_batch` path), then do the `run_pool` refactor; it must stay green. `test_seed_guard` and `test_feasibility_gate` stay green.
   - Write `test_threshold_calibration.py` first: tiny plan repeatable; equals serial; slow tiny-plan test of `reproduction_check` and `held_out_check` (B3); marker check (AC 6); budget test. Then `tests/threshold_calibration.py`.
   - Write `test_slow_calibration.py` (AC 7) and `test_held_out_calibration.py` (AC 2a, 2b, 3). **Do not run them.**
   - Apply W7's Makefile, marker and hook edits (2.11), with the hook test.
5. **The calibration run** (background, idle machine, about 14-18 min): `uv run --locked python tests/threshold_calibration.py --out src/denoisifier/stripe_free_calibration.json > <log> 2>&1; echo "EXIT=$?" >> <log>`.
   - Apply the step-5 rules of section 13 (ties, early warning, profile-only floor) before going on.
   - Set `PACKAGE_STORED_THRESHOLD` and `PACKAGE_STORED_THRESHOLD_5PCT` from the file (W4).
   - Add the stored-file `make check` tests (2.2) and add the JSON to `STAMPED_FILES`.
   - Record k, both thresholds, the share of zero scores, the measured per-frame wall clock and the run info in Comments. Commit.
   - **The score path is frozen from here** (N4): any later edit to `analysis.py`, `_local_stripes.py`, `_data_quality.py`, `synthetic.py` or the driver's generation settings forces a re-run of step 5 and a new lockfile approval.
6. **Switch the default.**
   - Tests first: AC 4 default-path tests and the `false_alarm_rate` option test.
   - Then remove `THRESHOLD` and wire `stored_calibration()`.
   - Rename the sweep kind (W8), update docstrings and comments (2.3).
   - Re-pick `BORDERLINE_TEST_CASES` by the W4 rule.
   - Apply the B4 rule (section 13) to any flip.
   - `make test-fast`, then `make check` (expected: only the stamp step is red, stale).
7. **CLI flags** (Q6): tests first. No Report field.
8. **Docs.**
   - ADR 0002 and the GLOSSARY entries (domain-modeling skill).
   - `analyse` / `Report.score` docstrings: scope (unclipped, typical, 400x1600, expected lower on crops, larger area and binning not covered) and the step note (2.9); `Calibration.threshold` 0.0-atom note; `calibrate_folder` `__main__` guard note.
   - The slow-module duration docstring (section 6), with the measured step-5 rate until the closing run's wall clock replaces it. `test_held_out_calibration.py`'s docstring says it is stamped but not run by `make check-slow`, so a green check-slow does not cover it (N9).
   - A follow-up issue "continuous stripe score" (`needs-triage`).
   - Ticket 08 Comments: the Q9 line (2.7).
   - The CLAUDE.md draft (2.11, 2.12) for the owner; the implementer does not edit CLAUDE.md before the owner sees the wording.
9. **Code review, then its fixes.** The review checks that the score path is unchanged since step 5 (N4) and that Q8's diff condition holds.
10. **One-off clipped measurement** at the frozen code (background, about 9-12 min, once): `threshold_calibration.py --clipped`. Record the count and its Clopper-Pearson interval in Comments and the docstring per 2.8. No code or check changes follow from it.
11. **Closing gates** (CLAUDE.md, run once each, background, idle machine, one at a time):
    - `make measure`: **not run**, on Q8's conditions (section 12). Quote in the handoff: the diff of `analysis.py`, `_local_stripes.py`, `_data_quality.py`, `synthetic.py` against `fd59d0c` (touches only the threshold's source), and `test_run_pool_matches_serial_scoring` green.
    - `make check-slow` (~20-24 min). Afterwards compare its `.gate/check-slow-measurement.json` with the saved pre-ticket copy (`free.max_score` = 101.51738269624258 and the per-case `min_score` values): equality is supporting evidence for Q8 only.
    - `make check-held-out` (~19-24 min), **once** (2.11). A red is handled by section 13, rule 1.
    - `make check`.
    - Quote each: the command, its exit status, pytest's summary line, `git rev-parse --short HEAD` (+`-dirty`).

## 10. Gates

- The inner loop: `make test-fast` after every change.
- Heavy jobs, in the background with a log and `EXIT=`, on an idle machine (`uptime`), one at a time:
  - step 5, the calibration run;
  - step 10, the clipped measurement;
  - the closing `make check-slow`, then `make check-held-out`.
- The stamp is per worktree: a worktree build of this ticket needs its own `make check-slow` (~20-24 min) before `make check` is green. `make check-held-out` runs only in the tree that closes the ticket.

## 11. Risks

- **Fast-tier flips at the lower default T.** P1 measured them for any default T in [70, 110]: only the five `BORDERLINE_TEST_CASES` (W4 re-pick) and the `THRESHOLD` lockfile line go red. The highest stripe-free test score is 53.3 (clipped), profile-only 38.3. Three frames flip verdict with no test asserting on them (pass-mark seed 90 at 149.7, tiny-plan seeds 60 at 84.9 and 61 at 132.5). Outside [70, 110] the step-5 rules apply.
- **Ties at rank 3 or 15** (atom at 0.0 or equal maxima). P1: about 10% zeros, far from both ranks. Caught at step 5.
- **The full-frame calibration differs from 85.17**, by sampling noise (k = 3 of 300 on new seeds; the 256x256 tail is heavy) and slightly by spikes. P1's 50 spiked frames put the top scores at 69.6-78.2, so T is likely about 75-90. Whatever it is, the stored value is what the run gives; it is not tuned.
- **A cross-machine float difference** turns the reproduction red on another machine (Q7); the message tells a platform difference from a detector change.
- **AC 2 has weak power against 2-4% true rates** at n = 300 (section 5). Stated in the ADR and Comments.
- **AC 3 has no justified baseline** for spiked full frames at the new T (C1); a red there is a finding (section 13).
- **check-slow grows from about 6 to about 20-24 min**, and `make check-held-out` adds about 19-24 min at the close and at measure milestones (owner-accepted, Q2).

## 12. Rulings

| Q | Settled answer | Reason |
|---|---|---|
| Q1 shape | 400x1600 only, used for every shape; docs say "expected lower on crops" (not a guarantee); larger light area and binning not covered | real frames are full frames, and it is the only option whose rate claim is checked on the shape users run |
| Q2 sizes and placement | **Owner, 2026-11-14: "Reproduce only".** Sizes 300/300/100 kept; `make check-slow` runs regression + reproduction (`-m "slow and not held_out"`, ~20-24 min); held-out tests are `slow` + `held_out`, run by `make check-held-out` once at this ticket's close and at measure milestones; Makefile/marker edit owner-approved (W7, 2.11) | reproduction already pins the stripe-free scores exactly; recurring held-out runs on fixed seeds add little for ~20 min per check-slow, and it keeps closer to agent-gates/05's small check-slow |
| Q3 spikes | `CALIBRATION_SPIKES` = 30 per frame, an ADR assumption; fixed before P1's results, not tuned on them; the owner is told at close | exercises spike rejection on every frame; P1 shows the count barely moves the upper tail; real-frame recalibration replaces it |
| Q4 gating jumps | keep the score; document the jumps and the 0.0-atom tie; `needs-triage` follow-up "continuous stripe score" | the order-statistic rate holds for any score distribution; a continuous score is a detector change for its own ticket |
| Q5 clipped frames | one-off measurement on 200 clipped full frames at the frozen code after review fixes; count + Clopper-Pearson CI, not pass/fail; 1% stated for unclipped frames | answers the 2026-11-13 Comment; clipped frames are not exchangeable, so no tolerance is valid |
| Q6 API | `analyse(false_alarm_rate=, calibration=, threshold=)`, CLI `--false-alarm-rate` and `--calibration`, `python -m denoisifier.recalibrate` (a module nothing imports; no pyproject edit); **no** `Report.false_alarm_rate` | the spec and stories 4 and 53 need these paths; the Report field is unneeded and misleading on other shapes; E4 forbids `-m` on an imported module |
| Q7 exactness | exact equality of per-seed scores and thresholds; failure message reports the number of differing seeds and the largest relative difference | same lockfile-pinned toolchain on one machine; a tolerance cannot absorb a gating flip anyway |
| Q8 measure at close | skip `make measure` when (1) **primary**: the diff of `analysis.py`, `_local_stripes.py`, `_data_quality.py`, `synthetic.py` against `fd59d0c` touches only the threshold's source, and (2) **primary**: `test_run_pool_matches_serial_scoring` (per-seed scores, ids, order) is green after the refactor; equality of the closing `.gate/check-slow-measurement.json` with the saved pre-ticket copy is supporting evidence only (C2). If (1) or (2) fails, `make measure` runs. Recorded in Comments | follows CLAUDE.md's "only when the detector changed since the last measure"; the saved summary drops per-seed scores, so it cannot prove equality alone |
| Q9 other shapes | same threshold for every shape, scope documented; one line in ticket 08's Comments | a Report note now would be designed twice; binning is ticket 08's ground |

Review items, where folded: B1 → 2.1, 2.2, AC 7; B2/E3 → 2.3, AC 4; B3/E5 → 2.5, section 3 tiny-plan test, section 13; B4 (+ codex refinement, P1) → W10, section 13; B5 → 2.3, W8; C1 → section 5; C2 → 2.5, Q8; C3 → AC 4, AC 5; E1 → sections 1, 6, W6; E2 → 2.6, AC 5; E4 → 2.4; E6/N1 → section 5; N2 → section 1; N3 → 2.5, AC 2b; N4 → step 5; N5 → 2.1; N6/N7 → sections 4, 2.2; N8 → 2.10; O1 → Q8; O2 → 2.12; critic smaller points → section 4 (registry), section 5 (bounds), AC 3 (pooled).

## 13. Pre-declared rules

Fixed now, before any calibration or held-out seed is looked at; approved by the orchestrator and recorded in the ticket Comments before step 5.

1. **Red held-out at the closing run.** A red AC 2a, 2b or 3 at the closing `make check-held-out` (or a red AC 7 at the closing `make check-slow`) stops the ticket and goes to the orchestrator as a finding. No re-seeding, no change of n, N, the spike count, the tolerance level or `MIN_DETECTION_RATE`, and no second look at the held-out ranges to "confirm".
2. **Step-5 early warning.** After the calibration run: if either rank is tied or its score is ≤ 0, stop and report. If `PACKAGE_STORED_THRESHOLD` lands near or above about 110 (the probe's weakest case, period 3, has its lowest m = 0.2 score at 116.1, `feasibility-gate.json`), report to the orchestrator before going on. If it lands at or below the highest profile-only test score (38.3, P1), that is a real false verdict on a clean frame (profile-only frames are not in the Calibration Set's population): stop and report.
3. **B4 flip rule** (critic's three points, codex refinement). At step 6: (a) a test whose subject is the default verdict keeps the default; a flip there is a finding for the orchestrator, not a seed move or an explicit threshold. (b) A test of another property on a small frame (spike or clip pairing, two-region, minimum size) may take `threshold=GATE_STORED_THRESHOLD` explicitly only if it is on the list approved before step 5 (W10), and its comment must not describe that value as calibrated for any shape but 256x256; default-verdict coverage of the same frames is kept elsewhere. (c) Profile-only frames carry no rate claim; a flip there is rule 2's stop. P1 predicts that only the W4 borderline re-pick applies; any other flip is a finding, never a silent fix.
4. **Score path frozen from step 5.** No edit to the score path (`analysis.py`, `_local_stripes.py`, `_data_quality.py`, `synthetic.py`, the driver's generation settings) after step 5 without re-running step 5 and a new lockfile approval; the code review checks it.
5. **Q8 skip conditions (C2).** `make measure` is skipped only if both primary conditions in Q8 hold (diff review limited to the threshold source; serial-vs-pool equivalence of per-seed scores, ids and order green). Summary equality with the saved pre-ticket check-slow measurement is supporting evidence; if it differs while both primary conditions hold, that is a finding for the orchestrator before `make check`.
