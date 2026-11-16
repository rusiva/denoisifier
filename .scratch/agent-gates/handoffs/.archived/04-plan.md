# 04 plan: runtime seed guard

- Ticket: `.scratch/agent-gates/issues/04-runtime-seed-guard.md`
- Spec: `.scratch/agent-gates/spec.md`
- BASE: `43d0897`
- Review: `.scratch/agent-gates/handoffs/04-plan-review.md`. This plan folds in O1, O2 and N1-N7. Codex's opinion (session scratchpad `04-codex.md`) is folded in too.
- Status: **settled.** The owner has ruled (see below). Nothing is open. Every step that edits a protected surface is marked **[APPROVED]**, with the ruling that covers it.

## Owner rulings (2026-11-11)

These are recorded in the ticket's `## Comments` (O1, Q2, Q5). The coordinator ruled Q1, Q3 and Q4 on the plan's recommendations.

- **Q1, the seam:** an audit event in `generate`, plus explicit guard installation in spawned workers.
- **Q2 (owner):** split `USED_SEEDS` into 0-9 (`_A0` calibration), 10-99 (tests) and 100-199 (`THRESHOLD` calibration). Their union stays 0-199, and the disjointness check stays unconditional.
- **Q3, the marker:** it lives in `tests/seed_guard.py`. When ticket 07 comes, it wraps its calibration call at the driver.
- **Q4, the script:** guard `feasibility.main()`, workers included, and prove it with a standalone-process negative test.
- **Q5 (owner):** the edits to `tests/conftest.py`, `tests/protected.py`, `tests/protected_numbers.lock` and CLAUDE.md listed here are approved as one bundle. The bundle includes the seed entries that O1 and Q2 require. It covers **no** tolerance or expected-value change.
- **O1 (owner):** register `range(0, 10)` as `_A0` calibration data. Every test the guard catches is re-seeded onto unused seeds in the test range. The new seeds are pinned in `protected.py` and the lockfile, and the affected test IDs are listed in Comments. If a re-seeded test's assertion fails, that is a **finding**: record it and stop for the owner. Do not change any tolerance or expected value.
- **Codex's holes:** the claimed guarantee covers seeds passed to `generate`, and no more. Two known limits are documented here and in a ticket Comment (see "Guarantee and known limits").

## Findings that shape the plan

These were measured 2026-11-11 at `43d0897` without changing any repo file. The prototypes ran in the session scratchpad.

**F1. Where seeds reach the generator.** `denoisifier.synthetic.generate(*, seed: int, ...)` is the only entry point. It calls `np.random.default_rng(seed)` after validating its arguments. Callers:
- **The pytest process:** `test_analyse.py`, `borderline.py`, `test_synthetic.py`, `test_cli.py` and `test_read_frame.py`, plus `feasibility.time_full_frame` (`TIMING_SEED`).
- **Spawned workers:** `feasibility.score_batch` → spawn `ProcessPoolExecutor` → `_score_one` → `_frame` → `generate`. This path is the only one for the feasibility gate's calibration and held-out frames. A guard installed only in the pytest process never sees these seeds.
- The `test_cli.py` CLI subprocesses read CSVs and never call `generate`.

**F2. Calibration ranges in use (complete after review O1):**
- `A0_CALIBRATION_SEEDS = range(0, 10)`. `_A0 = 3e-3` was chosen on ticket 01's profile-only frames (Gaussian noise 0 / 0.001 / 0.01, seeds 0-9; `src/denoisifier/_local_stripes.py:34-40`). `_A0` sits in the score's denominator. Codex measured that seed 0, noise 0 scores 326.55 at `_A0 = 0.001` and 36.28 at 0.003, which changes the verdict at 154.
- `THRESHOLD_CALIBRATION_SEEDS = range(100, 200)`: see the comment above `THRESHOLD` in `analysis.py`.
- `GATE_CALIBRATION_SEEDS = range(10_000, 12_000)` and `PROBE_CALIBRATION_SEEDS = range(70_000, 70_300)`: the feasibility gate.
- Ticket 07's routine does not exist yet. It registers its ranges when it lands.
- Considered and **not** registered (review N6): `borderline.py` chose its frames from test seeds 0-19 by score window. That is fixture selection, not detector calibration. Its seed-0 entry is still re-seeded, because 0 is now in the `_A0` range (see R1).

**F3. Tests the guard will catch (prediction).** Under the seam below (the audit event fires just before `default_rng`, so a call that fails validation raises its `ValueError` first and is never caught), every non-slow test that generates a frame from a seed in 0-9 will be caught. The implementer takes the **actual** list from a guard run (step 4) and compares it with this prediction:
- `test_analyse.py`: `test_stripe_free_mottled_frames_are_not_striped[0-9]`, `test_clear_stripes_in_mottle_are_found_and_measured[0-9]`, `test_clear_full_frame_stripes_are_found_and_measured` (seeds 0-6, both noises), `test_profile_only_frame_is_not_striped` (all 30), `test_report_has_score_and_threshold` (7), `test_rejects_frame_smaller_than_min_side` (0), `test_rejects_non_finite_values` (0), `test_input_frame_is_not_modified` (2), `test_report_converts_to_json` (1), `test_strong_stripes_are_measured` (all 10), `test_modulation_depth_is_relative_to_local_envelope` (all 6), `test_period_and_angle_extremes_are_detected` (all 8), `test_multiscale_mottle_is_handled` (all 10), `test_borderline_striped_frame_has_finite_measurements[0-20]`.
- `test_synthetic.py`: `test_same_seed_gives_same_frame` (3, 4), `test_returns_frame_and_ground_truth`, `test_mottle_has_the_requested_strength`, `test_mottle_none_is_unchanged_from_ticket_01`, `test_emccd_peak_photon_count`, the four `test_emccd_*` tests through `_noise_residual` (seed 0), `test_stripe_free_frame_has_no_stripe_peak` (all 20), `test_clean_stripes_put_the_spectral_peak_at_the_true_period_and_angle` (all 3). `test_rejects_invalid_settings` is **not** caught: it raises in validation first.
- `test_cli.py`: `test_cli_writes_json_report_for_striped_csv` (1), `test_cli_reports_borderline_frame` (`BORDERLINE[0]` = seed 0), `test_cli_prints_json_to_stdout_without_output_flag` (2), `test_cli_fails_cleanly_when_output_dir_missing` (3).
- `test_read_frame.py`: `test_written_csv_reads_back_as_the_same_frame` (5).
- No current seed is in 100-199, 10 000-11 999 or 70 000-70 299. The review re-checked this with grep.

**F4. Mechanism prototypes (scratchpad, project venv, Python 3.11.15).**
- An exception raised by a `sys.addaudithook` hook propagates out of `sys.audit` to the caller.
- The hook installed in a spawn-pool worker through `initializer=`/`initargs=`: the worker's exception reaches the parent through `ex.map` with its type and message intact. Review N4 re-ran it with `chunksize=4` over 40 jobs: the parent failed after 3.1 s, because `map` cancels the pending futures. A hit in a 2000-seed batch therefore fails fast.
- A `BaseException` subclass escapes a test's `except Exception: pass`. pytest still fails **only that test** (`1 failed, 2 passed`), and the session goes on.
- `default_rng([10000])` draws the same stream as `default_rng(10000)`, so the guard refuses any seed that is not an integer.

**F5. Cost of the worker path.** A single-seed `score_batch(..., (40, 40), workers=1)` takes 2.2 s (spawn dominates). A tiny real-worker `measure` takes 11.6-13.4 s, which is too close to the 60 s timeout under load. So the worker path is tested with single-seed calls (T4, T7), and `measure`'s context placement is tested in-process (T5). Review N5 confirmed that T5's small plan works with the real calibration math: `threshold_rank(99, 0.01) = 1`, `false_alarm_tolerance(99, 10, 0.01) = (0, 1)`, and `rate_interval(0, 10)` is finite.

**F6. Lint.** Imports in `tests/feasibility.py` that come after its thread-variable loop carry `# noqa: E402`, and adding another `noqa` is a weakening move. `import seed_guard` therefore goes **above** the loop. The review checked that ruff `I` sorts it as first-party with no `noqa`. mypy covers `src/denoisifier` only, so the `synthetic.py` edit must stay strict-clean.

## Guarantee and known limits

**Guarantee:** during `make check`, `make check-slow`, `make test-fast` and `uv run python tests/feasibility.py`, every seed passed to `denoisifier.synthetic.generate` that is used to seed its RNG is checked against the registered calibration ranges, in the main process and in `score_batch`'s workers. A seed in a calibration range raises `SeedGuardError` unless it lies inside an active `seed_guard.calibrating(...)` block for that range. A non-integer seed is refused.

**Known limits** (not fixed; the implementer records them in a ticket Comment too):
1. **A pool or subprocess without the initializer runs unguarded.** Today `score_batch` is the only pool. A new pool would show up in the diff, and CLAUDE.md lists the initializer as a protected surface. T7 covers the script's own path.
2. **Calibration frames or scores reused after an allowed block are not seen.** Frames or scores produced inside `calibrating(...)` can be kept and judged later without another `generate` call. For example, `measure` handles plain score arrays with no provenance. The guard sees generation, not data flow. T5 checks that the block encloses only the calibration call (review N1). Reuse of its output can still be caught only by review.
3. Frames built without `generate` (direct `np.random.default_rng(...)`) are not seen.

## Design

### Seam 1: audit event in `generate` (`src/denoisifier/synthetic.py`)

`sys.audit("denoisifier.synthetic.generate", seed)` goes immediately before `rng = np.random.default_rng(seed)`. That is the point where the seed takes effect: invalid-argument calls raise their `ValueError` first and generate nothing. Add `import sys` and one docstring sentence naming the event. The RNG draws are unchanged, so frames stay bit-identical. Because this changes the generator, `make check-slow` is required.

### Seam 2: the guard (`tests/seed_guard.py`, new)

- `SeedGuardError(BaseException)` takes one string argument, so it pickles back from workers.
- `install(allowed: tuple[range, ...] = ()) -> None` adds the audit hook once per process (idempotent; audit hooks cannot be removed). `installed() -> bool`.
- The hook, on `"denoisifier.synthetic.generate"`:
  - `seed = operator.index(args[0])`, else raise `SeedGuardError(f"seed {args[0]!r} is not an int; the seed guard cannot check it (ticket agent-gates/04)")`.
  - Then, for each `(name, r)` in `protected.CALIBRATION_SEEDS.items()`, if `seed in r` and no allowed range contains it, raise `SeedGuardError(f"seed {seed} is in calibration range {name} = {r!r}, outside a seed_guard.calibrating(...) block. Evaluate on held-out seeds (ticket agent-gates/04); a new or wider calibrating block is a protected-surface change (CLAUDE.md).")`.
- **The marker** is `calibrating(seeds: range)`, a `@contextlib.contextmanager`.
  - On entry it validates `seeds` (review N3). Each of these raises `ValueError` worded like the guard: `seeds` is not a `range`, it is empty, its step is not 1, or it does not lie inside one registered `CALIBRATION_SEEDS` range. The emptiness check runs first, so `r[-1]` is never taken on an empty range.
  - It pushes `seeds` onto the allowed stack, `yield`s, and pops it in `finally`, so an exception inside the block cannot leave the range allowed.
  - It allows only that range, so the gate's block cannot touch the probe's range. The grep target is `calibrating(`.
- `worker_allowance() -> tuple[range, ...] | None` returns `None` when the guard is off in this process, else a snapshot of the stack.
- `install_worker(allowance) -> None` is the pool initializer. It installs with that allowance when the allowance is not `None`.
- The module imports only `contextlib`, `operator`, `sys` and `protected` (which imports only `cases` → `typing`). It imports **no NumPy**, and a comment says why (feasibility imports it before its thread-variable loop).

### Seam 3: install for the whole run (`tests/conftest.py`) **[APPROVED: Q5]**

`pytest_configure` calls `seed_guard.install()`. All gate targets run pytest with this conftest. pytest inserts `tests/` into `sys.path` before it imports the rootdir conftest.

### Seam 4: calibration contexts and workers (`tests/feasibility.py`)

- `import seed_guard` goes in the top import block **above** the thread-variable loop, with a one-line comment. No `noqa`.
- `measure`: `with seed_guard.calibrating(plan.calibration): calibration_scores = score_batch(plan.calibration, 0.0, plan.shape, workers)`. The block encloses that one call only.
- `score_batch`: `ProcessPoolExecutor(..., initializer=seed_guard.install_worker, initargs=(seed_guard.worker_allowance(),))`. A pool is created per call, so the snapshot is always current.
- `main()`: its first statement is `seed_guard.install()` (Q4). Its workers inherit the guard through `score_batch`.

### Seam 5: the registry (`tests/protected.py` + lockfile) **[APPROVED: Q5, Q2, O1]**

```python
A0_CALIBRATION_SEEDS = range(0, 10)  # _A0 (_local_stripes.py): ticket 01 profile-only frames
TEST_SEED_BLOCK = range(10, 100)  # non-slow tests; every *_TEST_SEED(S) lies in here
THRESHOLD_CALIBRATION_SEEDS = range(100, 200)  # THRESHOLD (analysis.py comment)
USED_SEEDS = [
    A0_CALIBRATION_SEEDS,
    TEST_SEED_BLOCK,
    THRESHOLD_CALIBRATION_SEEDS,
    range(1000, 1400),
    range(2000, 2032),
    range(50_000, 50_300),
    range(59_999, 60_100),
]
CALIBRATION_SEEDS = {
    "A0_CALIBRATION_SEEDS": A0_CALIBRATION_SEEDS,
    "THRESHOLD_CALIBRATION_SEEDS": THRESHOLD_CALIBRATION_SEEDS,
    "GATE_CALIBRATION_SEEDS": GATE_CALIBRATION_SEEDS,
    "PROBE_CALIBRATION_SEEDS": PROBE_CALIBRATION_SEEDS,
}
```

The union of `USED_SEEDS` stays 0-199 plus the rest, unchanged. The per-test seed names from R1 are added too. Lockfile: new lines for each new name, and the changed `USED_SEEDS` line. Each value is copied from the failing protected-numbers test's `live ...` text.

**The disjointness check keeps its name and file**, `test_seed_sets_are_disjoint_and_unused` in `tests/test_feasibility_gate.py`, because ticket 05 refers to it (review N2). It becomes registry-wide and discovers ranges, so ticket 05's regression seeds are covered without editing it.
- **Top-level ranges:** every module-level `range` in `protected` (except `*_TEST_SEEDS` names), each `USED_SEEDS[i]`, and every module-level `int` named `*_SEED` (except `*_TEST_SEED`) as `range(v, v + 1)`. Deduplicate **by identity (`is`) only**, keeping the first name (closing-check B1). Every intended alias is the same object: `USED_SEEDS[i]` holds the named ranges, `CALIBRATION_SEEDS` values are the named ranges, and `SEED_SETS` values are the named ranges, except `"timing"`, which is checked by the link rule below. Deduplicating by value would merge two different names bound to equal ranges, for example a ticket 05 set written by mistake as `range(10_000, 12_000)`, and never compare them. All entries are pairwise disjoint, **unconditionally**. A failure names both ranges and the shared count.
- **Testing the check itself (B1):** the discovery-and-compare logic is a function in the test module, `seed_range_overlaps(namespace) -> list[str]`. `test_seed_sets_are_disjoint_and_unused` runs it on `protected`. A second test, `test_equal_ranges_under_two_names_are_an_overlap`, runs it on a `types.SimpleNamespace` with `A_SEEDS = range(5, 9)` and `B_SEEDS = range(5, 9)` (two distinct but equal objects) and expects one overlap naming both. The same namespace with `B_SEEDS = A_SEEDS` (an alias) expects none. Plant P6 shows the same thing on the real path.
- **Test seeds:** every `*_TEST_SEEDS` (range or tuple) and `*_TEST_SEED` value, and every seed in `BORDERLINE_TEST_CASES`, lies inside `TEST_SEED_BLOCK`. These may share seeds with each other, as the tests did before.
- **Registry links:** every `CALIBRATION_SEEDS` key is a top-level name whose value is that range. Every `feasibility.SEED_SETS` value equals a top-level range. Every `SEED_SETS` entry whose name contains `calibration` is in `CALIBRATION_SEEDS.values()`.
- The old test's exact-size assertion (`{"calibration": 2000, ...}`) stays in this test unchanged.

### R1: re-seeding (O1) **[APPROVED: O1, Q5]**

**Rule:** a caught seed `s` in 0-9 becomes `s + 20`. Seeds 20-29 are in the test block and used by no test today ("unused"). Seeds already in 10-19 stay. A uniform +20 shift keeps every seed-derived case mapping:
- `CASES[seed % 10]` stays the same case.
- `test_multiscale_mottle_is_handled`'s `([3, 8, 20][s % 3], [-10, 0, 10][(s // 3) % 3])` still covers all 9 Period/Angle pairs over 20-29 (checked by hand: pairs (2,0) (0,1) (1,1) (2,1) (0,2) (1,2) (2,2) (0,0) (1,0) (2,0)).
- Pairs of seeds stay distinct (3, 4 → 23, 24).

Names in `protected.py`. Tests import them, and module-level literals move there.

| name | value | used by |
|---|---|---|
| `MOTTLED_TEST_SEEDS` | `range(10, 30)` | `test_analyse.SEEDS` (both mottled tests) |
| `FULL_FRAME_TEST_SEEDS` | `range(20, 27)` | `test_clear_full_frame_stripes_...`, zipped with its 7 cases in order |
| `PROFILE_ONLY_TEST_SEEDS` | `range(20, 30)` | `test_profile_only_frame_is_not_striped` |
| `STRONG_TEST_SEEDS` | `range(20, 25)` | `test_strong_stripes_are_measured` |
| `ENVELOPE_TEST_SEEDS` | `range(20, 23)` | `test_modulation_depth_is_relative_to_local_envelope` |
| `EXTREMES_TEST_SEEDS` | `range(20, 28)` | `test_period_and_angle_extremes_are_detected`, zipped with `EXTREMES` |
| `MULTISCALE_TEST_SEEDS` | `range(20, 30)` | `test_multiscale_mottle_is_handled` |
| `STRIPE_FREE_SPECTRUM_TEST_SEEDS` | `range(20, 30)` | `test_synthetic.test_stripe_free_frame_has_no_stripe_peak` |
| `SAME_SEED_TEST_SEEDS` | `(23, 24)` | `test_same_seed_gives_same_frame` |
| `SINGLE_FRAME_TEST_SEED` | `20` | each remaining single-frame test whose seed was 0 (`test_analyse` 110 and 120, `test_synthetic` 20, 32, 43, 48, 104) |
| `SINGLE_FRAME_ALT_TEST_SEEDS` | `(21, 22, 23, 25, 27)` | old seeds 1, 2, 3, 5 and 7, by `s + 20` (`test_analyse` 83, 127, 135; `test_synthetic` 39; `test_cli` 31, 56, 79; `test_read_frame` 34) |
| `BORDERLINE_TEST_CASES` | see below | `borderline.BORDERLINE` (re-exported) |

Naming is the implementer's call. The constraints are fixed: one named constant per value, and every value inside `TEST_SEED_BLOCK`. A **caught** seed `s` (0-9) becomes `s + 20`, and seeds already in 10-19 stay as they are (closing-check N9). The one exception is the borderline pick below. A test needing its own name may add one.

**Borderline (`(0, 20)`):** `+20` does not preserve the property under test, which is a score in (THRESHOLD, 1.5×THRESHOLD). Re-pick it the way `borderline.py`'s docstring describes: scan Period 20 frames at seeds 20, 21, … 99 (not already in `BORDERLINE`) with the `borderline_frame` settings, and take the **lowest** seed whose score lies in the window. Record the scan and score in Comments, and update the docstring ("picked from test seeds 10-99"). `BORDERLINE_TEST_CASES = [(<new>, 20), (13, 5), (13, 8), (12, 20), (16, 8)]`, keeping order, so `test_cli`'s `BORDERLINE[0]` is the new pick. If no seed in 20-99 qualifies, that is a finding: stop.

**Ruling O3 (orchestrator, 2026-11-11; not an owner ruling): the borderline scan is accepted.** The score window is the fixture's defining property (`borderline.py` docstring). The frames were first picked the same way. The rule (the lowest qualifying seed in 20-99) is fixed before the scan. So this is fixture selection, not seed shopping, and it falls outside O1's failure rule. Every other re-seeded test follows the failure rule.

**Failure rule (O1):** after re-seeding, any test that fails its own assertion (not the guard) is a finding. Record the test ID, old and new seed, and the assertion message in Comments, then **stop for the owner**. Do not change any tolerance, window or expected value, and do not try other seeds (only the borderline pick scans). The likeliest at-risk tests are the statistical `test_emccd_*` tests and the Period/Angle/Depth tolerance tests.

## Tests, one per acceptance criterion, on the real path

These go in a new `tests/test_seed_guard.py` (non-slow) unless noted. None adds a timeout mark, skip or filter.

- **AC1 (registry).** `test_seed_sets_are_disjoint_and_unused` (reworked, above) and `test_protected_numbers_match_the_lockfile` (new names pinned).
- **AC2 (guard during gates).**
  - **T1** `test_guard_is_installed_for_the_run`: `seed_guard.installed()`.
  - **T2** `test_generate_refuses_each_calibration_range`, parametrized over `CALIBRATION_SEEDS.items()`: `generate(seed=r[0], shape=(40, 40))` and `generate(seed=r[-1], ...)` raise `SeedGuardError` matching `re.escape(f"seed {r[0]} is in calibration range {name} = {r!r}")`. `r[-1] + 1` does not raise. Neither does `r[0] - 1` when `r[0] > 0`.
  - **T3** `test_calibrating_allows_only_its_range`:
    - Inside `calibrating(GATE_CALIBRATION_SEEDS)`, a gate seed generates, while a probe seed and an `_A0` seed still raise. After the block the gate seed raises again.
    - An exception raised inside the block still leaves the range disallowed afterwards (N3).
    - `calibrating(range(0, 10_000_000))`, `calibrating(range(10_000, 10_000))` and `calibrating(range(10_000, 10_100, 2))` each raise `ValueError`.
  - **T4** `test_guard_reaches_the_feasibility_workers`: `feasibility.score_batch([GATE_CALIBRATION_SEEDS[0]], 0.0, (40, 40), workers=1)` raises `SeedGuardError` with the message. Inside `calibrating(GATE_CALIBRATION_SEEDS)`, it returns one finite score. This is the only real-worker proof in the non-slow tier, and the only one at all once ticket 05 removes per-run calibration from `check-slow` (N2).
  - **T5** `test_measure_calibrates_inside_the_block_and_evaluates_outside`:
    - `monkeypatch.setattr(feasibility, "score_batch", fake)`. `fake(seeds, depth, shape, workers=None)` runs in-process. It first asserts `seed_guard.worker_allowance() == (plan.calibration,)` when `seeds is plan.calibration`, and `== ()` otherwise (review N1: catches a block that is too wide). Then it calls the real `feasibility._frame(seed, depth, shape, feasibility.case_of(seed))` (real `generate`, real hook) and returns each frame's std.
    - The plan is `SeedPlan((40, 40), GATE_CALIBRATION_SEEDS[:99], range(40, 50), range(50, 60))`, with held-out seeds from the unused test block. The test asserts `fake` was called three times and `measure` returned.
  - **T6** `test_non_int_seed_is_refused`: `generate(seed=[10_000], shape=(40, 40))` raises `SeedGuardError`.
  - **T7** `test_feasibility_script_guards_itself_and_its_workers` (Q4, standalone negative proof). It runs a fresh `subprocess.run([sys.executable, "-c", SCRIPT], cwd=<tests dir>, capture_output=True, text=True, timeout=…)`; the conftest never loads in that process. `SCRIPT` replaces `feasibility.measure_all` with a function that calls the real `feasibility.score_batch([GATE_CALIBRATION_SEEDS[0]], 0.0, (40, 40), 1)`, then calls `feasibility.main(["--out", <tmp path>])`. Assert: a nonzero return code, `SeedGuardError` and `seed 10000 is in calibration range GATE_CALIBRATION_SEEDS` in stderr, and no output file. This proves `main()` installs the guard and that the guard reaches its workers. The `subprocess` timeout argument bounds a hung child. It is not a pytest timeout mark, so it is not a weakening move. Set it well under 60 s (for example 45 s) and measure the run (expect about 4-5 s idle).
  - **`make check-slow`:** the fresh `measure_all` runs the real calibration inside the block in real workers and the held-out sets outside it. This holds only until ticket 05 lands. T4, T5 and T7 carry the proof without it.
- **AC3 (explicit marker, protected).** `seed_guard.calibrating(...)`, plus the CLAUDE.md line (step 8).
- **AC4 (plants).** See "Planted-case proof".
- **AC5 (green).** Steps 4-6 and 10, under the O1 rule.

## Planted-case proof (not committed)

Run each plant alone through the real `make check` (foreground, about 1.5-2 min), then revert it. Record make's exit status, the `FAILED ... SeedGuardError: ...` line and pytest's final summary line. Afterwards `git status --porcelain -- src tests CLAUDE.md pyproject.toml Makefile` must show only the intended uncommitted work (empty if run on the commit), with no plant file left.

- **P1, a parametrized test over a calibration seed:** a new `tests/test_zz_plant.py` with `@pytest.mark.parametrize("seed", [10_500])` and `generate(seed=seed, shape=(40, 40))`. Expect `FAILED tests/test_zz_plant.py::test_plant[10500] - seed_guard.SeedGuardError: seed 10500 is in calibration range GATE_CALIBRATION_SEEDS = range(10000, 12000), ...`.
- **P2, a seed computed into a variable:** in the same file, `base = 70_000; seed = base + 3 * 7`, then `generate(seed=seed, ...)`. Expect the `PROBE_CALIBRATION_SEEDS` message.
- **P3, an evaluation step drawing from the calibration set:** in the real `feasibility.measure`, `free_scores = score_batch(plan.calibration, 0.0, plan.shape, workers)` (outside the block). Expect T5 red with the `GATE_CALIBRATION_SEEDS` message. No other test catches this plant, because the seed plan is unchanged. Back up `tests/feasibility.py` before the plant and restore from the backup.
- **P4 (Q4):** delete `seed_guard.install()` from `main()`. Expect T7 red (zero return code, or no `SeedGuardError` in stderr).
- **P6 (B1, the dedup rule on the real path):** add `DUPLICATE_SEEDS = range(10_000, 12_000)` to `tests/protected.py`. Expect `test_seed_sets_are_disjoint_and_unused` red, naming `GATE_CALIBRATION_SEEDS` and `DUPLICATE_SEEDS`. The lockfile test will also be red (an unpinned number). Record both lines.
- **P5 (optional):** P1 wrapped in `try: ... except Exception: pass` still fails with the guard's message.

## Order of work

1. **Registry [APPROVED: Q5, Q2, O1]:** `A0_CALIBRATION_SEEDS`, `TEST_SEED_BLOCK`, `THRESHOLD_CALIBRATION_SEEDS`, the `USED_SEEDS` split, `CALIBRATION_SEEDS` and lockfile lines; rework `test_seed_sets_are_disjoint_and_unused`. Run `make test-fast`. Commit. (The per-test seed names come in step 5.)
2. **Seam 1:** `sys.audit` in `generate`. Run `make test-fast` (no hook yet, so no behaviour change). Commit.
3. **Seams 2 and 4:** `tests/seed_guard.py`, the `feasibility.py` changes, and T1-T7. Until step 4 installs the guard in the conftest, these are **red by design**: T1, T2, T3, T6 and the `SeedGuardError` half of T4 (closing-check N8). T5's allowance assertions also depend on the install, because `worker_allowance()` returns `None` without it. So at this step, run `make lint` plus `uv run --locked pytest tests/test_seed_guard.py -k 'script or measure'`. T7 does not depend on the conftest. Expect T7 green, and T5 red only on its allowance assertion. Do not run `make test-fast` here. Commit only with steps 4 and 5.
4. **Seam 3 [APPROVED: Q5]:** the conftest install. Run `make check` and save its output. Every `SeedGuardError` failure is a caught test. Compare the IDs with F3's prediction, explain any difference in Comments, and **list the affected test IDs in Comments (O1)**. A caught test outside 0-9, or one in the slow tier, is a finding not covered by O1: stop. Do not commit a red tree; carry on to step 5 uncommitted.
5. **R1 re-seeding [APPROVED: O1, Q5]:** add the per-test seed names to `protected.py` and the lockfile, switch the tests to them, and re-pick the borderline case. Run `make check`. If any re-seeded test fails its own assertion, apply the **failure rule**: record it and stop. Once green, commit steps 3-5 together (guard, install, re-seeds). The commit message says that the re-seeding follows owner ruling O1.
6. Measure T4, T5 and T7 idle and under load (for example during a second `make test-fast`, but **never** while `make check-slow` runs). Record the times. Do not add timeout marks.
7. CLAUDE.md, Gates section: a protected-surfaces line covering the seed guard (`tests/seed_guard.py`), its install in `tests/conftest.py` and in `feasibility.main()`, the `score_batch` initializer, the audit event in `generate`, the `CALIBRATION_SEEDS` registry and every `seed_guard.calibrating(...)` block. Adding, widening or moving a `calibrating` block, or removing an install or the initializer, is a weakening move needing owner approval. **[APPROVED: Q5]** Commit.
8. Plants P1-P4 and P6 (and P5) through `make check`, each reverted.
9. Ticket Comments: the guarantee and known limits 1-3 (Codex's holes) as their own Comment.
10. **Gates on the committed HEAD:** `make check` (foreground), then `make check-slow` **in the background**, with output to `.scratch/agent-gates/handoffs/04-check-slow.log` and `/proc/loadavg` recorded at the start and end. Nothing else runs meanwhile. It is required because the generator, `feasibility.py` and tests changed. Expect about 48 min (ticket 03: 2850.97 s), but only if ticket 05 has not landed. Record the fresh timing median beside ticket 03's (review N7: the audit hook is live during the 10 s timing test; `analyse` raises no audit events, so the cost should be nil). If `check-slow` is caught by the guard, stop for the owner.
11. Ticket Comments: design, approvals (pointer to the 2026-11-11 rulings), affected test IDs, the borderline re-pick, plant evidence, timings, and gate quotes (command, exit status, pytest's summary line, `git rev-parse --short HEAD` with `-dirty` if applicable).
