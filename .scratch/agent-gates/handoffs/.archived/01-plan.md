# 01 plan: gate skeleton and protocol

- Ticket: `.scratch/agent-gates/issues/01-gate-skeleton-and-protocol.md`
- Spec: `.scratch/agent-gates/spec.md`
- BASE: `d90c66f` (it replaced the brief's original `f0c8f6c`; see F1).
- Review: `.scratch/agent-gates/handoffs/01-plan-review.md`. B1, B2 and N2-N5 are folded in below.
- Status: **settled.** The owner ruled Q1 = B and Q2 = 5400 s as a per-test mark on that param. Q3 and Q4 were settled as recommended (review N5). No open questions remain.

## Findings that shape the plan

**F1. At HEAD the `slow` tier is empty.** Commit `d90c66f` replaced the `@pytest.mark.slow` feasibility tests with tests that read the saved `.scratch/stripe-detector/feasibility-gate.json`. Nothing in `tests/` carries `slow` any more (`grep -rn "mark.slow" tests` finds nothing), and the non-slow run reports `208 passed` with 0 deselected. So `pytest -m slow` today deselects everything and exits 5 ("no tests ran"). That means `make check-slow` cannot be "green on the current code", and it cannot raise worker-process warnings, unless something brings a slow test back. Ticket 01 was written against `f0c8f6c`, where the slow tests existed. The owner ruled Q1 = option B: a `fresh` parametrisation marked `slow` (see "Slow path" below).

**F2. Today's non-slow suite already passes the strict settings.** Measured 2026-11-10 at `d90c66f`, load average 0.35 at the start:

```
PYTHONWARNINGS=error uv run --locked pytest -p no:cacheprovider -W error \
  --strict-markers --strict-config -o xfail_strict=true --durations=25 -q
208 passed in 82.15s (0:01:22)        # exit 0
```

`PYTHONWARNINGS=error` also covers the subprocesses in `test_cli.py`. So turning the settings on needs no fixes to the non-slow tests.

**F3. Timer clock.** The uv-managed CPython 3.11.15 reports `HAVE_SEM_CLOCKWAIT 0`, the same condition cadmesh found in its issue 11. With it, pytest-timeout's `threading.Timer` waits on a `CLOCK_REALTIME` deadline, so a WSL VM resume that steps the clock can fire a timeout early. The result is a false **red**, which is loud, never a silent pass. Settled: accept the risk and note it in the pyproject comment (see the block below). Port cadmesh's monotonic-clock conftest (`~/dev/cadmesh/tests/conftest.py`) only if a spurious timeout is ever seen.

## Timeout evidence (copy under the ticket's `## Comments`)

Slowest test steps (the `call` phase; setup is negligible because there are no heavy fixtures in the non-slow tier):

| condition | slowest | next | whole suite |
|---|---|---|---|
| idle (load 0.35 → 2.57) | 1.28 s `test_multiscale_mottle_is_handled[2]` | 1.26 s, 1.23 s; CLI tests 0.87–0.96 s | 82 s, 208 tests |
| 32 busy-loop processes on 16 CPUs (load 23) | 7.07 s `test_cli_prints_json_to_stdout_without_output_flag` | 6.44 s, 5.51 s (`multiscale_mottle`) | (subset of 11 tests: 56.6 s) |

Commands used: the F2 command for the idle row. For the loaded row, the same command with `-k "multiscale_mottle or cli_prints" --durations=4`, run while 32 `sh -c 'while :; do :; done'` processes were going.

**Chosen: `timeout = 60` (seconds), `timeout_method = "thread"`.** That is about 8.5× the slowest step under 2× CPU oversubscription and about 47× the idle slowest step. A genuinely hung native call still ends the run within a minute. cadmesh uses 120 s and polsigns 300 s, but both have JIT or OCCT steps of several seconds. Nothing here is that slow.

What the limit measures: pytest-timeout times each test's setup + call + teardown (the default `timeout_func_only = false`) on its own timer thread, which is independent of `--durations`. When a test exceeds the limit, the thread method dumps every thread's stack between `+++ Timeout +++` banners and calls `os._exit(1)`. The whole run ends, with no summary line.

Slow tier (owner ruling Q2): the fresh measurement takes about 39 min (`.scratch/stripe-detector/feasibility-gate.md`, line 98, measured with 8 workers; today's default is 12 workers, so it should be shorter). It is a module-scoped fixture, so the first test that uses it carries all of that time. The `fresh` param carries `pytest.mark.timeout(5400)` (90 min, about 2.3× the measurement), with a comment citing that number. Only that param is marked, and the 60 s global limit still applies to everything else. The review's prototype P1 confirmed the mechanism: a timeout mark on a fixture `pytest.param` overrides the global limit and inherits `slow`.

## Design choices settled

1. **Lock check.** Every target calls `uv run --locked …`. `--locked` refuses to run if `uv.lock` is stale; `--frozen` would skip the check, so it is not used. `check` and `check-slow` also run `uv lock --check` first as their own step, so a stale lock shows a named failure before any test starts. Its message, measured on a scratch copy of the repo with a dependency added to `pyproject.toml`: ``The lockfile at `uv.lock` needs to be updated, but `--check` was provided. To update the lockfile, run `uv lock`.`` (exit 1).
2. **Tier selection** stays in config: `addopts = ["-m", "not slow"]`. A bare `uv run pytest` and `make check` then select the same tests, and narrowing them is visibly a gate-config edit. `check-slow` passes `-m slow`; the last `-m` wins, as the old docstring's `uv run pytest -m slow` relied on.
3. **Strict settings are separate ini keys**: `strict_markers`, `strict_config`, `strict_xfail` (pytest 9 names; `xfail_strict` is an alias), and `filterwarnings = ["error"]`. Not used: pytest 9's umbrella `strict = true`. It also turns on `strict_parametrization_ids`, and it is documented to grow with future pytest versions, which would change the gate without a diff.
4. **Warnings in worker processes.** pytest's `filterwarnings` does not reach the spawned `ProcessPoolExecutor` workers. A new `tests/conftest.py` sets `os.environ["PYTHONWARNINGS"] = "error"` in `pytest_configure`, so every child process started under pytest (spawned feasibility workers, the CLI subprocesses) turns warnings into errors. A warning raised in a worker becomes an exception that `ex.map` re-raises in the test. It is set in conftest rather than exported from the Makefile so that a bare `uv run pytest -m slow` behaves the same way (settled, Q4). F2 shows this is already green for the CLI subprocesses. The review's prototype P2 showed spawned feasibility workers clean on 12 frames.
5. **Dependency:** add `"pytest-timeout>=2.4.0"` to `[dependency-groups].dev`, then `uv lock`. 2.4.0 is the current release, the version cadmesh uses, and what `uv run --with pytest-timeout` resolved on 2026-11-10. `strict_config` then also turns a missing plugin into a loud `Unknown config option: timeout`.
6. **Which files may change.** "Only `make fix` changes files" means tracked files. `.pytest_cache` is git-ignored tool state, and `test-fast --ff` needs `check` to record its failures there. Ticket 05's stamp relies on the same reading.
7. **Default goal.** `check` is the first rule, so a bare `make` never changes anything. polsigns puts `fix` first; this repo does not copy that.
8. **`test-fast`** = `pytest -x --ff`. "Reruns failures first" means `--ff`, which runs the whole selection with last-failed tests first. `--lf` would run only the failures. `-x` stops at the first failure. It runs no lock-check step of its own because `--locked` already refuses a stale lock.

## Files touched

| file | change |
|---|---|
| `Makefile` (new) | the four targets plus `lock-check` |
| `pyproject.toml` | pytest settings; `pytest-timeout` in the dev group |
| `uv.lock` | regenerated by `uv lock` (adds pytest-timeout only) |
| `tests/conftest.py` (new) | `PYTHONWARNINGS=error` for child processes |
| `tests/test_feasibility_gate.py`, `tests/feasibility.py` | the fresh, `slow` measurement path (owner ruling Q1 = B) |
| `CLAUDE.md` | the protocol section |
| `.scratch/agent-gates/issues/01-gate-skeleton-and-protocol.md` | create the `## Comments` heading (the ticket has none yet), add the evidence under it, tick the criteria |

### Slice order

Each slice is green on its own:

1. Dependency + pyproject block + `tests/conftest.py`.
2. `Makefile`.
3. The slow-path refactor. It touches only `tests/feasibility.py` and `tests/test_feasibility_gate.py`, so it is disjoint from the other slices.
4. `CLAUDE.md` + the ticket's Comments.

### Makefile (shape)

```make
# Agent gates (ticket 01). Editing this file is a gate-config change: owner approval (CLAUDE.md).
UV     := uv run --locked
PYTEST := $(UV) pytest

.PHONY: check check-slow test-fast fix lock-check

check: lock-check           ## gate: every non-slow test, whole run
	$(PYTEST)

check-slow: lock-check      ## the slow tier (~40 min): run in the background
	$(PYTEST) -m slow

test-fast:                  ## inner loop: stop at first failure, failures first
	$(PYTEST) -x --ff

lock-check:
	uv lock --check

fix:                        ## the ONLY target that changes files; ruff arrives in ticket 02
	@echo "make fix: nothing to do yet (ticket 02 adds ruff)"
```

`fix` is a no-op until ticket 02 adds ruff; the ticket's "every target runs through the locked uv environment" applies to it from then on.

### pyproject.toml `[tool.pytest.ini_options]`

```toml
testpaths = ["tests"]
# The slow tier is `make check-slow` (-m slow). Narrowing this selection is a weakening move (CLAUDE.md).
addopts = ["-m", "not slow"]
markers = ["slow: long measurement runs (feasibility gate); `make check-slow`"]
# A misspelt marker or config key, or an xfail that passes, fails the run.
strict_markers = true
strict_config = true
strict_xfail = true
filterwarnings = ["error"]
# Operating setting, agent-chosen from measured slowest steps (1.28 s idle, 7.07 s at 2x CPU
# oversubscription; ticket agent-gates/01 Comments). Thread method: a hung native call never
# returns to Python for a signal handler; the thread dumps stacks and ends the run.
# Known risk, accepted: this CPython lacks sem_clockwait, so the timer waits on CLOCK_REALTIME
# and a VM resume can fire it early. That is a false red, never a false green; port cadmesh's
# monotonic-clock conftest if it is ever seen.
timeout = 60
timeout_method = "thread"
```

### Slow path (owner ruling Q1 = B)

- `tests/feasibility.py`: move `main`'s measuring body (run info, timing first, gate, optional probe, the progress prints) into a new `measure_all(workers: int | None = None, probe: bool = True) -> dict`. It returns the same dict that `main` writes. `main` and the `fresh` fixture both call it, and `main` writes the file. The existing `measure(plan, workers) -> RateResult` (`tests/feasibility.py:235`, called by `measure_gate`/`measure_probe`) is not touched. Same seeds, same order; no change to any number.
- `tests/test_feasibility_gate.py`: the `saved` fixture becomes a `result` fixture with `params=["saved", pytest.param("fresh", marks=[pytest.mark.slow, pytest.mark.timeout(5400)])]`, module-scoped. `"fresh"` calls `feasibility.measure_all()`. The four limit tests (timing, held-out False Alarm rate, detection rate, probe) take `result`. The clean-tree/seed-plan test stays on the saved data only. The non-slow count stays 208, and the slow tier has 4 tests.
- Load-sensitive until ticket 05 (review B2): in the fresh run, the timing test asserts the 10 s `TIMING_LIMIT_S`. The saved measurement (taken at `f0c8f6c`) ran 7.14-7.72 s idle, and CPU-bound steps slowed about 5.5× at 2× oversubscription. So nothing else may run while `check-slow` does. CLAUDE.md says so, and AC 4 requires an idle start. Ticket 05 loosens the limit to about 30 s.

### CLAUDE.md section (text to add, under a new `## Gates` heading)

- **When:** `make test-fast` after every change. `make check` before declaring any work done; it must be green. `make check-slow` whenever the slow tier is relevant (detector, generator or calibration changes). It takes about 40 min, longer than the 10-minute foreground Bash limit, so always run it in the background with output sent to a log. Until ticket 05 lands, run no other gate or heavy job while `make check-slow` runs: its 10 s timing test is load-sensitive. `make fix` is the only target that changes files.
- **Fix the code, never the check.** When a test or check is red, change the code under test, not that test, that check or its config. Adding and changing tests as part of a ticket's work is normal.
- **Weakening moves need the owner's explicit approval**, asked before the change and recorded in the ticket's Comments: changing a tolerance or expected value; adding `skip`, `skipif` or `xfail` (or `strict=False`); suppressing a warning (`filterwarnings`, `warnings.catch_warnings`, `PYTHONWARNINGS`) or a lint (`noqa`, `type: ignore`); narrowing the selected tests (`addopts`, `-m`, `-k`, `--deselect`, `testpaths`, the Makefile); raising or disabling a timeout; editing gate config (the `Makefile`, `[tool.pytest.ini_options]`, `tests/conftest.py`, and the `pytest`/`pytest-timeout` pins and other `[dependency-groups].dev` gate tools).
- **Handoffs quote the gate; they never claim it.** Paste the command, its exit status, pytest's final summary line (e.g. `208 passed in 82.15s`) and `git rev-parse --short HEAD`, plus `-dirty` if the tree had changes. "Tests pass" without that quote does not count.

## Acceptance criteria → change → verification

All verification runs from the repo root. Plants go in a throwaway `tests/test_zz_plant.py`, which is deleted afterwards; `git status --porcelain` must then show only the intended files.

1. **Four targets, locked env.** Change: the Makefile above.
   Verify: `make -n check check-slow test-fast fix` shows `uv run --locked` on every pytest line and `uv lock --check` before `check`/`check-slow`. `make test-fast` → exit 0 and `208 passed`. After the plant in 5a: `make test-fast` stops at `1 failed`, and the next `make test-fast` runs the plant first (it appears first in `-v` order). `make fix` → exit 0, and `git status` is unchanged.
2. **Strict pytest + thread timeout, evidence recorded.** Change: the pyproject block, the dependency, and the table above copied into Comments.
   Verify: the `make check` header shows `timeout: 60.0s` and `timeout method: thread` (pytest-timeout's header lines). Optional hang proof: a test containing `time.sleep(30)`, run with `make check PYTEST="uv run --locked pytest -o timeout=3"`, prints `+++++ Timeout +++++` and a `Stack of MainThread` dump, exit 1 (measured in scratch with pytest-timeout 2.4.0).
3. **Stale lock fails the gate.** Plant: append `"pillow"` to `dependencies` in `pyproject.toml` without running `uv lock`.
   Verify: `make check` → ``The lockfile at `uv.lock` needs to be updated, but `--check` was provided. To update the lockfile, run `uv lock`.``, make exits 2, and no tests run. Revert with `git checkout pyproject.toml`.
4. **Green on current code.** Verify: `make check` → exit 0, `208 passed, 4 deselected`. Then, with the 1-minute load average in `/proc/loadavg` under about 1 (record it in Comments) and no other gate or heavy job running, `make check-slow > .scratch/agent-gates/handoffs/01-check-slow.log 2>&1`, run in the background → exit 0, `4 passed, 208 deselected`, about 40 min. If a worker raises a warning, the run fails with the warning as the exception; fix it where it is raised and do not filter it.
5. **Planted failures, pytest's own messages** (all three measured in scratch with this exact config):
   a. `import numpy as np` / `def test_plant(): np.log(np.array(0.0))` → `E       RuntimeWarning: divide by zero encountered in log`, `1 failed`, exit 1 (make exit 2).
   b. `@pytest.mark.xfail(reason="planted xpass")` on `def test_plant(): pass` → `[XPASS(strict)] planted xpass`, `1 failed`.
   c. `@pytest.mark.slwo` on a test → collection error ``'slwo' not found in `markers` configuration option``, `Interrupted: 1 error during collection`, exit 2.
   After each plant, delete the file and confirm `git status --porcelain` lists only the intended files.
6. **CLAUDE.md protocol.** Change: the section above. Verify by reading it: the four commands with when-to-run, the fix-the-code rule, all six weakening moves from the ticket, and the handoff quote rule are all present.

## Decisions (formerly open questions, all settled)

- **Q1, what the slow tier runs:** owner ruled option B, a `fresh` parametrisation marked `slow`, built on `measure_all` (see "Slow path"). Rejected: A, the driver writes to a temp file through an env-var seam, which needs the clean-tree test skipped; C, leave the tier empty, which contradicts AC 4.
- **Q2, the slow-tier timeout:** owner ruled 5400 s, as a `pytest.mark.timeout` on the `fresh` param only.
- **Q3, the realtime-clock timer:** accept the risk and note it in the pyproject comment (a false red only). Port cadmesh's monotonic conftest only if it is ever seen.
- **Q4, the `PYTHONWARNINGS=error` scope:** `tests/conftest.py`, so a bare `uv run pytest` matches the gate.
