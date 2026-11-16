# 04 orchestrator log

- Ticket: `.scratch/stripe-detector/issues/04-frame-reader-solis-exports.md`
- BASE: `0e56381767e7ffe79db1c834a2595bb68847a5b8`
- Args: MIN_MODEL=opus, WORKER_LIMIT=200000, SELF_LIMIT=200000
- User rule: before any human question, run Codex adversarial review, critically read it, self-decide; ask the user only for taste / external knowledge / hard-to-revert architecture.
- Plan: (pending) `.scratch/stripe-detector/handoffs/04-plan.md`
- Plan review: (pending) `.scratch/stripe-detector/handoffs/04-plan-review.md`

## Workers

- planner `ab19a429013cb4ff9` (opus): write `04-plan.md` with seams, per-AC tests, gate notes, open questions. Status: done. Plan written; touches only unstamped files (`src/denoisifier/{frame_io,cli,report}.py`, `tests/{test_read_frame,test_cli}.py`), so no check-slow/lockfile. Open Qs O1–O8 (O8 = a real Solis export sample is needed; owner question).
- plan reviewer `a4418046d9cd0a473` (opus): blind review → `04-plan-review.md`. Status: done. B1 break (rule 6 guard scope + one-row drop test), O1 owner (real Solis layout: trailing comma / numeric header row / delimiter), N1–N6 notes.
- fold planner `a2f6637b2fda22f00` (opus): fold the Decisions section into `04-plan.md`. Status: done, all folded (Settled S1–S9; known gap = real Solis layout).
- plan reviewer `a4418046d9cd0a473`: closing check done; nothing open. New N7 (corrupted boundary row in a ≤2-wide grid still skipped as metadata) → pass: it is counted in notes, and real frames are ≥ MIN_SIDE wide.
- implementer `a5e8f37829f3f265c` (opus): build the plan test-first with tdd, commit to main per slice, `make check` at end; stop on weakening moves or a stale slow tier. Status: done. Commits 20a569a, 510f92c, bb0d1a8, 5bf2287, beefc76, 2d4311a (ticket file). `make check` exit 0, `326 passed, 4 deselected in 123.50s` at beefc76 (later commit: ticket file only). No weakening moves. Open: ticket Status line; known gap written into ticket; some tests green-from-start (6d, 6e, 6f, 6g, 7c, 7d).
- Codex adversarial review of plan + review: done, log `/tmp/claude-1000/-home-rusiva-dev-denoisifier/a1a17e7f-3fb2-4d3d-8ed4-d7bd854fa209/scratchpad/codex-04-plan.log`.

## Decisions

Codex adversarial review (log above): needs-attention; only real Solis layout needs owner. My rulings after critical reading:

- B1 → break, fold: explicit drop is independent of the axis heuristic: cols < 2 → error, else drop column 0. The ≥2 rows/≥2 cols guard applies only to `looks_like_axis` (kept-axis warning and "does not count up" warning). One-row drop: drop, note says the column was dropped and its axis identity was not assessed. Tests: one-row drop, one-column error.
- Codex high (boundary-row loss) → break, fold. Agree a corrupted first/last row (`abc,8,9`) must not be silently skipped as metadata. Ruling: a non-grid line before/after the grid whose field count equals the grid width and where more than half the fields parse as numbers is an error naming its position (a corrupted row), not metadata. Other non-numeric-first lines are metadata. Tests: corrupted first row, corrupted last row → error; `Gain:,300` after a 2-wide grid → skipped and counted. Reason: fail loud over silent truncation, still accepts key/value metadata.
- Codex medium (BOM fixture 4c contradicts axis warning) → fold: use a falling first column and assert exact values.
- Planner O1 → superseded by the boundary-row ruling (first field numeric starts a grid line; boundary-row check above).
- O2 drop+warn when not counting up → agree (Codex agrees).
- O3 blank lines ignored, not counted; delimiter-only rows (empty fields) still fail → agree.
- O4 → per B1.
- O5, O6, O7 → agree (Codex agrees).
- Trailing comma → reject by default with a clear error (terminal empty field may be a missing pixel). Codex agrees.
- Numeric header row → no detection; kept as data (ticket: never guess). Codex agrees.
- N1 fold: field-count error first; test metadata line embedded between numeric rows. N2 fold: write 7a before the Report change. N3 fold: docstring on float syntax, test non-finite rejection. N4 fold: docstring on `#` handling change. N5 fold: empty and whitespace-only input tests. N6 pass: speed fine (0.11 s).
- Review O1 / planner O8 (real Solis layout) → owner: external knowledge. Asked the user; owner chose "ship, note gap": conservative parser now, state "real-file check pending" in the handoff, real-file test in a follow-up ticket.

## Code review

- Standards reviewer `a9d7e677a9c545bf2`, Spec reviewer `af578bd226d9121d9` (diff 0e56381...HEAD, 6 commits). Standards: done — no hard violations; 9 judgement-call smells (S1 "warning: " prefix as note kind; S2 reader_notes on Report; S3 long read_frame; S4 library note names CLI flag; S5 duplicated range text; S6 _drop_axis_column output arg; S7 path clump; S8 `_numbers` name/terse names; S9 redundant `_counts_up` guard) + glossary suggestion "Axis Column". Spec: done — no blocking findings; 6f/6g verified non-vacuous by mutation (they passed early because slice 1 treated every line as a grid line); ticket Status still ready-for-agent; gate quote lacked `-dirty` form; residual: numeric-first-field footer of other width → "uneven" error (Known gap).

Sorting:
- fix S3: extract the metadata/boundary classification from `read_frame` into a helper.
- fix S5: build the axis range text once.
- fix S6: `_drop_axis_column` returns (grid, notes) instead of appending to the passed list.
- fix S8: rename `_numbers` to say it parses-and-raises (e.g. `_parse_row`); drop the explaining comment; un-terse `n0`/`d`/`grid_at` where cheap.
- fix spec: set ticket `Status: resolved` (repo convention, issue-tracker.md:26); fixer's handoff quotes the gate in the CLAUDE.md form incl. `-dirty`.
- pass S1: string notes with a documented `warning: ` prefix keep `FrameFile.notes` a plain tuple of str and the JSON simple; a Note type is churn without a spec need.
- pass S2: `reader_notes` on `Report` was settled in plan S8; the CLI-assembled JSON alternative is a taste-level reshuffle.
- pass S4: naming the CLI flag in the warning helps the experimenter, who is the main reader of the notes.
- pass S7: minor; `path` is only for error messages.
- pass S9: the guard is the keep-path's S4 rule, intended.
- pass glossary "Axis Column": domain.md adds entries lazily; plan O7 said none.
- pass residual footer risk: covered by the owner's "ship, note gap".
- owner: none.

- fixer `a29c9bdcbb2313ae4` (opus): apply the "fix" lines, set ticket resolved with final gate quote, `make check`. Status: done. Commits 02ddd2f, a744265, 67256d3 (make fix format), 0f1aede (ticket resolved). `make check` exit 0, `326 passed, 4 deselected in 133.71s (0:02:13)`, HEAD `67256d3-dirty` (dirty = ticket edit committed in 0f1aede, plus pre-existing 02/07 and handoff dirs).

**CLOSED** 2026-11-11. Owner items: none open (real-Solis gap accepted by owner; follow-up real-file fixture). No prototyper worktrees.
