# 04 orchestrator log

- Ticket: `.scratch/agent-gates/issues/04-runtime-seed-guard.md`
- BASE: `43d089780ac7907edbc72b10ff3866cb74bd63f3`
- Args: MIN_MODEL=opus, WORKER_LIMIT=200000, SELF_LIMIT=200000
- Plan: `.scratch/agent-gates/handoffs/04-plan.md` (pending)
- Plan review: `.scratch/agent-gates/handoffs/04-plan-review.md` (pending)

## Workers

- planner `a8f4fd964de3ed9a4` (opus): write `04-plan.md` from ticket+spec+code; report open questions. Status: done (plan written). Open Qs: Q1 audit event in `generate` vs patch from conftest (rec audit event); Q2 split USED_SEEDS 0-199 vs exempt overlap (rec split; lockfile edit, approval); Q3 marker in tests/seed_guard.py vs package (rec tests); Q4 guard standalone feasibility script (rec yes); Q5 one approval bundle for conftest+registry/lockfile+CLAUDE.md (rec yes). Key finding: feasibility gate generates frames in spawned workers; guard must reach them.
- plan reviewer `ab7a22bf135463a8e` (opus, blind): review into `04-plan-review.md`. Status: done. 0 break, 0 prototype, 2 owner (O1 seeds 0-9 tuned `_A0`, used by tests/test_analyse.py; rec don't register + record reason w/ owner ruling. O2 = Q1-Q5 stand, agrees), 7 notes (N1 T5 fake score_batch assert allowed ranges per call; N2 keep disjointness test name ticket 05 refers to; N4 info).

## Review items

- Notes N1-N7: fold all (planner folds); N2 by keeping the test name.
- Codex adversarial (scratchpad/04-codex.md): agrees Q1-Q4; disagrees O1 (register 0-9: seed 0 noise 0 score 326.55->36.28 when _A0 0.001->0.003, verdict flips); holes: pool without initializer; calibration frames/scores reused after an allowed block (no generate event).
- Q1 self-decided: audit event in `generate` + explicit worker install (Codex: module-attr patch misses aliases in test_analyse.py:10, feasibility.py:45).
- Q3 self-decided: marker in tests/seed_guard.py (ticket 07 wraps its driver call; folder-input provenance is ticket 07's own concern).
- Q4 self-decided: guard feasibility.main() incl. workers, plus standalone-process negative proof (fold).
- Holes self-decided: narrow the claimed guarantee to "seeds passed to generate", document pool-without-initializer and post-block reuse as known limits in plan + ticket Comments (ticket scope is generator seeds).
- Owner rulings 2026-11-11: O1 register 0-9 as _A0 calibration, re-seed caught tests onto unused 10-99 seeds (failing re-seeded assertion = finding, stop); Q2 split USED_SEEDS 0-9/10-99/100-199; Q5 approve bundle (conftest, protected.py+lock, CLAUDE.md).
- Planner resumed to fold all into plan + write rulings to ticket Comments. Done; plan marked settled. Re-seed s -> s+20 (20-29 shared). Self-decided: shared re-seeds OK (status quo sharing). My concern to check after closing check: "seed 0 borderline case re-picked by a scan" = possible seed-shopping; ensure the scan criterion is fixed a priori, not "first seed that passes".
- Closing check sent to reviewer ab7a22bf135463a8e. Done: O1/O2/N1-N7 closed. New: B1 dedupe-by-value hides same-valued ranges (fold: dedupe by `is` + red test); O3 borderline re-pick scan (self-decided accept: window is fixture's defining property, rule fixed a priori, lowest seed 20-99; resolves my seed-shopping concern); N8 step 3 test-fast red by design (fold); N9 "+20" wording vs 10-19 stay (fold).
- Planner resumed for final fold (B1, N8, N9, O3 record). No further closing check. Done: B1 identity dedupe + test + plant P6; N8 step 3 runs lint + 2 tests; N9 wording; O3 in R1 + ticket Comments. Plan phase closed.
- implementer `a0f0da0de64e191fe` (opus): build per settled plan, tdd, commit to main, plants proved+reverted, check-slow in bg with log in handoffs/, quote gates. Status: done. Commits 86599da registry, 2009908 audit event, 49fe7d8 guard+installs+T1-T7+re-seeds, c7c9b72 CLAUDE.md, d21e659 T5 fix, 9cc3f2c ticket evidence. make check @d21e659 exit 0 `229 passed, 4 deselected in 99.70s`; check-slow exit 0 `4 passed, 229 deselected in 2464.59s` (no src change after). 144 tests caught (all 0-9), all re-seeds green; borderline pick seed 22 (217.09); P1-P6 red then reverted. Open: ticket Status line; timing median not in log (pytest captures print). check-slow log: handoffs/04-check-slow.log.

## Code review

- From BASE 43d0897 to 9cc3f2c. Standards reviewer `a9c665a0422f9c0e8`, Spec reviewer `a3885e19960246151` (opus, background). Standards done: no hard violations. S1 3 calibrating() blocks in test_seed_guard.py (51,65,86) unapproved per new CLAUDE.md rule + ticket Comment false ("only block in feasibility.measure"); S2 unnamed seeds/limits in test_seed_guard.py:83, 10_000, timeout=45; smells: SINGLE_FRAME_ALT_TEST_SEEDS[i] index, suffix-convention registry, BORDERLINE alias + empty SeedGuardError.__init__, dup ValueError msgs, T5 fake uses privates, install() ignores allowed after first call. Spec done: no blocking gaps; timing median missing; Status line; SEED_SETS calibration link by name; link check by value (harmless); measure_all unguarded outside pytest/main().

Sorting (orchestrator, under owner delegation 2026-11-11):
- FIX: S1 approve the 3 calibrating blocks (testing the marker needs it) + correct false Comment; S2 name seeds/10_000/timeout=45 in protected.py+lock (CLAUDE.md: seeds/limits live there); positional SINGLE_FRAME_ALT_TEST_SEEDS[i] -> named scalars; delete empty SeedGuardError.__init__; install() raise on different repeat allowance; add known limits (name-linked calibration plans, measure_all unguarded outside pytest/main) to ticket Comments.
- PASS: BORDERLINE alias (keeps import sites stable); duplicated ValueError suffix (minor); T5 fake uses privates (fake must mirror scoring); suffix-convention registry (plan's design, ticket 05 relies on it; larger refactor than this ticket warrants); SEED_SETS value comparison (harmless, calibration entries checked by identity); timing median (needs a check-slow re-run, owner rule forbids without a src change); shotgun installs (inherent across processes, CLAUDE.md lists them).
- Status line: orchestrator sets it at close.
- OWNER: none.
- fixer `a483913bb41833f8e` (opus): fix list above, make check only (no src change → no check-slow). Status: done. 19d13ed (SeedGuardError init removed, install() raises on different repeat allowance), 84b1f8a (constants to protected.py+lock, named scalars), 9a08356 (ticket Comments). make check exit 0 `230 passed, 4 deselected in 98.52s` @84b1f8a. Left inline: `range(0, 10_000_000)` in T3. PASS: it's a deliberately oversized invalid argument, not a seed set.
- Close: 56f081e ticket Status resolved; 23b55ca CLAUDE.md (weakening-move delegation, check-slow only on src change).

## Status: CLOSED 2026-11-11

## Next
Wait for fixer; verify make check quote; then close: Status line resolved, CLAUDE.md weakening-move delegation edit (separate commit, writing-for-agents), archive files. Owner rule 2026-11-11: re-run check-slow only if src/ changed since last green run; put this in fixer brief. Owner rule 2026-11-11: weakening-move approvals are self-decided via Codex + own judgment; stop only if undecided or no clearly good motivated reason. After implementer finishes (it edits CLAUDE.md), update CLAUDE.md's weakening-move bullet to say so (load writing-for-agents), separate commit. Owner question pending: are weakening-move approvals self-decidable via Codex, or do they still need the owner (CLAUDE.md)?
