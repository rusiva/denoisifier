# Ticket 08 orchestrator log

- Ticket: `.scratch/stripe-detector/issues/08-bin-factors.md`
- BASE: `0032d7fe42318e5eb14584d48e341c3627839b9a`
- Args: MIN_MODEL=opus, SELF_LIMIT=200000, WORKER_LIMIT=200000
- User rule: before any human question, get an adversarial second opinion from a fresh-context critic agent on model `fable`, critically review its verdict, decide by best practice; escalate only taste / external knowledge / hard-to-revert architecture.
- Milestone gates (fixer, end): `make measure` only if detector output changed (bin 1x1 must be identical, so likely not; decide at review), `make check-slow`, `make check`.

## Workers
- planner `a16f43bf4ed3d6f25` (opus): write `08-plan.md` with seams, AC→tests, open questions. Status: done; plan at `.scratch/stripe-detector/handoffs/08-plan.md`. Open Qs: 1 option shape (BinFactors dataclass rec), 2 reference filters count toward searchable range so 1x2 warns <4px (prototype), 3 plain-pixel constants stay in frame px, 4 always emit bin_factors/units/warnings in JSON, 5 calibration mismatch: Calibration.bin_factors + recalibrate --bin + warning, 6 CLI `--bin 2x1`, 7 unsearchable bins → ValueError. Approvals flagged: additive lockfile entries; extended key list in test_report_converts_to_json. Claims 1x1 byte-identical → no make measure.
- plan reviewer `a96f1d7e1e229f7dc` (opus, blind): review into `08-plan-review.md`. Status: done; `08-plan-review.md`: B1 bbox tolerance per-axis (p/v rows, p/h cols), B2 `tests/calibrate_regions.py:264` direct `_Filters`/`estimate_local_stripes` calls → default bins args, B3 lockfile list missing `Report.bin_factors`, `Report.UNITS` ClassVar; P1 extend prototype to 2–3 frame px + 1x1 baseline; O1 = Q2; O2 = Q5 (file format; shape clause should compare pixel count); 6 notes.
- critic `a36a30cb8f3917486` (fable, fresh, read-only): adversarial verdict on Q1–Q7 + review items into `08-critic.md`. Done: `08-critic.md`, no human decisions needed (unless P1 forces AC3 limit ≠ 4 px).
- prototyper `a429ed8e080a02714` (opus, worktree): P1/Q2 into `08-prototype-p1.md`. Running. Watcher armed.

## Decisions
My critical reading of `08-critic.md` (all items settled without the owner so far):
- Q1 BinFactors dataclass: fold (axis-order safety beside `Calibration.shape`).
- Q2/O1 (a) references count, warning text names which filter is unresolved: fold; owner only if P1 forces a limit ≠ 4 px at 2x1 (would change AC 3).
- Q3 plain-px constants in frame px: fold.
- Q4 always emit; add `unresolved_period_px` to to_dict; `units` covers every unit-bearing field; no `warnings.warn` (filterwarnings=error): fold.
- Q5/O2 note yes, via `settings["bin_factors"]` only when ≠1x1 + read-only `Calibration.bin_factors` property; no file-format/digest change → not hard-to-revert; shape clause by pixel count; ADR 0002 consequence line: fold.
- Q6 `--bin HxV`, justified by ticket notation, help states order: fold.
- Q7 ValueError on no searchable period: fold.
- B1 per-axis bbox tolerance: fold. B2 `bins` required on internals, `_Filters` reads spec.bins, edit `tests/calibrate_regions.py`: fold (critic's fix over reviewer's — defaults silently hide a missed call site). B3 + `Report.UNITS` ClassVar: fold.
- N5 warnings JSON-only (stderr one-line rule, test_cli.py:43-45): fold critic. Other notes: fold.
- M1 binning test seeds in 10–99; P1 seeds change `USED_SEEDS` lock line → approval request names it: fold.
- M2 AC3 test asserts presence of sub-2-px warning + `unresolved_period_px`, "exactly one" only with threshold=: fold.
- M3 directional Mottle under binning: real; prototype measures; if inflation material, binned-only reference scaling by bin transfer factor (exactly 1 at 1x1) + ADR 0001 consequence. Pending P1 (sent as scope addition).
- M4 depth reported as measured on the binned frame, documented in units/docstring, no correction: fold (correction amplifies noise, needs own validation).
- M5 size rule under 2x1: prototype checks (scope addition).
- Prototype (`.claude/worktrees/agent-a429ed8e080a02714/.scratch/stripe-detector/handoffs/08-prototype-p1.md`, branch @ d5e81b8; prototyper reported writing to main checkout was blocked — NOT copied by me, surfaced to owner; keep worktree until plan fold done, then archive file content into plan): Q2 → A (1x2 no-rule: stripe-free median 1216 vs 1x1 max 49; rule A max 39.2); 2x1 reliable from 4.2 px → AC 3's 4 px stands, no owner item. M3: 1.88x at 1x2/4.19; compensation over-corrects → no compensation, document in ADR 0001 consequence + coverage wording. M5: 84/84, no change. Seeds 108_000–108_399 → USED_SEEDS.
- Approvals (orchestrator, from Fable critic + own reading; CLAUDE.md lets orchestrator approve): additive lockfile entries, changed `protected :: USED_SEEDS` line, extended key list in `test_report_converts_to_json`. Reason: new fields/seed reservation, no tolerance or expected value loosened. Recorded in ticket Comments by implementer.
- M6 no `make measure`; handoff carries calibration reproduction + to_json/labels diff vs BASE for striped frames: fold.

## Next
Plan settled; closing check: none open. N7 (caller `settings` already has `bin_factors`) → ValueError + test, passed to implementer in brief (refuse > silent override).
Implementer `a97a75207bc6fa7f3` (opus, main branch, tdd; no check-slow/check/measure; saves BASE outputs for 1x1 diff; records approvals in ticket Comments) DONE: commits 62617f2, accd940. `make check` @accd940 exit 2, `1141 passed, 8 deselected in 625.68s`, only stamp red (expected). 1x1 diff vs BASE (4 frame kinds, with/without BinFactors(1,1)): identical. Scratch: base_diff.py, base/, check.log in session scratchpad b8f9158a…. Notes: 640x1024 test frame now gets pixel-count coverage note; N7 on `calibrate` only.
Implementer stopped (had leftover background work). Code review running: standards `a4e92f4c133b8e720`, spec `af811db86b4a45cb2` (opus, read-only). Then sort fix/owner/pass; fixer runs check-slow → check.
Standards DONE: no hard violations. S1 glossary "array pixel" avoided term → MIN_FRAME_PERIOD_PX + "frame px" text (lockfile rename, approval); S2 inline approx(19.43) in test_analyse.py:1349 → protected.py; S3 BinFactors in unstamped report.py (reason recorded); smells: "2 frame pixels" literal dup, --bin argparse dup + recalibrate imports cli, unresolved tuple+str switch, hand-written sensor↔frame conversions ~7 places, bins via spec vs param inconsistency, redundant int() in to_dict. Spec DONE: no spec defects; physics checks out per axis; 1x1 identity argued; minor: calibrate tuple → AttributeError; scope extras (TypeError in analyse, __str__, extra tests) small.

## Code review disposition
Fix:
- F1 S1 rename `MIN_ARRAY_PERIOD_PX`→`MIN_FRAME_PERIOD_PX`, "array"→"frame px" in UNITS/docstrings/messages (glossary rule). Lockfile rename, value unchanged → orchestrator approves.
- F2 S2 move 19.43/0.01 to `tests/protected.py` (CLAUDE.md: tolerances live there). Additive protected number → approved.
- F3 interpolate the 2-frame-px constant in messages/docstrings (duplication of a protected number).
- F4 one shared `--bin` parser next to `BinFactors`; recalibrate stops importing cli.
- F5 unresolved range → small frozen dataclass with Literal/enum `by`, no tuple slicing.
- F6 sensor↔frame conversions as `BinFactors` methods; one plumbing route for bins (via filters.spec or param, consistently). Must keep 1x1 bit-identical → re-run base_diff.py.
- F7 `calibrate*` reject non-BinFactors with TypeError like `analyse`.
- F8 drop redundant int() in to_dict.
- F9 closing: tick ACs, Status → resolved after gates green.
Pass:
- S3 BinFactors in unstamped report.py: reason recorded in ticket; stamp test doesn't require it.
- Scope extras (TypeError, __str__, 2x2 test, extra CLI params, dropped cast): harmless, consistent.
- Limit 4.0 vs first searched 4.19: plan accepts.
Owner: none.

Fixer `add845699f7673ffc` (opus): DONE. Commits 5175b97 (F1–F8), b7c6731 (F9, ticket file only). Identity diff `DIFFERENCES: 0`. Gates at 5175b97 clean: `make test-fast` exit 0 `670 passed, 482 deselected in 258.36s`; `make check-slow` exit 0 `5 passed, 1147 deselected in 1257.06s`; `make check` exit 0 `1144 passed, 8 deselected in 679.63s`, stamp green. F6 accepted as helpers in stamped `_local_stripes.py` (keeps detector maths stamped; consistent with S3 pass). Pre-existing inline `<= 2.0` tolerance in test_analyse.py: pass (pre-existing, outside approval).

## CLOSED 2026-11-14
Next: on fixer report, close (report to user, mark log closed, TaskStop self watcher bm37fkx5f, archive ticket files).
Owner ruling: prototype findings file not kept ("No, just delete"). Prototyper worktree + branch (throwaway commits 81aff16, d5e81b8) removed. Other locked worktree agent-a8dfa301… is not this ticket's; left alone.
Owner item pending: keep prototype findings file before worktree removal?
