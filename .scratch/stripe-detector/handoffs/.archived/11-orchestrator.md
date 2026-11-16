# Ticket 11 orchestrator log

- Ticket: `.scratch/stripe-detector/issues/11-calibrated-fake-defects.md`
- BASE: e06a902aa4d99487144450795db5339662f976ff
- Args: MIN_MODEL=opus, SELF_LIMIT=200000, WORKER_LIMIT=200000
- Owner rule: second opinion (Codex adversarial review; fresh-context Fable critic per this session's args) before any human question; ask only taste / external knowledge / hard-to-revert architecture.
- Milestone gates (fixer only): `make measure` only if detector changed (calibration of break/fork thresholds may not move stripe score), `make check-slow`, `make check-held-out` if re-store, `make check`.

## Workers

- planner a21d95594843a6162 (opus): write `11-plan.md`, name scalars/routine/seeds/storage/option+flag/AC tests/gates, list open questions. Status: done; plan `11-plan.md`. Open Qs OQ1-OQ8 (floors, rate split, storage, frames, AC3 check, check-held-out ruling, count vs frames, reproduction size).
- plan reviewer a8b33dca346eb11a9 (opus, blind): review into `11-plan-review.md`. Status: done; `11-plan-review.md`: B1-B5 breaks, O1-O5 owner, N1-N8 notes.
- Codex adversarial review (bg blte69vp3) → `11-codex-raw.log` / `11-codex-review.md`. Status: done (key: union rule invalid 5.305%>5%; count estimand; coverage narrow).
- Fable critic a2ff0c48312c83cf8 (fresh context) → `11-critic.md`. Status: done (agrees B/N; OQ4 arms, paired lost count, one-sided bound, private DefectCalibration, missed items).
- fold planner a872b2c33fff577c5 (opus): fold `11-rulings.md` into `11-plan.md`, ticket Comments approvals. Status: done; public names `break_fork_false_alarm_rate`, `--break-fork-false-alarm-rate`, `break_fork_free_calibration.json`; spare second-look seeds 114_300-114_599, 115_200-115_399.
- plan reviewer a8b33dca346eb11a9 resumed for closing check. Status: done; open B6 (CLI subprocess vs monkeypatch), N9-N12 — all ruled (a), mechanical; no owner item.
- fold planner a872b2c33fff577c5 resumed: fold B6/N9-N12. Status: done. Plan settled (closing check done; no owner items).
- implementer-P1 ad3527b2bb5817620 (opus): plan §7 step 1 only → `11-prototype-p1.md`; stop and report stop rules. Status: done; no stop rule fired (multiplicity ruled not fired, see rulings 'P1 outcome'); floors bind; prefix branch; check-held-out projected ~60-62 min (flag at close).
- implementer a0405ec6fa1964889 (opus): plan §7 steps 2-7, tdd, commit per step; stops on red 09/10 seed or uncovered weakening. Status: rotated; handoff `11-implementer-1.md`; commits 7ec6451 (step 2), 172b879 (step 3), 7d05e6c (steps 4-5). Stopped.
- implementer-2 ab2623ddcc2143136 (opus): same brief + continue from `11-implementer-1.md`. Status: rotated at 209k; handoff `11-implementer-2.md`; step 6 uncommitted; its driver run was killed by the stop (no output) — successor reruns.
- implementer-3 a02c6d39ccffa8641 (opus): continue from `11-implementer-2.md`, finish steps 6-7. Status: done; commits 1e065f8 (step 6), 634d4a8 (step 7), 66c08f0 (fix). Driver EXIT=0, floors 0.1/0.3, digest 148ba19d…6862. `make check` exit 2, `1599 passed, 13 deselected in 1684.51s`, only stamp red. Open for fixer: held-out numbers in ADR 0003 + docstring; slow_stamp.py '~20 min' message (approval needed).
- Lesson: before TaskStop of a rotated worker, check its background jobs; stopping kills them.

## Decisions

All rulings in `11-rulings.md` (self-decided from Codex + critic; no owner question: OQ4 depth and O2 multiplicity escalate only on pre-declared P1 stop rules). Plan path stays `11-plan.md`.

CLOSED 2026-11-15. Next: none.

## Code review

Standards (a5827b21f9878c76d) + Spec (a34ca48d78c59b354) from BASE..66c08f0. Fix/owner/pass with reasons: `11-fix-list.md` (fix F1-F9; owner: none blocking, report held-out ~60 min and check 1684 s; pass 4 smells).
- fixer a5bcb44b364ec26b5 (opus): F1,F3-F9 → check-slow → check-held-out → F2 → check → close-out comments. Status: done; commits 98db7ff, 7a05d7a, 62428d8; all gates green (check @7a05d7a: `1601 passed, 13 deselected in 1964.25s`); held-out 0 fakes, AC3 100/100 each.
- Ticket marked resolved: aae4084.
