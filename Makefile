# Agent gates (tickets agent-gates/01-02). Editing this file is a gate-config change: owner approval (CLAUDE.md).
UV     := uv run --locked
PYTEST := $(UV) pytest

.PHONY: check check-slow bench measure test-fast fix lock-check lint no-inline-mypy

# The slow-tier stamp (ticket agent-gates/05): tests/slow_stamp.py STAMPED_FILES. check runs it
# after pytest, so test results are not hidden; a stale stamp fails check.
check: lock-check lint      ## gate: lock, format, lint, types, every non-slow test, then the slow-tier stamp
	$(PYTEST)
	$(UV) python tests/slow_stamp.py check

check-slow: lock-check      ## regression check (~6 min; duration: tests/test_slow_regression.py): background only; writes the .gate/ stamp when green
	$(UV) python tests/slow_stamp.py run -- $(PYTEST) -m slow

bench:                      ## speed gate 10 s + ticket-13 target 5 s: idle machine, background; writes .gate/bench.json
	$(UV) python tests/bench.py

measure:                    ## full ticket-03 measurement (~39 min): milestones only, background; rewrites feasibility-gate.json
	$(UV) python tests/feasibility.py
	$(PYTEST) tests/test_feasibility_gate.py

test-fast:                  ## inner loop: first seeds only (not slow, not wide; tests/inner_loop.py), stop at first failure, failures first
	$(PYTEST) -x --ff -m "not slow and not wide"

lock-check:
	uv lock --check

lint: no-inline-mypy        ## read-only: format check, ruff, mypy (scope and rules: pyproject.toml)
	$(UV) ruff format --check
	$(UV) ruff check
	$(UV) mypy

# Inline mypy config comments (`# mypy: ignore-errors`, `ignore_errors=True`, `disable-error-code`,
# `allow-untyped-defs`, ...) loosen strict mode and pass both tools; reject every `# mypy:` comment
# in ruff's scope (a superset of mypy's own `# mypy: ` line prefix). Fails closed:
# git grep exits 0 on a match, 1 on none, anything else (not a work tree, bad pathspec) is an error.
no-inline-mypy:
	@git grep --untracked -nE '#\s*mypy:' -- '*.py' '*.pyi' ':!.scratch'; \
	rc=$$?; \
	if [ $$rc -eq 0 ]; then echo "make check: inline mypy config comment found (ticket agent-gates/02)"; exit 1; fi; \
	if [ $$rc -ne 1 ]; then echo "make check: git grep failed (exit $$rc); inline mypy config comments not checked"; exit 1; fi

fix:                        ## the ONLY target that changes source: ruff autofixes, then formatting
	$(UV) ruff check --fix --exit-zero
	$(UV) ruff format
