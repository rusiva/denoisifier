# 05 orchestrator log

- Ticket: `.scratch/stripe-detector/issues/05-striped-regions-and-mask.md`
- BASE: `87005b9c476a1dd4750c089c2c19352d5865ae50`
- Args: MIN_MODEL=opus, WORKER_LIMIT=200000, SELF_LIMIT=200000
- User rule: before any human question, get a Codex adversarial review (`/codex:adversarial-review` / codex-rescue) and decide from a critical reading of it; ask the human only on taste, external knowledge, or hard-to-revert architecture.
- Plan: `.scratch/stripe-detector/handoffs/05-plan.md` (pending)
- Plan review: `.scratch/stripe-detector/handoffs/05-plan-review.md` (pending)

## Workers

- planner `a4aaa55a579dbfcbb` (opus): write `05-plan.md`, list open questions. Status: done (plan written, uncommitted). Open Qs Q1–Q10 at the end of the plan; recommendations: Q1 score = highest level at which a region of minimum size exists (striped ⇔ regions reported; changes the score scale); Q2 measure the 3×2 minimum on the core component, test margins 0.8/1.4 after a probe on test seeds; Q3 drop the top-level period/angle/depth from Report; Q4 grow the mask from the core out to half the median local depth; Q5 mask CSV holds region labels, not 0/1 (taste); Q6 write only with `--mask PATH`; Q7 mask laid out like the analysed grid, transposed back under `--transpose`, no axis column; Q8 test the IoU at scorched mottle, ~100 photons, m=0.5; Q9 each connected part is its own region; Q10 add a Mask entry to the glossary.
- plan reviewer `a5c40f79ab20b18a0` (opus, blind brief). Status: done. Review at `05-plan-review.md`: B1–B6, P1–P2, O1–O3, N1–N8, all open.
- prototyper P1 `a7632079fa53d7558` (opus, worktree): blur-corrected size rule → `05-prototype-p1.md`. Status: running.
- prototyper P2 `af7544ea93dfaf1d6` (opus, worktree): real-pipeline IoU at geometry in Periods, plus timing → `05-prototype-p2.md`. Status: running.
- Codex adversarial review of O1–O3, Q3/5/6/7/8/10, B3: background, log at scratchpad `codex-05-design.log`. Status: running.

## Decisions

Planned dispositions, pending Codex and the prototypes:
- B1–B6: break → planner folds them (B1 fold waits on P1; B2 on P2).
- P1, P2: prototype (running).
- O1–O3: owner-class → decide from Codex plus my own reading; escalate only if hard to revert and undecided.
- N1–N8: note → fold all into the plan (each is cheap and correct).

### Codex adversarial review (done, verdict needs-attention; log: scratchpad `codex-05-design.log`)
New findings: (high) even an exact sweep can't make the largest-passing-level score match the verdict, because the size predicate isn't monotone in t (counterexample: median Period moves 9.32→10.44 between t=200 and T=154). (high) `--mask` can alias the input or `-o`. (medium) Under `--transpose` the JSON bboxes and the mask CSV use different coordinates.

### Rulings (orchestrator, from Codex plus my reading)
- **O1/Q1 → T-free candidates (B4's second option), not level-bisection B.** Codex's counterexample is decisive against any level-based score. Candidates are built without reference to T: peaks/seeds, Period split, growth to the half-depth extent, then the size test (blur-corrected per P1). Score = max peak ratio over qualifying candidates, 0.0 when none (also fixes B6). Regions = qualifying candidates with peak > T, so striped ⇔ regions non-empty by construction. Test it across several thresholds, including ties and empty or constant frames. Reasons: it's the only option that satisfies the ticket's verdict rule exactly; the score stays near today's max-ratio scale; ticket 07 hasn't calibrated on it yet, so it's revertible now. `make measure` re-stores the thresholds.
- **Q2 → measure the size on the grown extent with a blur correction** (B1 plus P1), consistent with O1.
- **O2 → A.** Test AC 5 at low noise / no Mottle. In the handoff, record detection against region size at typical noise and at the operating T, as a measured number. Conditional on P1 finding a separating rule; if none exists, owner.
- **O3/Q9 → B, with Codex's bounds.** Merge fragments by complete linkage: every member's Period and Angle lie within tolerance of the group's, so there's no chaining, and members are within about one window of each other. Run the size test and the measurement on the merged group. Full-frame tests assert every reported region's measurements. The (5,12) and (8,16) pairs must stay separate. Constants come from the calibration range. Reason: one entry per stripe set (spec story 7); this is internal and the format is unchanged.
- **Q3 → A (remove top-level fields).** Re-adding them later is additive and cheap. Note the JSON change in the CLI docs.
- **Q4 → B (half-depth growth).**
- **Q5 → OWNER answered: region labels** (0 = background, k = region k, matching the JSON `label`; integers; identity is local to the report).
- **P2 (done, `05-prototype-p2.md`; seeds 410_000–410_079, 411_000–411_003):** at 4P×5.3P with half-depth growth, the median IoU is 0.88 and the worst is 0.79–0.80 at P16–20. At 5P×6.6P or FRAC 0.6, the worst is about 0.83. The 2P dilation cap breaks short Periods (IoU 0.34–0.87 at P≤6). Growth costs about 0.08 s per region. Rulings: test geometry is semi-axes max(5P,45)×max(6.6P,60) in frames large enough to hold them; drop the fixed 2P cap (bound the growth some other way, e.g. by the merge/complete-linkage rule from O3 and by the half-depth contour); tune FRAC on the new calibration range; put the two-region test in an early slice, since P2 didn't cover it. The IoU tolerance stays at the spec's 0.8. If the real pipeline misses it, stop and bring it to me.
- **P1 (`05-prototype-p1.md`; seeds 390_000–007, 390_100–107, 390_200–207, 390_300–307):** the width rule works. It uses the sub-pixel half-peak width of the re-tuned depth map, in Periods, with a cut at 3.24P; margins are about 3.5%/5% for 0.8×/1.25× and better for 0.8×/1.4×. Height can't be measured with today's along-window (FWHM about 3.5P). → follow-up running: option D (a short along-window filter used only to measure height), plus Codex on the height question (scratchpad `codex-05-height.log`). Test pair: use 0.8×/1.4× for headroom.
- **Lockfile approval (orchestrator, CLAUDE.md weakening list):** adding the new ticket-05 module constants and test numbers to `tests/protected_numbers.lock` is approved; it records new numbers and loosens nothing. Changing existing pinned numbers follows the normal rules (`make measure` re-stores the thresholds; borderline seed re-picks need their reason recorded). Record this in the ticket Comments.
- **Q6 → A**, plus reject aliasing between `--mask` and the input or `-o` (including existing filesystem aliases, via samefile/resolve). Add a test that a collision leaves the files intact.
- **Q7 → A, plus one coordinate contract:** JSON bboxes index the written mask directly (file orientation, axis column dropped). Period and Angle stay in today's convention, and the JSON records whether a transpose happened. Test with an asymmetric region in a non-square transposed input.
- **Q8 → scorched m=0.5 (primary) and multiscale m=0.5**, both at the IoU tolerance. m=0.2 is informational only. If multiscale goes red, that's a detector finding to surface, not a reason to loosen the tolerance.
- **Q10 → A, refined:** the glossary defines Mask as the labelled array (0 = background, k = region k) and says the boolean mask is its union.
- **B3 → approve the guarded move:** register a new calibration range in `CALIBRATION_SEEDS` for growth/merge/size-rule tuning, used inside `seed_guard.calibrating(...)`. Reserve the N8 seeds and the prototypers' seeds. Freeze tuning before the held-out evaluation. Reason: it strengthens calibration/evaluation separation (spec.md:112). Record this in the ticket Comments.
- B1, B2, B4–B6, N1–N8 → planner folds them (B4 is superseded by the O1 ruling).

- **Codex on height (done, `codex-05-height.log`):** reject A and B. Width-only breaks story 13 and spec decision 110; it's a requirement change, not a reading. Pursue D, with C (narrowing the detection bank) as the fallback. Add tests with the axes varied independently (wide/short including 4P×1P, narrow/tall, qualifying controls), measure height from the input rather than the blurred map, and use height-qualified candidates for both score and regions. I agree; it's folded once D's result is in. If D fails: C is a detector redesign and A is a requirement change, so both go to the owner.

- **Height ruling: D adopted** (P1 follow-up, `05-prototype-p1.md` last section; seeds 391_000–007, 391_100–107, 391_200–207). A size-only re-tuned filter at the candidate's Period and Angle, with a 0.5P along-stripe window, measures the sub-pixel half-peak height. Cut at 1.93P, with about 10% margins at low noise, holding on hold-out seeds. Width keeps its 3.24P cut. Costs 7–17 ms per candidate at 256², 55–92 ms at 400×1600, with one shared spectrum. The new constants are covered by the lockfile-additions approval. Codex's conditions are folded: tests vary each axis independently (wide/short including 4P×1P, narrow/tall, controls that pass on both); measure from the input; use the same qualified candidates for score and regions. AC 5 is tested at low noise (O2). The typical-noise result (few small regions detected; 1/240 at 0.8× would be reported) is recorded in the handoff as a measured number. The two-region case and Mottle at low noise are untested, so put them in early slices.

### Workers (cont.)
- P2 prototyper `af7544ea93dfaf1d6`: done. Worktree `.claude/worktrees/agent-af7544ea93dfaf1d6` (remove at close).
- P1 prototyper `a7632079fa53d7558`: resumed for the option-D height follow-up. Worktree `.claude/worktrees/agent-a7632079fa53d7558` (remove at close). Findings in scratchpad `05-prototype-p1.md`; copy again to handoffs when done.
- Codex height review: background, scratchpad `codex-05-height.log`.
- Fold planner `ac263829a43eeedf6` (opus, fresh): done. Everything folded; section 7 is now "Settled decisions" and section 8 holds the ticket Comments. Its own additions: `analyse(frame, *, threshold=THRESHOLD)`, which rejects negative or NaN thresholds; `Report.transposed` plus `in_file_layout()`; `REGION_CALIBRATION_SEEDS = range(90_000, 90_600)`; and `tests/calibrate_regions.py`. Open: `HEIGHT: PLACEHOLDER`. Approvals still to give:
  - **Borderline re-pick:** approved only if `make measure` shows a seed is no longer borderline, with the reason recorded in the Comments.
  - **Removing pinned constants that the change makes obsolete:** approved, since it removes dead numbers and loosens nothing; list each one in the Comments.
  - **Stored thresholds after `make measure`:** follow the CLAUDE.md procedure. Pass counts are never edited; if `test_regression_plan_meets_the_operating_rule` goes red, stop and bring it to me.

- Fold planner: height folded (width 3.24P, height 1.93P; the AC 5 tests vary each axis on its own; 391_* added to USED_SEEDS). The plan has no placeholders left. The approvals it asked about are already given in the entry above.
- Plan reviewer `a5c40f79ab20b18a0`: closing check done. B1–B6, P1–P2, O1–O3 closed and N1–N8 folded. New: B7 (break) and N9 (note).
  - **B7 → break, folded per the reviewer's fix.** Overlaps and emptied regions are resolved across all size-qualified candidates before T, so the plan's T-free contract follows. Not owner-class: it's a direct consequence of the O1 ruling. Adds a test that bboxes and areas stay the same when T changes.
  - **N9 → note, folded.** Candidates are ordered by peak; the cap must not drop a qualifying candidate (size it from calibration, or log when it's hit). Count cap hits and angle-unmerged fragments before the freeze.
  - The skill allows no second closing check, so planning is done once the planner reports this fold.

- Fold planner: B7 and N9 folded. **Planning closed.**
- Implementer `addba95d23df5915d` (opus): builds the whole plan test-first (one worker, since the files overlap), including `make measure`, `make check-slow` and `make check`, and writes `05-implementer-handoff.md`. It stops and reports on IoU, size or two-region failures, a failing feasibility gate, or a red regression-plan check. Status: running.

- Implementer `addba95d23df5915d`: ROTATE at fill 201991. I've asked it to pause and write `05-implementer-1.md`. Status: rotating.

- Implementer 1 stopped. Handoff `05-implementer-1.md`. Committed `146102c` (slice 1, the generator). Uncommitted work in progress: rewrites of report.py and analysis.py, plus 3 deviations from the plan text, to be recorded.
- Implementer successor `addd6d91db168aeed` (opus): same brief plus "continue from `05-implementer-1.md`" and "name each deviation". Status: running.

- Harness SECURITY WARNING "[Security Test Removal]" on the successor. Checked the diff from 87005b9 against the working tree: no `def test_` removed; no skip, xfail, filterwarnings, noqa, type-ignore, timeout or `calibrating(` edits; Makefile, pyproject and conftest untouched; lockfile +2 lines only. The 48 removed test lines are frame-level `period_px`/`angle_deg`/`modulation_depth` assertions, each rewritten against `report.regions` (Q3 ruling). The constant-frame test is now stricter (`score == 0.0`, no regions). Verdict: false positive. The code review re-checks this.

- Owner asked why the P1 prototyper was still around (it sat idle waiting on its own background work). TaskStopped it; no leftover processes. Both prototyper worktrees and branches removed (nothing in them beyond the findings already copied to handoffs). Worktree `agent-a0bf8d77…` is not this ticket's; left alone.

- **PAUSED by the owner (going offline).** I asked implementer `addd6d91db168aeed` (fill about 178k) to stop its background jobs, commit green work, and write `05-implementer-2.md`. Once its reply arrives: TaskStop it, then stop the self and worker watchers.

- Paused cleanly. The implementer finished and wrote `05-implementer-2.md`. Self and worker watchers are stopped; no tuning or gate processes are left. HEAD is still `146102c`, with 17 uncommitted paths (work in progress, described in the handoff). The `fill-watch.py self` process (pid 1092569) belongs to another session, so I left it.

- **Resumed.** Self watcher re-armed. Handoff 2 read. Tuned knobs: `_SEED_FRACTION` 0.1, `_GROW_FRACTION` 0.6, cap 20, plus the new `_CORE_FRACTION`/`_ABSORB_FRACTION` (deviation 4). On the tuning range: worst IoU 0.873, full-frame 0/60 mis-measured, two-region 30/30. The freeze run hasn't been redone yet. Deviations 1–7 are in the ticket Comments.
  - Deviation 3 OK: the all-zero frame was already rejected at BASE.
  - Deviation 4 (the absorb rule) goes to the code review's spec axis instead of a separate Codex pass.
  - Risk to report at close: 7/30 regions at 1.4× in scorched Mottle at low noise aren't reported (peak ratio 44–117 < T). That's a detection limit, not the size rule. The AC 5 tests run Mottle-free per O2.
- Implementer successor 2 `a867c158864c681cf` (opus): continues from handoff 2 (freeze → lockfile → acceptance → CLI → gates). Status: running.

## Next:
Wait for successor 2; rotate if its watcher fires. Then run code-review from BASE 87005b9, with deviation 4 explicitly in scope.

## (superseded) Next (on resume):
Re-arm the self watcher. Check that `05-implementer-2.md` exists and that no tuning or gate processes are left (`ps`). Spawn a successor implementer with the same brief plus "Continue from `05-implementer-2.md`", and arm its watcher. Then follow the earlier Next below.

(old) Wait for the successor; rotate per `watchers.md` if its watcher fires. When it reports, review the deviations it names (Codex if any is non-trivial), then run code-review from BASE 87005b9.

(old) Wait for the implementer. When its watcher fires, rotate per `references/watchers.md`. Then run code-review from BASE 87005b9.

(old) When the closing check reports: take anything left open through Codex, then to the owner only if it is owner-class. Then implement (section 4 of the skill).

(old) When the height follow-up and Codex land: rule on height (D if it separates; else decide A vs owner), and send the ruling to the fold planner. Then send the plan reviewer (`a5c40f79ab20b18a0`) the closing check.

(old) When P1 and P2 report: rule on O1–O3 and the Qs, then send one fold brief to the planner (`a4aaa55a579dbfcbb`), then the reviewer's closing check.
