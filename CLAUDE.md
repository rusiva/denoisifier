You are on Ubuntu in WSL2.

## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix), recorded as `Status:` lines. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one root `GLOSSARY.md` + `docs/adr/`. See `docs/agents/domain.md`.

## Gates

- **When:** `make test-fast` after every change (stops at the first failure, reruns failures first). `make check` before declaring any work done; it must be green. `make check-slow` whenever the slow tier is relevant (detector, generator or calibration changes). It takes about 40 min, longer than the 10-minute foreground Bash limit, so always run it in the background with output sent to a log. Until ticket agent-gates/05 lands, run no other gate or heavy job while `make check-slow` runs: its 10 s timing test is load-sensitive. `make fix` is the only target that changes files.
- **Fix the code, never the check.** When a test or check is red, change the code under test, not that test, that check or its config. Adding and changing tests as part of a ticket's work is normal.
- **Weakening moves need the owner's explicit approval**, asked before the change and recorded in the ticket's Comments:
  - changing a tolerance or expected value;
  - adding `skip`, `skipif` or `xfail` (or `strict=False`);
  - suppressing a warning (`filterwarnings`, `warnings.catch_warnings`, `PYTHONWARNINGS`) or a lint (`noqa`, `type: ignore`);
  - narrowing the selected tests (`addopts`, `-m`, `-k`, `--deselect`, `testpaths`, the Makefile);
  - raising or disabling a timeout;
  - editing gate config (the `Makefile`, `[tool.pytest.ini_options]`, `tests/conftest.py`, and the `pytest`/`pytest-timeout` pins and other `[dependency-groups].dev` gate tools).
- **Handoffs quote the gate; they never claim it.** Paste the command, its exit status, pytest's final summary line (e.g. `208 passed, 4 deselected in 77.93s`) and `git rev-parse --short HEAD`, plus `-dirty` if the tree had changes. "Tests pass" without that quote does not count.
