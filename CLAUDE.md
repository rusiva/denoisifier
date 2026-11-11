You are on Ubuntu in WSL2.

## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix), recorded as `Status:` lines. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one root `GLOSSARY.md` + `docs/adr/`. See `docs/agents/domain.md`.

## Gates

- **When:** `make test-fast` after every change (stops at the first failure, reruns failures first). `make check` before declaring any work done; it must be green. `make check-slow` only when `src/` changed since its last green run; otherwise cite that run's quote and commit. It runs far longer than the 10-minute foreground Bash limit (measured duration: the `fresh` timeout comment in `tests/test_feasibility_gate.py`), so always run it in the background with output sent to a log. Until ticket agent-gates/05 lands, run no other gate or heavy job while `make check-slow` runs: its 10 s timing test is load-sensitive. `make fix` is the only target that changes files.
- **Fix the code, never the check.** When a test or check is red, change the code under test, not that test, that check or its config. Adding and changing tests as part of a ticket's work is normal.
- **Weakening moves need an approval**, given before the change and recorded with its reason in the ticket's Comments. A worker asks whoever runs it (the orchestrator, else the owner). The orchestrator approves from a Codex adversarial review plus its own critical reading, and escalates to the owner only when undecided or when the move lacks a clearly good, motivated reason. The moves:
  - changing a tolerance or expected value;
  - adding `skip`, `skipif` or `xfail` (or `strict=False`);
  - suppressing a warning (`filterwarnings`, `warnings.catch_warnings`, `PYTHONWARNINGS`) or a lint (`noqa`, `type: ignore`);
  - narrowing the selected tests (`addopts`, `-m`, `-k`, `--deselect`, `testpaths`, the Makefile);
  - editing the protected-number lockfile `tests/protected_numbers.lock` or its check (`tests/protected_lock.py`, `tests/test_protected_numbers.py`); the lockfile pins every module- and class-level number in `src/denoisifier` and every number in `tests/protected.py`, where test-side tolerances, acceptance limits and seed ranges live;
  - raising or disabling a timeout, including a per-test or per-param `pytest.mark.timeout(...)` mark;
  - editing gate config (the `Makefile`, `[tool.pytest.ini_options]`, `[tool.ruff]`, `[tool.mypy]`, `tests/conftest.py`, and the `pytest`/`pytest-timeout`/`ruff`/`mypy`/`scipy-stubs` pins and other `[dependency-groups].dev` gate tools);
  - weakening the runtime seed guard, which refuses calibration seeds in `generate` (ticket agent-gates/04): adding, widening or moving a `seed_guard.calibrating(...)` block (grep `calibrating(`), or editing `tests/seed_guard.py`, the `CALIBRATION_SEEDS` registry in `tests/protected.py`, the `denoisifier.synthetic.generate` audit event in `generate`, the guard's installs (`tests/conftest.py`, `feasibility.main()`) or the `score_batch` pool initializer.
- **Handoffs quote the gate; they never claim it.** Paste the command, its exit status, pytest's final summary line (e.g. `208 passed, 4 deselected in 77.93s`) and `git rev-parse --short HEAD`, plus `-dirty` if the tree had changes. "Tests pass" without that quote does not count.
