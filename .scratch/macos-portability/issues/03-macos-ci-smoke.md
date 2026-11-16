# 03: macOS CI smoke

**What to build:** Native macOS evidence without the friend's machine: a GitHub Actions workflow on an Apple Silicon runner (`macos-14` or newer) that runs `uv sync --locked`, `make lint` and `make test-fast` on every push to `main`, and `make check-slow` only on manual dispatch (`workflow_dispatch`). It is evidence for ticket 04, not a gate: a red macOS run is a finding, not something to fix by changing tests. The issue tracker stays local; the workflow does not use GitHub Issues. See `../spec.md`.

**Blocked by:** 01, 02, and the first push to `origin` (after stripe-detector ticket 10)

**Status:** ready-for-agent

- [ ] The owner approves the workflow before it is pushed: it is outward-facing, and on a private repo macOS minutes count 10x.
- [ ] The owner's fine-grained token has **Workflows: Read and write** on the repo (pushing `.github/workflows/` fails without it).
- [ ] The job records the runner's OS, architecture, Python and numpy/scipy versions (`uv pip list` or similar) in its log.
- [ ] Runs on an Apple Silicon runner, uses the locked environment only (no `uv lock` changes, no extra installs that change resolution).
- [ ] The first run's results (pass/fail per target, the failing test ids) are recorded under ticket 04's `## Comments`.
- [ ] Gate config is not changed for CI (no extra `-m`, `--deselect`, env var or `PYTHONWARNINGS`). If anything must differ, it is a listed CLAUDE.md move and needs approval.

## Comments
