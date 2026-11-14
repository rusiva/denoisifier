# Ticket 07 orchestrator log (stripe-detector)

- Ticket: `.scratch/stripe-detector/issues/07-calibrated-stripe-score.md` (working-tree edit adds the `make check-slow` criterion; uncommitted at start)
- BASE: `987caec7eade8a0c4b5f92b67198480396d926bc`
- Args: MIN_MODEL=opus, SELF_LIMIT=200000, WORKER_LIMIT=200000
- User correction 2026-11-14: second-opinion source is now `/codex:adversarial-review` (background); Fable critic only as fallback if codex is unavailable. Codex re-review of the rulings so far → `07-codex-review.md` (bash bhz1so3nu, running).
- (superseded) User rule: before any human question, get an adversarial second opinion from a fresh-context Fable critic, then decide myself by best practice; only ask the human on taste, external knowledge, or hard-to-revert architecture.
- Milestone gates (fixer, end): `make measure` (detector changed), update stored thresholds, `make check-slow`, `make check`.
- Plan: `.scratch/stripe-detector/handoffs/07-plan.md` (pending)
- Plan review: `.scratch/stripe-detector/handoffs/07-plan-review.md` (pending)

## Workers
- planner `a2c1c3f9205308a52` (opus): write `07-plan.md`, map ACs to tests, address 11-13 Comments, list open questions tagged. Status: done; plan written, open Q1-Q9 (Q1 shape, Q2 check-slow time +28 min, Q3 spikes/frame, Q4 gating jumps, Q5 clipped, Q6 API/CLI, Q7 exact equality, Q8 skip measure, Q9 other shapes).
- plan reviewer `a4008950409810673` (opus, blind): `07-plan-review.md`. Status: done; B1-B5 break, P1 prototype, O1 (skip measure vs CLAUDE.md), O2 (recalibration workflow in CLAUDE.md), N1-N8. Awaiting closing check later.
- prototyper P1 `a8a17091543a85483` (opus, worktree): fast-tier flip table + 50 spiked full-frame scores on 104_000-104_049 → `07-prototype-p1.md`. Status: running.
- Fable critic `a7cc9ec811a2dcb47`: adversarial review of Q1-Q9 into `07-critic-plan.md`. Status: done → `07-prototype-p1.md` (copied from worktree `.claude/worktrees/agent-a8a17091543a85483`; remove at close). At T 70-110 only the 5 `BORDERLINE_TEST_CASES` and the `THRESHOLD` lockfile line go red (W4 covers); stripe-free test max 53.3, profile-only max 38.3 (not ~72); full-frame 30-spike p99 ≈ 77.6, 5/50 zeros; 293 vs 30 spikes: median change 0. Q3 was fixed at 30 before these results (not tuned on them).

- fold planner `af494af166f42ea67` (opus): fold all Decisions into `07-plan.md`, Rulings + Pre-declared rules sections. Status: done. Q2 → marker `held_out`, `test_held_out_calibration.py`, check-slow `-m "slow and not held_out"`, new `make check-held-out` (added to background hook list), close order check-slow → check-held-out → check; at measure milestones held-out runs as a separate step after re-store (planner's reading; I accept it: running against a stale calibration would be meaningless — within the owner's ruling, no question). Critic's 2% bound dropped (held-out out of check-slow).
- plan reviewer closing check: done. All closed except B6 (folded by me into 2.5 + section 3: `evaluate`/`held_out_check` take optional `calibration=None`, gate passes None) and N9 (folded into step 8 docs). Plan settled; no second closing check.
- Codex adversarial review of W1-W6, W8-W10 + lockfile approvals: done → `07-codex-approvals.md`. My approvals (all codex conditions accepted; W2 split core/guarded entry; W4 + `PACKAGE_CALIBRATION_DIGEST` + frozen re-pick rule; W10 empty; new W11 inner()) written to plan §8.1. No owner question.
- implementer `a60bfd101a971e951` (opus): plan steps 0-8 incl. step-5 calibration run; commits per step; CLAUDE.md wording to `07-claude-md-draft.md`; leaves check-slow/check-held-out/measure/step 10 to fixer. Status: running.

## Decisions
- P1 → B4 rule: keep the critic's 3-point rule as the pre-declared rule; the only expected application is the W4 borderline re-pick; no explicit-threshold list needed unless step 6 shows otherwise (then it's a finding, not a silent fix).
Critic file: `07-critic-plan.md` (Fable). My reading agrees with it except where noted.
- Q1 note: 400x1600 only; docs say "expected lower on crops", not a guarantee; larger area not covered.
- Q2 OWNER (asked 2026-11-14): reverses agent-gates/05 "check-slow about 6 min" ruling; (a) all in check-slow ~38-47 min vs (c) reproduction only in check-slow ~20-23 min + held-out at milestones (Makefile/marker edit). Sizes 300/300/100 kept. OWNER RULED 2026-11-14: "Reproduce only" — check-slow runs reproduction only; held-out tests marked slow + own marker, run once at this ticket's close and at measure milestones; Makefile/marker edit approved by owner (record in ticket Comments).
- Q3 note: 30 spikes/frame as `CALIBRATION_SPIKES`, ADR assumption; tell owner at close. Not tuned on P1.
- Q4 note: keep score, document jumps, follow-up needs-triage issue; doc the 0-atom tie.
- Q5 note: one-off clipped measurement at frozen code after review fixes; report count + Clopper-Pearson CI, not pass/fail.
- Q6 note: API as plan minus `Report.false_alarm_rate`; no `python -m denoisifier.calibration` (E4): entry point in a module nothing imports (no pyproject edit).
- Q7 note: exact equality; failure message reports #differing seeds + max rel diff.
- Q8/O1 note: skip `make measure` on critic's two conditions (diff only threshold source; regression scores bit-identical to saved pre-ticket `.gate/check-slow-measurement.json` — save a copy first). Not a CLAUDE.md departure ("only when the detector changed"). Record in Comments.
- Q9 note: same threshold all shapes; add line to ticket 08 Comments.
- B1 break: split compared `settings` vs uncompared `run_info`; JSON-normalise.
- B2/E3 break: `is None`; rate-0 tests via analyse and CLI.
- B3/E5 break: fast tiny-plan test of slow assertions; pre-declared rule: red AC2/3 at closing gate = stop, report; no reseed/size/tolerance change. Step-5 early warning: threshold near/above ~110 → report.
- B4 break: critic's 3-point rule; explicit threshold only `GATE_STORED_THRESHOLD`, only on a list approved before step 5 (from P1).
- B5 break: keep or rename sweep kind; add `test_inner_loop.py:272` to W table.
- E1 break: split fixture into 3 module fixtures; per-test timeout ~2400 s; runtime figures from measure rate.
- E2 break: real crop is 64x64; use it in folder test; `kinetic.asc` for reader error.
- E6/N1 note: fix 2b power figures.
- O2 note (fold A): CLAUDE.md Gates line for re-store procedure incl. when re-store is NOT allowed; add driver --out to Write targets. Wording shown to owner at close.
- N2-N8 notes: fold (N4 score path frozen from step 5; N5 `__main__` guard docstring; N8 region outputs note).
- Codex review (`07-codex-review.md`, saved by me; codex ran read-only): verdict needs-attention, no owner question. Fold all three:
  - C1 break: drop the unconditional combined 2% false-red claim / 0.964 baseline for AC 3; state it as conditional on a baseline justified for the new threshold and spiked population; keep 90/100 rule predeclared, untuned.
  - C2 break: Q8 skip condition rewritten: summary equality of `.gate/check-slow-measurement.json` is supporting evidence only; primary = score-path diff review (analysis/_local_stripes/_data_quality/synthetic vs fd59d0c touches only threshold source) + a serial-vs-pool equivalence check of per-seed scores/ids/order after the `run_pool` refactor.
  - C3 break: AC 5 round-trip with 12 frames uses `false_alarm_rate=0.1`; assert default 1% raises clearly; default-rate injection test uses a calibration of ≥99 scores.
  - B4 refinement: explicit `GATE_STORED_THRESHOLD` only for named property tests, never described as calibrated for other shapes; default-verdict coverage kept.
- Critic smaller points: keep `THRESHOLD_CALIBRATION_SEEDS` registered; state check-slow overall false-red bound 2%; AC 3 pooled accepted in words.

## Next
Wait for implementer report (or a section-13 stop). Then code-review from BASE, sort fix/owner/pass (codex adversarial for owner-candidates), spawn fixer (fixes + step 10 + closing gates per plan step 11).
