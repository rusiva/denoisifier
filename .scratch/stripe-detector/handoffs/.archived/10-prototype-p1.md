# 10 P1 prototype findings: the PQ5 stop rule fired

PROTOTYPE, throwaway. Do not merge.

- Worktree `/home/rusiva/dev/denoisifier/.claude/worktrees/agent-a893b57897cdc4f7a`, branch `worktree-agent-a893b57897cdc4f7a`, commit **`e3fa432`**, BASE `ca48498`. The code is in `prototypes/p10_forks/`. The frozen ticket-09 break finder is unchanged: the prototype touches only the generator, through a monkeypatch in `common.py`.
- **Status: stopped at PQ5's stop rule (plan section 0 and PQ5).** On explore, the frozen break finder fakes breaks on fork frames that contain no true break. It also loses true breaks with a fork 1.5-8 P away. As the brief says, I did not tune, freeze or validate.
- **Frozen config: none.** Every number below comes from one explore configuration. It is not a frozen config. The configuration: finder candidate A in lattice form (`finder.py`), loop half-size R = 2 P, `min_mag` 0.5, break band 2 σn (explain away, then step across), no E threshold, and the search domain = the region closed by a 3 P disc, holes filled, other regions removed (`forks.py`).
- Plan cells marked "P1" (`FORK_EXACT_POSITION_TOL_PERIODS`, `FORK_NEAR_BREAK_PERIODS`, `FORK_PAIR_SEPARATION_PERIODS`, `FORK_PAIR_MIN_PERIOD`, every `_FORK_*` constant): **not filled.** They wait on the escalation. The explore numbers below are what exists.

## Seed ranges looked at

- Explore stage 1 (`harness.py explore`): **111_000-111_199**. Every set uses `base + k`, so only the first 200 of the 600 explore seeds were used. Sets reuse seeds and differ by frame kind. 1566 frames, 0 errors.
- Noise-free checks (`nf.py`): 111_000-111_115 (phase0 only). Quick scripts: 111_000-111_019.
- **Validation 111_600-111_999: untouched** (not generated, not looked at).
- The break-only negative set uses the 09 frame kinds on prototype seeds, not the 09 test seeds.

## PQ5 stop rule (the reason for stopping)

**Rule 1 fired: breaks reported on fork frames that have no true break.** Fork-free twins on the same seeds and geometry: 0/200 single, 0/40 full. Script: `stop_rule.py`.

| Fork set | Frames with a reported break | Where the line lies |
|---|---|---|
| pair, opposite directions, 3 / 4 / 6 / 8 P | 11/15, 4/15, 3/15, 9/15 (27/60) | through both forks (0.0-0.5 P from each): the break finder reads the fork-pair dipole as a break line joining them; \|jump\| 0.96-2.8 rad |
| pair, same direction | 2/100 (seed 111016, P 16, at 3 and 4 P) | 1.2 P / 0.4 P from one fork |
| edge, 1 / 2 / 3 P inside the 0.5 contour | 2/30, 12/30, 11/30 | 0.2-1.5 P from the fork: the half winding reads as a break from the fork to the edge |
| single (fork within 1 P of the centre) | 1/200 (111129, P 14, jump -0.87, line 0.4 P from the fork) | that frame's IoU falls to 0.534 |
| weak (depth 0.2) | 1/100 (111021, two breaks) | |
| full, binned | 0/40, 0/40 | |

**Rule 2: a true break is lost with a fork near it** (review P1). Near-break set: 60 frames per distance. Their fork-free break-only twins: break matched 60/60, first line accepted 60/60.

| Distance (P) | Break matched | Lost vs twin | First-line rule that lost it | Fork matched | AC 3 (fork + break + one each + same region) |
|---|---|---|---|---|---|
| 1.5 | 0 | 60 | spread 44, accepted-then-lost 16 | 20 | 0 |
| 2 | 1 | 59 | spread 41, accepted 16, E+jump 2 | 24 | 0 |
| 3 | 5 | 55 | spread 44, accepted 10, E+jump 1 | 36 | 4 |
| 4 | 30 | 30 | spread 25, accepted 5 | 25 | 7 |
| 5 | 43 | 17 | spread 14, accepted 3 | 24 | 10 |
| 6 | 52 | 8 | spread 4, accepted 4 | 18 | 11 |
| 8 | 56 | 4 | spread 1, accepted 3 | 14 | 10 |

- The spread rule (`_BREAK_JUMP_SPREAD_RAD`, π/4 over 3 pieces) is the main cause at every distance.
- "Accepted" means the first coarse line passed its rules but the break still did not match: the line was refined or placed elsewhere.
- No distance in {1.5 … 8} P reaches even 20 % AC 3 success. "Near" in AC 3 has no workable value with the frozen break finder.

## Answers per question (explore, R 2 P, no E threshold)

- **PQ1 (finder).** Candidate A (lattice residues + square-loop winding, centroid, E = winding-disc area / (2R)²) works where no break or edge interferes:
  - single: 199/200 matched, 0 wrong direction, 0 extras, error max 0.53 P (p95 0.32), E min 0.313;
  - full: 40/40, max 0.42 P, E min 0.333;
  - binned: 40/40, max 0.35 P;
  - noise-free: 96/96, max 0.172 P (so `FORK_EXACT_POSITION_TOL_PERIODS` would be about 0.25).
  - Not frozen.
- **PQ2 (break handling).** Explain away + step the band: **0 fakes on every break-only and fork-free set**:
  - b_ac2 0/60, b_ac3 0/24, b_full 0/16, b_pair 0/10, b_two (crossed, bridged) 0/10, b_compat 0/10, b_binned 0/8, b_refusal 0/2;
  - single_free 0/200, full_free 0/40, near_free 0/60, free_two 0/20, Stripe-free 0/20, 30 spikes 0/20, binned_free 0/16;
  - largest fake candidate E 0.000 on all of them.
  - The band-exclusion variant was not tried (stopped).
- **PQ3 (near-break distance).** No distance works (table above): the break finder loses the break or fakes extra breaks. Blocked by PQ5.
- **PQ4 / review P2 (BASE effects).**
  - Striped: single 200/200, full 40/40, near 420/420, pair 160/160, edge 90/90, binned 40/40; weak 69/100.
  - One region: single 200/200, full 40/40 (twins 38/40), near 413/420.
  - **The fork's own pixel is in a reported region 0/200 single and 0/40 full** (and 0/40 binned, 66/320 pair, 8/90 edge, 82/420 near). BASE carves a notch or slot at every fork. AC 4's "nearest frame pixel lies in a reported region" fails on BASE every time.
  - Period within tolerance 200/200 (max 2.9 %).
  - **Angle within 1° 171/200** (max 1.97°; twins 200/200, max 0.23°). So a fork moves BASE's Angle: the AC 4 measurements test cannot be written as planned. It is a ticket-17 item.
  - IoU ≥ 0.8 199/200 (min 0.534 on 111129, the fake-break frame; twins min 0.871).
- **PQ5 pairs.**
  - Both forks matched, no extras, same direction: 3 P 24/25, 4 P 24/25, 6 P 25/25, 8 P 12/25.
  - Opposite directions: 3 P 3/15, 4 P 11/15, 6 P 12/15, 8 P 7/15.
  - At 8 P the forks sit 4 P from the centre, near the region edge for large P (see PQ6).
  - Opposite pairs also fake breaks (rule 1), which then corrupt the fork search.
  - Not finalised.
- **PQ6 (edge).** Found at 1 P 0/30, 2 P 0/30, 3 P 16/30, inside the 0.5 contour. The limit is more than 3 P. Edge frames also fake breaks (rule 1).
- **PQ7 (binned, 2x1 / 1x2, P 8 / 12).** 40/40 matched, error max 0.35 P in sensor geometry, E min 0.387, 0 fakes on 16 binned fork-free frames.
- **PQ8 (cost).** Not timed single-process: stopped, and the machine was loaded (load average 15-18 from other work). Contended parallel finder + domain: mean 0.13 s per frame, max 1.79 s. `timing.py` is ready.
- **Weak (info).** Depth 0.2: 65/100.
- **Review P3.** Done: the break-only set runs the negative test's frame kinds (AC 2, AC 3, full, parallel pair, crossed / two-region bridged, compatible pair, binned, refusal). 0 fake forks on all of them.

## For the orchestrator

1. **Escalate PQ5.** Forks make the frozen break finder report false breaks:
   - opposite pairs: a line through both;
   - forks near an edge;
   - rarely a single fork.

   It also loses true breaks with a fork within about 8 P, mostly through the spread rule. Fixing either re-opens 09's explore and validation. Alternatively, the ticket could accept these as stated limits (AC 3 "near" undefined, the fork-pair/edge fake break as a known BASE break-finder limit sent to ticket 17). Either way it is a ruling, not a prototype choice.
2. **AC 4.** The fork pixel is never in a reported region under BASE, and the Angle error exceeds 1° on 29/200. AC 4's pixel clause needs a new reading (e.g. in the region's closed domain), and the measurements test is not writable. Both go to ticket 17.
3. If work continues: freeze candidate A after an E threshold (true E min 0.31 on single/full/binned against fake E 0.000 on fork-free and break-only frames), then run validation once.
