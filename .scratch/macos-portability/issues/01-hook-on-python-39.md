# 01: Hook runs on Python 3.9

**What to build:** The background-gate hook works on the `python3` that ships with macOS (3.9), so a fresh clone on a Mac is guarded before anyone runs `uv sync`. Today `.claude/hooks/require_background_gate.py:106` uses `list[str] | None` with no `from __future__ import annotations`, so the import fails with a TypeError on 3.9: the hook errors on every Bash call and never blocks a foreground gate. The hook is stdlib-only, so keep the `python3` launcher in `.claude/settings.json` and make the script 3.9-clean. Do not switch the launcher to `uv run` (sync cost on every Bash call, and it fails before the first `uv sync`). See `../spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The hook imports and runs on Python 3.9 (e.g. `from __future__ import annotations`, no 3.10+ stdlib or syntax).
- [ ] A test runs the hook through the exact command configured in `.claude/settings.json` on a Python 3.9 interpreter (e.g. one fetched by `uv python install 3.9`; the test must fail, not skip, when 3.9 is unavailable unless that is approved) and checks: a foreground `make check-slow` is refused, a background one is allowed, an unrelated command passes, and it works in a tree with no `.venv`.
- [ ] Editing the hook is a listed CLAUDE.md move: approval recorded under `## Comments` before the change; nothing about what the hook refuses gets looser.
- [ ] Ends on the CLAUDE.md sequence (`make check-slow` if a stamped file changed, then `make check`), quoted in the handoff.

## Comments
