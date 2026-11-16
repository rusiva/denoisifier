# 02: Portable process lifecycle

**What to build:** `make check-slow`'s process handling works on macOS, and its tests prove it rather than passing by accident. Two problems: `tests/slow_stamp.py:160` `find_leftover_workers` iterates `/proc`, so on macOS `make check-slow` crashes with `FileNotFoundError` before it starts; and `tests/test_slow_stamp.py:154` waits `while Path(f"/proc/{child}").exists() ...`, which is always False on macOS, so the group-stop test passes without checking anything. See `../spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Leftover-worker discovery works without `/proc` (e.g. `ps -axo pid=,command=` or `psutil`; a new dependency is a `uv.lock` change and gate-adjacent, justify it) and keeps today's ownership rules: only multiprocessing spawn workers whose `argv[0]` is under this tree's `.venv/bin/`, never matched on the shared uv interpreter (review B4).
- [ ] Tests cover: a tree path containing spaces, another venv sharing the same interpreter (not matched), a process-listing failure (fails loudly or refuses to start; never reports "no leftovers"), concurrent runs, and cleanup after an interrupted run.
- [ ] Both the `/proc` path and the portable path run in the Linux suite (`ps` exists on Linux), so macOS behaviour is exercised without a Mac.
- [ ] The group-stop test checks child liveness portably (e.g. `os.kill(pid, 0)` plus zombie handling) and is shown to go red when a child is planted to survive the stop. The plant is not committed.
- [ ] `tests/slow_stamp.py` and `tests/test_slow_stamp.py` are listed CLAUDE.md moves: approval recorded under `## Comments` before the change.
- [ ] Ends with `make check-slow` (stamped files changed) then `make check`, quoted in the handoff.

## Comments
