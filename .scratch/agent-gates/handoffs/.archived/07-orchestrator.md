# 07 orchestrator log

- Ticket: `.scratch/agent-gates/issues/07-seed-breadth-split.md`
- BASE: `21487c9580837c4fa7cf3d6a00c608ad81ecfe61`
- Args: MIN_MODEL=opus, WORKER_LIMIT=200000, SELF_LIMIT=200000
- User rule: before any human question, get a fresh-context Fable critic's adversarial second opinion, critically review it, decide by best practice; ask the human only on taste, external knowledge, or hard-to-revert architecture.
- Plan path: `.scratch/agent-gates/handoffs/07-plan.md` (pending)
- Plan-review path: `.scratch/agent-gates/handoffs/07-plan-review.md` (pending)
- Milestone gates (fixer, end): `make check-slow`, then `make check` (no `make measure`: detector unchanged).

## Workers

| Role | agentId | Brief | Status | Handoff |
|---|---|---|---|---|
| planner | a2ede03aead950377 | step 0 durations run (log `07-step0-durations.log`), collect-only id lists for check/check-slow, write `07-plan.md`, ticket Comment | done: ae3b350; step 0 `1009 passed, 4 deselected in 852.15s` (load 2.05 at start); projected inner loop ~265 s (~185 s idle), slowest ~7 s; misses 2 min | — |
| plan reviewer | a1c0de1411746bbb9 | blind: ticket + plan, per plan-review.md → `07-plan-review.md` | done (no commits): B1 `--lf` exit 4 from all-wide check; B2 66-scorched not cached (two keys); B3 dark regression seed 93130 marked wide; B4 step-0 noise up to 6x; O1 seed-count 1 scope; 5 notes. Keep for closing check. | — |
| Fable critic | af7c8a087a4609f2b | read-only adversarial opinion on Q1-Q3, O1, target realism, B1-B4 | done: no owner Q now; target ~170-175 s idle in scope; owner Q likely after measurement | — |
| planner (fold) | a2ede03aead950377 | fold rulings below into plan | done: 69c8730 (plan only); projects ~180 s idle; open: step-0 Comment load-spike line left for the implementer to correct (accepted); read-only cache fallback (implementer decides); analysed-once count is checked by a scratch plugin only (accepted) | — |
| plan reviewer (closing) | a1c0de1411746bbb9 | closing check on 69c8730 | done: nothing open; N6 (the `--lf` test plants its failing-wide function apart from the all-wide cases) passed to the implementer; `analyse` accepts read-only frames | — |
| implementer | ab89bc15ed1091084 | tdd per plan 69c8730 + N6; measured idle `make test-fast` + after-id comparisons; no check/check-slow/measure; stop and report if >2 min | done: ee2f774, bc9c441. `make test-fast` at ee2f774: EXIT=0, `556 passed, 476 deselected in 252.89s`, load 0.81→1.57, slowest 8.21 s (run 1 was 336 s on a load spike). check collects 1028 (1009 + 19 new), check-slow 4. Misses the 2 min target. | — |
| Fable critic 2 | ab09f9799cd7d9f49 | read-only: where the 253 s goes, remaining levers in and out of scope, the option set for the owner | done: about 183 s idle estimated (run 2 was load-bound, peak 3.35). In scope: shared cache for identical frames (about 4 s), thin the verdict sweep (about 7 s). Out of scope: spike + clip aggregates `wide` (about 29 s), seed count 1 (about 18 s). Nothing reaches 2 min. Load of 3-6 during the runs is unexplained. | — |

Planner open questions (settle in one pass with review items; Fable critic before any human question):
- Q1: `clear_stripes_in_mottle` 10 seeds (all CASES) vs 2 — planner recommends 10 (+5 s).
- Q2: shared cache for two-region frame (analyse once) vs twice (+7 s) — planner recommends cache.
- Q3: 40 spike-aggregate pairs (46 s): (a) keep unmarked [rec], (b) mark wide (outside approval scope), (c) cut → one 42 s item.
- Fallback: INNER_LOOP_SEED_COUNT=1 if measured >150 s (~-25 s).
- Note: helper imported only by test_analyse.py to avoid a slow_stamp.py edit.

## Decisions

The critic's verdict, checked critically by the orchestrator. Its points are sound; the free-frame cache is the same identical-call memoising as Q2, so it does not change how tests reach the detector.
- Q1: keep 10 seeds, because the ticket says "every Period/Angle case".
- Q2: use the cache, because the ticket says "analysed once" and existing memo helpers already follow that pattern.
- Q3: (a), keep the pairs unmarked, because (b) is outside the approval scope and (c) creates a 42 s item.
- O1: the seed count stays 2. It saves only about 17 s, and lowering it is an owner call.
- Target: measure first. If the run is over 2 min, ask the owner once before the closing gates: accept about 3 min, or approve Q3 (b).
- B1: fold, reading the option with `getoption("lf", False)` (plain `getoption("lf")` raises under `-p no:cacheprovider`).
- B2, B3 and B4: fold as the review proposes.
- The review's 5 notes go to the planner, which folds or passes each with a reason.
- Extra folds from the critic:
  - cache the free-frame score in `_spike_pair_scores`;
  - fix the arithmetic (33 items, not 23);
  - add the CLAUDE.md note on rerunning a `wide` id;
  - add coverage asserts in `tests/test_inner_loop.py`;
  - note that `tests/regions.py` is not stamped.
- 2026-11-13, owner ruling (AskUserQuestion): accept about 3 min; no further narrowing. The fixer adds the in-scope wins:
  - a shared cache for identical frames (about 4 s);
  - a thinner verdict sweep that keeps every threshold kind (about 7 s).
  It then records one quiet `--durations=0` idle time in the ticket, and the ticket notes that the 2 min target was waived by the owner.

## Code review (from BASE): standards a81d71927eaf0cd22, spec a38c57bf7bf0229c0

Fix:
- F1. The `::` exemption in conftest disables the all-wide check for a whole mixed collection. Exempt only when every arg names a node. (Reported by both reviewers.)
- F2. `_size_params` re-implements `diagonal`; `SIZE_PERIODS` and `(-10, 10)` are duplicated; its docstring is stale. Reuse `diagonal` and the shared constants.
- F3. `_spike_pair_scores` still regenerates the free frame that `_free_score` already builds. Generate it once per seed.
- F4. The names `_WIDE_DROP`, `_FIRST`/`_SECOND` and `_per_seed` hide their roles. Rename them.
- F5. `_sweep_report` special-cases `two-region` next to a `SWEEP_FRAMES` lambda. Keep one call site.
- F6. `diagonal` builds `pairs` twice. Build it once.
- F7. Seed subsets are hard-coded and not tied to `INNER_LOOP_SEED_COUNT`. Derive them from the constant where the spec allows. `keep=1` for the two-region frame stays, since the spec says "analysed once". `test_inner_loop.py` asserts guard the rest.
- F8. Cache hits depend on the positional spelling of arguments. Normalise the cache key, so a different spelling cannot silently miss.
- F9 (decided here; no owner question needed, since the strict reading costs about 0 s net with thinning). The spec reads "every frame kind (the sweep frames, ...)". Use the strict reading: every one of the 18 sweep frames appears at least once in the inner loop. Combine it with the approved thinning: every threshold kind still appears, but not on every frame.
- F10. Add the in-scope speedup: a shared cache for identical frames.
- F11. Fix the step-0 Comment's load-spike line, if the implementer has not already.

Pass:
- The `make check` count went from 1009 to 1028. The 19 new ids are all in `tests/test_inner_loop.py`, and no old id is missing; the Comment explains this.
- The read-only freeze of the cached Report is harmless, and it protects the shared cache.
- `_free_score` reuse returns an identical result and is not a weakening; the plan already folded it in.
- The `_pytest` `ParameterSet` import: pytest has no public type for it, and it is used only for typing and construction.
- The spike and clip aggregates keep every seed in the inner loop. This is the owner's Q3 (a) ruling plus the "accept about 3 min" ruling.

## Next

CLOSED 2026-11-14. The fixer landed 63672c1, 72e67e2, 3f09325 and b043708. Gates:
- `make test-fast`: `558 passed, 478 deselected in 190.40s`.
- `make check-slow`: `4 passed, 1032 deselected in 310.85s`.
- `make check`: `1032 passed, 4 deselected in 535.91s`, at 3f09325-dirty (dirty only in unrelated .scratch files).

The F2 seed reassignment in the size tests is passed: coverage is unchanged, and `make check` runs every seed. No prototyper worktrees were used. The `.claude/worktrees` entries belong to other sessions and were left alone.

Earlier note: fixer ab1e4138c6558caba running: F1-F11, a quiet durations run, check-slow, check. Then Close. Old plan for this step: spawn the fixer: review fixes, the two free wins, one quiet `--durations=0` run, then check-slow, then check.
