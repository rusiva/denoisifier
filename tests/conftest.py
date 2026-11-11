"""Gate config shared by every test (ticket agent-gates/01). Editing it needs owner approval
(CLAUDE.md)."""

import os

import seed_guard


def pytest_configure() -> None:
    # pytest's filterwarnings does not reach child processes (the feasibility
    # workers, the CLI subprocesses); this makes their warnings errors too.
    os.environ["PYTHONWARNINGS"] = "error"
    # Refuse calibration seeds in generate() for the whole run, outside a
    # seed_guard.calibrating(...) block (ticket agent-gates/04).
    seed_guard.install()
