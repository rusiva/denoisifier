# 01 orchestrator log

- Ticket: `.scratch/stripe-detector/issues/01-first-end-to-end-version.md`
- BASE: `ca0a0ee36856ac8ee81bd2ad3a7c3bdbbdecff79`
- Args: MIN_MODEL=opus, WORKER_LIMIT=200000, SELF_LIMIT=200000
- Plan path: (pending) `.scratch/stripe-detector/handoffs/01-plan.md`
- Plan review path: `.scratch/stripe-detector/handoffs/01-plan-review.md`

## Workers

- planner `aa930aafebded32a7` (opus, watcher armed). Brief: write `01-plan.md` from ticket/spec/glossary/ADR; settle seams, generator, reader, analyse/Report, JSON/CLI, simple detection, AC→test map; no code. Status: done (plan at `01-plan.md`). Handoff: none.
- plan reviewer `ab510aa682d71c027` (opus, watcher armed). Blind brief: ticket + plan path, review per plan-review.md into `01-plan-review.md`. Status: done (2 break, 1 prototype, 4 owner, 8 note).
- prototyper `a54466ed65a18faf7` (opus, worktree, watcher armed). Brief: answer P1/B1 (score robust at noise 0/0.001/0.01, threshold from seeds outside 0–9), confirm B2 no NaN; findings to `01-prototype-score.md`. Status: done. Findings copied from scratchpad to `01-prototype-score.md` (worktree blocked direct write; worktree auto-removed). Result: floored score `P_peak / max(median band P, (1e-3·sum(w)/2)^2)`, threshold 500 (seeds 100–199); no NaN.
- planner `aa930aafebded32a7` resumed to fold B1/B2/P1/N1–N8/owner rulings. Status: done — plan rev 2 folds all. Planner's own call: `.python-version` pinned 3.11 (fallback installed Python). Non-blocking open: owner to check angle sign on a real Solis view.
- plan reviewer `ab510aa682d71c027` resumed for closing check. Status: done — nothing open. New N9 (note): constant-frame test assert `score < threshold`, not `== 0.0` → passed to implementer brief.
- implementer `a619ffdba2479f6ff` (opus, watcher armed). Brief: build plan test-first with tdd skill, commit to main; includes N9. Status: done — commit `7fe505b`, 66 tests green (py 3.11.15). Departures: write_frame_csv round-trip test never red; 3 CLI error-exit tests passed before cli.py existed (vacuous red). Open: O1 Solis check; ticket Status line; handoffs not committed.

Plan phase done. Plan path: `.scratch/stripe-detector/handoffs/01-plan.md` (rev 2).

## Review dispositions
- B1 break → planner folds (after P1 result).
- B2 break → planner folds: guard constant/non-positive frames, no NaN, CLI never writes invalid JSON.
- P1 prototype → prototyper above.
- O1–O4 owner → user ruled all "as planned": O1 sign as plan §3 (document in GLOSSARY), O2 schema top-level/null/threshold, O3 FrameFile now, O4 stdout default + `-o`, exit 1/2. Planner Q1–Q6 accepted as recommended.
- N1 fold (update comment after P1). N2 fold (threshold from seeds outside 0–9). N3 fold (provisional constant in step 4). N4 fold (catch OSError read+write; note non-atomic write). N5 fold (`shutil.which` test of console script). N6 fold: keep uv-generated `.python-version`/README; set requires-python consistent with pin — low stakes, planner picks. N7 fold: drop `slow` marker (ticket 07's). N8 fold: concrete min size 40 px/side, testable.

## Planner open questions (recommendations)
1. Package name `denoisifier`.
2. Period/angle `None`/`null` when not striped.
3. Period/angle top-level in Report now; ticket 05 moves to regions.
4. `read_frame` returns `FrameFile(frame, notes)` now (stable for ticket 04).
5. Include `threshold` in Report now.
6. CLI writes JSON to stdout unless `-o`.

## Decisions

## Code review

Running from BASE ca0a0ee (HEAD 7fe505b): standards reviewer `aa98f1ee761875567`, spec reviewer `a1422823a487dd088` (both opus, background). Spec reviewer also checks the 3 vacuous-red CLI error tests.
Standards report in: one hard breach ("amplitude" synonym in analysis.py `amp_floor`/A0 comment vs GLOSSARY Avoid list); ADR-0001 conflicts surfaced in comments (compliant); glossary gap for score/threshold/striped; smells: mysterious names in analysis.py, angle convention restated 4x, test tolerances duplicated, CSV format split frame_io/synthetic, `to_json(indent)` unused, FrameFile.notes (owner-ruled O3), long `analyse`. Spec report in: 3 CLI error tests don't pin behaviour (main finding); argparse exit 2 untested; constant-frame score==0.0 not pinned; generator oracle checks absent (not in ticket); py.typed + non-finite test minor creep.

### Fix
- F1 tighten 3 CLI error tests: stderr starts `denoisifier: error:`, one line, cause-specific detail (path / "no positive light" / missing dir name). — tests currently pass vacuously.
- F2 rename `amp_floor` and "amplitude" wording in analysis.py to glossary terms (e.g. depth floor). — hard breach of domain.md synonym rule.
- F3 add test: CLI with no args exits 2. — plan §8 behaviour untested; cheap.
- F4 move `write_frame_csv` into frame_io.py next to `read_frame` (keep generator calling it). — CSV format in one module.
- F5 share truth-match tolerances between test_analyse and test_cli (one helper). — duplicated tolerance.
- F6 angle convention: keep full statement in GLOSSARY; docstrings in Report/GroundTruth/generate refer to it briefly. — single source.
- F7 drop unused `to_json(indent=…)` param unless the CLI uses it. — speculative.
### Owner
- Glossary gap: score/threshold/striped verdict not in GLOSSARY.md; run /domain-modeling?
- O1 carry-over: check angle sign on a real Solis view.
### Pass
- constant-frame `score == 0.0`: deliberate per review N9 (only exact for all-ones).
- mysterious short names, broadcast dup, long `analyse`: stopgap detector replaced by ticket 02.
- period/angle data clump: schema owner-ruled (O2); ticket 05 moves into regions.
- FrameFile.notes: owner-ruled O3 for ticket 04.
- ADR-0001 conflicts: surfaced in comments, compliant.
- generator oracle checks: not in ticket 01 scope.
- py.typed, non-finite test: harmless / covers planned guard.

## Next

CLOSED 2026-11-10. Fixer `a76b7e37b9fbe7eaa` done: commit `07e28af` (F1–F7), 67 tests green; F1 tests each shown failing on wrong cause. Commits: 7fe505b, 07e28af. Owner items open: glossary gap (score/threshold/striped), O1 Solis angle check, ticket Status line, handoffs uncommitted. Worktrees: none remain. Files archived to `handoffs/.archived/`.
