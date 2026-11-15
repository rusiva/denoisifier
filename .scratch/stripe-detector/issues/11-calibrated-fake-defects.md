# 11: Calibrated fake breaks and forks

**What to build:** Reported phase breaks and forks can be trusted. The break and fork thresholds are calibrated on generated **striped frames with no breaks or forks**, at typical settings with spikes present, so that fake breaks and forks occur at most about once per 20 frames. The rate can be changed. Calibration and evaluation use separate seeds, and the thresholds are stored with the package next to the stripe threshold.

**Blocked by:** 06, 09, 10

**Status:** ready-for-agent

- [ ] A repeatable calibration routine sets the break and fork thresholds from calibration seeds.
- [ ] On held-out striped frames with no breaks or forks (scorched mottle, about 100 photons at the peak, spikes present), the number of fake breaks and forks is about 1 per 20 frames or less.
- [ ] After calibration, breaks with jumps of π/2 or more and forks are still found at the rates required by 09 and 10.
- [ ] The rate can be set through the library option and a CLI flag.
- [ ] The statistical tests are marked slow.

## Comments

- 2026-11-15, from ticket 10 (Forks). The held-out frames here have no Forks, so the fake-defect rate will not see the fake Phase Breaks on Fork frames (close opposite Fork pairs, Forks near a region edge: ticket 10 Comments, ticket 18). The fork evidence scalar is yours to calibrate: E = winding-component area / (2R)², R = `_FORK_LOOP_PERIODS` = 2 P; gate `_FORK_GATE_EVIDENCE` = 0.2, reported `_FORK_MIN_EVIDENCE` = 0.3; true-Fork E min 0.31 (P2 explore), largest fork-free candidate 0.000. A fake region gets fake Forks too (09's 109797 kind).
- 2026-11-15, orchestrator: **approvals** (CLAUDE.md delegation, from Codex `handoffs/11-codex-review.md` and critic `handoffs/11-critic.md`; rulings `handoffs/11-rulings.md`, folded into `handoffs/11-plan.md`).
  - `make check-held-out` at ticket 11's close, plus the CLAUDE.md and Makefile help text wording for it (gate config, doc-only). Reason: AC 2 needs exactly one held-out look at the frozen pipeline; a red there is a finding, never a tuning trigger, and a second look uses the reserved fresh seeds.
  - The break/Fork calibration driver as an additional writer of tracked source outside `make fix` (step 6 and the re-store procedure). Reason: a reproducible generated file is the ADR 0002 precedent (ticket 07 step 5), approved before its first run.
  - Strict `>` on the reported break comparison (`_accepted`, `_local_phase.py:500`) and the reported Fork comparison (`_post_break_forks`); the pre-break gate stays `>=`. Reason: a frame with no candidate (S = 0) must never count as a fake at T = 0 (ADR 0002's `score > threshold`); the gate decides the field, not what is reported.
  - The remaining lockfile and protected-number edits of plan §10 are approved when the closing check passes them.
- 2026-11-15, implementer (step 6): **approved edits made** (plan §10, passed by the closing check; reasons as in the plan).
  - A1 lockfile: `denoisifier.calibration :: DEFAULT_BREAK_FORK_FALSE_ALARM_RATE :: 0.05` (step 3, implementer-1); the `protected.py` ticket-11 block (seed ranges 112_000-112_199, 113_000-113_299, 114_000-114_599, 115_000-115_399, tiny test seeds 40-47 / 10-13, `BREAK_FORK_REPRODUCTION_PREFIX` 60 (OQ8 prefix branch), shape (400, 1600), depth 0.5, rate 0.05, `BREAK_FORK_MAX_FAKES` 29 (betabinom(300, 15, 286) one-sided at `CALIBRATION_MAX_FALSE_RED`), `BREAK_FORK_CASE_ALARM_FRAMES` 6, min detection 0.95, 100 + 100 detection frames, `PACKAGE_BREAK_FORK_*` from the driver run); `USED_SEEDS` += prototype and the two `_2` ranges. New pins only, nothing loosened. Reason: every new verdict number is pinned.
  - A2 seed guard: `CALIBRATION_SEEDS["BREAK_FORK_FREE_CALIBRATION_SEEDS"]` and the one `seed_guard.calibrating(...)` block in `calibrate_break_forks` (generation and evidence pass). Reason: the Calibration Set must be refused everywhere else.
  - A3 stamp: `STAMPED_FILES` += `break_fork_free_calibration.json`, `tests/break_fork_calibration.py`, the two new slow modules and their `tests/` imports (`breaks.py`, `forks.py`, `regions.py`, `truth_match.py`, `shared_cache.py`, `binning.py`). Strengthens the stamp.
  - A4: `pytest.mark.timeout(CALIBRATION_TIMEOUT_S)` on the new slow tests (07 precedent).
  - Floors bind (OQ1): the thresholds are the floors 0.1 / 0.3; see the driver run below.
- 2026-11-15, implementer: **driver run** (step 6, approved O3) at `1e065f8`'s tree: `uv run --locked python tests/break_fork_calibration.py --out src/denoisifier/break_fork_free_calibration.json`, `EXIT=0`: n = 300, S_b > 0 on 0 and S_f > 0 on 0 frames, thresholds at 0.05 = (0.1, 0.3), the floors (OQ1: "the floors set the thresholds; measured 0 of 300 calibration frames with any evidence"), digest `148ba19d40307b00cacb210fd0b21159a0a1651635020a72a49fe67471656862`, 2.38 s/frame (started at load 7.9, decaying from a killed run; output does not depend on load).
- 2026-11-15, fixer: **approvals recorded before the edits** (orchestrator, `handoffs/11-fix-list.md`).
  - F9: `tests/slow_stamp.py` stale-stamp message, its `make check-slow` duration text only, "about 20 min" to "about 23 min" (no logic change), and the same words in the exact-text expectation of `tests/test_slow_stamp.py::test_stamped_edit_makes_check_fail_naming_only_that_file`, which pins that message. Reason: the documented check-slow duration changed with the 60-frame reproduction prefix (step 7); the message must not quote the old one.
  - F6: Makefile `check-held-out` `##` help string names `.gate/held-out-break-fork.json` beside the calibration file (gate text only). Reason: the held-out run now writes both files.
  - F1 glossary gap, for `/domain-modeling` (`docs/agents/domain.md`): "fake Phase Break / Fork" (a break or Fork reported on a frame that has none) has no GLOSSARY entry, and **False Alarm** covers stripe Verdicts only. No GLOSSARY edit in this ticket.
