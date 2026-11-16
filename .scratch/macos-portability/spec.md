# macOS portability

Status: ready-for-agent

## Goal

The owner (WSL2 Ubuntu, x86_64) will push this repo to GitHub (`origin` = https://github.com/rusiva/denoisifier.git, after stripe-detector ticket 10 lands) and share it with a friend on macOS, the person the tool was built for, so they can get to know the dev workflow (gates, tickets, agent workflow in CLAUDE.md). Aim: as close to plug-and-play as possible on macOS.

## Decisions so far

- `.gate/` stays git-ignored and is not shared. It is per-working-tree, per-machine state (slow-tier stamp hash, lock with pgids, `bench.json` timings, held-out measurement). A fresh clone needs its own `make check-slow` anyway. Tracked results (`.scratch/stripe-detector/feasibility-gate.json`, `src/denoisifier/stripe_free_calibration.json`, stored thresholds in `tests/protected.py`) already carry what is worth sharing.
- Prefer native macOS fixes over a Docker/devcontainer: a container is less plug-and-play for a friend and does not settle arm64 numerics either.

## Findings (from a grep for Linux-only constructs)

| Where | macOS effect |
|---|---|
| `tests/slow_stamp.py:160` `find_leftover_workers` iterates `/proc` | `FileNotFoundError`: `make check-slow` crashes before it starts |
| `tests/test_slow_stamp.py:154` loops while `/proc/<child>` exists | always False on macOS: the group-stop test passes vacuously (Codex review) |
| `.claude/hooks/require_background_gate.py:106` uses `list[str] \| None` without `from __future__ import annotations`; run by `python3` from `.claude/settings.json` | macOS system python3 is 3.9: TypeError at import, so the hook errors on every Bash call and the background guard is inert |
| `slow_stamp.loadavg`, `tests/feasibility.py` `/proc/cpuinfo` | already fall back on OSError: fine |
| `tests/test_synthetic.py:195,500` compare SHA-256 of generated frames | not portable across CPU dispatch: with NumPy X86_V3/V4/AVX512_ICL dispatch disabled on this machine, 2,625/65,536 pixels moved by at most 4.55e-13 and the default-frame test failed (Codex review). Likely red in `make test-fast` on Apple Silicon; unverified on macOS |
| Stored thresholds and calibration digest (`tests/protected.py`, `PACKAGE_CALIBRATION_DIGEST`) | unverified: produced on x86 Linux; Apple Silicon numpy/scipy builds may differ in the last bits and turn the calibration-reproduction tests red |
| `CLAUDE.md` "You are on Ubuntu in WSL2." | wrong environment for the friend's agent |
| Owner's auto-memory (outside the repo): "get a Codex adversarial opinion before asking the human; self-decide unless taste/external knowledge/hard to revert" | the friend will not get it; the batch-heavy-gates memory is already in CLAUDE.md. Codex plugin also needed on their side |

## Plan

Reviewed by Codex adversarial review (2026-11-14, verdict needs-attention) and revised. Tickets in `issues/`:

| # | Ticket | Blocked by |
|---|---|---|
| 01 | Hook runs on Python 3.9 | none |
| 02 | Portable process lifecycle | none |
| 03 | macOS CI smoke | 01, 02, first push to `origin` |
| 04 | Numerical qualification | 03 (or the friend's native run) |
| 05 | Onboarding | 01-04 |

Rules that hold across tickets:

- Not macOS-ready until 04 closes. Sharing before that is fine as "Linux-verified, macOS in qualification".
- Editing `tests/slow_stamp.py`, `tests/test_slow_stamp.py` or the hook is a listed CLAUDE.md move: approval through the normal process (orchestrator from a Codex review, owner only when undecided), recorded in the ticket's Comments.
- Never regenerate baselines, skip, or relax a numeric check to get macOS green. A cross-platform comparison policy is an approved decision made from 04's evidence.
