# Orchestrator log — ticket 03

- Ticket: `.scratch/stripe-detector/issues/03-feasibility-gate-weak-stripes.md`
- Spec: `.scratch/stripe-detector/spec.md`
- BASE: `c0d99ab1fd2c838b6278b45fbe521cc4ff980379`
- Args: MIN_MODEL=opus, WORKER_LIMIT=150000, SELF_LIMIT=150000
- Plan path: `.scratch/stripe-detector/handoffs/03-plan.md` (pending)
- Plan review path: `.scratch/stripe-detector/handoffs/03-plan-review.md` (pending)

## Workers

- Self watcher: background task `bunlybf8g`.
- Planner `a8aeb3a04080d6c39` (opus): write `03-plan.md` from ticket+spec+code at c0d99ab, list open questions. Status: done (plan written; may have leftover background work). Watcher `b2d7bte2x` stopped. Open questions O1–O8 (see plan's final section); planner's preliminary measurement: 256×256 likely passes (thr≈61, 200/200 m=0.2 detected, thin margin at period 3); 1600×400 heavier null tail, uncertain; 5.9 s/frame.
- Plan reviewer `ac1dbdb05aaf54e49` (opus): blind brief (ticket + plan paths, plan-review.md) → `03-plan-review.md`. Status: done; watcher stopped. Review: 4 break, 1 prototype, 5 owner, 8 notes.
- Prototyper `aa79c7cdba1dc5407` (opus, worktree): answer P1 (full-frame 400×1600 m=0.2 at own 1% threshold) → `03-prototype-p1.md` + `.py`. Status: done; watcher stopped. P1 = clear pass: 98/100 at full frame (CI 0.930–0.998), threshold 128.95, 6.24 s/frame single process. Worktree `.claude/worktrees/agent-aa79c7cdba1dc5407`, branch `worktree-agent-aa79c7cdba1dc5407` (c674f3a) → remove at close.
- Planner `a8aeb3a04080d6c39` resumed via SendMessage to fold B1–B4, N2–N6, N8, P1, and O1–O5 rulings. Status: done — plan folded (03-plan.md 10:28). Watcher stopped. Plan moves P1/premeasure files to `.scratch/stripe-detector/evidence/` during implementation.
- Plan reviewer `ac1dbdb05aaf54e49` resumed for the closing check. Status: done — no items open; watcher stopped. New notes N9 (show the probe CI next to a FAIL) and N10 (set `*_NUM_THREADS` before the numpy import) → fold, passed to the implementer by pointer.
- Implementer `ac2e5948d9e7762a9` (opus): build the plan test-first, apply N9/N10, run the slow gate, write results, update ticket status per gate path, commit to main. Handoff path `03-implementer-handoff.md` if it stops early. Status: done; watcher stopped. Commits 22ee548, 7a5b00a. Gate PASS (256²: 490/500, FA 7/1000, thr 74.12; probe 100/100; 6.31 s). 4 slow tests green (40 min); default suite 194 passed, mypy clean. Left ticket 03 status for the owner. Deviation: the dirty flag only looks at code paths.
- Observed: the ticket-02 file has an uncommitted change marking it resolved. It wasn't in the session-start git status and isn't ours → owner item, left untouched.

- Code review (from c0d99ab): Standards reviewer `a92404c200db0c021`, Spec reviewer `a839d6e3e045c4362` (both opus, background, watchers armed). Standards: done, S1–S7. Spec: done, P1–P7 (spec met; seeds disjoint, stats and doc↔JSON verified). Both watchers stopped.

## Code review sort

Fix:
- S1 + P3: `tests/feasibility.py` imports the private `_order` from private `_calibration` → expose k through a public API and drop the private import (rule from ticket 02; the plan's exception covers test_calibration.py only).
- S2 + S3: seed sets written out twice; seed/shape clump → one seed-plan type / `SEED_SETS`.
- S4: the Period/Angle case as a bare tuple → NamedTuple.
- S5: `_table` / `_result_dict` → methods of RateResult.
- S6: names `fz`, `_order`, `d`, `sel`/`cal`/`free`.
- S7: repeated exceedance count → helper; "400x1600" literal → derive from PROBE_SHAPE.
- P1: record the worker count in run_info/JSON.
- Because the fixes touch measurement code, the fixer re-runs the slow gate. Numbers must reproduce exactly (deterministic seeds); the JSON is regenerated, which also records the worker count.
Owner:
- Ticket 03 status (left `ready-for-agent`; recommend `resolved` on PASS).
- Uncommitted ticket-02 edit (marks it resolved). Not from this session's workers.
Pass:
- P2: dirty flag narrowed to code paths. Deliberate and documented; N5 was a note I folded, not an owner ruling.
- P4: "Weak spots" cause labelled "Not investigated"; harmless context for 07.
- P5: 5.2–6.4 vs 5.24–6.39 s is rounding.
- P6: AC7 "(Not triggered)" tick matches plan §6; status → owner item.
- P7: timing warm-up reuses TIMING_SEED, but never reaches a threshold; no leak.

- Fixer `a101e33d25ed67521` (opus): fix S1–S7 and P1, run the full suite, re-run the slow gate, numbers must reproduce exactly. Don't touch ticket 02 or the ticket 03 Status line. Status: running. Watcher armed. Commit f0c8f6c landed; a slow script run was in progress at 12:20.
- User authorized raising the gate's CPU use (12:20). Current default is cpu_count()//2 = 8 workers (machine: 8 cores / 16 threads). Told the fixer to let the current run finish, then make the default three quarters of the logical CPUs (12 here; the user keeps 4 for their own work), edited in place with no addenda.

## Review item dispositions

- B1, B2, B4: break → planner folds (B4 depends on O1 answer).
- B3: break → planner folds once O1 is ruled.
- P1: prototype → prototyper above.
- O1–O5: owner → asked user in one message.
- N1: pass — agrees plan O1/O2/O8 need no owner ruling; keep as plan recommends (no tuning, leave THRESHOLD=154, fixed CASES).
- N2, N3, N4, N5, N6, N8: fold — doc/number fixes and small robustness changes.
- N7: pass — confirms the plan works, no change needed.

## Decisions

- User rulings (2026-11-10):
  - O1: decide after P1. Gate at 256×256 if full-frame m=0.2 ≥ ~95%; otherwise also gate at 1600×400.
  - O4: measured rate ≥ 90%, CI reported.
  - O2: private `_calibration`.
  - O3+O5: default-skip slow (`-m 'not slow'`), and a failed gate gets `xfail(strict=True)` pointing at the result doc.
- O1 applied from the user's rule: P1 measured 98% ≥ 95% → gate at 256×256, full-frame probe informs only. Note: CI lower bound 0.93 < 0.95, but O4 ruling uses point estimates.
- B3 folded as: final-run full-frame probe < 95% → treated as gate fail (ready-for-human). This extends the user's O1 rule.
- B4 folded as: probe stays small; its false-alarm check is labelled uninformative, with the tolerance band.

- Ticket leaves design choices open (batch sizes, threshold statistic, seed split, script vs slow test, result doc location) → spawn planner.

## Next

CLOSED (2026-11-10). Fixer done: f0c8f6c (review fixes), ffffbed (workers = 3/4 of CPUs = 12), 102d67c (regenerated JSON/doc). Numbers reproduced exactly; default suite 203 passed, mypy clean; slow 4 passed in 37.2 min at 12 workers. Timing median 7.56 s (under 10 s). Prototyper worktree removed; files archived.
Owner items handed to the user: ticket 03 Status; uncommitted edits to issues 02 and 07; the new `.scratch/agent-gates/`.
