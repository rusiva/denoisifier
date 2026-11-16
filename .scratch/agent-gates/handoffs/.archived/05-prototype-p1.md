# 05 prototype P1: do spawn-pool workers survive a killed parent?

Question (05-plan-review.md P1): when the parent of a spawn-context `ProcessPoolExecutor` (3 workers, an initializer, `ex.map(..., chunksize=4)`, as in `score_batch`) is killed, do the workers exit or linger?

Setup: minimal script mirroring the pool (spawn context, initializer, initargs), Python from `.venv`, run in its own session (`setsid`). Busy = 12 tasks of 12 s in chunks of 4 (about 48 s per worker). Idle = pool warmed up, parent sleeping. Observed with `pgrep -f multiprocessing.spawn -s <sid>` for up to 60 s. All leftovers were killed by session afterwards; `pgrep` shows none left.

| Signal sent to | Busy (mid-task) | Idle |
|---|---|---|
| SIGTERM, parent only | parent dies at once; 3 workers LINGER (still there at 60 s) | parent dies; 3 workers LINGER (60 s) |
| SIGKILL, parent only | LINGER (60 s) | LINGER (60 s) |
| SIGINT, parent only | parent catches KeyboardInterrupt, then the pool shutdown waits for running chunks: parent and workers exit together after 44 s | exit after 2 s |
| SIGINT, whole process group (what a terminal Ctrl-C does) | all exit after 2 s | all exit after 2 s |

Caveat: a plain `cmd &` in a non-interactive shell sets SIGINT to ignored, so a first run of the INT cases showed "no effect". The valid runs reset SIGINT to default before exec. Agent Bash tools that background a job may have the same ignored SIGINT; then only SIGTERM/SIGKILL reach it.

Why TERM/KILL linger: the parent dies without running the executor's shutdown. Workers block in `call_queue.get()`; the pipe still has a write end open inside the workers themselves, so they never see EOF. None exited in 60 s, so assume they stay until killed by hand. (Lifetime past 60 s was not measured.)

## Recommendation for the plan (P5 and CLAUDE.md)

1. Workers linger on SIGTERM and SIGKILL. Idle ones cost no CPU; busy ones keep burning cores until their chunk ends (about 4 frames of work), which loads the next timing-sensitive run.
2. P5 cleanup after a killed `check-slow` must kill the workers, not only the pytest parent. Workers are orphans (PPID 1), so `pkill -f '[p]ytest -m slow'` does not reach them. Kill them by command line: `pkill -f '[m]ultiprocessing.spawn'` is simplest but also hits other sessions' pools; narrower is to match this repo's venv python plus `multiprocessing.spawn`. Best: start check-slow under `setsid` and `pkill -s <sid>`, which takes parent and workers together.
3. Pre-flight check at the start of `check-slow` (and `begin`): fail if `pgrep -f '[m]ultiprocessing.spawn'` (scoped to this repo's venv) finds any process, and print the cleanup command. CLAUDE.md: after an interrupted run, check for leftover workers.
4. Agent kill path: send SIGINT to the process group first (`kill -INT -- -<pgid>`); that exits cleanly in about 2 s. Fall back to SIGTERM, then the worker cleanup above.
5. Optional hardening in `score_batch` (parent-death signal or a parent-pid watchdog in the initializer) would cover TERM and KILL, but it edits `tests/feasibility.py` and needs approval; the check in 2 and 3 is cheaper.

Prototype scripts (throwaway): `/tmp/claude-1000/-home-rusiva-dev-denoisifier/a84d73a5-b2f4-47dc-85d7-1ef732017ed3/scratchpad/pool.py` and `run2.sh` in the same folder.
