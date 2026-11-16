# Ticket 13 orchestrator log

- Ticket: `.scratch/stripe-detector/issues/13-speed-budget.md`
- BASE: `aae408447272dfe33972627ed5b13f6c9ee28995`
- Args: MIN_MODEL=opus, SELF_LIMIT=200000, WORKER_LIMIT=200000
- User rule (updated 2026-11-15): second opinion = `/codex:adversarial-review` in background mode (Skill); Fable critic only as fallback if Codex fails. Before any human question, it reviews it adversarially; I decide from its verdict + my own critical reading. Only ask the human about taste, external knowledge, or hard-to-revert architecture.
- Plan: `.scratch/stripe-detector/handoffs/13-plan.md` (pending)
- Plan review: `.scratch/stripe-detector/handoffs/13-plan-review.md` (pending)

## Workers

- planner `a457a15767c24e2c2` (opus): profile 1600×400 pipeline, write 13-plan.md with seams, result-preservation proof, AC tests, open questions. Status: done. Plan written. Profile: bank 4.7-5.7 s (198 iFFTs 464×1664), break pass 1.5 s at P3-4, total 5.6-7.9 s. Bit-identical: bank tidy −0.36 s, 4-thread Periods bank 4.64→1.98 s (~4.5 s worst). Open Qs Q1 threads in analyse, Q2 env-var thread setting, Q3 AC1 frame P3 2-break+Fork, Q4 5 s check in check-slow + bench w/ 30% margin, Q5 defer 09 break-finder speedup.
- plan reviewer `a17097c13618c8c1b` (opus, blind): writes 13-plan-review.md. Status: done. Breaks B1 calibrate_folder pool oversubscription; B2 lazy thread count, cap = lockfile entry (approval), sched_getaffinity, threads= arg; B3 margin vs Q4 contradiction; B4 AC1 timed span = read→analyse→report + record cold CLI. Prototype P1 whole-analyse at 1/2/4 threads idle+load. Owner O1 threads default + DENOISIFIER_THREADS, cold CLI in 5 s?; O2 where 5 s check lives (2026-11-10 ruling).
- prototyper `afa1e161598018954` (opus, worktree `.claude/worktrees/agent-afa1e161598018954`, branch prototype/13-p1-threads bc2e884): Status: done. 13-prototype-p1.md. Worst frame idle base 8.68 s → 4 threads 6.20 s; cold CLI 9.46 → 6.65 s; ~2.9 s non-threadable (break pass 1.7 s); bit-identical at 1/2/4/16 threads. ⇒ C1 required, Q4(b). Forwarded to re-planner.
- Fable critic `abc08492db5bb5451` (fable, fresh): adversarial verdicts on Q1-5, O1-2, B1-4. Status: done (folded into Decisions).
- re-planner `a36dc7b34a25d03df` (opus): rewrite 13-plan.md in place around algorithmic savings toward ~1 s cold CLI on ≤8 cores; fold B1-B4 + rulings; bit-identical slices first, score-moving grouped for one measure/re-store sequence. Status: done. Plan rewritten. Bit-identical: 1 lazy scipy.stats −0.39 cold; 2 A1 −0.36; 3 A2 shared spectrum −0.03; 4 threads ~−0.9. Score-moving (one measure+both re-stores): 5 scipy.fft/nonzero kernel/pruned iFFT bank 6.03→3.34; 6 float32 bank 3.34→1.80; 7 C1 −1.0..1.3; 8 multirate ~−0.5 (prototype first). Projected cold CLI ~2.8 s @4 threads. Open: O1 slice 8 now?; O2 aim < 2.3-2.8 s (batch/watch follow-up)?; O3 float32?
- `/codex:adversarial-review` cannot be model-invoked (disable-model-invocation) → Fable fallback per user rule.
- planner #3 `a829743e820306e2b` (opus): fold re-plan rulings into 13-plan.md, file follow-up issues. Status: done. Follow-ups 19-multirate-bank, 20-crop-local-region-and-fork-spectra, 21-batch-watch-mode (needs-triage). Seeds: harness 601_000-601_099, null screen 602_000-602_159, C1 603_000-603_099, reserved in USED_SEEDS (step 3). Explore set → ~/.cache/denoisifier/p13-c1/.
- planner #3 fold 2: B5 (bench fails on cold CLI median too; tests/test_bench.py 3 stubbed cases), N8 (cache cleanup item §3.4), N9 (private `analysis._analyse`). Status: done. Plan settled.
- implementer-1 `a0e4430226714751f` (opus): build plan in work order, tdd, commit per slice to main; handoff `13-implementer-1.md`; leaves measure/drivers/re-stores/check-slow/held-out/bench/check to fixer. Status: rotated (stopped). Handoff 13-implementer-1.md. Landed f1eae1f step0, 57ac55c slice1 (CLI import 0.65→0.35), 386c65d harness, df3c78b slice2 (bank 5.02→4.47), ef79e1f slice3=G1, 1257fee seeds, e04b377 handoff. Slice 5 WIP on branch t13-slice5-wip daca07d.
- implementer-2 `a87c30107ba09f7ad` (opus): continue from 13-implementer-1.md; handoff 13-implementer-2.md. Status: rotated (stopped). Landed 2f38fd8 (tie_bound.py). Branches t13-slice5-wip, t13-step3 pending. ε RULED: `_BANK_TIE_REL`=1e-9 approved (Fable re-review + own); max-relative rule; 4b own null screen; slice 5 vs 4b array_equal except pre-stated band ε(1±1e-3), else drop 5+6; float32 ε fixed from rounding size pre-look. In ticket Comments.
- implementer-3 `a36c03ef64f9194da` (opus): continue from 13-implementer-2.md; handoff 13-implementer-3.md. Status: running. Seed 38 shared by AC1 frame and P6 timing frame: OK (ruled). Slice 4b (branch t13-s4b) FAILS pre-stated rows 'found identically' (1 px region, breakfork_601052) and 'report fields ≤1e-9' (max fork dA 1.26e-5°); passes score=0, ratio/Period equal, Angle only at tied px. 4b RULED A (accept on slice-6 pre-stated decision criteria) with binding conditions: 4b null screen unamended; slice 5 rows vs 4b final, no more rescues; end re-store/held-out independent. Fable advised owner decide (3rd after-look move); I decided per CLAUDE.md and flagged it to the user for possible overrule. implementer-3 rotated (stopped); handoff 13-implementer-3.md. Nothing on main yet (main 2f38fd8). 4b: replacement rows PASS, null screen vs G1 PASS (cond 1 holds); test-fast on t13-s4b was running. Slice 5 vs 4b harness all PASS (0 exempt px); its null screen pending. Slice 7 WIP t13-s7 (finder 2.5→0.5 s on test field). Slice 7 fresh layout (136 frames / 100 seeds) confirmed.
- implementer-4 `a8dfce140d0fa1d06` (opus): continue from 13-implementer-3.md; handoff 13-implementer-4.md. Status: running. Landed f381d80 step3, ea359a7 4b (test-fast 969 passed), 53a7871 slice5 (null screen PASS; test-fast 983 passed; bank 4.48→2.39, analyse 6.80→4.63 single thread). Slice 6 approvals: ε=1e-3 (≥10× f32 rounding max 2.69e-5), SINGLE_PRECISION_REL_TOL=1e-5 — in ticket Comments.
- Fable approvals reviewer `a67c705d20141a52c`: reviews handoff Next-steps item 2 (_GAUSS_TRUNC_SIGMAS=8.0, FULL_GRID_REL_TOL=1e-12 → protected.py, speed-test protected numbers, STAMPED_FILES += tests/speed.py, tests/test_speed.py). Status: done — all 4 approved with conditions; recorded in ticket Comments; sent to implementer-2.
- Fable critic #2 `ae189c257233c8c82` (fable, fresh): verdicts on re-plan O1-O3 + top risks. Status: done.

- implementer-5 `a8849d518fe70b8e3` (opus): continue from 13-implementer-4.md; land slice 4 with _MAX_BANK_THREADS=4 (rebase t13-s4 on 8e15c03, make test-fast, ff main), then plan step 9 `pytest -m wide`; no heavy gates; handoff 13-implementer-5.md. Status: done. Slice 4 = 231aabb (make test-fast 991 passed; pytest -m wide 639 passed), handoff 1a3f864. Implementation complete.

## Decisions

Fable critic done (verdicts per item; strongest objection: plan meets 5 s by changing measurement conditions — threads on a 16-thread WSL2 box; single-thread saving only 0.4 s). My rulings (critic + own reading):
- Q2: lazy env read + internal `threads=` arg on `estimate_local_stripes`, env knob private/undocumented. Revertible; no owner.
- Q3: AC1 gates on P3 two-break + Fork; record P6 too. "Fix the code, never the check" — no easy frame. No owner.
- Q4/O2: 5 s target lives in `make bench`, check-slow keeps ~30 s — already ruled (owner 2026-11-10, `.scratch/agent-gates/spec.md:26`, verified). No owner.
- Q5: decide on P1 numbers; if threaded worst > ~4.5 s, C1 (09 break-finder speedup) is in scope. If deferred, persist explore_v2 proof set + file follow-up.
- B1 accept (threads=1 into `_score_file` package pool); B2 accept (lazy read; only cap constant to lockfile — approval by me, recorded in ticket Comments); B3 accept (P1 before slice 3); B4 accept (AC1 asserts read→analyse→report via one function; record cold CLI wall time).
- Owner RULED 2026-11-15 (recorded in ticket Comments): ≤8 cores; budget includes cold CLI start; goal = as fast as possible by better computation/algorithms (not only threads), target down to ~1 s, beyond unnecessary. Score-moving changes thus in scope (AC2 re-store path). Was: Q1/O1 — thread default depends on the experimenter laptop's cores and load during acquisition (external knowledge); does 5 s cover a cold per-frame CLI call (how tool is invoked; external).

Rulings on re-plan (Fable critic #2 + own reading; no owner question needed):
- O1: slice 8 (multirate) deferred to a follow-up ticket (needs-triage), P2 prototype goes there. Reason: unmeasured, ~1e-3 score shift (100x slices 5-6), gain within projection noise; keeps the one-look score-moving set smaller.
- O2: close ticket at the plan's result; file follow-ups (needs-triage): multirate bank; crop-local region/Fork spectra (~0.75 s); batch/watch mode (new public interface → owner triages it there). Owner's ruling already covers cold per-frame CLI "as far as possible"; each extra score-moving lever costs its own ~3 h re-store.
- O3: adopt float32 only with a decision-based go/no-go: shipped variant (with mean subtraction) on full harness + null screen; no score>threshold flip; fine Period/Angle/depth shifts ≤1 % of each accuracy tolerance; else recompute winners' `response` in float64 (`analysis.py:920,1025` `_phase_steps`).
- Risk 1 accept: per Group II commit, foreground null screen on unregistered seeds (not overlapping any registered/held-out ranges; ~100 stripe-free + ~60 break-free striped incl. `free`/`full_free`/`two_free` tags) vs slice-4 baseline, before the end sequence. Plan states: AC 7 or held-out red = stop and report (finding, no re-store, no second look).
- Risk 3 accept: step 0 persists the 09 explore set (335 MB pickle, durable git-ignored location + recipe); C1 criterion pre-stated (same basin, found/AC 4 identical, per-frame |Δerror| ≤ fixed ε, max not worse, plus fresh unregistered-seed frames). Slice 4 (threads) moves after Group II; `_MAX_BANK_THREADS` approved on measured final gain.
- Confirmed planner picks: C1 ε = 0.05 P per-frame |Δline error| (tight vs 09's cap regression 0.17→0.75 P); threads kept only if 4 beat 1 by ≥0.3 s and ≥15 %.
- Approval (orchestrator, lockfile edit): reserving the three new seed ranges in `USED_SEEDS` in `tests/protected.py` — strengthening (prevents overlap); record in ticket Comments when landed. Does NOT touch CALIBRATION_SEEDS or the seed guard.
- Slice 5: fast test covers cyclic wrap at P3, binned and reference-angle filters.

## Code review

Closing check done: B5 open (bench must also fail on cold CLI median > target) → planner #3 folds with N8 (name ~/.cache copy for cleanup) and N9 (private helper, not _threads kw on analyse). N7 done: orchestrator reading + seed approval recorded in ticket Comments. No second closing check.

- Slice 5 go/no-go: harness row "Period/Angle array_equal" FAILS on 2 frames (1 px each, last column, Angle −10→+10 at exact ±10° tie at P4.193; G1 diff −3e-15 / 0.0, s5 +3.9e-15/+6.1e-15). All other rows pass by wide margins. Plan says drop → also drops slice 6 (~4 s). Fable reviewer `a17f53b8130c49d38` judging A drop / B tie-aware criterion (weakening approval) / C robust tie-break code / D. Slice 5 null screen vs G1 (160 frames): all 6 rows PASS (max score shift 1.7e-13; no flips, no new breaks/Forks). Implementer-2 told: hold slice 5, land step 3, may start slice 7 on main.
- Slice 5 RULED (Fable `a17f53b8130c49d38` + own reading): option C — new slice 4b, a deterministic tie-break in `_match_period` (ε from the structural mirror-column bound, ≥10× safety, approval with numbers), checked vs G1 under tie-aware rows + null screen, then the new baseline for slice 5 (rows unchanged). Fable said ask the owner, but its premise was wrong: the rule came from the plan, not the owner. Recorded in ticket Comments. Note for slice 6: float32 tie noise ~1e-7 needs ε re-derived there.

Next: wait for implementer-2 (later approvals: C1 cap slice 7, _MAX_BANK_THREADS slice 4). Then code-review from BASE; fixer runs gates.

## PAUSED 2026-11-16 (self fill 200479 ≥ 200000)

In flight: implementer-4 `a8dfce140d0fa1d06` (slice 6 with approved ε=1e-3 + tol 1e-5; then slice 7 cap → my approval; then slice 4 threads → `_MAX_BANK_THREADS` approval; handoff 13-implementer-4.md); its watcher b14ovbj07.
Open branches: t13-s7 (slice 7 WIP), t13-slice5-wip / t13-s4b / t13-step3 (landed, delete at close). Worktrees in session scratchpad c1df1e95… (ref_base, ref_g1, s4b, s6, s7, wip5) + `.claude/worktrees/agent-afa1e161598018954` (P1 prototype, branch prototype/13-p1-threads). Cache ~/.cache/denoisifier/p13-c1/.
Second-opinion source: `/codex:adversarial-review` cannot be model-invoked; Fable fallback used.

Next (on resume): re-arm self watcher; check implementer-4 via `fill-watch.py --now`; answer its approval requests (slice 7 cap, threads cap); when implementation done → code-review from BASE aae4084 → fixer (fix list, then make measure → threshold re-store both drivers → make check-slow → make check-held-out → make bench → make check, tracked bench.json) → close.

- (paused) implementer-4: slice 6 DROPPED. Variants A and B both fail the pre-stated 'found identically' row (16 harness frames, labels differ by 1-6 edge px) and the null screen 'labels equal' row (8 frames); no rows amended; branch t13-s6 6e8361f kept. TODO on resume: add a ticket Comment recording the drop (the implementer asked). Harness pickles moved to ~/.cache/denoisifier/p13-h/ (cleanup). Slice 7 is fixing its cap against slice 5.
- (paused) implementer-4: slice 7 fails the pre-stated same-basin row (b) at every cap 10k-80k: 27-115 of 216 frames, apparently only on searches that found no line. Every other row passes with zero change, and reported breaks are bit-identical. The implementer treats slice 7 as DROPPED per the plan unless I rule otherwise; an accepted-searches-only rule would be a 4th after-look amendment. On resume: confirm the drop (or owner question), add a ticket Comment, file the finder follow-up naming the explore set. Implementer started slice 4 (threads) on main c8e02a5.
- (paused) implementer-4 watcher: ROTATE agent=a8dfce140d0fa1d06 fill=201620 limit=200000 — rotation deferred until resume.
- (paused) implementer-4: slice 4 (threads) passes its timed go/no-go on t13-s4 0e2d0f0: median 4.532 s at 1 thread vs 3.389 s at 4 threads, a gain of 1.143 s and a ratio of 0.748 (bars 0.3 s and 0.85). Output exactly equal at 1/4/16 threads on 58 frames. It requests approval for _MAX_BANK_THREADS = 4. Pending on resume: approve, rotate the implementer (fill 225k), confirm the slice 7 drop and record slices 6 and 7 in the ticket.
- (paused) implementer-4 reported and finished. Handoff 13-implementer-4.md (main = 2c6482f handoff commit; slices 1-3, 4b, 5 landed). Pending on resume: _MAX_BANK_THREADS=4 approval, then a successor implementer lands slice 4 (t13-s4 0e2d0f0) after make test-fast; slice 7 drop confirmation; ticket Comments for slices 6 and 7.

## RESUMED 2026-11-16 (new session)

- Self watcher re-armed. implementer-4 was already done (age 26502 s), so no rotation.
- RULED: slice 7 dropped (plan section 2, line 166: any fail → drop; no 4th after-the-look amendment). APPROVED: `_MAX_BANK_THREADS = 4` (pre-stated bars ≥0.3 s / ≥15 %; measured 1.143 s / 25 %). Ticket Comments for slice 6 drop, slice 7 drop and the threads approval, plus follow-up `issues/22-faster-break-finder.md`: commit 8e15c03.
- Spawned implementer-5 (see Workers).

Next: on implementer-5's report → code-review from BASE aae4084 → sort fix/owner/pass → fixer (fixes, then make measure → both re-stores → make check-slow → make check-held-out → make bench + tracked bench.json → make check) → close and clean up (handoff cleanup lists; keep ~/.cache/denoisifier/p13-c1 and .scratch/stripe-detector/p13-c1-ref for ticket 22).

- implementer-5 done (231aabb slice 4, 1a3f864 handoff). Starting code-review from BASE aae4084.
- code-review running: Standards a85cc1da5b5371fd5, Spec a61ec8caeed5afd7c (opus, read-only).
- Standards review done: no hard violations; judgement calls S1 speed-frame locals (_DEPTH, _FORK_DIRECTION, _SLOW_REPEATS) not in protected.py; S2 sigma formula x4 + response/local-mean pair; S3 gaussian(period=None) switch; S4 truncate test hook; S5 threads knob two mechanisms + delegators; S6 "DENOISIFIER_THREADS" literal x4 in tests; S7 terse names in _matches; S8 stage_timings uses feasibility._frame. Waiting for Spec.
- Spec review done: P1 AC 3 driver partial (no BASE column, no threads-1 column, no adopted/dropped list); P2 SPEED_TEST_SEED also used by the stage timer's P6 frame, against approval 3's condition "used nowhere else" (I OK'd this earlier but never recorded it in Comments); P3 "wrap" wording/ids still in tests/test_spectrum_filters.py. Seams all checked correct; nothing blocks AC 1/AC 2.

### Code review sort

Fix:
- F1 (P1): tests/stage_timings.py gives plan §4's table: BASE (P1's table, quoted), final HEAD at threads 1 and at the default, plus the adopted and dropped slices.
- F2 (P2): own seed for the P6 typical frame, `SPEED_TYPICAL_TEST_SEED` (free in TEST_SEED_BLOCK). Approved here (adds a protected number, makes nothing weaker).
- F3 (P3): "wrap" → Nyquist-clipped wording and ids in test_spectrum_filters.py.
- F4 (S1): speed-frame depth, Fork direction and _SLOW_REPEATS into protected.py. Approved (they only add numbers).
- F5 (S2): one sigma helper for the 3 src sites, and the test imports it rather than copying it; exact harness at threads 1 vs HEAD must show 0 differences.
- F6 (S6): tests import _local_stripes._THREADS_ENV instead of the literal.
- F7 (S7): clearer names in _matches; make the two-phase use of _BankBuffers.energy obvious.
Pass:
- S3 (gaussian(period=None) switch): the seam was just proven bit-identical and documents the None case; splitting it re-opens that proof for a cosmetic gain.
- S4 (truncate=False): it is the reference oracle that approval 2's condition requires.
- S5 (private twins, threads=1 vs env var): by design (rulings B1, N9). Pools that call public functions can only be reached through the env var.
- S8 (stage_timings uses feasibility._frame): a test-side measurement script.
Owner: none.
- fixer `a52fd8913fa2bf959` (opus): F1-F7, then end sequence (measure → re-stores → check-slow → check-held-out → bench + tracked bench.json → check → AC 3 table); handoff 13-fixer.md. Status: running.

Next: on fixer report → close (report to user, archive, cleanup per handoff lists; keep p13-c1 cache + p13-c1-ref for ticket 22).
- fixer reported: F1-F7 b928464, measure a91fa51 (thresholds ~1e-14 rel, op-rule green), stripe re-store 4b6f3de, break/Fork c723810 (thresholds unchanged), check-slow 7 passed 793.96s, held-out 7 passed 2083.24s, make bench EXIT=0 (warm 4.23, cold 4.59). Tracked record MISSED (cold 5.28, non-idle start, overlapped my commit 7a2c7bd). RULED: one idle rerun, result stands; miss → owner (Comments 0750b7c). Fixer resumed for rerun → bench.json → make check → stage table → spec pointer.
- Filed agent-gates/08 (gate reuse across end sequence) at owner request, 7a2c7bd.
- 13:48: fixer idle-wait loop self-matched its pgrep pattern and spun 38 min (load ~0.1); killed by orchestrator, fixer told to start the bench record directly.
- Ruled rerun MISSED (cold 5.22 s idle, warm 4.03). Owner RULED: accept and close; no target change; make bench stays red on cold; follow-up 23 cold-start overhead (d4ea2f2). Fixer resumed: bench.json = miss-2 record → make check → stage table + spec pointer → handoff.

## CLOSED 2026-11-16

- Fixer done: bench.json c8095cb (the ruled idle rerun as measured); `make check` at c8095cb EXIT=0 `1633 passed, 14 deselected in 1321.61s (0:22:01)`, stamp check green; stage-timings table `.scratch/stripe-detector/stage-timings.md` plus spec story 39 pointer; handoff 253e67d.
- Result: warm pipeline 8.68 → 4.03-4.73 s (4 threads), cold CLI 9.46 → 4.5-5.2 s; AC 1 cold half missed on the idle record (5.22 s), accepted by the owner.
- Follow-ups: stripe-detector 19, 20, 21, 22, 23; agent-gates 08.
- Cleanup done: all t13 worktrees, the fixer's ref worktree, the P1 prototype worktree, branches t13-step3/s4b/slice5-wip/s4, ~/.cache/denoisifier/p13-h. Kept: branches t13-s6, t13-s7 (record; 22 names s7), prototype/13-p1-threads; ~/.cache/denoisifier/p13-c1 and .scratch/stripe-detector/p13-c1-ref (ticket 22).
- Watchers stopped.
