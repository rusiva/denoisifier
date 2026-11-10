"""Gate config shared by every test (ticket agent-gates/01). Editing it needs owner approval (CLAUDE.md)."""

import os


def pytest_configure(config):
    # pytest's filterwarnings does not reach child processes (the feasibility
    # workers, the CLI subprocesses); this makes their warnings errors too.
    os.environ["PYTHONWARNINGS"] = "error"
