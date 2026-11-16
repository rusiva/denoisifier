# 11 rulings (orchestrator, after Codex `11-codex-review.md` + Fable critic `11-critic.md`)

Inputs: plan `11-plan.md` §12 (OQ1-OQ8), review `11-plan-review.md` (B1-B5, O1-O5, N1-N8).

## Breaks and notes
- **B1-B5: fold all.** B1: keep the pre-break gate `>=`; only the reported comparisons go strict; name both strict comparisons (`_region_forks` reported side and `_accepted` at `_local_phase.py:500`) in the approval list. B4: P1 records true-defect E on every 09/10 test frame (incl. `wide`); stop rule uses the smaller of those and 0.18/0.31 with a margin; a red 09/10 seed at step 6 is a stop for the orchestrator, never a threshold/seed edit. B5: one shared private front-half helper used by `analyse` and the evidence pass, plus a test of the conservative implication against public Reports (not a spy alone).
- **N1-N8: fold all.** N1: replace "exactly" with a conservative bound ("found" ⊇ "reported"). N2: see OQ7. N3: scope disclosure in docstring and CLI help. N4: fast stale-digest test. N5: Makefile help text update (approved, see below). N6: move the CLI test to step 6. N7: name the finder argument; P1 measures runtime. N8: `make check` at step 6.
- **Codex extra:** when break thresholds move, masks / region merges / measurements change (`analysis.py:1249-1253`, `1340-1382`), not only reported defects. The plan states the effect and the gate consequence (does any `make measure` output move? if yes, `make measure` at the fixer).

## Open questions
- **OQ1 → (b)** floors at current constants. Both critics agree. If P1 shows the floors bind at every valid rate, say so plainly in ADR 0003 and the ticket Comment ("the floors set the thresholds; measured rate x of 300"); P1 reports the smallest rate at which either threshold leaves its floor.
- **OQ2 → (a)** fixed r/2 each, ordinary marginal order statistics, floors kept. Reason: Codex's analytic counterexample (union rule gives 5.305 % at r = 5 %); r/2 + r/2 is a valid union bound. Error message states the smallest valid rate.
- **OQ3 → (a)** separate `defect_free_calibration.json` (name per glossary ruling below). Version its evidence semantics and record the stripe digest dependency.
- **OQ4 → (a) as a narrow, declared baseline** (400x1600 full-frame, depth 0.5, the ten cases). Add P1 measurement arms on prototype seeds at the candidate thresholds: (i) full-frame stripes at m = 0.2, (ii) a partial region in a 400x1600 frame at depth 0.5, (iii) stripe `false_alarm_rate=0.05`. Pre-declared: any arm with fake frames above ~5 % → stop for the orchestrator (owner question: which depths/geometries are typical, external knowledge). Otherwise record all arm numbers in ADR 0003 as the claim's scope; the docstring restricts the claim to the declared recipe. No runtime Report warnings for mismatched settings in this ticket (new public Report surface not asked for; docstring disclosure suffices).
- **OQ5 → (b)** plus a paired "lost by calibration" count: on the same frames, true defects found at the floors but lost at the stored thresholds; expect 0. Report per-case outcomes.
- **OQ6 / O1 → (a)** ticket 11's close is a held-out milestone; the fixer runs `make check-held-out` once, after `make check-slow`. Approved by the orchestrator under CLAUDE.md's delegation (motivated: AC 2 needs exactly one held-out look at the frozen pipeline). Pre-declared red rule: a red AC 2 / AC 3(c) is a finding for the orchestrator; no threshold, floor, recipe or seed is edited in response; a second look after any evidence-moving change uses a reserved fresh seed range (planner picks one disjoint from every registered range and registers it). CLAUDE.md and Makefile help wording updated in the same change.
- **OQ7 → (a)** assert the total count, with a one-sided bound (the one-sided point at `CALIBRATION_MAX_FALSE_RED`, ~29 at n = 300), not the central (3, 33). Write the measured count, frames-with-fakes and an exact upper limit into ADR 0003 and the docstring. No fallback to frames-with-fakes.
- **O2 → option semantics:** the rate option is the calibrated share of defect-free striped frames with at least one fake break or Fork, "at most r" (floors). AC 2 checks the count, which is the stricter reading. Pre-declared: P1 records fake multiplicity per frame; if the total count exceeds ~1.5× frames-with-fakes, stop for the orchestrator before freezing (would need count-based calibration). Record per-case fakes in P1 and in the held-out JSON, with a pre-declared per-case alarm level.
- **OQ8 / O5 → decide from P1, against the owner's known ~20 min check-slow preference** (`07-orchestrator.md:34`): if the full 300-frame reproduction keeps `make check-slow` at ≤ ~25 min idle, reproduce all 300; otherwise a 60-frame prefix (6 per case) in check-slow and the full 300 reproduced at re-store and at the held-out milestone. Record P1's timing and the branch taken.
- **O3 → approve** the defect driver as an additional writer of tracked source outside `make fix` (at this ticket's step 6 and in the re-store procedure). Record in the ticket Comments before step 6; update the CLAUDE.md wording.
- **O4 → keep `DefectCalibration`, its loader and any `defect_calibration=` parameter private.** Publish only the rate option and its CLI flag (all AC 4 asks). Reason: a public calibration-file format is hard to reverse (ADR 0002); private is the revertible choice. spec.md:112 "can be recalibrated later": add a one-line spec note that real-frame recalibration of these thresholds is deferred. Tests replace `stored_defect_calibration` (B3).

## Critic's "missed" items — fold
- Rate depends on the stripe threshold: covered by arm (iii) + docstring.
- Per-case rates: recorded (O2 ruling).
- At-scale scalar-vs-real-path check on held-out frames: a reported break ⇒ S_b > T_b; a reported Fork ⇒ S_f > T_f or a found break; both below ⇒ none.
- Assert every calibration and held-out frame is `striped`, or report the rate over striped frames and count the rest.
- Spikes' effect on Fork candidates: P1 reports the S_f distribution at 400x1600 with spikes.
- `GLOSSARY.md:85` lists "defect" under Fork's Avoid: name the public option and file from existing glossary terms (e.g. breaks and Forks), or add a glossary term in the same step; never use an Avoid term publicly.

## Approvals recorded (orchestrator, CLAUDE.md delegation)
- `make check-held-out` at ticket 11's close; CLAUDE.md + Makefile help text wording (gate config, doc-only).
- Defect driver as a source writer (step 6, re-store).
- Strict `>` on the reported break and Fork comparisons (gate stays `>=`).
Remaining §10 lockfile/protected-number edits are approved when the closing check passes them, per the folded plan's list.

## Closing check (orchestrator, on `11-plan-review.md` "Closing check")
- **B6 → fold as proposed.** The AC 4 CLI tests call `cli.main([...])` in-process with the monkeypatched calibration; keep one subprocess smoke test of the flag.
- **N9 → fold.** List the 9 direct finder calls in `test_local_phase.py` among the seams to update.
- **N10 → fold.** T8 asserts a precondition that the chosen thresholds sit above the floors (a hand-made calibration via the private seam), else it is not a valid test.
- **N11 → fold.** AC 2 count model: the union of two r/2 events has frame rate ≤ r, so assert the total count ≤ the one-sided point of the single-order-statistic model at r (k = 15 at n = 300, ~29). The plan and ADR 0003 state that this is conservative for frames-with-fakes and an approximation for the count, covered by the 1.5× multiplicity stop rule. Fixed before the held-out run.
- **N12 → fold.** Arm (i) reports fake rates over striped frames, with the non-striped count alongside.

## P1 outcome (orchestrator, 2026-11-15; `11-prototype-p1.md`)
- Floors bind: S_b = S_f = 0 on all 200 base frames; T_b = 0.1, T_f = 0.3 at every valid rate. Proceed (OQ1); ADR 0003 and the ticket Comment say so plainly.
- Stop rule 2 (multiplicity) **not fired**: it is defined on the base Calibration Set (0 fakes). Arm (ii)'s 3 fakes on 1 frame (seed 112065, a fake edge region, the 109797 kind) is one event; its count rate 3/200 = 1.5 % is far under 5 %. Record it in ADR 0003 as scope (partial regions carry multi-fake frames from fake regions; ticket 17's mechanism), no count-based calibration.
- OQ8 branch: prefix (full 300 → check-slow ~32-33 min; prefix ~22-23 min).
- m_b = 0.18, m_f = 0.31 (true E min 0.267 / 0.340); stop rule 1 not fired.
