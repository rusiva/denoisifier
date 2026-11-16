# 05: Onboarding

**What to build:** A friend on macOS can clone the repo and get into the dev workflow from the README alone. See `../spec.md`.

**Blocked by:** 01, 02, 03, 04

**Status:** ready-for-agent

- [ ] The project `CLAUDE.md` no longer asserts "You are on Ubuntu in WSL2." (the owner's global `~/.claude/CLAUDE.md` already says it for the owner).
- [ ] README "Getting started" lists the tools needed (uv, gh, git, Claude Code, the Codex plugin used for adversarial reviews) and the first run: `uv sync --locked`, `make test-fast`, one background `make check-slow` (it creates this clone's stamp; about 20 min), `make check`. It also says what `.gate/` is and why it is not in the repo.
- [ ] Only the missing workflow rule is promoted from the owner's memory into `CLAUDE.md` or `docs/agents/`: get a Codex adversarial opinion before asking a human, and decide yourself unless it's a matter of taste, needs outside knowledge, or is hard to undo. The end-of-ticket gate sequence and the delegated approval process are already in `CLAUDE.md`; do not duplicate them or add a blanket owner-approval rule. Editing `CLAUDE.md` is a docs change, not a gate-config change, but any wording that loosens a gate rule is a listed move.
- [ ] A fresh native macOS clone runs the steps above; the exit status and pytest summary line of each are recorded under `## Comments`. The macOS CI run from 03 counts only if it used a fresh clone and the same commands.
- [ ] The README's macOS-support wording matches 04's outcome.

## Comments
