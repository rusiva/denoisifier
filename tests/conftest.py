"""Gate config shared by every test (ticket agent-gates/01). Editing it needs owner approval
(CLAUDE.md)."""

import os

import pytest

import seed_guard


def pytest_configure() -> None:
    # pytest's filterwarnings does not reach child processes (the feasibility
    # workers, the CLI subprocesses); this makes their warnings errors too.
    os.environ["PYTHONWARNINGS"] = "error"
    # Refuse calibration seeds in generate() for the whole run, outside a
    # seed_guard.calibrating(...) block (ticket agent-gates/04).
    seed_guard.install()


def _functions_with_only_wide_items(items: list[pytest.Item]) -> list[str]:
    wide: dict[str, bool] = {}
    for item in items:
        function = item.nodeid.partition("[")[0]
        is_wide = item.get_closest_marker("wide") is not None
        wide[function] = wide.get(function, True) and is_wide
    return [function for function, only_wide in wide.items() if only_wide]


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """make test-fast deselects `wide` parameters (ticket agent-gates/07, tests/inner_loop.py):
    a test function whose every item is `wide` would leave the inner loop silently, so the
    full collection refuses it, before -m, -k or --deselect remove any item."""
    # Partial collections are exempt: --lf drops passed items while collecting
    # (cacheprovider's LFPluginCollWrapper), and a "file::test[id]" arg selects items.
    if config.getoption("lf", False) or any("::" in arg for arg in config.args):
        return
    only_wide = _functions_with_only_wide_items(items)
    if only_wide:
        raise pytest.UsageError(
            "test functions with only `wide` parameters would leave make test-fast "
            "(ticket agent-gates/07): " + ", ".join(only_wide)
        )
