# 02: Lint and type checks

**What to build:** `make check` rejects unformatted code, lint findings, unused or blanket suppressions and type errors in the package. `make fix` is the only way formatting and autofixes get applied. The current backlog is cleared, so the gate starts green. See `../spec.md`.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] ruff runs in the gate with a fixed rule set (start from polsigns/cadmesh's `E F W I UP B ARG PGH RUF`, plus `NPY` and `PT`), and with a format check. Narrowing the set is a weakening move under the CLAUDE.md protocol.
- [ ] mypy runs in strict mode over the package in the gate. Test code is out of scope unless a later decision widens it.
- [ ] `make fix` applies ruff autofixes and formatting. No other target changes files.
- [ ] The existing backlog is cleared (14 findings and 6 unformatted files when measured on 2026-11-10). Fixes that change behaviour are kept out of this ticket. If one is needed, it gets its own commit, and `make check` and `make check-slow` stay green.
- [ ] Proof: a planted unused `noqa`, a planted blanket `type: ignore` and a planted type error each turn `make check` red with the tool's own message. The plants are not committed.
- [ ] The tool versions are locked in `uv.lock`.
