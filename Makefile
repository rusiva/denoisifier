# Agent gates (ticket agent-gates/01). Editing this file is a gate-config change: owner approval (CLAUDE.md).
UV     := uv run --locked
PYTEST := $(UV) pytest

.PHONY: check check-slow test-fast fix lock-check

check: lock-check           ## gate: every non-slow test, whole run
	$(PYTEST)

check-slow: lock-check      ## the slow tier (~40 min): run in the background, nothing else meanwhile
	$(PYTEST) -m slow

test-fast:                  ## inner loop: stop at first failure, failures first
	$(PYTEST) -x --ff

lock-check:
	uv lock --check

fix:                        ## the ONLY target that changes files; ruff arrives in ticket 02
	@echo "make fix: nothing to do yet (ticket 02 adds ruff)"
