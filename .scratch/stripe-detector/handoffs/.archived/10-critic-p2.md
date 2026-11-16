# 10 critic: the fired P2 pass bar (adversarial second opinion)

Read-only review. BASE `ca48498`, prototype worktree commit `0264a24`. No repo file edited except this one. No seed generated; everything below is read from `10-prototype-p1.md`, `10-prototype-p2.md` and `prototypes/p10_forks/p2_out/` (`eval_B.txt`, `fakes_B.txt`, `pre_E_A.txt`). All numbers are explore numbers, not validated.

## Verdict

**Option D, with five conditions. The orchestrator can rule it; the owner is not needed now.** The bar fired and must be recorded as fired, not as met. Accepting the limits is honest only because every frame that fired it is BASE's own output, and only if the validation bars are written down before the validation run.

## 1. Stated limits: honest or moved goalposts?

**It is a re-ruling of a bar, so it has to be recorded as one. It is not a quiet weakening, for four reasons.**

- **Every frame that fired the bar is bit-identical to BASE.** `fakes_B.txt` lists 19 single and pair frames with a fake break. The gate fired on none of them (`gate fired False` on all 19). K1 shows a gate-silent report equals an unpatched `analyse`. So these 19 fake breaks are what `main` reports today on the same frames. Ticket 10 does not create them; its generator is the first thing that can show them.
- **P2 is equal to or better than BASE in every cell that fired.**

  | Set | BASE (P1) | P2 (run B) |
  |---|---|---|
  | single | 1/200 (111129) | 1/200 (same frame) |
  | opposite pairs 3 / 4 / 6 / 8 P | 11, 4, 3, 9 of 15 (27/60) | 9, 0, 1, 8 of 15 (18/60) |
  | same-direction pairs | 2/100 | 0/100 |
  | edge 1 / 2 / 3 P | 2, 12, 11 of 30 | 2, 12, 9 of 30 |
  | weak (info only) | 1/100 (111021) | 1/100 (111059, added by the correction) |
  | full, binned | 0/40, 0/40 | 0/40, 0/40 |

  `pairbig` has no BASE number: the set is new in P2.
- **No ticket AC mentions fake breaks.** The spec's fake-defect rate (story 22, spec.md:140) is for defect-free striped frames, and ticket 11 owns it. A fork frame is not defect-free. The bar was my addition in `10-critic-pq5.md`, not the ticket's and not the owner's.
- **CLAUDE.md's weakening list does not name it.** No test, tolerance, expected value, protected number, selection or gate config changes. The rule's spirit still applies: the reason goes into the ticket's Comments before the next run, in the same form as an approval.

**What stays uncomfortable, and must not be smoothed over:**

- **My earlier verdict rejected "ship with limits"** because a report drew a break through 27/60 opposite pairs. It is now 18/60 on 09-size regions and 0/60 on the large region. That is better, not gone. The earlier reason for rejecting it (AC 3 at 11/60 at best) no longer holds: AC 3 is 60/60 at 4 P.
- **The three limits are one number.** Pair separation 4 P, edge 4 P and near 4 P all equal 2R, the loop's full width at R = 2 P. P1 tried R = 1.5 P once, on the single set only (45/45 found, E min 0.19). The limits are the finder's footprint at one untuned setting, not a property of forks.
- **"Forks under 4 P apart" is not the measured fact.** A 3 P opposite pair fakes a break on 9/15 frames in a 5 P by 6.6 P region and on 0/15 in an 11 P region, with the forks 4.3-6.9 P from the edge in the first. The cause is not diagnosed. State what was measured, with the region sizes.
- **"About 4 P from a region edge" covers most of a 09-size region.** `REGION_SEMI_AXES_PERIODS` is (5.0, 6.6). Only a core of about 1 P by 2.6 P half-widths is 4 P from the edge. The single set passes because its fork is within 1 P of the centre. In a region of the size every other ticket tests on, forks are found only near the centre.
- **The edge limit grew.** My note said "about 3 P". At 3 P the fork was found 16/30 with no E threshold (P1) and is found 2/30 at E_final 0.3. The threshold bought 0 extra forks and cost the 3 P edge cell. Record the trade.

### Conditions on D

1. **Record the bar as fired.** In `10-orchestrator.md` and the ticket's Comments: "P2 pass bar 'zero fake breaks on single and pair frames' fired on explore (single 1/200, pair 18/160). Ruled as stated limits because all 19 frames are gate-silent and identical to BASE, and P2 is equal or better than BASE in every cell." Do not write "met".
2. **Declare the validation bars before the run, in the freeze commit.** No second re-ruling: a miss on any of these goes to the owner with the question in section 3.
   - Identity: the gate fires on 0 fork-free and break-only frames, and every gate-silent report equals BASE.
   - AC 3 on `nearbig` at 4 P: at least 90 % (09's bar), 0 extra forks.
   - AC 2 on single, full and binned: at least 90 % per cell, 0 wrong directions, 0 extra forks on every set.
   - `pairbig` and `pair` at 4 P: both forks matched on at least 90 %.
   - Fake breaks inside the served geometry (single, full, binned, `pairbig` at 4 P and more, `pair` at 4 P): at most 1 frame in 20 per set, and every one on a gate-silent frame. A fake break on a frame where the gate fired counts as the ordering's own harm: 0 allowed on these sets.
   - Limit cells (pair 3 P, pair 6 and 8 P, edge, weak): no bar. Run them also with the gate off (`enabled=False`) on the same validation frames and report P2 beside BASE. P2 worse than BASE in total is a finding for the owner.
3. **Word the limits as measured**, in the docstring and Comments: the region sizes, the 3 P pair result in both regions, the edge trade, the two harms (111059, 111050) with their frames.
4. **Send the fake breaks somewhere.** A new needs-triage ticket for the break finder on fork frames (pair dipoles in small regions, forks near an edge, the 1.5-3 P hole next to a break). A note in ticket 11: its held-out frames have no forks, so its rate will not see these. A note in ticket 12: the PNG will draw these breaks. 111129 goes to ticket 17.
5. **Tell the owner at close**, with the table above and the question in section 3.

**Optional, the orchestrator's call, not a condition:** one explore run at R = 1.5 P on the fork sets plus the identity sets, on seeds already looked at, before freezing. Declare first: freeze R = 1.5 P only if identity holds, extras stay 0 and AC 3 reaches 90 % at 3 P; otherwise freeze R = 2 P as is. It costs about 25 min and tests whether the 4 P limits are real. Skipping it is defensible; then name R as untuned in the follow-up ticket.

## 2. Is "near" = 4 P a fair reading of AC 3?

**Fair, not a weakening, with two things stated openly.**

- **The plan allowed it in advance.** Plan 5.3 defines "near" as the smallest distance in {1.5, 2, 3, 4} P that holds on explore and validation, with closer stated as undefined. 4 P is in the list. PQ3 expected 2-3 P; an expectation is not a bar. My earlier note accepted "3 P or more".
- **The test is not trivial at 4 P.** BASE at 4 P matches the break on 30/60 and passes AC 3 on 7/60. The ordering takes it to 60/60. So the 4 P test exercises exactly what the ticket delivers. 3 P is 50/60 (83 %), under 09's 90 % bar, so 3 P cannot be claimed.
- **State 1: the AC 3 test needs the large region.** The plan's AC 3 test (line 185) uses 09-size region frames. There a fork 4 P from a centre line is 1-2.6 P from the edge, and run A passes only 25/60. The test must use the `nearbig` geometry (semi-axes max(11 P, 60 px)). That is a plan edit, and Comments must say AC 3 is shown only in regions that large.
- **State 2: closer than 4 P the fork and the break are both usually lost.** At 1.5 and 2 P: fork 5/60 and 10/60, no break on 44/60 and 36/60. The docstring says "undefined closer than 4 P"; Comments carry the rates.

## 3. Owner or orchestrator?

**Orchestrator.** None of the three owner triggers applies.

- **Not an AC change.** No AC text changes. The readings (near, pair separation, edge) were delegated to the prototype by the plan (PQ3, PQ5, PQ6).
- **Not hard to revert.** One internal ordering in `analyse`; fork-free frames are bit-identical to BASE; new lockfile lines only; scores cannot move.
- **Not a choice between equal options.** A (split) throws away a working AC 3 at 4 P. B (re-open 09's finder) un-validates 09 to fix frames 09 never claimed. C (drop the break check) is weaker than what D already passes. D dominates.
- **The outside-knowledge question does not block.** How common close opposite pairs, forks near an edge and small regions are in real frames sets how much the limits matter and the follow-up ticket's priority. It does not change what ticket 10 should land: D is better than or equal to BASE on every frame kind measured, and any fix builds on it. Record it and ask at close.

**The question for the owner at close (and at once if a declared validation bar fails):**

> Ticket 10 finds forks that are at least 4 Periods from the region edge, from each other and from a phase break. Inside that, AC 3 holds (explore 60/60) and no fake break is added. Outside it, the ticket-09 break finder still draws a fake break on some fork frames, as it does on `main` today: 18/60 opposite pairs in a 5 by 6.6 Period region (27/60 on `main`), 23/90 forks within 3 Periods of an edge.
> In your real frames, how many Periods across is a Striped Region, and do forks sit in close opposite pairs or near the region's edge?
> - A. Rare, or regions are large: keep the limits; the follow-up ticket stays low priority. (Recommended unless you know otherwise.)
> - B. Common: raise the follow-up ticket (smaller fork loop, or a break-finder rule for fork dipoles, with new seeds and 09's criteria re-proved) ahead of ticket 11.
> - C. Regions are usually under about 10 Periods across: the fork finder as built serves little of a real frame; re-plan it before ticket 11.

## Path

1. Orchestrator records the ruling and the validation bars (conditions 1 and 2) in `10-orchestrator.md`.
2. Optional R = 1.5 P explore run, declared first.
3. Freeze the `P2()` defaults, commit, run validation once, with the gate-off twin run on the limit cells.
4. All bars pass: write the plan edits (section-0 identity wording, AC 3 on the large region, AC 4's closed-domain reading), then implement. Any bar fails: owner question above, plus split (A in `10-critic-pq5.md`) as the fallback.
5. At close: Comments, follow-up ticket, notes to tickets 11, 12 and 17, the owner question.
