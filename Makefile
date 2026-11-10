# Agent gates (tickets agent-gates/01-02). Editing this file is a gate-config change: owner approval (CLAUDE.md).
UV     := uv run --locked
PYTEST := $(UV) pytest

.PHONY: check check-slow test-fast fix lock-check lint no-inline-mypy

check: lock-check lint      ## gate: lock, format, lint, types, then every non-slow test
	$(PYTEST)

check-slow: lock-check      ## the slow tier (duration: tests/test_feasibility_gate.py): background, nothing else meanwhile
	$(PYTEST) -m slow

test-fast:                  ## inner loop: stop at first failure, failures first
	$(PYTEST) -x --ff

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

fix:                        ## the ONLY target that changes files: ruff autofixes, then formatting
	$(UV) ruff check --fix --exit-zero
	$(UV) ruff format
