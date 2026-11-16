# 10 critic: the PQ5 stop rule (adversarial second opinion)

Read-only review at BASE `ca48498`; prototype worktree commit `e3fa432`. No repo file edited except this one.

## Verdict

**Take option 3, in a sharper form than the brief states it: find forks first, explain them away, and run the frozen break finder unchanged on the corrected field.** Run it as a second prototype round (P2) with the kill criteria below. **The orchestrator can rule this; the owner is not needed now.** No acceptance criterion changes, no existing protected number changes, no break-finder rule or constant changes, and scores cannot move. The owner is needed only if P2 fails; the question for that case is framed at the end.

## Three things the findings file gets wrong or leaves out

I re-ran the prototype's fork step on its stored explore data (seeds 111_000-111_199, already looked at; no new seed generated, validation untouched). Scripts and outputs: `/tmp/claude-1000/-home-rusiva-dev-denoisifier/a5c31385-01e3-4bc0-bce8-a97c1d5a1f5a/scratchpad/critic/` (`nobreaks.py`, `oracle.py`, `eval_E*.txt`). Same explore configuration (R 2 P, closed domain). These are explore numbers, not validated.

1. **The near-break table is confounded by the region edge from 3 P on.** The near set uses `single_region`, whose semi-axes are 5 P by 6.6 P (`REGION_SEMI_AXES_PERIODS`), with the break through the centre. A fork 4 P from the line is 1-2.6 P from the edge; at 6-8 P it is at or outside the 0.5 contour. PQ6 puts the edge limit above 3 P. So:
   - "no distance in 1.5-8 P works" is not shown: no tested frame has a fork 3 P or more from both the break and the edge;
   - "breaks are lost within about 8 P of a fork" is not shown past 4 P either: the break recovers at 6-8 P because the fork has left the region.
   - Cross-tab at 8 P: break matched 56/60, fork missed 46 of those. That is the edge, not the break.

2. **The fork finder does not need the breaks to stay quiet on break frames.** With found breaks ignored (nothing explained away), the fake count is still 0 on every break-only and fork-free set (b_ac2 0/60, b_ac3 0/24, b_full 0/16, b_pair, b_two, b_compat, b_binned, b_refusal, and all the fork-free sets), largest candidate E 0.000. The magnitude floor already drops loops that cross a π break's dim line. The plan's PQ2 worry did not show up on explore. Single, full and binned are unchanged (199/200, 40/40, 40/40).

3. **What breaks fork finding is a wrong break, not a missing one; with the right break it works close in.**
   - Breaks ignored: opposite and same pairs together 38/40 at 3 P, 40/40 at 4 P, 39/40 at 6 P (P1 with the fake break explained away: opposite 3/15, 11/15, 12/15). The fake dipole break is what ruined the pairs.
   - P1 cross-tab at 3 P: no break reported, fork found 38/44; wrong break reported, fork found 0/11.
   - True break fed to the fork step (oracle): fork matched 54/60 at 1.5 P, 55/57 at 2 P, 49/58 at 3 P (P1: 20, 24, 36). Caveat: six extras with E about 1.0 at 1.5 P that I did not diagnose (possibly my truth-to-`FoundBreak` conversion); one-region frames only.

So the fork finder is sound, and AC 3 fails because the break finder is given a field it was never validated on. That points at correcting the field, not at changing the finder or the AC.

## The options

### 1. Re-open the break finder
- **AC honesty:** could meet AC 3 as written.
- **Cost:** the highest. The spread rule that loses the break is also what keeps fakes at 0 on break-free frames. Any change to a `_BREAK_*` constant is a lockfile edit (a weakening move, approval each), un-validates every P1 v2 number in ticket 09's Comments, needs fresh explore and validation seeds (09's are spent) and re-proves 09's ACs. Ticket 09 refused this twice for smaller reasons (the half-bin bias, the junction-region rule).
- **Revert:** easy in code, but 09's validated state is gone once touched.
- **Verdict:** reject. It changes behaviour on fork-free frames to fix fork frames, when the corrected-field route leaves fork-free frames bit-identical.

### 2. Frozen finder, ship with stated limits
- **AC honesty:** fails. AC 3 at 11/60 at best is not a limit, it is the criterion not met. Dropping the break check is not enough either: fork-only success is 20-36/60 at 1.5-4 P, because wrong breaks get explained away. "Rewrite near to a distance where it holds" has no measured distance (point 1), and 8 P at P 20 is 160 px, which is not "near".
- It also ships a report that draws a phase break through 27/60 opposite fork pairs. Fork frames are this ticket's subject; a false break on them is a wrong statement in the feature being delivered. Ticket 17 owns region growth and the score path; a break-finder fake is not its subject.
- **Verdict:** reject as a quiet weakening. Any rewrite of AC 3 is the owner's.

### 3. Gate on found forks (recommended, sharpened)
The brief's variants (exclude fork neighbourhoods from the fit, reject lines ending at forks) change the finder's rules or its sample set. Do not do that. Instead:

1. Fork search first on each region's response, no breaks explained (point 2 says this is quiet on break frames), with a conservative E.
2. Only where a fork is found: multiply the field by `exp(-i·d·atan2)` about it, the same move the plan already makes for breaks in the other direction.
3. The frozen break pass, code and constants untouched, on that field.
4. Fork search again with the found breaks explained away (the plan's present step); the result fills `Report.forks`.

- **AC honesty:** nothing weakened. The plan's 5.3 reading of AC 3 (fork matched, break matched, one each, same region) stays. `FORK_NEAR_BREAK_PERIODS` is still "the smallest tested distance that holds", which PQ3 already allowed.
- **09's validation:** it covers fork-free frames. Where step 1 finds nothing, the break finder's input and output are bit-identical to BASE. On explore the gate fired on 0 of about 750 fork-free and break-only frames with E margin 0.31 against 0.000. On fork frames 09 never made a claim, so nothing is un-validated; the new claims are validated on 111_600-111_999, which are untouched.
- **Gates:** scores still cannot move (everything is after the threshold; slow-tier, calibration and feasibility frames have `forks=()`). No `make measure`, no re-store. `make check-slow` then `make check`, as already planned. New lockfile lines only.
- **Cost:** one more prototype round; a second break pass on frames with a found fork (09: up to about 1.4 s on break frames); ticket 13's perf frame has forks, so `make bench` at close.
- **Revert:** easy. One internal ordering in `analyse`; no public surface beyond `forks`.
- **Plan edits needed:** section 0's "purely additive, never changes breaks or regions" becomes "on a frame where no fork is found before the break pass, regions, measurements and breaks equal BASE's" (the break pass also bridges, fills and re-measures, so regions can differ on fork frames). The step-6 BASE diff and 5.4's identity test must assert exactly that, and must include 09's break frames.

**Weak points P2 must measure (kill criteria, declared before the run):**
- **Identity.** On every fork-free and break-only explore frame, and on 09's AC 2 / AC 3 test frames, the pre-break fork search finds nothing at the frozen E and the report equals BASE's. One fake here changes a break on a frame 09 validated: that is a stop.
- **The close-in hole.** With breaks ignored, forks 1.5-2 P from a break are found only 22/60 and 33/60, so the gate often will not fire there. Either a second round (breaks, forks, explain forks, breaks again) closes it, or "near" is pinned at 3 P or more. Both are inside PQ3.
- **Geometry.** Re-build the near set so the fork is at least 4 P from the region edge at every distance (a larger region or the full frame). Without this no distance can be judged.
- **Residual.** A fork placed up to 0.5 P off leaves a dipole after the correction; check the spread rule no longer rejects the true break at the pinned distance, and that single-fork and pair frames report no break (P1: 1/200, 27/60).
- **Pass bar:** AC 3 at the pinned distance and zero fake breaks on single and pair frames, on explore and then once on validation, at the rates 09 accepted (09's worst accepted validation cell was 18/20).

**What stays a stated limit under option 3** (no AC covers these; record in Comments, the docstring and the named ticket):
- Forks within about 3 P of a region edge are not found, and the half winding can read as a break (25/90). The gate cannot fire on a fork it cannot find. Note for ticket 11 (fake-break rate) and a new needs-triage ticket for the break finder, not ticket 17.
- BASE carves a notch at the fork pixel and the Angle moves over 1° on 29/200: score-path effects, ticket 17's Comments, as the plan pre-declared.

### 4. Split the ticket
- **AC honesty:** honest bookkeeping, but ticket 10 then closes without AC 3: a change to its acceptance criteria, so the owner's. The fake breaks on fork pairs ship meanwhile, and tickets 11 and 12 build on them.
- **Verdict:** the right fallback if P2 fails; not the first move, since point 3 says AC 3 is probably reachable inside this ticket.

## AC 4 (decidable now, no owner)
The ticket's AC 4 is "a frame with forks is still recognised as striped": 200/200, 40/40, 420/420, 160/160, 90/90, 40/40. It is met. "The fork's nearest frame pixel lies in a reported region" is the plan's own addition and fails 0/200 on BASE; replace it with what the design claims (the reported fork's `region` is the region whose closed search domain holds the true point). The measurements test is not written, by the plan's own rule ("only if P1 shows BASE holds it"); the numbers go to ticket 17. Tell the owner at close.

## Does it need the owner?
**Not now.** Option 3 changes no AC, loosens nothing, moves no score, keeps the break finder's code and numbers, and is one revertible ordering. The stop rule said "escalate"; the orchestrator is the escalation, and a P2 round with declared kill criteria is ordinary practice here (09 ran P1 v2 the same way).

**If P2 fails a kill criterion, ask the owner:**
> Forks make the ticket-09 break finder lose or invent breaks near a fork, and correcting the field for found forks did not fix it (numbers attached).
> A. Split: land generator, fork finder and report now with the limits stated; AC 3 and the fake breaks on fork pairs move to a new ticket blocked by 10. (Recommended: smallest honest step, nothing un-validated.)
> B. Re-open the break finder inside ticket 10: new seeds, re-prove ticket 09's criteria, lockfile changes to `_BREAK_*`.
> C. Keep AC 3 in ticket 10 but reword "near" to a measured distance and drop the break check.

One question for the owner at close either way, not blocking: how common opposite fork pairs and forks within 3 P of a region edge are in real frames. That is outside knowledge and sets how much the stated edge limit matters.
