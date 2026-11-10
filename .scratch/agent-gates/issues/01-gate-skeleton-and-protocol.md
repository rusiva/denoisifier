# 01: Gate skeleton and protocol

**What to build:** An agent has one command to run after every change, one gate to pass before declaring work done, and one command for the slow measurement tier. Only one target ever changes files. Warnings, unknown markers or config keys, a test that unexpectedly passes while marked `xfail`, and a hung native call all fail the run loudly, so agents can't let them slide. CLAUDE.md states the protocol: fix the code under test, never the check; any weakening needs the owner's approval; a handoff quotes the gate's output (command, exit status, summary line, commit) instead of claiming a pass. Keep it thin: lint, types and the other checks arrive in later tickets. See `../spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [x] `make test-fast` (inner loop, stops at the first failure, reruns failures first), `make check` (gate: every non-slow test, whole), `make check-slow` (the `slow` tier) and `make fix` (the only target that changes files, empty until ticket 02) exist. Every target runs through the locked uv environment.
- [x] pytest runs with strict markers, strict config, strict xfail, all warnings as errors, and a per-test timeout using the thread method. The timeout is an operating setting chosen from measured slowest-test times, and the evidence is recorded under `## Comments`.
- [x] The gate fails when `uv.lock` is out of date with `pyproject.toml`.
- [x] `make check` and `make check-slow` are green on the current code with the new settings. Any warning the slow tier's worker processes raise is fixed at its source, not filtered.
- [x] Proof that the gate can fail: a planted `RuntimeWarning`, a planted `xfail` that passes, and a planted misspelt marker each turn `make check` red with pytest's own message. The plants are not committed.
- [x] CLAUDE.md states which command to run when, the fix-the-code rule, the list of weakening moves that need owner approval (changing a tolerance or expected value, skip/xfail, suppressing a warning or lint, narrowing the selected tests, raising a timeout, editing gate config), and the handoff rule about quoting gate output.

## Comments

**Timeout evidence (implementer, 2026-11-10).** Measured at `d90c66f` with `PYTHONWARNINGS=error uv run --locked pytest -p no:cacheprovider -W error --strict-markers --strict-config -o xfail_strict=true --durations=25 -q` (idle row), and the same with `-k "multiscale_mottle or cli_prints" --durations=4` while 32 `sh -c 'while :; do :; done'` processes ran (loaded row). Slowest steps are the `call` phase; setup is negligible.

| condition | slowest | next | whole suite |
|---|---|---|---|
| idle (load 0.35 → 2.57) | 1.28 s `test_multiscale_mottle_is_handled[2]` | 1.26 s, 1.23 s; CLI tests 0.87–0.96 s | 82 s, 208 tests |
| 32 busy-loop processes on 16 CPUs (load 23) | 7.07 s `test_cli_prints_json_to_stdout_without_output_flag` | 6.44 s, 5.51 s (`multiscale_mottle`) | (subset of 11 tests: 56.6 s) |

Chosen `timeout = 60`, `timeout_method = "thread"`: about 8.5× the slowest step under 2× CPU oversubscription, 47× idle. The slow tier's `fresh` param carries `pytest.mark.timeout(5400)` (owner ruling Q2): the fresh measurement took about 39 min with 8 workers (`.scratch/stripe-detector/feasibility-gate.md`). Known risk accepted (Q3): this CPython lacks `sem_clockwait`, so a VM resume can fire the timer early: a false red only.

**Gate runs (implementer, 2026-11-10).**

- `make check` → exit 0, `208 passed, 4 deselected in 77.93s (0:01:17)`, HEAD `d90b8a7`. Header: `timeout: 60.0s`, `timeout method: thread`.
- `make check-slow > .scratch/agent-gates/handoffs/01-check-slow.log 2>&1` (background) → exit 0, `4 passed, 208 deselected in 2280.55s (0:38:00)`, HEAD `d90b8a7-dirty` (only CLAUDE.md edited during the run). Started 15:16:37 with `/proc/loadavg` `0.84 0.81 0.66`; nothing else ran meanwhile. No worker warnings under `PYTHONWARNINGS=error`.
- Stale lock (`"pillow"` added to `dependencies`, no `uv lock`): `make check` → ``The lockfile at `uv.lock` needs to be updated, but `--check` was provided. To update the lockfile, run `uv lock`.``, make exit 2, no tests ran. Reverted.
- Plants in `tests/test_zz_plant.py`, each through `make check` (make exit 2), each deleted afterwards with a clean `git status`:
  - `np.log(np.array(0.0))` → `E       RuntimeWarning: divide by zero encountered in log`, `1 failed, 208 passed, 4 deselected`.
  - `@pytest.mark.xfail(reason="planted xpass")` on a passing test → `[XPASS(strict)] planted xpass`, `1 failed, 208 passed, 4 deselected`.
  - `@pytest.mark.slwo` → ``'slwo' not found in `markers` configuration option``, `Interrupted: 1 error during collection`.
  - A failing plant: `make test-fast` stopped at `1 failed`; the next run printed `run-last-failure: rerun previous 1 failure first` and ran the plant first. A child process `warnings.warn` under pytest failed with `UserWarning: child` (conftest's `PYTHONWARNINGS=error`).
- `make fix` → exit 0, prints the ticket 02 placeholder, tree unchanged.
