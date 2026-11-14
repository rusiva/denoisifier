#!/usr/bin/env python3
"""PreToolUse (Bash) hook: refuse to run long make targets in the foreground.

Adapted from polsigns (.claude/hooks/require_background_gate.py) for ticket
agent-gates/05. The Bash tool's `timeout` is clamped to 600000 ms (10 min); a
larger value is silently ignored and the call is killed at 10 min with exit 143.
`make check-slow` (about 20 min idle, longer under load; duration:
tests/test_slow_regression.py), `make check-held-out` (about 20 min; ticket
stripe-detector/07), `make bench` (timing on an idle machine) and `make measure`
(about 39 min) belong in the background, with nothing else running meanwhile.
This hook makes the foreground form unrepresentable.

Scope: this is about the harness clock only. It has nothing to do with the
pytest-timeout limits (60 s per test globally; 1200 s for the whole
tests/test_slow_regression.py module), which fire the same way in the
background. Raising either is a weakening move (CLAUDE.md).

Design invariants:
  * Fail-open. Any internal error, unparseable payload or command, or
    unexpected schema exits 0 (allow). A hook that blocks work it does not
    understand is worse than the mistake it prevents.
  * Blocks ONLY the targets in _LONG_TARGETS. Other targets (`check`,
    `test-fast`, `fix`) and non-make commands pass untouched. A dry run
    (`make -n`) is allowed.
  * Explicit escape hatch: a command whose FINAL unquoted shell comment is
    `# hook-allow-foreground` is always allowed. The marker must be a real
    trailing comment; a mention inside quoted data does NOT disarm the hook.
  * Sees through shell wrappers: `bash -lc 'make check-slow'` is unwrapped
    recursively (to depth 5). Heredoc bodies are data and are not scanned.

Detection note (from polsigns, Claude Code 2.1.225): `tool_input` carries
`run_in_background: true` when the call is backgrounded, and omits the key
otherwise. Absence therefore means foreground.
"""

import json
import re
import shlex
import sys

# Targets that must run in the background (ticket agent-gates/05; CLAUDE.md "Gates";
# check-held-out: ticket stripe-detector/07, W7).
_LONG_TARGETS = frozenset({"check-slow", "check-held-out", "bench", "measure"})

_MARKER_WORD = "hook-allow-foreground"
_ESCAPE_MARKER = f"# {_MARKER_WORD}"

# Trailing unquoted comment carrying the marker, and nothing after it.
_ESCAPE_RE = re.compile(r"(?:^|\s)#\s*" + re.escape(_MARKER_WORD) + r"\s*$")

# Shells whose `-c` payload is another command line to be scanned recursively.
_SHELL_NAMES = frozenset({"sh", "bash", "zsh", "dash", "ksh", "ash"})

# A token that is purely shell control punctuation (`;`, `&&`, `||`, `|`).
_PUNCT_RE = re.compile(r"^[;&|]+$")

# Bound on wrapper nesting (`bash -c "bash -c '...'"`) so pathological input
# cannot recurse without limit.
_MAX_WRAPPER_DEPTH = 5

# Start of a heredoc: `<<EOF`, `<<-EOF`, `<<'EOF'`, `<<"EOF"`.
_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def _strip_heredocs(command: str) -> str:
    """Drop heredoc BODIES, keeping the lines that introduce them.

    A heredoc body is data fed to a program, not a command line. Without this
    the scanner reads `make check` appearing inside an embedded script -- a
    test fixture, a generated file, this hook's own documentation -- as if it
    were an invocation, and blocks a command that runs no gate at all.
    """
    kept = []
    pending: list[str] = []
    for line in command.split("\n"):
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue  # inside a body: data, not code
        kept.append(line)
        pending.extend(m.group(2) for m in _HEREDOC_RE.finditer(line))
    return "\n".join(kept)


def _has_escape_marker(command: str) -> bool:
    """True iff the marker appears as the command's real trailing comment.

    A bare substring test would let unrelated commands disarm the hook merely
    by MENTIONING the marker -- `grep hook-allow-foreground .claude/hooks/*`,
    or echoing this file's own documentation. Two conditions must hold: the
    marker must terminate the command, and it must survive as a comment rather
    than as quoted data.
    """
    stripped = _strip_heredocs(command)
    if not _ESCAPE_RE.search(stripped):
        return False
    try:
        # `comments=True` strips real comments; anything left holding the
        # marker was quoted, i.e. data rather than a directive.
        remaining = shlex.split(stripped, comments=True)
    except ValueError:
        return False
    return not any(_MARKER_WORD in tok for tok in remaining)


def _tokenize(command: str) -> list[str] | None:
    """Split `command` into shell tokens, keeping `;`/`&&`/`||` as tokens.

    `punctuation_chars=True` is what makes this safe to run BEFORE splitting on
    control operators: quoted scripts stay intact, so `bash -lc 'a && make
    check-slow'` yields one script token instead of being torn in half.
    Returns None when the command cannot be parsed: fail-open.
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return None


def _wrapped_scripts(tokens: list[str]) -> list[str]:
    """Return `-c` payloads of any shell invocations among `tokens`."""
    scripts = []
    for i, tok in enumerate(tokens):
        if tok.rsplit("/", 1)[-1] not in _SHELL_NAMES:
            continue
        # Find this shell's -c/-lc/-lic option; its argument is the script.
        for j in range(i + 1, len(tokens)):
            arg = tokens[j]
            if not arg.startswith("-"):
                break  # first non-option is the script FILE, not inline code
            if "c" in arg.lstrip("-"):
                if j + 1 < len(tokens):
                    scripts.append(tokens[j + 1])
                break
    return scripts


def _targets_in_segment(tokens: list[str]) -> list[str]:
    """Return known-long make targets invoked directly by one segment."""
    make_idx = None
    for i, tok in enumerate(tokens):
        if tok == "make" or tok.endswith("/make"):
            make_idx = i
            break
    if make_idx is None:
        return []

    rest = tokens[make_idx + 1 :]

    # A dry run compiles no code and runs no tests -- always cheap.
    opts = [a for a in rest if a.startswith("-")]
    if any(o in ("-n", "--dry-run", "--just-print", "--recon") for o in opts):
        return []

    # Targets are the args after `make` that are neither options (-...) nor
    # variable overrides (FOO=bar).
    targets = [a for a in rest if not a.startswith("-") and "=" not in a]
    return [t for t in targets if t in _LONG_TARGETS]


def _long_targets_in(command: str, depth: int = 0) -> list[str]:
    """Return the known-long make targets invoked by `command`, if any.

    Descends into shell wrappers, so `bash -lc 'make check-slow'` is caught as
    surely as a bare `make check-slow`.
    """
    if not command or depth > _MAX_WRAPPER_DEPTH:
        return []

    tokens = _tokenize(_strip_heredocs(command))
    if tokens is None:
        return []  # unparseable: allow
    found: list[str] = []
    segment: list[str] = []
    for tok in [*tokens, ";"]:
        if _PUNCT_RE.match(tok):
            if segment:
                found.extend(_targets_in_segment(segment))
                for script in _wrapped_scripts(segment):
                    found.extend(_long_targets_in(script, depth + 1))
            segment = []
        else:
            segment.append(tok)

    return found


def _deny(targets: list[str]) -> None:
    """Emit the PreToolUse blocking payload."""
    listed = ", ".join(f"`{t}`" for t in sorted(set(targets)))
    reason = (
        f"Refused: {listed} must run in the background. The Bash tool kills a "
        f"foreground call at 10 min (any larger `timeout` is clamped) with exit 143, "
        f"and these runs are long or timing-sensitive (CLAUDE.md, Gates).\n\n"
        f"Re-issue the SAME command with `run_in_background: true`, sending output "
        f"to a log and recording the real exit status:\n\n"
        f"    make check-slow > .scratch/<feature>/handoffs/NN-check-slow.log 2>&1; "
        f'echo "EXIT=$?" >> .scratch/<feature>/handoffs/NN-check-slow.log\n\n'
        f"Then wait for the completion notification and read the log. Run no other "
        f"gate or heavy job meanwhile. Never `| tee` the make call: the pipe masks "
        f"make's status.\n\n"
        f"After an interrupted run, check for leftover spawn workers before the next "
        f"one (CLAUDE.md): stop the run's process group with `kill -INT -- -<pgid>` "
        f"(the pgid is in .gate/check-slow.lock).\n\n"
        f"This is about the harness clock only, not a pytest-timeout diagnosis: the "
        f"60 s per-test limit and the 1200 s limit on tests/test_slow_regression.py "
        f"fire the same way in the background.\n\n"
        f"If you genuinely want this in the foreground, append `{_ESCAPE_MARKER}` "
        f"to the command."
    )
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload))


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # fail open

    try:
        if data.get("tool_name") != "Bash":
            return 0

        tool_input = data.get("tool_input") or {}
        command = tool_input.get("command", "")

        if _has_escape_marker(command):
            return 0

        # Backgrounded already -- nothing to correct.
        if tool_input.get("run_in_background") is True:
            return 0

        targets = _long_targets_in(command)
        if targets:
            _deny(targets)
    except Exception:
        return 0  # fail open -- never wedge the session

    return 0


if __name__ == "__main__":
    sys.exit(main())
