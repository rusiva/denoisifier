# 10 P2 prototype findings: fork-first ordering. Frozen and validated once; bars B3 and B4 fail

PROTOTYPE, throwaway. Do not merge.

## Final step (orchestrator ruling: option D in 10-critic-p2.md, with its R = 1.5 P run)

- **Freeze commit `3922e33`.** It sets the `P2()` defaults and declares the bars in `prototypes/p10_forks/p2_bars.py`, before any validation frame was generated. Results are committed at **`9872cb4`**. BASE is still `ca48498`.
- **Outcome.** Validation ran once. **B3 and B4 fail; B1, B2 and B5 pass.** I stopped there, as the brief said: no re-ruling and no PQ8 timing (see "PQ8" below). This goes to the owner with the question in 10-critic-p2.md section 3.

### Step 1: R = 1.5 P explore run, R decision

- **Rule, declared before the run** (10-critic-p2.md): freeze R = 1.5 P only if identity holds, extras stay 0 and AC 3 reaches 90 % at 3 P. Otherwise R = 2 P.
- **Run.** E_pre 0.2, E_final 0.3, 1 round, 1714 frames: every explore set except the 09-size `near`, plus 09's test frames.
  - Seeds: 111_000-111_199 and 09 test seeds 10-19, all looked at before. No new seed.
  - Output: `p2_out/eval_R15.txt`. Run time 46 min at 14 workers.
- **Results at R = 1.5 P:**
  - Identity holds: the gate fired on 0/624, and 624/624 reports are identical to BASE.
  - **Extras: 1** (edge 3 P).
  - **AC 3 at 3 P: 43/60 (72 %).**
  - It is also worse than R = 2 P (run B) almost everywhere:

    | Cell | R = 1.5 P | R = 2 P |
    |---|---|---|
    | AC 3, 4 P | 44/60 | 60/60 |
    | single ok | 173/200 | 199/200 |
    | pairbig 4 P | 21/40 | 40/40 |
    | full P 3 | 6/10 | 10/10 |
    | binned (2x1, P 8) | 4/10 | 10/10 |
- **Decision: R = 2.0 P.** R = 1.5 P failed two of the three conditions. The 4 P limits are not an artefact of R = 2 P that a smaller loop removes.

### Step 2: frozen config (`P2()` defaults at `3922e33`)

| Parameter | Value |
|---|---|
| finder | A (lattice residues + square-loop winding) |
| R (`loop_periods`) | 2.0 P |
| magnitude floor | 0.5 |
| break band | 2.0 σn |
| closed domain | 3.0 P |
| E_pre (gate) | 0.2 |
| E_final | 0.3 |
| rounds | 1 |
| sign | −1 |

### Step 3: validation, once

- **Seeds 111_600-111_732.** Every set is at 2/3 scale, so this is all of the 111_600-111_999 range that was generated.
  - Main run: 1394 frames, 0 errors, 35 min.
  - Gate-off twin (`enabled=False`) on pair, edge and weak: 235 frames, 0 errors.
- **Outputs:**
  - bars: `p2_out/bars_validate.txt`;
  - full evaluation: `p2_out/eval_validate.txt`;
  - the frames that failed: `p2_out/bars_failures.txt`;
  - log: `p2_out/validate.log`.
- **Command.** `p2_harness.py validate`, then `p2_bars.py validate.pkl validate_twin_off.pkl`.

| Bar | Result | Measured |
|---|---|---|
| B1 identity | **PASS** | The gate fired on 0/384 fork-free and break-only frames. 728/728 gate-silent reports (all sets) are identical to BASE. |
| B2 AC 3, `nearbig` 4 P | **PASS** | 39/40 (97.5 %), 0 extra forks. |
| B3 AC 2, single/full/binned | **FAIL** | AC 2 is 100 % in every cell: single 133/133; full 6/6, 7/7, 7/7, 7/7; binned 6/6, 7/7, 7/7, 7/7. 0 wrong directions. **The clause "0 extra forks on every set" fails with 4 extras, all in limit cells** (listed below). On single, full and binned the extras are 0. |
| B4 pairs at 4 P, both matched ≥ 90 % | **FAIL** | `pairbig` 26/27 (96.3 %). **`pair` 24/27 (88.9 %).** |
| B5 fake breaks, served geometry | **PASS** | single 0/133, full 0/27, binned 0/27, `pairbig` 4/6/8 P 0/81, `pair` 4 P 0/27. 0 on frames where the gate fired. |

**What failed:**

- **B3, the 4 extra forks.** Three of them are the true fork found 1.24-1.43 P away, beyond the 1 P match tolerance, so each counts as a miss plus an extra:
  - near 1.5 P 111605 (P 4, gate fired, E 1.01);
  - edge 3 P 111605 (P 4, gate silent, E 0.35);
  - nearbig 1.5 P 111602 (P 8, gate fired, E 0.99).

  The fourth is a real false fork: nearbig 2 P 111613 (P 12, gate silent, E 0.53), 4.2 P from the true fork, on a frame with 3 reported breaks.
- **How I read B3.** The critic's text was "0 extra forks on every set". `p2_bars.py` declared it as every set run, so B3 is reported as **FAIL**. Under the narrower reading (only the three AC 2 sets) it would pass. I did not re-rule; the orchestrator can choose the reading.
- **B4, the 3 `pair` 4 P misses.** In each, one fork of the pair is not reported. None has a wrong direction or a fake break, and the gate fired on all three:
  - 111600 (P 3, opposite pair; the same frame is also `pairbig`'s one miss);
  - 111606 (P 16, same direction);
  - 111610 (P 3, same direction).

  Explore had 39/40 here, so the explore estimate did not hold. 24/27 is one frame under the bar.

**Gate-off twin, limit cells (no bar).** "Fake" counts frames reporting a break. "Matched" counts forks.

| Cell | Frames | P2 fake | BASE fake | P2 matched | BASE post-search matched | Gate fired |
|---|---|---|---|---|---|---|
| pair 3 P | 27 | 7 | 10 | 24/54 | 23 | 15 |
| pair 6 P | 27 | 0 | 3 | 45/54 | 42 | 27 |
| pair 8 P | 27 | 8 | 8 | 24/54 | 24 | 15 |
| edge 1 P | 20 | 0 | 0 | 0/20 | 0 | 0 |
| edge 2 P | 20 | 11 | 11 | 0/20 | 0 | 0 |
| edge 3 P | 20 | 5 | 5 | 6/20 | 6 | 9 |
| weak | 67 | 0 | 1 | 44/67 | 43 | 46 |
| **total** | | **31** | **38** | | | |

P2 is not worse than BASE in total: 31 fake-break frames against 38. In no cell is P2 worse.

**Other validation numbers (info):**

- **AC 3, `nearbig`:** 1.5 P 7/40, 2 P 8/40, **3 P 38/40 (95 %)**, 4 P 39/40, 6 P 38/40. 3 P passed 90 % on validation, but it was 50/60 on explore, so "near" stays 4 P as declared.
- **AC 4:**
  - striped on every fork set except weak (48/67);
  - each matched fork's region's closed domain holds the true point: single 133/133, full 27/27, nearbig 130/130, pairbig 174/174, pair 144/144, binned 27/27.
- **Measurements:**
  - single: Period 133/133, Angle within 1° 116/133 (max 1.68°), IoU ≥ 0.8 133/133;
  - full: 27/27 on all three.

### Limits, worded as measured (condition 3)

- **Region size.**
  - `nearbig` and `pairbig` use a round region with semi-axes max(11 P, 60 px).
  - 09-size regions (`REGION_SEMI_AXES_PERIODS` 5.0 by 6.6) leave only about a 1 P by 2.6 P core that is 4 P from the edge.
- **Near a break.**
  - AC 3 is shown at 4 P in the large region: explore 60/60, validation 39/40.
  - 3 P: explore 50/60, validation 38/40.
  - Closer than that, both the fork and the break are usually lost: 1.5 P 5/60 and 7/40, 2 P 10/60 and 8/40.
  - In 09-size regions (`near`), AC 3 is 9-16/40 at every distance, because of the edge.
- **Opposite pairs 3 P apart.**
  - 09-size region: a fake break on 9/15 opposite pairs (explore) and 7/15 (validation). The gate-off twin on validation has 10/27 frames with a fake break, against P2's 7/27.
  - Large region: 0/15 and 0/15.
  - The forks are 4.3-6.9 P from the edge, so this depends on region size and is not an edge effect.
  - Both forks resolved (explore / validation): 09-size region 18/40 and 11/27; large region 11/40 and 5/27.
- **Near an edge.**
  - Forks found at 1, 2 and 3 P from the 0.5 contour: explore 0, 0 and 2 of 30; validation 0, 0 and 6 of 20.
  - Fake breaks there are BASE's: validation 0, 11 and 5 of 20, the same as the twin.
  - The trade: with no E threshold (P1), the fork was found at 3 P on 16/30. E_final 0.3 bought 0 extra forks and cost that 3 P cell.
- **The ordering's own harms (explore):**
  - weak 111059: the correction added a fake break that BASE did not report;
  - nearbig 6 P 111050: the correction pushed a matched line to 3.16 px against a tolerance of 3.0.

  On validation the ordering added no fake break in any limit cell. In every cell P2's count is no higher than the twin's.
- **BASE-split region:** single 111129 (explore). The gate cannot see the fork. This is ticket 17's kind of error.

### PQ8

- **Not re-timed.** The brief says to stop and report when a bar fails, and step 4 comes after the bars.
- The frozen config equals the timed one (`p2_out/timing.txt`, E_pre 0.2): bench +0.38 s; bench with a fork +0.47 s; P 3 full frame +0.22 s. Load average was 1.7-2.5, so not fully idle.
- To re-time on an idle machine, run from `prototypes/p10_forks`: `uv run --locked python p2_timing.py` (single process, about 2 min).

### Seed ranges looked at, this step

- **R = 1.5 P run:** 111_000-111_199 and 09 test seeds 10-19, all looked at before.
- **Validation:** 111_600-111_732, the first time anything in 111_600-111_999 has been generated. The rest of that range (111_733-111_999) is not generated.

---

*Earlier P2 findings follow; the explore numbers below are unchanged.*

- **Where the code is.** Worktree `/home/rusiva/dev/denoisifier/.claude/worktrees/agent-a893b57897cdc4f7a`, branch `worktree-agent-a893b57897cdc4f7a`, commit **`0264a24`** (P2 code first committed at `1e643f5`). BASE is `ca48498`.
- **What P2 adds.** The code is in `prototypes/p10_forks/`:
  - `p2.py`: the ordering;
  - `p2_harness.py`, `p2_eval.py`: the runs and the scoring;
  - `p2_timing.py`: PQ8;
  - `p2_inspect.py`, `p2_fakes.py`, `p2_dbg*.py`: diagnosis;
  - `p2_out/`: the evaluation outputs.
- **The break finder is untouched.** Its code and every `_BREAK_*` number are unchanged. P2 changes only the field it reads, and only when the gate fires. It does this by wrapping `analysis.break_response` while the frozen `_with_phase_breaks` runs.
- **Status: stopped. The kill criterion "zero fake breaks on single and pair frames" fired on explore** (see "Kill criteria" below).
- **No config was frozen. The validation seeds 111_600-111_999 were not generated or looked at.**
- The config below is the explore candidate. It is ready to freeze if the orchestrator rules the fired criterion a stated limit.

## The ordering (`p2.py`)

1. **Pre-break fork search.** It runs on each reported region's finder response (`break_response` at the region's Period and Angle) with no breaks explained. It uses P1's finder (candidate A, lattice winding) and searches the region closed by a 3 P disc, holes filled, other regions removed. A fork is accepted when E ≥ E_pre.
2. **No pre-break fork accepted:** the frozen pass runs exactly as in BASE (same call, same inputs).
3. **Pre-break fork accepted:** `break_response` returns `z · exp(-i·d·atan2(Y − Yf, X − Xf))` for each accepted fork. This sign was checked noise-free (`p2_sign.py`): with it, the corrected field matches the fork-free twin's phase with resultant length 1.000; with the other sign, 0.09-0.14. The frozen pass then runs unchanged.
4. **Post-break fork search.** It runs on the settled regions and the raw response, with the found breaks explained away (P1's step: step across a band of 2 σn). Forks with E ≥ E_final are reported.
5. **Optional round 2.** If step 4 finds a fork that step 1 did not, steps 3-4 are redone with step 4's forks. This **never triggered (0 frames)**: where step 1 misses a fork next to a break, the break is usually also missing, so step 4 sees the same field.

**Direction convention.** The generator's +1 adds one stripe toward row 0. Noise-free check at P 10: the row 5 P above the fork has 51 maxima and the row below has 50; for −1 it is the reverse. This agrees with the ruled convention.

## Explore candidate config (not frozen)

| Parameter | Value |
|---|---|
| finder | A (lattice residues + square-loop winding; point = centroid; E = winding area / (2R)²) |
| R (loop half-size) | 2.0 P |
| magnitude floor | 0.5 × domain median |
| break band (post search) | 2.0 σn, explain away then step across |
| domain | closing 3.0 P |
| **E_pre (gate)** | **0.2** |
| **E_final (reported)** | **0.3** |
| rounds | 1 |

- **Run A** used E_pre = 0.3: every set, 2134 frames. Output in `p2_out/eval_A.txt`.
- **Run B** used E_pre = 0.2: the fork sets single, nearbig, pair, pairbig, edge and weak, 1010 frames. Output in `p2_out/eval_B.txt`.
- **E_pre = 0.2 is better.** At 3 P from the break, AC 3 passes on 50/60 frames against 32/60 at 0.3. The pair and edge frames also report fewer fake breaks.
- **Lowering E_pre cannot touch K1.** Fork-free and break-only frames have no pre-break candidate at any E: max 0.000, 0 candidates on 624 frames.
- **E_final = 0.3 gives 0 extra forks on every set in both runs.**

## Seed ranges looked at

- **Explore:**
  - 111_000-111_199: P1's sets, re-run through the ordering;
  - 111_000-111_059: `nearbig` and `nearbig_free`;
  - 111_000-111_039: `pairbig`.

  Of the 600 explore seeds, 111_200-111_599 are still unused.
- **09's test seeds 10-19, identity check only:**
  - AC 2 (10-19);
  - AC 3 (10, 11 × 6 line/jump cases);
  - full frames (10-13);
  - break pair (the seeds with P ≥ 5);
  - binned (12, 13 × 2x1 and 1x2);
  - two-region frames (10-19).
- **Timing:** `feasibility.TIMING_SEED` and 111_000.
- **Validation 111_600-111_999: untouched.**

## New geometry (the critic's "Geometry" point)

- **`nearbig`:**
  - a single region in a 512x512 frame, round, semi-axes max(11 P, 60) px;
  - a break through the centre, with the same line, jump and side draws as P1's near set;
  - a fork at {1.5, 2, 3, 4, 6} P from the line, which leaves it at least 4.5 P from the 0.5 contour at every distance;
  - fork-free twins in `nearbig_free`.
- **`pairbig`:** the same region with pairs at {3, 4, 6, 8} P; every fork is at least 7 P from the edge.

## Kill criteria (declared in 10-critic-pq5.md), measured on explore

### K1, identity: holds
- **Gate silent on every fork-free and break-only frame.** The gate fired on 0 of 624 frames. That covers:
  - P1's sets: b_ac2, b_ac3, b_full, b_pair, b_two, b_compat, b_binned, b_refusal, single_free, full_free, near_free, free_two, Stripe-free, 30 spikes, binned_free;
  - `nearbig_free`;
  - 09's test frames: AC 2 10/10, AC 3 12/12, full 4/4, pair 8/8, binned 4/4, two-region 10/10.

  No pre-break candidate was found at any E (max 0.000).
- **Reports bit-identical to BASE.** The test compares `to_dict()` and `labels` against a truly unpatched `analyse`. It held:
  - on all 624 of those frames;
  - on every fork frame where the gate stayed silent: 619/619 in run A and 272/272 in run B.

### Close-in hole: not closed, so "near" is pinned at 4 P
- **Rates (run B, `nearbig`, 60 frames per distance).** "AC 3" means fork matched, break matched, exactly one of each, same region.

  | Distance | AC 3 | Gate fired |
  |---|---|---|
  | 1.5 P | 5 | 14 |
  | 2 P | 10 | 20 |
  | 3 P | 50 | 53 |
  | 4 P | **60** | 60 |
  | 6 P | 58 | 59 |

  The fork-free twins match their break on 60/60.
- **Why the hole stays open.** At 1.5-2 P the pre-break search does not see the fork:
  - 43/60 and 32/60 frames have no candidate at all within 1 P of the fork (run A);
  - the break is then lost as in BASE ("no break" on 44/60 and 36/60).

  Round 2 cannot help, because nothing new is found after the break pass.

### Residual: holds at the pinned distance, with one regression at 6 P
- **At 4 P** the break is matched on 60/60 after the correction. The spread rule no longer rejects it.
- **At 6 P, one frame regresses:** nearbig 111050, P 3. The correction moved the line to 3.16 px from the truth against a tolerance of 3.00; BASE matched it.
- **The weak set (depth 0.2) has one more:** 111059. The gate fired correctly: fork E 0.49, 0.23 P off. Then the corrected field made the frozen pass report a break 4.3 P from the fork, which **BASE did not report**. This is the only fake break the ordering *adds*. The weak set is info only, with no claim.

### Pass bar "zero fake breaks on single and pair frames": FIRES
Run B; run A gives similar numbers. Details in `p2_out/fakes_B.txt`.

| Set | Frames with a reported break | Gate fired on them | Fork distance to the truth region's edge |
|---|---|---|---|
| single | **1/200** (111129, P 14) | no | 4.3 P |
| pair 3 P (09-size region) | **9/40** (9/15 opposite) | no | 4.3-6.9 P |
| pair 4 P | 0/40 | | |
| pair 6 P | 1/40 | no | 3.6 P |
| pair 8 P | **8/40** | no | 2.2-3.1 P |
| pairbig 3 / 4 / 6 / 8 P | 0/40 each | | ≥ 7 P |
| full, binned | 0/40, 0/40 | | |
| edge 1 / 2 / 3 P | 2/30, 12/30, 9/30 | | (stated limit) |

Diagnosis of each case:
- **single 111129 is BASE's region split, as in P1.**
  - Before the pass, BASE reports only half the true region: bbox cols 233-345 against the truth's ~163-348, IoU 0.534.
  - The fork lies 7.6 px (0.5 P) outside that half region, so the closed domain cannot enclose it and the gate cannot fire.
  - The fake break runs 0.4 P from the fork.
  - This is a BASE region-growth error (ticket 17 kind). The ordering cannot reach it.
- **Opposite pairs 3 P apart in a 09-size region are not an edge effect.** The forks are 4.3-6.9 P from the edge.
  - The finder does not resolve 3 P pairs: matched 24/80 in pairbig and 38/80 in pair (R = 2 P), so the gate does not fire.
  - BASE then reads the dipole as a break (|jump| 0.86-1.24).
  - In the large region the same 3 P pairs fake nothing (0/40). The fake depends on region size, not only on the pair.
- **Pairs at 6 and 8 P:** the forks are 2.2-3.6 P from the edge, which is the edge limit (PQ6).
- **Inside the geometry the ordering can serve** (forks at least 4 P from a region edge and from each other, BASE region not split), fake breaks are 0 on every set.

  The literal criterion still fires:
  - single 1/200;
  - pair 18/160, of which 9 are 3 P pairs well inside the region.

**Verdict:** a kill criterion fired on explore. I stopped before freezing and validation, as the brief says.

**Ruling needed.** Is "zero fake breaks" met by stating these as limits?
- forks closer than 4 P to each other (`FORK_PAIR_SEPARATION_PERIODS` 4);
- forks within about 4 P of a region edge;
- forks on a BASE-split region.

**Or is it the owner question in 10-critic-pq5.md (A split / B re-open / C reword)?** If the ruling is "limits", the explore candidate above can be frozen as is and validated once (command below). The 111059 case (a fake break added by the correction) and the 111050 case (a matched line pushed out of tolerance) should go into that ruling: they are the ordering's own cost on fork frames.

## The plan's "P1" cells (explore values, not validated)

| Number | Explore value | Basis |
|---|---|---|
| `FORK_EXACT_POSITION_TOL_PERIODS` | 0.25 | P1 noise-free max 0.172 P; the finder did not change in P2 |
| `FORK_NEAR_BREAK_PERIODS` | **4** | nearbig AC 3: 60/60 at 4 P, 50/60 at 3 P (E_pre 0.2) |
| `FORK_PAIR_SEPARATION_PERIODS` | **4** | pairbig 4 P: 40/40 matched, 0 breaks; 09-size pair 4 P: 39/40 matched, 0 breaks. 3 P: 11/40 and 18/40 |
| `FORK_PAIR_MIN_PERIOD` | none needed (3) | pairbig 4 P: 40/40 across every CASES Period 3-20 |
| `_FORK_LOOP_PERIODS` | 2.0 | |
| `_FORK_MIN_MAGNITUDE_FRACTION` | 0.5 | |
| `_FORK_BREAK_BAND_SIGMAS` | 2.0 | |
| `_FORK_DOMAIN_CLOSE_PERIODS` | 3.0 | |
| `_FORK_GATE_EVIDENCE` | 0.2 | |
| `_FORK_MIN_EVIDENCE` | 0.3 | |
| `_FORK_MAX_PER_REGION` | not measured | at most 2 forks per frame in P2 |

## Per question

- **PQ3.** Answered above, on `nearbig`. The near set is rebuilt so the fork stays at least 4.5 P from the region edge at every distance.
  - Pinned at **4 P** (60/60).
  - At 3 P the rate is 50/60 (83 %), under 09's 90 % bar.
  - 1.5-2 P is undefined.
  - For comparison, P1's 09-size `near` set under the ordering (run A) passes AC 3 on 9, 9, 17, 25, 18, 13 and 14 of 60 at 1.5-8 P. Those numbers are confounded by the edge, as the critic said.
- **PQ6 (edge).** Fork found (E_final 0.3) at 1 P 0/30, 2 P 0/30, 3 P 2/30 inside the 0.5 contour. The gate fired 0, 0 and 7/30.
  - With the fork at least 4.5 P from the edge (`nearbig` at 4-6 P from a break) it is found 119/120.
  - Stated limit: **about 4 P from a region edge.**
  - Forks closer than that still fake breaks on 2, 12 and 9 of 30 frames (BASE behaviour; the gate cannot fire). This is a stated limit, a ticket-11 note, and the needs-triage break-finder ticket the critic proposed.
- **PQ7 (binned: 2x1 and 1x2, P 8 and 12).**
  - Matched 40/40, wrong direction 0, extras 0.
  - Error max 0.35 P in sensor geometry; E min 0.387.
  - Gate fired 40/40; 0 breaks reported.
  - Binned fork-free frames and 09's binned break frames: gate silent, identical to BASE.
- **PQ8.** Single process, 5 repeats, median. Load average 1.7-2.5 from other sessions; not fully idle. Output in `p2_out/timing.txt`.

  | Frame | BASE `analyse` | With the ordering | Extra |
  |---|---|---|---|
  | bench (TIMING_SEED, P 8, Angle 0, 400x1600) | 6.39 s | 6.78 s | **+0.38 s** |
  | bench + one fork at the centre (gate fires: second break pass on the corrected field) | 6.47 s | 6.94 s | **+0.47 s** |
  | P 3 full frame | 6.77 s | 7.00 s | +0.22 s |

  - This is over the plan's 0.3 s budget and under its 1 s escalation line, so `make bench` runs at close.
  - The prototype recomputes the response for the fork searches. A shared cache in production removes part of the extra.
- **AC 4 (the measurements the critic proposed).**
  - **Striped on every fork frame:** single 200/200, full 40/40, nearbig 300/300, pairbig 160/160, pair 160/160, edge 90/90, binned 40/40, near 420/420 (weak 69/100, info).
  - **"Fork pixel in a reported region" fails on BASE**, as in P1: single 0/200, full 0/40, nearbig 3/300, pairbig 0/320, binned 0/40.
  - **The critic's reading** is that the reported fork's region is the region whose closed search domain holds the true point. It holds:
    - matched forks: single 199/199, full 40/40, nearbig 184/184, pairbig 264/264, pair 219/219, binned 40/40, weak 63/63;
    - true point inside some closed domain: single 199/200 (not 111129), full 40/40, nearbig 300/300, pairbig 320/320, binned 40/40;
    - edge: 47/90.
  - **Measurements are unchanged from P1.** BASE sets them before the pass:
    - single Period within tolerance 200/200;
    - Angle within 1° 171/200 (max 1.97°; twins 200/200, max 0.23°);
    - IoU ≥ 0.8 199/200 (min 0.534 on 111129);
    - full Period, Angle and IoU 40/40.

    The measurements test stays unwritten; the numbers go to ticket 17.
- **Plan section 0 edit (critic).** "On a frame where no fork is found before the break pass, regions, measurements and breaks equal BASE's" holds on every gate-silent frame measured (see K1).

## If the orchestrator rules "limits": the one validation run

```
cd /home/rusiva/dev/denoisifier/.claude/worktrees/agent-a893b57897cdc4f7a/prototypes/p10_forks
uv run --locked python p2_harness.py validate <OUT>.pkl --cfg e_pre=0.2 e_final=0.3 rounds=1 --workers 14
uv run --locked python p2_eval.py <OUT>.pkl
```

- **What it runs.** Every P1 set and nearbig/pairbig at 2/3 scale on 111_600-111_999. The 09 test-seed frames are skipped in validate.
- **Time.** About 35-45 min at 14 workers on an idle machine.
- **Changes needed first.** Before running, freeze the `P2()` defaults in `p2.py` to the values above and commit them.
