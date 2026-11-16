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

- Successor 2 STOPPED as instructed, with acceptance red after the freeze. Commits: `ce42580` (freeze; also committed the orchestrator's 05-*.md handoffs), `b9f4a88` (two test bugs, nothing loosened), `138ffb3` (handoff 3). `test_analyse`: 10 red; `test_cli`: 1 red. No gates run. Handoff `05-implementer-handoff.md`. Reds:
  1. ghost shallow regions next to sharp-edged AC 5 regions (5);
  2. dark-area test: interior Mottle holes (Envelope vs Profile definition) (3);
  3. strong P12 seed 23, Angle 1.02° off (1);
  4. borderline (22,20) now scores 0 (2).
  Codex review running → scratchpad `codex-05-reds.log`.

### Rulings on the post-freeze reds (orchestrator, from Codex `codex-05-reds.log` plus my own reading)
- **R1 ghosts → detector fix, re-freeze.** Develop leakage discrimination on the calibration range, adding unmottled `edge_px=1` cases for every size shape plus *genuine* unequal-depth neighbours, so the fix can't erase real weak regions next to strong ones. Compare against stronger candidates even when they fail qualification. Softening `edge_px` in the tests is rejected: that would be weakening, with no scope reason.
- **R2 dark area → approved weakening-class change**, recorded in the ticket Comments. "Dark" = the *Profile* (no Mottle, same seed, noise 0) below `DARK_FRACTION` of its max, i.e. the surround outside the spot. Reasons: the ticket says "the dark area *outside* the envelope"; the AC 3 truth mask is geometric and includes interior Mottle holes, so the Envelope-pixelwise assertion contradicts AC 3. The Glossary's Envelope stays as it is. Don't clip low-light pixels in the detector.
- **R3 Angle 1.02° → code fix.** Improve the region-restricted measurement (coherent support / phase refinement over the region, re-tuned consistently), developed on calibration seeds. Keep it T-free and keep neighbours separate. The tolerance stays; the seed stays.
- **R4 borderline (22,20) → investigate first; no re-pick yet.** Its one group measures 0.449 P wide on a *full-frame* m=0.2 frame, which looks like a width-measure bug. Fix it if it is one. A re-pick stays conditional on `make measure` showing it's no longer borderline after the fix, per the earlier approval.
- **Evaluation hygiene:** the seen reds stay as regression tests. Before any fixing, predeclare a fresh evaluation range (disjoint, registered in `USED_SEEDS`, recorded in the Comments) and leave it unlooked-at. After the new freeze, run the acceptance criteria once on it with a one-off driver command, with no tuning on its results, and record the numbers in the handoff. Then run the gates in plan order, including `make measure`.

- Implementer 4 `a6758030a2f9ba311` (opus): R1–R4 plus evaluation hygiene, re-freeze, then the remaining slices and gates. Status: running.

- Implementer 4 at fill 197k, waiting on its own background job. Rotating early: asked it for `05-implementer-4.md`.

- Implementer 4 stopped. Handoff `05-implementer-4.md`. Committed `f72c427` (fresh evaluation range 93_000–93_999 predeclared, no frames generated). Uncommitted:
  - R1: size-rule climb plus widest run; leakage test `_LEAK_FRACTION`.
  - R4: the borderline collapse was the width-measure bug (light-edge row); score back to 217.1, so no re-pick needed.
  - R3: `_REFINE_STEPS` refinement (seed 23 now 5.97°).
  - R2: dark-area test change.
  - `tests/evaluate_regions.py`.
  - Deviations 8–11.
  
  tuneR running in the background (pgid 1380230).
- Implementer 5 `a2b69c96327be181e` (opus): continues from `05-implementer-4.md`. Status: running.

- Implementer 5 STOPPED as instructed: the fresh range missed 2.
  - Commits: `2107a40` (second freeze: R1/R3/R4 + R2), `4242d68` (evaluation record + stop).
  - Acceptance after the freeze: test_analyse + test_cli `318 passed in 421.99s` (plain pytest, not a gate).
  - R1 guard OK: weak-neighbour misses are 7 with or without the leak test.
  - Fresh: AC2 39/40 (93024 depth 0.383 vs 0.5; about 4% of calibration frames are biased low by 0.10–0.12 at P12–20, at both freezes). AC6 dark 29/30 (93130: 2 corner pixels at Profile 4.9%). All else passed.
  - Also: the two-region threshold-sweep test took 59 s against its 60 s timeout under load (40.5 s green).
  - Codex review running → `codex-05-fresh.log`.

### Rulings on the fresh-range misses (orchestrator, from Codex `codex-05-fresh.log` plus my own reading)
- **A, depth biased low → code fix.** Codex: the depth is the median over `top_seed`, and 19–26% of its pixels lie in the blurred skirt (calibration 90003/16/23/46: 0.379–0.398; the median over the core gives 0.457–0.491). Develop an interior-support depth estimator on the calibration range. Validate it across depths, Periods, noise and both Mottles, and don't change the growth reference. Add depth error and depth-miss counts to the calibration summary. The tolerance stays; escalate to the owner only if the residual error shows a real accuracy limit.
- **B, dark corner → code fix.** These are a real miss under any reading: the true Envelope there is 3.9–4.4% too, while the smoothed noisy frame is 10.5%. No AND-narrowing of the test, and no boundary allowance. Improve surround exclusion on calibration cases (e.g. a light estimate less smeared by noise or smoothing at the frame edge), keeping interior Mottle holes and the IoU.
- **Evaluation:** 93_000–93_999 is consumed. 93024, 93048 and 93130 become regression cases. Before fixing, predeclare a new untouched range (registered, with a Comment) and its pass rule: **every frame meets every criterion, same as before**. Evaluate once after the third freeze and keep all prior results. If a fresh miss happens again, don't retry: stop and report. It then goes to the owner as a tolerance question, with the evidence.
- Watch the two-region sweep test's timing (59 s vs 60 s under load) in the gates. Raising its timeout is a weakening move and isn't approved; speed up the code or the test's construction instead.

- Implementer 6 `a040ee9bdd2584ad7` (opus): A/B fixes, third freeze, new fresh range, then gates. Status: running.

- Implementer 6: ROTATE (fill about 200k). Asked for `05-implementer-6.md`.

- **ORCHESTRATOR PAUSED at self fill 203454 ≥ 200000.** In flight: implementer 6 `a040ee9bdd2584ad7`, asked to write `05-implementer-6.md` (it may also leave a tune or gate running in the background). From here, notifications get one log line each and no action.

- (paused) Implementer 6 reported: handoff `05-implementer-6.md`. Commits 7f418cc..1fd3635. Second fresh range met every criterion; `make measure` gate PASS. STOPPED: after the stored thresholds were updated, `test_regression_plan_meets_the_operating_rule` went red (P(any false red) 8.43% vs the 1% rule). Per CLAUDE.md, re-deriving the pass counts is the OWNER's decision. check-slow and the final check haven't run; no background jobs. → owner question pending.

## Next (on resume with a new limit, or after /clear then `resume <this log>`):
Check whether `05-implementer-6.md` exists. If so, TaskStop implementer 6 if it's still running; otherwise rotate it per `watchers.md`. Then spawn implementer 7 with implementer 6's brief plus "Continue from `05-implementer-6.md`", and arm its watcher.

(old) Wait for implementer 6; rotate if its watcher fires. Then run code-review from BASE 87005b9.

(old) Wait for implementer 5; rotate if its watcher fires. Then run code-review from BASE 87005b9 (deviation 4, the R1 leakage rule and deviations 8–11 in scope).

(old) Wait for implementer 4; rotate if its watcher fires. Then run code-review from BASE 87005b9 (deviation 4 and the R1 leakage rule in scope).

(old) Wait for successor 2; rotate if its watcher fires. Then run code-review from BASE 87005b9, with deviation 4 explicitly in scope.

## (superseded) Next (on resume):
Re-arm the self watcher. Check that `05-implementer-2.md` exists and that no tuning or gate processes are left (`ps`). Spawn a successor implementer with the same brief plus "Continue from `05-implementer-2.md`", and arm its watcher. Then follow the earlier Next below.

(old) Wait for the successor; rotate per `watchers.md` if its watcher fires. When it reports, review the deviations it names (Codex if any is non-trivial), then run code-review from BASE 87005b9.

(old) Wait for the implementer. When its watcher fires, rotate per `references/watchers.md`. Then run code-review from BASE 87005b9.

(old) When the closing check reports: take anything left open through Codex, then to the owner only if it is owner-class. Then implement (section 4 of the skill).

(old) When the height follow-up and Codex land: rule on height (D if it separates; else decide A vs owner), and send the ruling to the fold planner. Then send the plan reviewer (`a5c40f79ab20b18a0`) the closing check.

(old) When P1 and P2 report: rule on O1–O3 and the Qs, then send one fold brief to the planner (`a4aaa55a579dbfcbb`), then the reviewer's closing check.

- **RESUMED** (same session, after compaction). Owner ruling on the operating-rule red: **B — fix the detector so it gives fewer False Alarms, then `make measure` again; the pass counts and rule constants stay unchanged.** (Explained to the owner: at 12/1000 held-out FA, pessimistic 2.09%, no limit on 800/1000/1200 free seeds meets both rules; 1600 seeds/limit 49 would. Owner chose the code fix.) Was 7/1000 at the previous measurement (gate threshold 74.1, now 49.7).
- Spawned implementer 7 `a0dbe7ed8d0f79bfa` (brief: ruling B; continue from `05-implementer-6.md`; handoff `05-implementer-7.md`). Watchers re-armed (worker + self, 200k).

## Next:
Wait for implementer 7; rotate if its watcher fires. Then code-review from BASE 87005b9 (deviation 4, R1 leakage rule, deviations 8–14+ in scope), fixer, close.

- Implementer 7 `a0dbe7ed8d0f79bfa` STOPPED before any change (handoff `05-implementer-7.md`, commit 05fb0a8): ruling B cannot work. Gate threshold = 20th largest of 2000 calibration free scores → held-out FA ~ betabinom(1000,20,1981) for any detector; rule passes only at FA ≤ 8 (P ≈ 0.38). My brief's "max 2→48" premise was wrong (it was the median). Verified the numbers. Codex (`codex-05-oprule.log`): (a) redefines the guarantee, not a repair; impossibility claim is narrower (calibration-averaged) but holds in practice; prefers predeclared (c), else (b) 1600/49 with disjoint seeds (Bonferroni 0.81%, pass-bad at 4% 2.85%; pass at 3% FA rises 39%→60%). → back to owner (pass counts are the owner's per CLAUDE.md).

- Owner rejected the more-compute options (b)/(c) and asked for fundamentals. Claude's suggested change to the regression check (for review, not adopted): the operating rule's fa0 comes from the held-out count's own Clopper-Pearson upper end (12/1000 → 2.09%), but the stored threshold is set at the k=20/2000 calibration rank, so held-out FA ~ 1% by construction and the rule passes only ~38% of measures for any detector. Proposal: take fa0 from the pooled exceedances at the stored threshold, calibration + held-out (19+12 = 31/3000 ≈ 1.03%, upper ≈ 1.4%), keeping pass counts 22/800, sample sizes, REGRESSION_MAX_FALSE_RED/PASS_BAD and the bad rates unchanged. Detector-side: area-corrected (extreme-value) score is a candidate for ticket 07, not ticket 05.

- Codex (`/codex:adversarial-review`, user-run): pooled-binomial framing wrong; the rank-based Beta(k+x, n+1-k+N-x) = Beta(32,2969) 97.5% bound (1.4636%) is sound; Bonferroni 0.626%. My review: agree on framing; the fixed-threshold guarantee it defends doesn't match how the threshold is made; 26/30 remark out of scope (ruling O1).
- **OWNER APPROVAL (weakening-class gate-design change):** in `test_regression_plan_meets_the_operating_rule`, fa0 = beta.ppf(0.975, k + x, n + 1 - k + N - x) (k, n calibration rank/count; x, N held-out exceedances/frames). Pass counts, sample sizes, REGRESSION_MAX_FALSE_RED/PASS_BAD, bad rates unchanged. No re-measure, no detector tuning; measurement at 317744b stands. Keep the held-out 3-18 band. Add a coverage simulation test and a tie guard at the threshold rank. Record in ticket 05 Comments and the agent-gates derivation. Then check-slow, check.
- Implementer 7 done (stopped, handoff 05-implementer-7.md). Spawned implementer 8 `a7b5d51c1f6848e89` (brief: the approval above, steps 1-5; handoff `05-implementer-8.md`), watcher armed.

## Next:
Wait for implementer 8; rotate if its watcher fires. Then code-review from BASE 87005b9 (deviation 4, R1 leakage, deviations 8–14, the rule-test change in scope), fixer, close. Close report: add ticket-07 note (area-corrected / extreme-value score).
- Implementer 8 done: 5559ef9 (rule-test fa0 rank-based, tie guard, coverage sim, 4 protected numbers, ticket Comment), c1b6243 handoff. Gates at 5559ef9: test-fast 730 passed; check-slow 4 passed (exit 0); check 730 passed (exit 0). Open (→ fixer list): tie guard limited (calibration scores unsaved); derivation note only in untracked archived plan; tests/protected.py cites a stale plan path.
- Phase: code review from BASE 87005b9.
- Code review launched from 87005b9: Standards `a92af8a39228de70d`, Spec `aa5fda21df9eaa49c` (background).
- Standards review in (no hard violations; judgement calls S1-S4, smells M1-M7). Waiting for Spec.
- Spec review in. **Code-review disposition:**
  - FIX F1 (spec 1): `_candidate_reach` measures the wrong thing (top group / old T=154, skips _A0+leakage). Measure the plan's quantity T-free (candidates needed to reach the last qualifying group after all filters) on calibration seeds; if 2× it > 20, raise `_MAX_CANDIDATES` to ≥ 2× (lockfile approval for ticket-05 knobs covers it) and then make measure + stored thresholds + check-slow. If ≤ 20, driver fix only.
  - FIX F2 (spec 2): overlap test must assert the grown extents overlap (and that settling ran).
  - FIX F3 (spec 5): docstrings cite untracked/missing derivation paths → move the derivation note to a tracked file and point there; coverage test takes the rate from the saved run_info like the tie test.
  - FIX F4 (std 1): inline tolerances in test_synthetic.py → tests/protected.py (+ lockfile; adding protected numbers approved by orchestrator: strengthening).
  - FIX F5 (std 3,4): rename light-area `_MASK_FRACTION`/"light mask" to light wording (avoid clash with Glossary Mask); drop "outlier" wording.
  - FIX F6 (smells): inline Middle Man `_period_and_angle`; rename `_seed_depth` to an honest name; name the `mask >= 0.5` truth level once in tests/regions.py.
  - PASS spec 3 (absorb vs union of original extents): approved text's "extent" admits it; calibrated and fresh-range evaluated as is; only merged groups.
  - PASS std 2 (deviation 6 seeds[:5]): recorded deviation on new tests, not test selection.
  - PASS smells Tuning data clump, size_depth Feature Envy, driver pool duplication, positional regression-case tuples: churn in frozen/protected code or one-off drivers for no behaviour gain.
- Spawned fixer `a90b7da1486e38843` (F1-F6; handoff `05-fixer.md`), watcher armed.

## Next:
Wait for the fixer; rotate if its watcher fires. Then close: report commits, owner items (none new), passed findings, Mottle detection-limit risk, two-region test timing, ticket-07 note (area-corrected score); mark log closed; TaskStop self watcher; archive ticket files.
- Fixer done: 0c7caae (F1-F6; _MAX_CANDIDATES 20→60 by the plan rule, no score/region change on 689 tune frames), 91a7ea0 (make measure: same counts and thresholds), 588c19d (handoff). Gates at 91a7ea0 green (see ticket Comment). Same-Period 12° merge: PASS → follow-up (not in AC4; detector change + measure).
- **CLOSED 2026-11-12.** Files archived to `.archived/`.
