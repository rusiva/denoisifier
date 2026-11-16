# 11 critic: plan open questions and review owner items (fresh context)

Read at HEAD `e06a902`: `11-plan.md`, `11-plan-review.md`, the ticket, `spec.md` 51, 97, 105, 112, 140, ADR 0002, `GLOSSARY.md`, `_local_phase.py`, `analysis.py`, `_calibration.py`, `tests/protected.py`, `07-plan.md` rulings, ticket 09 Comments. Nothing was run except `false_alarm_tolerance` and two binomial tails (numbers below).

Classes: (a) decidable by best practice, (b) taste, (c) needs external knowledge, (d) hard-to-revert architecture.

## Summary

| Item | Verdict | Class |
|---|---|---|
| OQ1 floors | agree (b), with a condition on what "floors bind" means | (a) |
| OQ2 rate split | agree (b) | (a) |
| OQ3 storage | agree (a) | (a) |
| OQ4 calibration frames | **disagree in part**: shape yes, depth 0.5 alone no | shape (a), depth (c) |
| OQ5 AC 3 evidence | agree (b), **plus a paired check** | (a) |
| OQ6 / O1 held-out at close | agree A, **plus a pre-declared red rule and spare seeds** | (a) |
| OQ7 AC 2 unit | agree (a), **disagree with the bound** | (a) |
| O2 public meaning | agree A | (a); (b) for the owner only if P1 shows count well above frames |
| OQ8 / O5 reproduction cost | **disagree with a fixed A**: decide from P1 | (b) |
| O3 third writer | agree A | (a) |
| O4 no real-frame recalibration | agree A, **but keep `defect_calibration=` out of the public interface** | (a); the public parameter is (d) |

## Open questions

### OQ1 floors: agree (b). Class (a).

- Option (a) is not viable. The largest fork-free candidate is 0.000 (ticket Comment), so the rank-7 `S_f` is 0 and strict `> 0` reports every candidate. That breaks ticket 10's "no extra Fork" tests.
- Option (c) retunes the finders on new frames, which un-validates 09/10's frozen configs.
- **Condition the plan glosses over** (§7 step 1, "if the floors bind, proceed"). The break-free maximum E was 0.082 against a floor of 0.1 (`_local_phase.py:82-85`). So the likely P1 result is that every stored value is under the floors. Then:
  - the calibration routine sets nothing (AC 1 says it "sets the break and fork thresholds");
  - the rate option changes nothing at any valid rate (AC 4 says "the rate can be set");
  - the 1-in-20 claim rests only on the held-out count, not on the calibration.
- This is acceptable, but it must be reported, not passed silently. P1 should state the smallest rate at which either threshold leaves its floor. If there is none, the ticket Comment and ADR 0003 say "the floors set the thresholds; measured rate x of 300".

### OQ2 union rule: agree (b). Class (a).

- Bonferroni r/2 each wastes the Fork half, since the Fork floor will bind. One rate each gives a frame rate of up to 2r, which misses spec.md:51.
- The rule is not exactly an order statistic: `T_f` comes from the calibration set only, so `C` is not exchangeable with a new frame. The error is of order 1/n. State it in ADR 0003 and in the budget test (review N2 says the same).
- The smallest rate becomes 2/(n+1) = 0.66 %, not the stripe option's 0.33 %. Say so in the error message.

### OQ3 separate file: agree (a). Class (a).

- A section in the stripe file would change `PACKAGE_CALIBRATION_DIGEST` and the stripe reproduction, which CLAUDE.md treats as a finding when scores did not move.
- Two constants lose the per-frame trace that ADR 0002 chose on purpose.
- The format is revertible as long as users cannot hold such a file (see O4).

### OQ4 calibration frames: disagree in part. Shape (a), depth (c).

- **Shape 400x1600: agree.** It is ADR 0002's ruling Q1 (`07-plan.md:400`).
- **"Conservative" is wrong for the one known fake mechanism.** The fake breaks of 109797 sat in a false region in the stripe-free part of a partial-region frame (`issues/17-region-growth-under-phase-breaks.md:25`: 3 breaks, E 0.54-0.80). A full-frame striped calibration frame has almost no stripe-free lit area, so neither the calibration nor the same-recipe held-out set can see that mechanism.
- **Depth 0.5 only.** Phase noise grows as depth falls. The detector's design point is m = 0.2 (`tests/protected.py:37`, `WEAK_DEPTH`). spec.md:112 defines typical settings by mottle and photons only, not depth. A user with m = 0.2 stripes gets breaks and Forks under a rate that was never measured there.
- **Alternative.** Keep (a) as the stored Calibration Set. Add two measurement arms to P1, on prototype seeds, at the candidate thresholds:
  - full-frame stripes at m = 0.2;
  - a partial region in a 400x1600 frame at depth 0.5.
- Pre-declare: if either arm shows fake frames above about 5 %, stop for the owner. Otherwise record both numbers in ADR 0003 as the scope of the claim.
- **Why (c).** Which depth real frames have is not in the repo. If the owner says weak stripes are the normal case, the Calibration Set should be a depth mix, and that decision is theirs.

### OQ5 AC 3 evidence: agree (b), with an addition. Class (a).

- The bar 0.95 at N = 100 is defensible. At a true rate of 0.99 a bar of 97 false-reds 1.8 % of the time and 96 does 0.34 %; at 0.995 a bar of 97 does 0.17 %. 09's 199/200 does not exclude 0.98, so 0.95 is not loose by much.
- **Missing: the check that isolates "after calibration".** On the same 200 frames, count the true defects found at the floors but lost at the stored thresholds. Expected 0; it is exactly 0 when the floors bind. This is the direct reading of AC 3, and a pooled 0.95 cannot show it: a fall from 99.5 % to 96 % passes.
- Plan review B4 (the stop rule ignores the 09/10 test seeds) stands and matters more than the bar.

### OQ6 held-out run at close: agree (a). Class (a).

- AC 2 cannot be met without one held-out run. `pyproject.toml:52` already says "at a ticket's close". The owner's 07 ruling Q2 moved held-out tests to milestones, and ticket 11 stores thresholds, so it is one.
- The CLAUDE.md and Makefile help wording is drafted for the owner, as `07-claude-md-draft.md` did.
- **Missing: what happens on a red.** The plan calls it "the one look" but gives no rule. Pre-declare, as 07's plan did:
  - a red AC 2 or AC 3(c) is a finding for the orchestrator;
  - no threshold, floor, recipe or seed is edited in response;
  - a second look after any change that moves evidence uses fresh seeds. Reserve a spare range now, for example 114_300-114_599.

### OQ7 AC 2 unit: agree (a) on the count, disagree with the bound. Class (a).

- The count is the stricter reading and is the AC's own wording.
- **The bound is too loose to carry the claim.** `false_alarm_tolerance(300, 300, 0.05, 0.995)` returns (3, 33) (`_calibration.py:34-46`). The plan's "about 29" is the one-sided 99 % point of the same distribution, which that function does not return. A test that passes at 33 fakes in 300 frames passes at 1 per 9 frames.
- That bound is right for "not inconsistent with a 5 % order statistic". It is wrong for a threshold held at a floor, where the expected count is near 0.
- **Alternative.**
  - Assert count ≤ the one-sided bound at `CALIBRATION_MAX_FALSE_RED` (29).
  - Write the measured count, the frames-with-fakes count and its exact upper limit into ADR 0003 and the `analyse` docstring. ADR 0002 does this for the stripe rate ("within about 0.2-2.4 %").
  - The claim users read is then the measured interval, not "the test passed".
- The fallback to frames-with-fakes is a weakening. It is allowed only from P1 numbers, before the held-out look, never after it.

### OQ8 reproduction cost: disagree with a fixed (a). Class (b).

- 07's ruling Q7 was about exactness, not size (`07-plan.md:406`). It is not a precedent for 300 frames.
- The relevant precedent is the owner's Q2 ruling: they rejected a 38-47 min `check-slow` for about 20 min (`07-orchestrator.md:34`). 30-34 min sits between the two, and every worktree pays it. That is the owner's taste.
- **My recommendation: decide from P1.**
  - If the floors bind at every valid rate, the stored values do not move the thresholds. Then use a 60-frame prefix in `check-slow` (6 per case), and the full 300 at re-store and at milestones.
  - If a threshold is above its floor, use all 300.
- Add review N4's fast stale-digest test in either case.

## Owner items

### O1: agree A. Class (a). See OQ6.

`make check-held-out` also re-runs the unchanged stripe held-out tests (about 20 min for an identical result). That is acceptable for one command and one rule.

### O2: agree A. Class (a).

- "At most r" is simply the correct wording once floors exist.
- spec.md:51 and :140 say "about one per 20 frames", which a frame share with an asserted count satisfies.
- It becomes an owner question, class (b), only if P1 shows the count well above the frame share.
- **Missed by both documents.** `GLOSSARY.md:85` lists "defect" under Fork's _Avoid_. Plan step 7 adds "Defect" as a term and the public option is `defect_false_alarm_rate`. The Fork entry needs the edit in the same step.

### O3: agree A. Class (a).

It is the direct analogue of 07 step 5. Record the approval in the ticket Comments before step 6, and draft the CLAUDE.md wording for the owner.

### O4: agree A. Class (a), with one (d) point.

- Story 53 (spec.md:97) asks for recalibration on "my own stripe-free frames". That is the stripe threshold only. Only the plural in spec.md:112 is departed from. A one-line spec note for the owner is enough.
- **The (d) point.** Plan §4 adds a public `defect_calibration=` parameter and a public `DefectCalibration` JSON format with no user story behind them. ADR 0002 says such a format "is hard to reverse once users hold calibration files of this format".
- **Alternative.** Publish only `defect_false_alarm_rate` and the CLI flag, which is all AC 4 asks. Keep `DefectCalibration` and its loader private. Tests replace `stored_defect_calibration` (review B3 already suggests this). If the owner wants the public seam now, that is their call.

### O5: class (b). See OQ8.

## Are B1-B5 and N1-N8 right?

All are right. I checked these against the code:

- **B1** `analysis.py:487-500`: `_region_forks` is shared by the gate and the reported search, and `test_analyse.py:2127-2132` injects E exactly at the gate.
- **B2** `test_phase_break_pass.py:37, 87, 104` and `test_analyse.py:1944` are as described.
- **B3** follows from the floors. It is the most important break, because the floors will probably bind.
- **B4** right. Add the margin to the stop rule.
- **B5** right. See the stronger check under "missed" item 5.
- **N1** `analysis.py:1474-1476` confirmed: a found break with no near pixel is not reported.
- **N2** confirmed by running it: (3, 33).
- **N3-N8** right. N3 understates its case: see "missed" item 2.

One addition to B1: the strict `>` on the break side also changes `_accepted` at exactly E = 0.1 (`_local_phase.py:500`). That is harmless, but it is the plan's approval A5 and should name both comparisons.

## What both documents missed about the 1-in-20 claim

1. **The Calibration Set excludes the known fake mechanism by construction.** Full-frame stripes leave no stripe-free lit area for a false region. See OQ4.
2. **The rate scales with the stripe false-alarm rate.** 109797's false region had a peak of 118 against a threshold of 100.8. At `false_alarm_rate=0.05` the stripe threshold is 60.9 (`07-orchestrator.md:22`), so many more false regions are reported, each open to fake breaks. The claim holds at the stored 1 % stripe threshold only. Measure one arm at 5 % in P1, or say "not covered" in the docstring.
3. **Depth.** Nothing is measured at m = 0.2. See OQ4.
4. **The pooled rate hides the per-Period rate.** Calibration and held-out sets are both 30 frames for each of 10 cases (`tests/cases.py:14-27`), and the claim is the average. A real setup has one Period. If the fakes sit in one case (P 3 is the usual worst), that user sees up to 10 times the rate. Record fakes per case in P1 and in `.gate/held-out-defects.json`, and pre-declare a per-case alarm level.
5. **Nothing checks the scalars against the real path at scale.** T7 uses 4 frames. The held-out run analyses 300 frames anyway. For each one also compute `(S_b, S_f)` and assert:
   - a reported break implies `S_b > T_b`;
   - a reported Fork implies `S_f > T_f`, or a found break;
   - `S_b ≤ T_b` and `S_f ≤ T_f` imply no break and no Fork.

   This catches B5's drift and N1's direction with real data, for about 0.1-0.3 s per frame.
6. **The denominator.** A calibration frame with no reported region has S = 0 and counts as fake-free. At depth 0.5 this should not happen. Assert `striped` on every calibration and held-out frame, or count the frames that are not and report the rate over striped frames only.
7. **If the floors bind, the held-out test has no power as written.** With a bound of 29 or 33 and an expected count near 0, it cannot fail on a tenfold regression. This is the OQ7 point: report the measured count and its interval.
8. **Spikes.** 30 events per frame is ADR 0002's assumption, confirmed by the owner for the stripe score. Its effect on Fork candidates at 400x1600 has not been measured (the 0.000 came from ticket 10's prototype frames). P1 covers it if it reports the `S_f` distribution; it should say so.
