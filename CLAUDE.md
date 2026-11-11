You are on Ubuntu in WSL2.

## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix), recorded as `Status:` lines. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one root `GLOSSARY.md` + `docs/adr/`. See `docs/agents/domain.md`.

## Gates

- **When:** `make test-fast` after every change (stops at the first failure, reruns failures first). `make check` before declaring any work done; it must be green. Its last step checks the slow-tier stamp: when it reports the slow tier stale, run `make check-slow`, then `make check` again. `make check-slow` takes about 6 min idle (duration: the module docstring of `tests/test_slow_regression.py`). Always run it in the background (Bash `run_in_background`, output to a log, then `; echo "EXIT=$?" >> <log>`; never `| tee`), and run no other gate or heavy job meanwhile. A PreToolUse hook (`.claude/hooks/require_background_gate.py`) refuses `make check-slow`, `make bench` and `make measure` in the foreground.
- **Write targets:** `make fix` is the only target that changes source. `make check-slow` writes local, git-ignored `.gate/` state (lock, stamp, measurement). `make bench` (the 10 s speed gate and ticket 13's 5 s target; background, idle machine) writes `.gate/bench.json`; a tracked record (`uv run --locked python tests/bench.py --out .scratch/stripe-detector/bench.json`) is written and committed only at stripe-detector ticket 13, for a handoff's speed claim, or once in ticket agent-gates/05. `make measure` (the full ticket-03 measurement, about 39 min, background) rewrites the tracked `.scratch/stripe-detector/feasibility-gate.json`; it runs at milestones where detector output is meant to move (stripe-detector 05, 07, 13), never inside `check` or `check-slow`.
- **The slow-tier stamp** (ticket agent-gates/05): a green `make check-slow` stamps a hash of `STAMPED_FILES` in `tests/slow_stamp.py` (detector, generator and calibration code, the slow tier and its imports, the `Makefile`, `pyproject.toml`, `uv.lock`, `.python-version`), and `make check` fails when any of them differs. `tests/protected.py` is stamped whole, so even an edit to non-slow test seeds needs `make check-slow`. The stamp is per working tree: every fresh clone and every `.claude/worktrees/*` worktree needs its own `make check-slow` before its `make check` is green, and orchestrated tickets budget for it.
- **After `make measure`:** update `GATE_STORED_THRESHOLD` and `PROBE_STORED_THRESHOLD` in `tests/protected.py` by hand to the new JSON values (`test_stored_thresholds_are_the_saved_measurement` forces this; it is a lockfile edit, so it needs an approval). If `test_regression_plan_meets_the_operating_rule` then goes red, re-deriving the pass counts is the owner's decision. Never edit the pass counts to make `make check-slow` green: a detector change that turns the regression check red means `make measure`.
- **Interrupted runs:** stop a running `make check-slow` with `kill -INT -- -<pgid>` (the pgid is in `.gate/check-slow.lock`), never `pkill -f`. Spawn workers outlive a killed parent; the runner refuses to start while this tree's workers are left over, and prints the commands to stop them.
- **Fix the code, never the check.** When a test or check is red, change the code under test, not that test, that check or its config. Adding and changing tests as part of a ticket's work is normal.
- **Weakening moves need an approval**, given before the change and recorded with its reason in the ticket's Comments. A worker asks whoever runs it (the orchestrator, else the owner). The orchestrator approves from a Codex adversarial review plus its own critical reading, and escalates to the owner only when undecided or when the move lacks a clearly good, motivated reason. The moves:
  - changing a tolerance or expected value;
  - adding `skip`, `skipif` or `xfail` (or `strict=False`);
  - suppressing a warning (`filterwarnings`, `warnings.catch_warnings`, `PYTHONWARNINGS`) or a lint (`noqa`, `type: ignore`);
  - narrowing the selected tests (`addopts`, `-m`, `-k`, `--deselect`, `testpaths`, the Makefile);
  - editing the protected-number lockfile `tests/protected_numbers.lock` or its check (`tests/protected_lock.py`, `tests/test_protected_numbers.py`); the lockfile pins every module- and class-level number in `src/denoisifier` and every number in `tests/protected.py`, where test-side tolerances, acceptance limits and seed ranges live;
  - raising or disabling a timeout, including a per-test or per-param `pytest.mark.timeout(...)` mark;
  - editing gate config (the `Makefile`, `[tool.pytest.ini_options]`, `[tool.ruff]`, `[tool.mypy]`, `tests/conftest.py`, and the `pytest`/`pytest-timeout`/`ruff`/`mypy`/`scipy-stubs` pins and other `[dependency-groups].dev` gate tools);
  - weakening the runtime seed guard, which refuses calibration seeds in `generate` (ticket agent-gates/04): adding, widening or moving a `seed_guard.calibrating(...)` block (grep `calibrating(`), or editing `tests/seed_guard.py`, the `CALIBRATION_SEEDS` registry in `tests/protected.py`, the `denoisifier.synthetic.generate` audit event in `generate`, the guard's installs (`tests/conftest.py`, `feasibility.main()`, `bench.main()`) or the `score_batch` pool initializer.
  - weakening the slow-tier stamp or the background hook (ticket agent-gates/05): removing a file from `STAMPED_FILES` or moving one to `NOT_STAMPED_SRC`, editing `tests/slow_stamp.py` or the `check`/`check-slow` recipes, or removing or loosening `.claude/hooks/require_background_gate.py` or its `.claude/settings.json` entry. The regression seeds, sample sizes, pass counts, rule constants and stored thresholds are protected numbers in the lockfile.
- **Handoffs quote the gate; they never claim it.** Paste the command, its exit status, pytest's final summary line (e.g. `208 passed, 4 deselected in 77.93s`) and `git rev-parse --short HEAD`, plus `-dirty` if the tree had changes. "Tests pass" without that quote does not count.
