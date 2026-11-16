# Handoff: parallel fast suite (pytest-xdist) prototype

Origin: the retrospective of stripe-detector ticket 05. The owner approved action items #1 (this prototype), #3 (CLAUDE.md gate order, done as `4b2e477`) and #4 (orchestrate skill, done). Items #2, #5 and #6 wait for **one** owner approval request, which you write after finishing step 1 below.

## State

- **Report so far:** `.scratch/agent-gates/xdist-prototype.md` (main tree). It has every timing below, the risks and the proposed config.
- **Worktree:** `/home/rusiva/dev/denoisifier/.claude/worktrees/agent-a8dfa301eb036d34b`, branch `worktree-agent-a8dfa301eb036d34b`, at HEAD `1cec498`, with uncommitted changes. It is throwaway: nothing in it lands on main.
  - `pyproject.toml` and `uv.lock`: `pytest-xdist` is added to the dev group.
  - `tests/test_analyse.py`: `@pytest.mark.xdist_group("sweep")` is on the three sweep tests, at lines 586, 602 and 617. Those tests share `_sweep_report`'s `@cache` (line 578).
- **Logs:** `/tmp/claude-1000/-home-rusiva-dev-denoisifier/72618a23-dbd5-4573-9e6c-b83c3532a4a4/scratchpad/run_*.log`. That directory may be gone after a reboot; the report has the numbers.
- **Nothing is running.** The first `loadgroup` run was stopped before it recorded anything.

## Results so far (fast suite, 732 tests, load < 2 at the start of each run)

| Run | Wall time | Result | Slowest test (timeout 60 s) |
|---|---|---|---|
| Serial | 442.9 s | 732 passed | 16.1 s |
| `-n 4 loadfile` | 420.3 s | 732 passed | 16.3 s (`test_analyse.py` lands on one worker) |
| `-n 4 load` | 230.1 s | 732 passed | 26.9 s |
| `-n 6 load` | 239.4 s | 732 passed | 45.4 s |
| `-n 8 load` | 251.8 s | 1 failed | the 60 s timeout killed a worker |
| `-n 4 worksteal` | 265.1 s | 732 passed | 33.2 s |
| `-n 4 load`, random order, twice | 315.6 s, 286.3 s | 732 passed, both | 51.9 s, 43.0 s |

- **Cause of the slow tests:** under `load`, every worker builds the `two-region` sweep cache again. On top of that, the 640×1024 frames compete for memory bandwidth, so each sweep test runs 2–3× slower.
- **Checked and fine under xdist:** the seed guard refuses calibration seeds inside the workers, `filterwarnings = error` still fails tests, no test writes a shared file, and random order caused no failures.
- The machine has 8 physical cores and 16 threads. Run with `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`.

## Next steps

**Status 2026-11-13:** step 1 is done. `loadgroup` was ruled out after one run (378 s; slowest test 39 s); see the report's Recommendation update. Step 2 is now an open decision: either make the slowest fast tests about 10 s or less serially, or keep the suite serial.

1. **Time `loadgroup` in the worktree.** Wait until `uptime` shows a 1-minute load below 2; the owner's raytracing project often loads the machine. Run each timing in the background with output to a log and `; echo "EXIT=$?" >> <log>`, one at a time. Use the worktree's `uv run --locked pytest -q --durations=15 -n 4 --dist loadgroup`:
   - once with `-p no:randomly`;
   - once in random order;
   - once at `-n 6`.

   Record wall time, the summary line and the slowest test for each. The step is done when all three rows are in the report.
2. **Decide on the numbers:**
   - It is safe if the slowest test stays at 30 s or less in both orders, with a clear margin under 60 s.
   - If it isn't safe, the fix is to split the slow tests, as commit `e70d99d` did. Raising the timeout is a weakening move and is off the table.
3. **Write the owner one approval request** that covers all three items, so they share one `make check-slow`:
   - **#2, parallel suite:** pin `pytest-xdist` in the dev group, add the `xdist_group` marks, and add `-n 4 --dist loadgroup` to the `check` and `test-fast` recipes. Leave `check-slow` and `addopts` alone. Changing the Makefile, `pyproject.toml` and `uv.lock` is gate config, and those files are stamped, so one `make check-slow` follows.
   - **#5, exact guard on the operating rule:** compute the pass probability exactly, as Σ_x betabinom(N, k, n+1−k).pmf(x) · [the rule passes at x], and assert it is at least 0.95. The new constant needs a lockfile line.
   - **#6, load warning:** warn at the start of `slow_stamp.py run` and `feasibility.py` when the load is above `BENCH_IDLE_LOAD`. Both files are stamped.
4. **After approval:** apply the changes on main, run `make check-slow`, then `make check`, and quote both gates. Then remove the worktree and its branch: `git worktree remove --force <path>`, then `git branch -D worktree-agent-a8dfa301eb036d34b`.

## Rules that apply (CLAUDE.md, Gates)

- Never `pkill -f`. Stop a run with `kill -INT -- -<pgid>`.
- Run one heavy job at a time.
- Leave the timeout, the markers' selection and `addopts` as they are without approval.
- Read the owner's `codex-before-human-questions` memory before asking anything.
- Leave the worktree `agent-a0bf8d77…` alone: it belongs to other work.
