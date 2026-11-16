# 05 plan: required slow tier

- Ticket: `.scratch/agent-gates/issues/05-required-slow-tier.md`
- Spec: `.scratch/agent-gates/spec.md` (owner rulings of 2026-11-10)
- BASE: `23b55ca`
- Review: `.scratch/agent-gates/handoffs/05-plan-review.md`. This plan folds in B1-B3 and N1-N9.
- Rulings: the orchestrator log `05-orchestrator.md` ("Decisions"), from Codex (`scratchpad/05-codex-rulings.md`) plus the orchestrator's own reading.
- Prototype P1: `.claude/worktrees/agent-a0bf8d77155d5b02b/.scratch/agent-gates/handoffs/05-prototype-p1.md`.
- Status: **settled. Nothing is open.** Every weakening move is marked **[W#]**, with the conditions of its approval. Before starting a step, check that its approval is recorded in the ticket's Comments.

## Rulings folded in

| id | ruling | reason (short) |
|---|---|---|
| O1 | **B:** 30 full-frame frames, a collapse check at a declared bad rate of **0.70** | The owner asked for "small" and "about 6 min" and left full-frame false alarms to the full run. The exact rule needs 240 frames and about 15 min. Codex dissented: a 0.90 full-frame detector passes 82% of the time. The plan and the Comments must **not** claim 0.90 protection at 400×1600. |
| O2 | **A:** the 3 timing verdicts count toward the 30-frame total | Asserting each verdict alone costs about 10.5% false red at the pessimistic end, which breaks rule (i). This is the plan's reading of "assert their verdicts". |
| O3 | **A:** tracked `.gitignore` negations for `.claude/hooks/` and `.claude/settings.json` | Distributes the hook reproducibly. Conditions: prove that unrelated local `.claude` state stays ignored, and prove live activation. |
| Q2 → joint budget | Pass counts are chosen **jointly** so that P(any false red) ≤ 1% for the whole gate (Codex medium) | The per-check minimax (280/21/26) sums to 1.13%, above a gate-wide 1%. |
| Q3 | Stamp `tests/protected.py` **whole** | Simple and fails closed. It amends the ticket's exception for non-slow tests (Comments). |
| Q4 | `make measure` joins the hook's targets | It runs about 39 min, beyond the foreground limit. |
| concurrency | An exclusive lock per tree, held from begin through pytest to commit. Hashes and measurement are bound to one run id, and commit rejects a missing or mismatched measurement (Codex high; review N4 and N5) | Two overlapping runs could otherwise stamp code that neither run tested. |
| W3 | The timeout covers the whole module (review B3) | Reruns of a single test or `--lf` pay for the fixture too. |
| W5 | Wording: the full measurement's full-frame bar is **0.95** (`PROBE_MIN_DETECTION_RATE`), not 0.90 | Codex. |
| B1 | `time_frames` takes the case explicitly | It keeps `time_full_frame` and the bench workload unchanged: `TIMING_SEED` with `TIMING_CASE = Case(8, 0)` and the same warm-up. |
| B2 | `make bench` writes `.gate/bench.json` (local). The tracked `.scratch/stripe-detector/bench.json` is written with `--out` and committed **only** at ticket 13, on a speed claim, and once in this ticket as the first record | See Seam 6. |
| P1 | Workers outlive a SIGTERM or SIGKILL of the parent. The runner kills the whole process group and refuses to start while workers are left over | See Seam 1 and the prototype. |

## Findings that shape the plan

These were measured 2026-11-11 at `23b55ca`. No repo file was changed.

**F1. Stored baseline** (`.scratch/stripe-detector/feasibility-gate.json`, commit `f0c8f6c`):
- **Gate, 256×256:** threshold 74.11851980928641 (k = 20 of 2000). Held-out false alarms 7/1000, exact 95% CI (0.00282, **0.014369**). m = 0.2 detected 490/500, CI (**0.96353**, 0.99037).
- **Probe, 400×1600:** threshold 105.80269099368302 (k = 3 of 300). Detected 100/100, CI (**0.96378**, 1). False alarms 3/200.
- **Timing:** median 7.56 s.

**F2. Cost.** Single-process and idle: 0.53 s per 256×256 `analyse` and 6.7 s per 400×1600 one. In the 39-min run, the pool's throughput was about 0.21 s of wall clock per 256×256 frame with 8 workers. A 400×1600 frame cost about as much as 12.6 small ones.

**F3. Fresh seeds.** 80 000-82 999 are used nowhere and are disjoint from every registered range. Starts at multiples of 10 balance `CASES[seed % 10]`.

**F4.** `.git/info/exclude` holds `.claude/`. The review verified that negations in the tracked `.gitignore` override it and leave `skills/`, `worktrees/` and `settings.local.json` ignored.

**F5. Polsigns hook.** It is fail-open on payload errors. It unwraps `bash -c`/`-lc` to depth 5 and strips heredocs. Its escape is a real trailing comment. Its `_tokenize` falls back to `command.split()` on a `shlex` error, which can still block.

**F6. Imports.** `denoisifier/__init__` and `analysis` import `report`, and `__init__` also imports `frame_io`. So the stamped `src` list is an explicit classification, not an import closure.

**F7. Prototype P1** (spawn pool shaped like `score_batch`):
- SIGTERM or SIGKILL to the parent alone: the workers **linger** (still alive at 60 s). Busy ones keep using cores.
- SIGINT to the parent alone: the parent waits for running chunks (up to 44 s).
- SIGINT to the **process group**: everything exits in about 2 s.
- A non-interactive `cmd &` may start with SIGINT ignored.

## Exact-binomial derivation

**Model.** Each frame is scored once at a fixed stored threshold, with no per-run calibration. Detected means `score > threshold`. Counts are Binomial(n, p).
- The stripe-free set is i.i.d.
- The striped sets are stratified (n/10 per case), so their counts are Poisson-binomial. That has no more variance than a binomial with the same mean. The review verified that Hoeffding's bound applies to both tails used, so the binomial bounds below are conservative.
- The three sets use disjoint seeds, so they are independent.

**Operating rule** (ticket, with the joint budget):
- (i) **P(any of the three regression assertions is red) ≤ 1%** when every true rate sits at the pessimistic end of the stored baseline's exact 95% CI.
- (ii) Each check passes a bad detector with probability ≤ 5%:
  - 256×256 detection at 0.90;
  - 256×256 false alarms at 0.04;
  - 400×1600 detection at the declared 0.70 (O1).

**Selection rule** (fixed before any run). The sizes are fixed at n = 300 / 800 / 30. Over all (c, a, c_p) that meet (i) and (ii), take the triple that **minimises the largest pass-bad probability**. Under the independent model the union is computed exactly as 1 - Π(1 - p_i). It is also checked against the Bonferroni sum, so (i) holds even without independence.

### The three checks at fixed sizes

The three checks, at the pessimistic ends from F1:
- **256×256 detection** (n = 300, p0 = 0.96353): P_fr(c) = BinomCDF(c-1; 300, p0) and P_pb(c) = BinomSF(c-1; 300, 0.90).
- **256×256 false alarms** (n = 800, p0 = 0.014369): P_fr(a) = BinomSF(a; 800, p0) and P_pb(a) = BinomCDF(a; 800, 0.04).
- **400×1600 detection** (n = 30, p0 = 0.96378): P_fr(c_p) = BinomCDF(c_p-1; 30, p0) and P_pb(c_p) = BinomSF(c_p-1; 30, 0.70).

These are the per-check values that meet (ii):

| check | count | P_fr | P_pb |
|---|---|---|---|
| detection | c = 279 | 0.172% | 4.58% |
| detection | c = 280 | 0.371% | 2.87% |
| detection | c = 281 | 0.766% | 1.71% |
| false alarms | a = 20 | 0.706% | 1.44% |
| false alarms | a = 21 | 0.350% | 2.38% |
| false alarms | a = 22 | 0.167% | 3.77% |
| probe | c_p = 26 | 0.416% | 3.02% (at 0.90: 82.5%) |
| probe | c_p = 25 | 0.063% | **7.66%**: fails (ii) |

So c_p = 26 is forced. Exhaustive search (`scratchpad/joint.py`) finds exactly three triples that meet (i) and (ii):

| (c, a, c_p) | P_fr: det / FA / probe | union (exact) | Bonferroni sum | largest P_pb |
|---|---|---|---|---|
| **(280, 22, 26)** | 0.371% / 0.167% / 0.416% | **0.951%** | 0.954% | **3.77%** |
| (279, 21, 26) (Codex) | 0.172% / 0.350% / 0.416% | 0.936% | 0.938% | 4.58% |
| (279, 22, 26) | 0.172% / 0.167% / 0.416% | 0.753% | 0.755% | 4.58% |

The per-check minimax (280, 21, 26) has a union of 1.133% and is ruled out. The ticket's start (281, 20, …) is ruled out too: 0.766% + 0.706% alone exceeds 1%.

**Chosen:** detected **≥ 280 of 300**, false alarms **≤ 22 of 800**, full-frame detected **≥ 26 of 30**. Union false red 0.951%. Pass-bad 2.87%, 3.77% and 3.02%.
- At the point estimates (0.98, 0.007, ≈ 0.99), the per-check false reds are 1.0e-6, 2.5e-8 and 1.2e-5.
- A full-frame detector at the full measurement's own bar of 0.95 passes ≥ 26/30 with probability 98.4%. One at 0.90 passes 82.5%. That is the O1 dissent, recorded and not hidden.
- The 30 s timing assertion is a deterministic limit, not a statistical one, so it is outside the budget. It is load-tolerant, not immune to load (W4).

**Note (2026-11-12, owner approval in ticket stripe-detector/05 Comments): the false-alarm baseline.** The false-alarm term's p0 is no longer the held-out count's exact CI end. The stored threshold is the k-th largest of n calibration scores, so its true rate is Beta(k, n + 1 - k), and the held-out count x of N updates it to Beta(k + x, n + 1 - k + N - x). The rule test takes p0 = that distribution's 97.5% quantile (`REGRESSION_FREE_RATE_BOUND_QUANTILE`), reading k, n, x, N from `feasibility-gate.json`; at `317744b`, Beta(32, 2969) gives 1.4636% and a false-red term of 0.209%. The guarantee is averaged over calibration draws, not conditional on one fixed threshold, and assumes i.i.d. continuous Stripe-free scores with no tie at rank k (`test_stored_threshold_rank_is_untied` guards the ranks above k; `test_free_rate_bound_covers_the_true_rate_for_continuous_scores` checks the coverage on uniform scores). Reason: under the old term the rule passed only about 38% of measures for any detector (`.scratch/stripe-detector/handoffs/05-implementer-7.md`). Pass counts, sizes, budgets and bad rates unchanged.

### Timing frames (O2)

The first `REGRESSION_TIMED_FRAMES = 3` seeds of the 30 full-frame seeds are analysed serially in-process and timed. Their scores count once toward the ≥ 26/30. The other 27 go through the pool.

### Determinism

Seeds are fixed, so a run is deterministic. The 1% applies to the draw of the seeds, and to each detector change that keeps the true rates. A red first run on the unchanged detector is a **finding**: stop for the owner. Do not re-seed and do not touch the pass counts.

### Wall clock (estimate)

- Pool: 1100 small frames + 27 × 12.6 ≈ 1440 small-frame units × 0.17-0.21 s ≈ 4-5 min.
- Serial timing: about 25 s. Three pool spawns: a few seconds.
- **Estimate: about 5-6 min.** Measured and recorded in Comments.

### The rule as a test

`test_regression_plan_meets_the_operating_rule` is non-slow and runs in `make check`. From the saved JSON's counts and the protected constants, it recomputes:
- the exact CI ends;
- the union (exact, 1 - Π(1 - p_i)) and the Bonferroni sum, each ≤ `REGRESSION_MAX_FALSE_RED`;
- each P_pb ≤ `REGRESSION_MAX_PASS_BAD` at its declared bad rate.

So when `make measure` stores a worse baseline, `make check` goes red. Re-deriving the counts is then an owner-approved W5, never a silent edit.

## Design

### Seam 1: stamp and runner (`tests/slow_stamp.py`, new; stdlib only)

**The list, defined once:** `STAMPED_FILES`, repo-relative and sorted.

| group | files |
|---|---|
| detector | `src/denoisifier/__init__.py`, `analysis.py`, `_local_stripes.py` |
| generator | `src/denoisifier/synthetic.py` |
| calibration | `src/denoisifier/_calibration.py` |
| slow tier and its imports | `tests/test_slow_regression.py` (new), `tests/feasibility.py`, `tests/cases.py`, `tests/protected.py` (Q3: whole file), `tests/seed_guard.py`, `tests/conftest.py`, `tests/slow_stamp.py` |
| how it runs, and numerics | `Makefile`, `pyproject.toml`, `uv.lock`, `.python-version` |

`NOT_STAMPED_SRC = (cli.py, report.py, frame_io.py, __main__.py, py.typed)` under `src/denoisifier/`. Every file in `src/denoisifier/` must be in exactly one of the two lists (test S5).

**Local state** lives in `.gate/`, which is added to the tracked `.gitignore`:
- `check-slow.lock`
- `check-slow-stamp.json`
- `check-slow-measurement.json`
- `bench.json`

**`python tests/slow_stamp.py run [--root PATH] -- <pytest command>`** (the check-slow runner) does the following, in order:

1. **Lock.** Open `.gate/check-slow.lock` and take `fcntl.flock(LOCK_EX | LOCK_NB)`. If another run holds it, exit 1 with `another make check-slow is running in this tree (pid N, pgid M); wait for it`. The lock is held until the runner exits. The kernel releases it even on SIGKILL.
2. **Pre-flight (P1).** Scan `/proc/*/cmdline` for processes whose argv contains `multiprocessing.spawn` and whose `cmdline[0]` is an absolute path under `<root>/.venv/bin/` (never `/proc/<pid>/exe`: the venv's `python` symlinks to a uv interpreter shared by every uv venv) (B4). If any exist, exit 1, say "another pool is running in this tree (or leftovers)", list their PIDs, and print `kill -INT -- -<pgid>` and then `kill <pids>`. A leftover pool would load the run and skew the timing.
3. **Run id.** `run_id = uuid4().hex`. Hash `STAMPED_FILES` (`hashes_begin`). Delete any old measurement file. Write the pid, pgid and run_id into the lock file, for the kill instructions.
4. **Pytest.** Run the command with `env CHECK_SLOW_RUN_ID=run_id` in a **new session** (`start_new_session=True`), so pytest and its spawned workers share one process group.
   - The runner traps SIGINT and SIGTERM. It sends SIGINT to the group, waits up to 10 s, then sends SIGTERM and SIGKILL to the group, and exits 130 or 143. This covers F7's lingering workers whenever the runner itself can run.
   - On a SIGKILL of the runner, nothing can run. The next pre-flight catches the leftovers, and CLAUDE.md gives the cleanup command.
5. **Verify.** On a nonzero pytest exit, exit with it and write nothing. On zero:
   - re-hash. If the hashes differ from `hashes_begin`, exit 1 naming the files;
   - read the measurement file. If it is missing, or its `run_id` differs, exit 1 (N5);
   - otherwise write the stamp atomically (temp file in `.gate/`, then `os.replace`).

   The stamp holds `{run_id, files: {path: sha256 | "MISSING"}, commit, finished, measurement}`.

**`check`** exits 1 when the stamp is missing or any hash differs. The message:

`make check: the slow tier is stale. Changed since the last green make check-slow: <paths>. Run make check-slow in the background (Bash run_in_background, output to a log; about 6 min) and run no other gate meanwhile. The stamp is per working tree: a fresh clone or worktree needs its own run. Stamped files: tests/slow_stamp.py STAMPED_FILES (ticket agent-gates/05).`

When the stamp is missing, the message says so instead of listing paths.

**Red, interrupted or concurrent runs write nothing.** Only step 5 writes the stamp, after a green pytest, matching hashes and a measurement with the same run id, all under the lock.

### Seam 2: Makefile **[W1]**

```make
check: lock-check lint      ## ... every non-slow test, then the slow-tier stamp (tests/slow_stamp.py)
	$(PYTEST)
	$(UV) python tests/slow_stamp.py check

check-slow: lock-check      ## regression check (~6 min; duration: tests/test_slow_regression.py): background only; writes .gate/ stamp when green
	$(UV) python tests/slow_stamp.py run -- $(PYTEST) -m slow

bench:                      ## speed gate 10 s + ticket-13 target 5 s; idle machine, background; writes .gate/bench.json
	$(UV) python tests/bench.py

measure:                    ## full ticket-03 measurement (~39 min): milestones only, background; rewrites feasibility-gate.json
	$(UV) python tests/feasibility.py
	$(PYTEST) tests/test_feasibility_gate.py
```

- `.PHONY` gains `bench measure`.
- The stamp check runs after pytest, so test results are not hidden.
- `test-fast` is unchanged.

### Seam 3: the regression check

**`tests/feasibility.py`.** These are additions. `measure_all`, `SEED_SETS` and the saved JSON format are unchanged.
- `time_frames(seeds, depth, shape, case_for: Callable[[int], Case]) -> list[tuple[float, float]]` (**B1**) returns (seconds, score) per seed, serial and in-process. Generation is not timed, and there is one untimed warm-up at `GATE.shape`.
- `time_full_frame(repeats)` keeps its exact workload: `TIMING_SEED`, `TIMING_CASE`, the same warm-up `_frame(TIMING_SEED, 0.0, GATE.shape, TIMING_CASE)`, and the same frame analysed `repeats` times. It is not rebuilt on `time_frames` unless both properties are kept. The test `test_time_full_frame_times_the_timing_frame` (non-slow) monkeypatches `analyse` and `_frame` to record their calls. It asserts the warm-up and timed frames are `(TIMING_SEED, 0.0, GATE.shape, TIMING_CASE)` and `(TIMING_SEED, DEPTH, PROBE.shape, TIMING_CASE)` and that `analyse` is called 1 + repeats times. It runs in milliseconds.
- `RegressionPlan` (NamedTuple) holds the shapes, the stored thresholds, the seed ranges, the timed count and the pass counts. `REGRESSION` is built from `protected`.
- `regression_check(plan=REGRESSION, workers=None) -> dict` does, in order:
  1. Times the first 3 full-frame seeds with `case_of`, before any pool runs.
  2. Calls `score_batch` on the other 27, the 300 striped and the 800 free.
  3. Returns the counts, the per-case breakdown, the times and median, `run_info(workers)`, the wall clock, `/proc/loadavg` at start and end, and the threading environment (`OMP_NUM_THREADS` etc. as seen in-process, with a note that NumPy was imported by test collection before `feasibility` set them, so BLAS threading in the in-process timed frames is not pinned (N7)).

  It does no calibration and adds no `calibrating(...)` block.

**`tests/test_slow_regression.py`** (new). It carries `pytestmark = [pytest.mark.slow, pytest.mark.timeout(1200)]` **[W3]**. A module comment is the one source for the slow tier's duration.
- A module-scoped fixture runs `regression_check()`. It writes `.gate/check-slow-measurement.json`, which includes `run_id = os.environ.get("CHECK_SLOW_RUN_ID")`, and returns the dict.
- `test_full_frame_is_analysed_within_30_s`: the median of the 3 timed frames ≤ `SLOW_TIMING_LIMIT_S`. The message prints all times.
- `test_regression_weak_stripes_detected_at_256`: ≥ 280 of 300 at `GATE_STORED_THRESHOLD`. The message prints the per-case counts and: "a detector change that moves the score scale goes red here: run `make measure`, then re-store the thresholds (approved lockfile edit); never edit the pass counts."
- `test_regression_false_alarms_at_256`: ≤ 22 of 800.
- `test_regression_full_frame_detected`: ≥ 26 of 30 at `PROBE_STORED_THRESHOLD`, timed frames included. The docstring says this is a collapse check at a declared 0.70. The 0.95 full-frame bar is `make measure`'s.

### Seam 4: the full measurement leaves `check-slow` (`tests/test_feasibility_gate.py`) **[W2]**

- Remove the `fresh` params from 5 tests, the 5400 s mark and its comment. `measurement` becomes `saved`.
- The saved-file tests stay in `make check` unchanged, `test_full_frame_is_analysed_within_10_s[saved]` included. It checks a stored record, so it is not load-sensitive.
- The docstring now names `make measure`.

### Seam 5: protected numbers (`tests/protected.py` + lockfile) **[W4, W5]**

```python
# Slow-tier regression check (ticket agent-gates/05; derivation: 05-plan.md).
GATE_STORED_THRESHOLD = 74.11851980928641    # = feasibility-gate.json gate.threshold
PROBE_STORED_THRESHOLD = 105.80269099368302  # = feasibility-gate.json probe.threshold
REGRESSION_STRIPED_SEEDS = range(80_000, 80_300)        # 256x256, m = WEAK_DEPTH, 30 per case
REGRESSION_FREE_SEEDS = range(81_000, 81_800)           # 256x256, stripe-free
REGRESSION_PROBE_STRIPED_SEEDS = range(82_000, 82_030)  # 400x1600, m = WEAK_DEPTH, 3 per case
REGRESSION_TIMED_FRAMES = 3      # first 3 probe seeds, timed serially; counted in the 30
REGRESSION_MIN_DETECTED = 280
REGRESSION_MAX_FALSE_ALARMS = 22
REGRESSION_PROBE_MIN_DETECTED = 26
REGRESSION_MAX_FALSE_RED = 0.01  # gate-wide: union over the three checks
REGRESSION_MAX_PASS_BAD = 0.05   # per check
REGRESSION_BAD_DETECTION_RATE = 0.90
REGRESSION_BAD_FALSE_ALARM_RATE = 0.04
REGRESSION_PROBE_BAD_DETECTION_RATE = 0.70  # declared (O1); not the 0.95 full-run bar
SLOW_TIMING_LIMIT_S = 30.0       # check-slow: real slowdowns only (owner, 2026-11-10)
BENCH_REPEATS = 5
TARGET_TIMING_S = 5.0            # ticket 13's target; make bench reports it
# test_slow_regression_plan.py tiny-plan run (test block)
REGRESSION_TINY_STRIPED_TEST_SEEDS = range(60, 62)
REGRESSION_TINY_FREE_TEST_SEEDS = range(62, 64)
REGRESSION_TINY_PROBE_TEST_SEEDS = range(64, 66)
```

`TIMING_LIMIT_S` (10.0) stays, asserted by `make bench`. The disjointness test discovers the new ranges without being edited. `CALIBRATION_SEEDS` is untouched.

**Consistency tests** (non-slow, `tests/test_slow_regression_plan.py`, new, unstamped):
- `test_stored_thresholds_are_the_saved_measurement`: exact equality with the saved JSON.
- `test_regression_plan_meets_the_operating_rule`: see the derivation.
- `test_regression_sets_are_balanced_over_the_cases`: each start and length is a multiple of 10.
- `test_regression_check_runs_on_a_tiny_plan`: at 40×40, with the tiny seeds, **`workers=2`** (N8), real workers and the real `regression_check`. It asserts the keys and counts.
- `test_time_full_frame_times_the_timing_frame` (B1).

### Seam 6: `make bench` (`tests/bench.py`, new) and the B2 decision

`main(argv)` does the following:
- installs the seed guard;
- records `/proc/loadavg`;
- runs `feasibility.time_full_frame(repeats=BENCH_REPEATS)`. The workload is unchanged (B1). The script imports `feasibility` before NumPy, so BLAS is single-threaded. That is recorded as `threads`. Because check-slow's in-process frames are not pinned, the two records are not directly comparable (N7).
- records `/proc/loadavg` again;
- writes `--out`, default `.gate/bench.json`. The record holds commit (plus `-dirty`), cpu, logical cpus, python, numpy, scipy, threads, loadavg at start and end, seconds, `median_s`, `limit_s` 10, `target_s` 5, `meets_limit` and `meets_target`.

Exit codes and messages:
- It exits 1 with a message when `median_s > TIMING_LIMIT_S`.
- It prints the 5 s target status without failing.
- It warns, without failing, when the 1-minute loadavg at start is > 1.0.

**B2: when is a bench record committed?** By default `make bench` writes the git-ignored `.gate/bench.json`, so a routine run never dirties the tree. A tracked record, `uv run --locked python tests/bench.py --out .scratch/stripe-detector/bench.json`, is committed only:
- (a) once in this ticket, as the first record of the timing split;
- (b) at ticket 13, the speed budget;
- (c) when a handoff makes a speed claim.

Why:
- A speed number is evidence only when someone cites it. A record committed after every run would churn and mix busy-machine runs into history.
- A routine run that left a tracked file modified would also make `run_info`'s `-dirty` rule fire on unrelated work, because `.scratch` is outside the dirty paths but still shows in `git status`.
- The citing handoff names the committed record's commit, as ticket 03 did with `feasibility-gate.json`.

`tests/test_bench.py` (non-slow) monkeypatches `time_full_frame`. With times at a 7 s median, it checks that every field is written to `tmp`, that `meets_target` is False and that the exit code is 0. With a 10.5 s median, the exit code is 1 and the message is given. With no `--out`, the record goes to `.gate/bench.json` (monkeypatched root).

### Seam 7: the hook (`.claude/hooks/require_background_gate.py` + `.claude/settings.json`)

Copy from polsigns, then:
- `_LONG_TARGETS = {"check-slow", "bench", "measure"}`.
- Unparseable means **allow**: on a `shlex` `ValueError`, `_tokenize` returns `None` and the scan returns `[]`.
- The deny text has no conda. It says:
  - re-issue with `run_in_background: true`, as `make check-slow > .scratch/<feature>/handoffs/NN-check-slow.log 2>&1; echo "EXIT=$?" >> <log>`;
  - run nothing else meanwhile, and never pipe through `tee`;
  - after an interruption, check for leftover workers (CLAUDE.md);
  - the escape is `# hook-allow-foreground`;
  - the pytest-timeout paragraph is reworded for 60 s / 1200 s.
- Fail-open, the wrapper unwrapping, heredoc stripping, the escape rule, `-n` allowance and `run_in_background: true` → allow are all kept.

`settings.json` registers PreToolUse, matcher `Bash`, `python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/require_background_gate.py"`.

**Tracking (O3=A).** Add to the tracked `.gitignore`: `!/.claude/`, `/.claude/*`, `!/.claude/hooks/`, `!/.claude/settings.json`. Conditions:
- `git check-ignore -v` shows `.claude/skills`, `.claude/worktrees` and `.claude/settings.local.json` still ignored, and the hook and `settings.json` not ignored;
- `git status --porcelain --ignored .claude` shows nothing else new;
- `ruff check --show-files` lists the hook.

**Live activation:** P4. If it is not refused, the owner must approve it in `/hooks` or restart the session. Record that.

`tests/test_require_background_gate.py` (non-slow, in-process through `main()`, plus one subprocess for the entry point):
- **Refused:**
  - plain targets: `make check-slow`, `make bench`, `make measure`;
  - with options or prefixes: `make -C . check-slow`, `timeout 5 make check-slow`, `timeout 900 make check-slow`, `true; make check-slow`;
  - wrapped: `bash -lc 'make check-slow'`, `bash -c "cd x && make check-slow"`;
  - `run_in_background` false or absent;
  - the marker only inside quotes.
- **Allowed:**
  - other targets: `make check`, `make test-fast`, `make fix`;
  - dry run and mentions: `make -n check-slow`, `git grep check-slow`;
  - background or escape: `run_in_background: true`, the trailing escape comment;
  - data, not commands: a heredoc body with `make check-slow`;
  - fail-open inputs: an unparseable command, a non-Bash tool, empty stdin, malformed JSON.

## Acceptance criteria → tests (real path)

| AC | proof |
|---|---|
| 1. A green check-slow writes the stamp; red or interrupted writes nothing; the list is defined once and documented | `tests/test_slow_stamp.py` (non-slow; real `slow_stamp.main` on a `tmp_path` root holding copies of `STAMPED_FILES`; the pytest command replaced by small `python -c` stubs that write the measurement with `$CHECK_SLOW_RUN_ID` and exit 0 or 1):<br>**S1** a green stub writes the stamp, then `check` passes.<br>**S2** a red stub writes nothing, and an earlier stamp stays byte-identical.<br>**S2b** a stub that edits a stamped file: exit 1 naming it, no stamp.<br>**S2c** a stub that writes no measurement, or one with another `run_id`: exit 1, no stamp (N5).<br>**S2d** a second `run` while the lock is held: exit 1 with the message (concurrency).<br>**S2e** a stub that spawns a child in its group and sleeps, then SIGTERM to the runner: the group is gone within 15 s, and no stamp is written (F7).<br>**S2f** pre-flight: a planted fake process is not practical, so `find_leftover_workers(proc_root)` is tested on a fake `/proc` tree under `tmp_path`, including a worker from another venv (not counted) and one whose `exe` symlink resolves to the shared interpreter (B4).<br>**S7** `make -n check-slow` from the real Makefile shows `slow_stamp.py run -- … pytest -m slow`.<br>**Live:** the final background run writes `.gate/check-slow-stamp.json`; P5. |
| 2. check fails on a stale stamp, names the files and says background; docs, CLI, report and non-slow tests never need it | **S3** a stamped edit makes `check` exit 1 with the exact message, naming only that path.<br>**S4** a missing stamp gives its message.<br>**S6** parametrized over `README.md`, `GLOSSARY.md`, `docs/adr/0001-*.md`, `src/denoisifier/{cli,report,frame_io,__main__}.py`, `tests/test_cli.py`, `tests/test_analyse.py`: none is stamped, and an edit keeps `check` green.<br>**S5** `test_stamped_files_cover_the_slow_tier`: `src/denoisifier/*` is classified exactly once, and every `tests/*.py` with `pytest.mark.slow`, its transitive `tests/` imports (AST) and `conftest.py` are stamped.<br>**S7** `make -n check` ends with `slow_stamp.py check`.<br>**Q3 exception:** `tests/protected.py` is stamped whole (Comments).<br>**Live:** P1, P2. |
| 3. The stamp is local and git-ignored; the list and rule are protected in CLAUDE.md | **S8** `git check-ignore -q .gate/check-slow-stamp.json` exits 0. CLAUDE.md (step 10). |
| 4. Timing split | `test_full_frame_is_analysed_within_30_s` (slow; the times are recorded in the measurement and stamp). `test_bench.py`. `test_time_full_frame_times_the_timing_frame`. **S7b**: `make -n check` and `make -n check-slow` mention neither `bench.py` nor `feasibility.py`. **Live:** one background `make bench`, its record committed (B2a). |
| 5. Slow-tier shrink | The derivation. `test_regression_plan_meets_the_operating_rule`, `test_stored_thresholds_are_the_saved_measurement`, `test_regression_sets_are_balanced_over_the_cases`, `test_regression_check_runs_on_a_tiny_plan`, `test_seed_sets_are_disjoint_and_unused`, `test_protected_numbers_match_the_lockfile`. The four slow tests in the real `make check-slow`. Measured wall clock goes in Comments. |
| 6. Hook | `tests/test_require_background_gate.py`. **Live:** P4. |
| 7. Proof | P0-P5. |

## Planted-case proof (nothing committed)

Run on the final commit, after step 12's green `make check-slow`. The stamp is content-addressed, so the order matters.

- **P0.** Before step 12, `make check` is red with the missing-stamp message. After it, `make check` is green ("after a green check-slow, check is green again").
- **P1.** Append `# plant` to `src/denoisifier/analysis.py`. Expect `make check` to exit 2 with the stale message naming `src/denoisifier/analysis.py`, while pytest's own summary is green. Revert with `git checkout --`. `make check` is green again with no re-run. Record both.
- **P2.** Append a comment to `src/denoisifier/cli.py` and `README.md`. `make check` stays green. Revert.
- **P3.** Create `src/denoisifier/_plant.py`. Expect `test_stamped_files_cover_the_slow_tier` red, naming it. Delete it.
- **P4 (N2).** A foreground Bash call `timeout 5 make check-slow`. Expect it refused with the hook's message. If the hook is not live, the call ends after 5 s: no harm, and see Seam 7. Also try `bash -lc 'timeout 5 make check-slow'`.
- **P5 (P1, N1).** Start `make check-slow` in the background. After about 60 s, read the pgid from `.gate/check-slow.lock` and send `kill -INT -- -<pgid>`. Expect:
  - a nonzero EXIT in the log;
  - `sha256sum .gate/check-slow-stamp.json` unchanged;
  - `pgrep -f '[m]ultiprocessing.spawn'` (scoped to this tree's venv) empty within 15 s.

  Then repeat with `kill -TERM <runner pid>`, which goes through the runner's trap. If anything lingers, kill it by pid and record it. Never use `pkill -f 'pytest -m slow'`: it matches the calling shell (N1).

Afterwards, `git status --porcelain -- src tests Makefile pyproject.toml CLAUDE.md .claude .gitignore` shows nothing beyond the intended work.

## Weakening moves and their approval conditions

The orchestrator approves each move from Codex plus its own reading, and records it in Comments.

- **W1. Makefile** (gate config). The `check` stamp step, the `check-slow` runner, and the `bench` and `measure` targets. *Condition (Codex): only with run isolation, meaning the lock, run id and measurement binding of Seam 1.*
- **W2. Narrowing the selected tests.** The full ticket-03 measurement (the `fresh` params of 5 tests) leaves `check-slow`, by the owner ruling of 2026-11-10 and O1=B. *Codex disagreed until full-frame protection was settled. The orchestrator ruled O1=B. The Comments state that the full-frame 0.95 bar is enforced only by `make measure` at milestones.*
- **W3. Raising a timeout.** `pytestmark` timeout of **1200 s** on the whole `tests/test_slow_regression.py` module. *Condition: measure the idle wall clock first. If idle exceeds 400 s (N/3), stop and re-ask with the number. Check that a single selected test (`pytest -m slow -k false_alarms`) completes under the mark.*
- **W4. Changing a tolerance.** The slow-tier timing goes from 10 s to `SLOW_TIMING_LIMIT_S = 30.0`; 10 s moves to `make bench`. *Described as load-tolerant, not load-immune.*
- **W5. Lockfile additions only.** The Seam 5 names. No existing line changes. *Condition: the joint design above is final. The wording keeps the full-run full-frame bar at 0.95 (`PROBE_MIN_DETECTION_RATE`).*
- **W6. CLAUDE.md.** *Condition: it documents the real write targets (B2), the manual threshold and baseline update after `make measure` (N6), the per-tree stamp (N3), the `protected.py` exception (Q3) and the worker cleanup (P1).* See step 10.
- **Not weakening:**
  - new files: the hook and its test, `slow_stamp.py`, `bench.py`, the new non-slow tests;
  - `.gitignore`.

  This ticket makes no edit to `conftest.py`, `[tool.pytest]`, `[tool.ruff]`, `[tool.mypy]` or `seed_guard.py`, and adds no `calibrating(...)` block and no `CALIBRATION_SEEDS` change. **If any turns out to be needed, stop and ask.**

## Order of work

1. **[W4, W5]** Add the Seam 5 constants and lockfile lines. Run `make test-fast`. Commit.
2. Add `time_frames` (B1), `RegressionPlan` and `regression_check` in `feasibility.py`, and `tests/test_slow_regression_plan.py`. Run `make test-fast`. Commit.
3. **[W3]** Add `tests/test_slow_regression.py` with the module `pytestmark`. Do not run it.
4. **[W2]** Strip the `fresh` params from `test_feasibility_gate.py`. Run `make test-fast`. Commit 3 and 4 together.
5. Add `tests/slow_stamp.py` (runner, lock, pre-flight, group kill, check) and `tests/test_slow_stamp.py`, and add `.gate/` to `.gitignore`. Run `make test-fast`. Commit.
6. **[W1]** Change the Makefile. Run `make check`. Expect red **only** on the missing stamp, with pytest's summary green. Commit.
7. Add `tests/bench.py` and `tests/test_bench.py`. Run `make test-fast`. Commit.
8. Add the hook, `settings.json`, the `.gitignore` negations and the hook test. Run the O3 checks (`git check-ignore -v`, `git status --ignored`, `ruff check --show-files`). Run `make check`, which is still red only on the stamp. Commit.
9. Measure idle: one `pytest -m slow -k false_alarms` run in the background, under the lock-less direct command. It is a timing probe only and writes no stamp. If idle exceeds 400 s, stop for W3.
10. **[W6]** CLAUDE.md, Gates section:
    - "When": `make check-slow` runs when `make check` reports the stamp stale. It takes about 6 min, always in the background (the hook enforces this), and nothing else runs meanwhile. Replace the "only when `src/` changed / cite that run's quote" text and the "Until ticket agent-gates/05 lands" clause. The duration pointer now names `tests/test_slow_regression.py`.
    - **Write targets** (B2): `make fix` is the only target that changes source. `check-slow` writes local `.gate/` state (lock, stamp, measurement). `bench` writes `.gate/bench.json`; a tracked bench record is written with `--out` only at ticket 13 or for a speed claim. `measure` rewrites the tracked `feasibility-gate.json`.
    - **Per-tree stamp** (N3): every fresh clone and every `.claude/worktrees/*` worktree needs its own `make check-slow` before its `make check` is green. Orchestrated tickets budget for it.
    - **After `make measure`** (N6): the stored thresholds in `tests/protected.py` must then be updated by hand to the new JSON values. `test_stored_thresholds_are_the_saved_measurement` forces that edit, and it is an approved W5 lockfile edit. If `test_regression_plan_meets_the_operating_rule` goes red, re-deriving the pass counts is an owner decision. Never edit the pass counts to make check-slow green.
    - **Interrupted runs** (P1): stop with `kill -INT -- -<pgid>` (the pgid is in `.gate/check-slow.lock`). Before the next run, the runner refuses while workers are left over and prints the cleanup.
    - **Protected surfaces:**
      - `STAMPED_FILES`/`NOT_STAMPED_SRC` and the stamp rule (`tests/slow_stamp.py`, the `check`/`check-slow` recipes);
      - the regression seeds, sizes, pass counts, rule constants and stored thresholds (lockfile);
      - the hook and its `settings.json` entry.

      Weakening moves added: removing a file from `STAMPED_FILES` or moving one to `NOT_STAMPED_SRC`, editing `slow_stamp.py`, and removing or loosening the hook.
    - **Q3 exception:** an edit to `tests/protected.py`, even one for non-slow test seeds, requires `make check-slow`.

    Commit.
11. `make check` in the foreground. Expect red only on the stamp.
12. **Gates on the committed HEAD:**
    - `make check-slow` **in the background**: `make check-slow > .scratch/agent-gates/handoffs/05-check-slow.log 2>&1; echo "EXIT=$?" >> …`, with `/proc/loadavg` at start and end, and nothing else running.
    - Record the wall clock against the 6-min target, plus the timing median.
    - A red regression assertion on the unchanged detector is a **finding**: stop for the owner.
    - Then run `make check`, which is now green.
13. `make bench` in the background on an idle machine. Then run `tests/bench.py --out .scratch/stripe-detector/bench.json` (B2a) and commit the record.
14. Plants P1-P5.
15. Ticket Comments: everything in the list below, plus the measured wall clock, the bench record, the plant evidence and the gate quotes (command, exit status, pytest's final summary line, `git rev-parse --short HEAD` with `-dirty` if applicable).

## Comments to record (ticket)

1. **O1 = B** (orchestrator, from Codex plus its own reading). Full frame: 30 frames, ≥ 26, a collapse check at a declared 0.70. Reason: the owner ruling's "small" and "about 6 min", and full-frame false alarms already left to the full run; the exact rule needs 240 frames and about 15 min. **Codex dissent:** a 0.90 detector passes 82.5%. No 0.90 protection at 400×1600 is claimed. The full-frame 0.95 bar is enforced only by `make measure` at milestones (stripe-detector 05, 07, 13).
2. **O2 = A.** The 3 timing verdicts count in the ≥ 26/30, which is the plan's reading of "assert their verdicts". Reason: individual assertions cost about 10.5% false red, against rule (i).
3. **O3 = A.** `.gitignore` negations override the owner's `.git/info/exclude` for `.claude/hooks/` and `settings.json` only. Reason: a reproducible hook that ruff lints. Evidence: the `check-ignore` output and the live P4.
4. **Joint false-red budget** (Codex medium). The gate-wide union is ≤ 1%. Counts are 280 / 22 / 26: union 0.951%, Bonferroni sum 0.954%, pass-bad 2.87% / 3.77% / 3.02%. Of the three feasible triples, this one minimises the worst pass-bad. The ticket's start (281/20) and the per-check minimax (280/21) exceed 1%.
5. **Q3.** `tests/protected.py` is stamped whole. This amends AC2's "tests outside the slow tier never require it": edits to non-slow test seeds do. Reason: it is simple and fails closed.
6. **Q4.** `make measure` is in the hook. Reason: about 39 min, which no foreground call survives.
7. **Concurrency** (Codex high; review N4 and N5). A per-tree `flock` across the run, a run id binding the hashes and the measurement, and commit refusing a missing or mismatched measurement.
8. **P1 prototype.** Workers linger after SIGTERM or SIGKILL of the parent. The runner kills the process group and pre-flight refuses leftovers. Recorded with the prototype's table.
9. **B1.** The bench and `time_full_frame` workload is unchanged (`TIMING_SEED`, `TIMING_CASE`, warm-up).
10. **B2.** Bench records stay local by default. A tracked record is committed here once, then at ticket 13 and on speed claims. The CLAUDE.md "only target that changes files" rule was reworded (W6).
11. **B3 / W3.** A module-wide 1200 s timeout, with the measured idle time and the single-test check.
12. **W1-W6.** Each approval, its reason and its condition, as listed above, including W5's correction that the full-run full-frame bar is 0.95.
13. **N7.** Timing in the check-slow process is not BLAS-pinned, while bench is. The records are not directly comparable.
14. **B4.** Pre-flight matches workers on `cmdline[0]` under `<root>/.venv/bin/`, not `/proc/<pid>/exe` (shared uv interpreter). The fake `/proc` test includes an other-venv worker.
15. **N10.** The pre-flight refusal says "another pool is running in this tree (or leftovers)", since a live tiny-plan or `make measure` pool also trips it.
