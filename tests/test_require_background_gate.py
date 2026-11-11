"""The PreToolUse hook that refuses long make targets in the foreground
(ticket agent-gates/05): .claude/hooks/require_background_gate.py."""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude/hooks/require_background_gate.py"

_spec = importlib.util.spec_from_file_location("require_background_gate", HOOK)
assert _spec is not None
assert _spec.loader is not None
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def decide(monkeypatch, stdin: str) -> dict | None:
    """The hook's decision payload for ``stdin``, or None when it allows."""
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    monkeypatch.setattr(sys, "stdout", out)
    assert hook.main() == 0
    return json.loads(out.getvalue()) if out.getvalue() else None


def bash(command: str, **extra) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command, **extra}})


@pytest.mark.parametrize(
    "command",
    [
        "make check-slow",
        "make bench",
        "make measure",
        "make -C . check-slow",
        "timeout 5 make check-slow",
        "timeout 900 make check-slow",
        "true; make check-slow",
        "bash -lc 'make check-slow'",
        'bash -c "cd x && make check-slow"',
        "make check-slow > log 2>&1; echo \"EXIT=$?\" >> log",
        'make check-slow; echo "# hook-allow-foreground"',
    ],
)
def test_long_targets_in_the_foreground_are_refused(monkeypatch, command):
    decision = decide(monkeypatch, bash(command))
    assert decision is not None
    out = decision["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "run_in_background: true" in out["permissionDecisionReason"]
    assert "# hook-allow-foreground" in out["permissionDecisionReason"]


def test_run_in_background_false_is_refused(monkeypatch):
    assert decide(monkeypatch, bash("make check-slow", run_in_background=False)) is not None


@pytest.mark.parametrize(
    "stdin",
    [
        bash("make check"),
        bash("make test-fast"),
        bash("make fix"),
        bash("make -n check-slow"),
        bash("git grep check-slow"),
        bash("make check-slow", run_in_background=True),
        bash("make check-slow # hook-allow-foreground"),
        bash("cat > f.txt <<'EOF'\nmake check-slow\nEOF"),
        bash("make check-slow 'unterminated"),
        json.dumps({"tool_name": "Read", "tool_input": {"command": "make check-slow"}}),
        "",
        "{not json",
    ],
    ids=[
        "check",
        "test-fast",
        "fix",
        "dry-run",
        "mention",
        "background",
        "escape",
        "heredoc",
        "unparseable",
        "not-bash",
        "empty",
        "malformed",
    ],
)
def test_everything_else_is_allowed(monkeypatch, stdin):
    assert decide(monkeypatch, stdin) is None


def test_the_hook_entry_point_refuses_through_stdin():
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=bash("make check-slow"),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_the_hook_is_registered_for_bash():
    settings = json.loads((ROOT / ".claude/settings.json").read_text())
    (entry,) = settings["hooks"]["PreToolUse"]
    assert entry["matcher"] == "Bash"
    assert entry["hooks"] == [
        {
            "type": "command",
            "command": 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/require_background_gate.py"',
        }
    ]
