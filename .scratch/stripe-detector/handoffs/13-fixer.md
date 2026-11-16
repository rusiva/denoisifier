# Ticket 13 fixer handoff

- Continues `13-implementer-5.md`; fix list F1-F7 from `13-orchestrator.md` ("Code review sort"). Branch `main`.
- **Status: CLOSED per the owner ruling (`d4ea2f2`): cold-CLI bench miss accepted; see "Close". The history below records the stop.** The tracked bench record run (`tests/bench.py --out .scratch/stripe-detector/bench.json`, the same rule as `make bench`) measured a cold CLI median of 5.28 s, above `TARGET_TIMING_S` = 5.0, EXIT=1. Nothing was rerun to get a green, and nothing was loosened. `make check` and the AC 3 stage-timing driver have not been run.
- Logs: `.scratch/stripe-detector/handoffs/13-fixer-*.log` (untracked). Every gate ran alone, in the background, and each log starts with `uptime` and `git rev-parse --short HEAD`. During all gates, the only tracked change outside `src`/`tests` was the orchestrator's own uncommitted edit to `13-orchestrator.md`.

## Commits

| commit | what |
|---|---|
| `b928464` | F1-F7 (below) |
| `a91fa51` | `make measure` record + `GATE_STORED_THRESHOLD`/`PROBE_STORED_THRESHOLD` |
| `4b6f3de` | stripe re-store: `stripe_free_calibration.json` + `PACKAGE_STORED_THRESHOLD`, `_5PCT`, `PACKAGE_CALIBRATION_DIGEST` |
| `c723810` | break/Fork re-store: `break_fork_free_calibration.json` + `PACKAGE_BREAK_FORK_CALIBRATION_DIGEST` (thresholds unchanged) |

## Fixes (`b928464`)

- **F1:** `tests/stage_timings.py` has these columns: BASE (P1's table, quoted in `BASE_P1`), then every frame at threads 1 and at the default thread count. It adds a warm-pipeline row and the adopted and dropped slices (`SLICES`). `run_once`/`stage_medians` take `threads` (via `analysis._analyse`). Built test-first: 2 new tests in `tests/test_stage_timings.py`.
- **F2:** the P6 typical frame gets its own seed, `SPEED_TYPICAL_TEST_SEED = 39`, free in `TEST_SEED_BLOCK` (39, 82, 87 and 99 were free). The `SPEED_TEST_SEED` comment now reads "only tests/speed.py".
- **F3:** `tests/test_spectrum_filters.py` ids and comment now say `P3-nyquist-clip-*`.
- **F4:** `SPEED_DEPTH = 0.5`, `SPEED_FORK_DIRECTION = 1` and `SPEED_SLOW_REPEATS = 3` move into `tests/protected.py` and the lockfile. `tests/speed.py` and `tests/test_speed.py` import them.
- **F5:** one helper, `_local_stripes._window_sigmas(period, across, along)`, used by the bank (`gabor`/`local_mean`), `_local_phase.break_response` and `analysis._Filters.size_depth`. `_bank_sigmas` is removed, and the test imports the helper (new test `test_window_sigmas_are_the_spatial_window_in_frequency`).
- **F6:** tests use `_local_stripes._THREADS_ENV`. In `feasibility.py` it is imported locally, so no `noqa` was needed.
- **F7:** in `_matches`: `workers`, `queue`, `in_flight`, `period`, `buffers`, `match`. `_match_period` names both phases of `_BankBuffers.energy` (`stripe_energy`, then `reference_energy`, with comments), and the `_BankBuffers` docstring states this.
- Approvals used: the ticket Comments of 2026-11-16 (code-review lockfile additions). No weakening move was made.

## Gates

- **Harness (F5/F7, exact) vs `1a3f864`**, tree `6d574f5-dirty` (the fixes, uncommitted, identical to `b928464`):
  - `identity.py compare ref.pkl new.pkl exact` at threads 1: `exact: 58 frames, 0 differences -> PASS`, EXIT=0.
  - Also at threads 4 (`new4.pkl`, against the threads-1 reference): `exact: 58 frames, 0 differences -> PASS`, EXIT=0.
- **`make test-fast`**, `6d574f5-dirty` (= `b928464` content): EXIT=0, `994 passed, 653 deselected in 623.12s (0:10:23)`. Load at start was 6.58, the trailing average of the harness, which had just ended.
- **`make measure`**, `b928464`, load 1.30 at start: EXIT=0, `16 passed in 0.60s`.
  - Gate threshold 49.7159577445053 → 49.71595774450364; probe 85.17105365821853 → 85.17105365821811 (both ~1e-14 relative).
  - Detected 500/500 and 100/100, false alarms 12 and 2: unchanged.
  - Timing median 5.41 → 2.70 s.
  - `test_regression_plan_meets_the_operating_rule` and `test_stored_thresholds_are_the_saved_measurement`: `2 passed`.
- **Stripe driver** (`tests/threshold_calibration.py --out src/denoisifier/stripe_free_calibration.json`), `a91fa51`: EXIT=0. The 1 % threshold went 100.80547983306298 → 100.80547983306502 and the 5 % one 60.91880891139576 → 60.91880891139533. Digest `648eb3f6…`. Its load warning was the trailing average of `make measure`; the output is deterministic.
- **Break/Fork driver**, `4b6f3de`: EXIT=0. Thresholds stay at breaks 0.1 and forks 0.3, with S_b and S_f max 0.0 on 300 frames. Digest `e36c419c…` (it moved because it names the new stripe digest).
- **`make check-slow`**, `c723810`, load 1.68: EXIT=0, `7 passed, 1640 deselected in 793.96s (0:13:13)`. AC 7 is green.
- **`make check-held-out`**, `c723810`, load 1.70: EXIT=0, `7 passed, 1640 deselected in 2083.24s (0:34:43)`.
- **`make bench`**, `c723810`, load 0.99: EXIT=0.
  - Timing frame median 2.20 s.
  - Speed frame warm pipeline: median **4.23 s** (4.15, 4.23, 4.54, 4.37, 3.97).
  - Cold CLI: median **4.59 s** (4.56, 4.56, 4.71, 4.73, 4.59). Both are under 5.0.
- **Tracked record** `uv run --locked python tests/bench.py --out .scratch/stripe-detector/bench.json`, `c723810`, run straight after, load 0.96 at the `uptime`. The script itself warned of load 2.25 at its own start.
  - **EXIT=1**: `make bench: cold CLI median 5.28 s exceeds the 5.0 s target`.
  - Warm median 4.49 s (4.75, 4.61, 4.41, 4.34, 4.49); cold CLI 5.22, 5.54, 5.28, 5.06, 5.54.
  - The written file is kept at `handoffs/13-fixer-bench-record-miss.json` (untracked). The tracked `bench.json` was restored to HEAD, not committed.

- **Tracked record, the one idle rerun the orchestrator ruled** (ticket Comments, `0750b7c`): `uv run --locked python tests/bench.py --out .scratch/stripe-detector/bench.json`, HEAD `0750b7c` (src/tests clean), started directly after the orchestrator checked the machine was idle. `uptime` at start: load 0.29, 0.30, 0.91; the script printed no load warning.
  - **EXIT=1**: `make bench: cold CLI median 5.22 s exceeds the 5.0 s target`.
  - Warm median **4.03 s** (4.44, 3.97, 4.11, 4.0, 4.03). Cold CLI 5.37, 5.22, 4.91, 5.24, 5.01. The timing frame took 2.59 s.
  - The written file is kept at `handoffs/13-fixer-bench-record-miss-2.json` (untracked), and the tracked `bench.json` is restored to HEAD. Per the ruling: stop, no third run.
  - Log: `13-fixer-bench-record-2.log`. My first rerun attempt never started: its idle-wait loop matched its own command line, and the orchestrator killed it.

## Close (owner ruling at `d4ea2f2`: accept the cold-CLI miss, no target changed; ticket 23)

- Tracked `bench.json` = `handoffs/13-fixer-bench-record-miss-2.json` exactly as measured (warm 4.03 s, cold CLI 5.22 s, EXIT=1 at `0750b7c`), no rerun: commit `c8095cb`. `make bench` stays red on the cold median by design (ticket 23).
- **`make check`**, `c8095cb` (src/tests clean), load 1.89 at start: EXIT=0, `1633 passed, 14 deselected in 1321.61s (0:22:01)`, slow-tier stamp check passed (`13-fixer-check.log`).
- **Stage-timing driver** `uv run --locked python tests/stage_timings.py`, `c8095cb`, load 1.87 at start (trailing `make check`; nothing else running): EXIT=0 → `.scratch/stripe-detector/stage-timings.md`. Speed frame warm pipeline 6.39 s at threads 1, 4.73 s at 4 (BASE 8.68); bank 3.25 / 1.63 s (BASE 5.63); break pass 1.80 s (BASE 1.61); cold CLI 4.52 s (BASE 9.46); import 0.30 s wall.
- Spec pointer under user story 39 (`spec.md`).

## Finding (for the orchestrator)

- **Idle, the cold CLI misses 5 s.** It was 5.22 s against a warm pipeline of 4.03 s, so cold start costs about 1.2 s on top (interpreter, imports, CSV read and JSON write in a fresh process). `make bench`'s green 4.59 s was the low end of the spread.

- AC 1's cold CLI sits right at the target on this box: 4.59 s in one run, 5.28 s in the next, 2 minutes later.
- The warm speed pipeline, 4.23-4.49 s at the default 4 threads, is well above slice 4's go/no-go (3.39 s at 4 threads, load 0.91) and the plan's projection (~3.4 s warm, ~3.9 s cold without slices 6 and 7).
- Possible causes, not investigated:
  - the machine was warm, after ~2 h of heavy gates (thermal or clock state);
  - the load just before the run;
  - a real slowdown since `231aabb`. The F5/F7 changes are bit-identical and add no work, but this is not timed.
- Per the stop rule I did not rerun the record or `make bench` to get a green.
- To decide: time on a cold, idle machine (for example after a pause), or treat the margin as too thin and look at follow-ups 20/22.

## Not done (after the stop)

1. A tracked `bench.json` that meets the target.
2. `make check`. The slow stamp is fresh for `c723810`.
3. The AC 3 stage-timing driver (`uv run --locked python tests/stage_timings.py`, background, idle) → `.scratch/stripe-detector/stage-timings.md`, plus the one-line pointer under `spec.md` user story 39 (plan §4).
4. Cleanup:
   - the reference worktree at `/tmp/claude-1000/-home-rusiva-dev-denoisifier/b0f0769d-6d29-4437-ade7-5f765a0b9eaa/scratchpad/ref` (`git worktree remove`);
   - the handoff cleanup lists of implementers 1-5.
