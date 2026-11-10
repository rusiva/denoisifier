# 05: Required slow tier

**What to build:** A change to anything that affects detector output can't reach a green `make check` without a green `make check-slow` on that same code. Today an agent can rewrite the detector and hand off after only the non-slow suite, never running the weak-stripe detection rate or the false-alarm rate (Codex adversarial review, finding 2). The slow tier also becomes reliable enough to require. Its wall-clock assertion is loosened so machine load can't fail it, and the real speed gates move to a separate benchmark target. Long runs are pushed into the background, because a foreground Bash call is killed at 10 minutes and the slow tier takes about 40. See `../spec.md` for the owner's rulings of 2026-11-10.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] A green `make check-slow` writes a stamp: a hash of the files that affect detector output (the detector, the generator, the calibration code; the list is defined once and documented). A red or interrupted run writes nothing.
- [ ] `make check` fails when those files differ from the stamped hash. The message names the changed files and says to run `make check-slow` in the background. Changes only to docs, the CLI, the report or tests outside the slow tier never require the slow tier.
- [ ] The stamp is local, git-ignored state. The file list and the stamp rule are protected surfaces in CLAUDE.md.
- [ ] Timing split (owner ruling): in `check-slow`, the per-frame timing test asserts only a loose limit (about 30 s for 1600×400) and records the measured time. Ticket 03's 10 s gate and ticket 13's 5 s target move to a new `make bench`, which is not part of `check` or `check-slow`. It takes the median of several runs and records commit, CPU, load average and versions, the way `feasibility-gate.json` records run info.
- [ ] A PreToolUse hook, adapted from `~/dev/polsigns/.claude/hooks/require_background_gate.py`, refuses `make check-slow` and `make bench` in the foreground. It allows anything it cannot parse, sees through `bash -lc` wrappers, and has an explicit trailing-comment override.
- [ ] Proof: after a planted no-op edit to a detector file, `make check` is red with the stale-stamp message. After a green `make check-slow`, `make check` is green again. A foreground `make check-slow` is refused by the hook. The plants are not committed.
