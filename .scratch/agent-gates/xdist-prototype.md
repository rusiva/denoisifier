# Prototype: pytest-xdist for the fast tier

Throwaway prototype, worktree `.claude/worktrees/agent-a8dfa301eb036d34b` at `1cec498-dirty`
(dirty = `pyproject.toml` + `uv.lock` gained `pytest-xdist==3.8.0` and `pytest-randomly==5.1.0`;
pytest-randomly was added only for the random-order runs). Nothing committed. Date 2026-11-12.

Machine: AMD Ryzen AI 7 PRO 360 laptop (8 cores / 16 threads), WSL2, 30 GB.
Every run: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run --locked pytest -q --durations=15|25 <args>`,
one at a time, started only when the 1-min load was < 2. Timeout stayed at 60 s (thread method); markers and selection were not changed.

## Results

| run | args | wall | summary line | max test | load before / after |
|---|---|---|---|---|---|
| serial (baseline) | `-p no:randomly` | 442.9 s | `732 passed, 4 deselected in 441.83s` | 16.14 s | 0.67 / 1.15 |
| n4 loadfile | `-p no:randomly -n 4 --dist loadfile` | 420.3 s | `732 passed in 419.98s` | 16.32 s | 1.15 / 1.42 |
| n6 loadfile | `-n 6 --dist loadfile` | stopped at 106 s (coordinator: loadfile unbalanced) | n/a | n/a | 1.42 / n/a |
| **n4 load** | `-p no:randomly -n 4 --dist load` | **230.1 s** | `732 passed in 229.83s` | 26.87 s | 1.71 / 6.38 |
| n6 load | `-p no:randomly -n 6 --dist load` | 239.4 s | `732 passed in 239.07s` | 45.35 s | 1.47 / 4.67 |
| n8 load | `-p no:randomly -n 8 --dist load` | 251.8 s | `1 failed, 731 passed in 251.34s` | 52.68 s, plus one test killed at the 60 s timeout | 1.65 / 7.43 |
| n4 worksteal | `-p no:randomly -n 4 --dist worksteal` | 265.1 s | `732 passed in 264.76s` | 33.24 s | 1.48 / 4.85 |
| n4 load, random order #1 | `-n 4 --dist load` (randomly on) | 315.6 s | `732 passed in 315.21s` | **51.92 s** | 1.72 / 5.10 |
| n4 load, random order #2 | `-n 4 --dist load` (randomly on) | 286.3 s | `732 passed in 285.93s` | 42.96 s | 0.90 / 4.04 |
| n4 loadgroup (2026-11-13) | `-p no:randomly -n 4 --dist loadgroup`, `xdist_group("sweep")` on the 3 sweep tests | 378.1 s | `732 passed in 392.51s` | **39.32 s** (sweep), 32.90 s (`test_mask_overlaps_the_true_region[73-scorched]`, not grouped) | 1.20 / 6.65 |
| seed guard, n2 | `-n 2 -v tests/test_seed_guard.py` | 3.0 s | `12 passed in 2.83s` | 1.69 s | 0.77 / 0.77 |

(The random-order seeds were not captured, because `-q` hides the header. A later verbose seed-guard run used `--randomly-seed=3137922191`.)

The n8 failure: `[gw4] node down: Not properly terminated` / `worker 'gw4' crashed while running
'tests/test_analyse.py::test_lowering_the_threshold_keeps_reported_regions_unchanged[two-region-above-score-below-score]'`.
The test hit the 60 s thread-method timeout, which ends the worker process. Its stack dump goes to the
worker's stderr, and xdist does not show it, so the report has no traceback.

### Why loadfile does not help
`tests/test_analyse.py` is most of the 442 s. loadfile pins it to one worker, so -n 4 saves only 22 s.

### Why more workers make the slowest tests slower (the `@cache` problem)
- `tests/test_analyse.py:578` `_sweep_report` and `tests/regions.py:99` `single_region_case` are
  module-level `functools.cache`s. Serially, the first sweep test pays for the `two-region` analyses once
  (16 s), and later tests read the cache. Under `load`, every worker that receives a `two-region` param
  recomputes the analyses it needs. `test_lowering_the_threshold_keeps_reported_regions_unchanged[two-region-*-*]`
  needs up to two (`kind_a`, `kind_b`) on a cold cache. Under `--dist load` the duplication also
  increases the total CPU spent on that sweep.
- Per-analysis CPU time also rises with the number of workers. `test_two_regions_with_different_periods_are_reported_separately[76-8-16]`
  has no cache and took 8.8 s serial, 15.6 s at n4, 23.5 s at n6 and 29.2 s at n8. That is 1.8x to 3.3x slower
  per test, from the laptop's all-core clock drop and shared memory bandwidth. Load reached 6 to 7, although the
  BLAS/OMP threads were pinned to 1.
- Together these push the worst test from 16 s serially to 27 to 52 s at n4, depending on order, and past
  60 s at n8. **Under random order at n4, the margin to the timeout was 8 s (51.92 s).** The
  current timeout comment calls 7.07 s at 2x oversubscription the slowest step. xdist breaks that
  assumption for the `two-region` sweep tests.
- Wall time does not improve beyond 4 workers: 230, 239 and 252 s for n = 4, 6 and 8.

## Correctness under xdist
- **Seed guard: holds in the workers.** `tests/conftest.py::pytest_configure` runs in every xdist worker, so
  `seed_guard.install()` and `PYTHONWARNINGS=error` apply per worker. The verbose `-n 2` run showed
  `[gw1] PASSED tests/test_seed_guard.py::test_guard_is_installed_for_the_run`, and
  `test_generate_refuses_each_calibration_range[*]` (all 5 ranges), `test_calibrating_allows_only_its_range`,
  `test_non_int_seed_is_refused`, `test_reinstall_with_a_different_allowance_is_refused`,
  `test_guard_reaches_the_feasibility_workers` and `test_feasibility_script_guards_itself_and_its_workers`
  passed, split across gw0 and gw1. The full runs also passed them.
- **`filterwarnings = error`**: it is ini config, so each worker applies it. No run raised a warning.
- **Shared files**: none found. CLI tests use `tmp_path`, which is per worker under xdist. `test_slow_stamp.py` runs the runner
  on a tmp-root copy, and `find_leftover_workers` is tested on a fake `/proc`. The only fast-tier read of real `.scratch` is
  `tests/test_analyse.py:639` (read-only `region-calibration.json`). `test_the_stamp_is_git_ignored_local_state`
  only runs `git check-ignore`.
- **Process-global state**: the seed-guard audit hook and `_allowed` list are per process, so they are isolated per worker.
  The `@cache`s are correct per worker. They are only slower (see above).
- **Order**: 2 random-order runs at n4 (randomly on, load mode): no failures and no flakiness. The only
  order effect is on timing, through the cold caches.
- **Diagnostics get worse**: under xdist a timeout ends the worker with no stack dump in the report. Serially,
  the thread method prints the stacks.

## Recommendation

**Update, 2026-11-13: loadgroup is ruled out.** It took 378 s and its slowest test took 39 s.
The group puts every sweep param on one worker, which turns the group into the critical path. Its
tests still run 2–2.5x slower than serially (39 s against 16 s), so the cold cache was not the main
cause. Memory-bandwidth contention is. Tests outside the group get just as slow
(`test_mask_overlaps_the_true_region`: 32.9 s). The random-order and n6 loadgroup runs were skipped,
because they cannot rescue a run that is both slower than `load` and over the 30 s bound.
Consequence: under any `-n 4` mode the slowest test runs at about 2–3x its serial time. Parallel
runs are safe only once every fast test takes about 10 s or less serially, which needs faster or
split tests (as `e70d99d` did). The text below predates this update.

**Do not adopt xdist yet.** It saves time: n4 `--dist load` cut the wall time from 442 s to 230 s (1.9x)
in collection order, and to 286 to 316 s (1.4 to 1.5x) in random order. But the best setting left only an
8 s margin under the 60 s timeout, and n8 crossed it. The fixes are a test-side grouping, a timeout
change (a weakening move) or a cheaper `two-region` sweep frame. Each needs the orchestrator's decision.

If it is adopted, use **`-n 4 --dist loadgroup`**, with the `_sweep_report` sweep tests
(`test_verdict_is_striped_exactly_when_a_region_is_reported`,
`test_lowering_the_threshold_keeps_reported_regions_unchanged`) marked
`@pytest.mark.xdist_group("sweep")`. That keeps the cache warm on one worker, which brings the slowest
test back to the serial ~16 s. This variant was **not measured**: the brief ruled out marker changes. It
needs one more timing run before adoption. Not 6 or 8 workers: they are slower and nearer the timeout on
this 8-core laptop.

### Exact config change proposed (gate config, needs an approval)
`pyproject.toml`:
```toml
[dependency-groups]
dev = [
    ...
    "pytest-xdist>=3.8.0",   # locks 3.8.0
]
```
`Makefile`. Parallelise the full fast run only. Keep `test-fast` serial, because `-x --ff` stops sooner
and gives clearer output serially, and it keeps timeout stack dumps:
```make
check: lock-check lint
	$(PYTEST) -n 4 --dist loadgroup
	$(UV) python tests/slow_stamp.py check
```
`tests/test_analyse.py`: `@pytest.mark.xdist_group("sweep")` on the two sweep tests above.
`addopts` stays unchanged. Putting `-n` in addopts would also parallelise `make check-slow` (`-m slow`),
whose feasibility pools already use the cores.
Do not add pytest-randomly. It was used only for this probe.
