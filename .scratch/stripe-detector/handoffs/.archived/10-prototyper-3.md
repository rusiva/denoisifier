# 10 prototyper handoff (P2 round): paused at a clean point

PROTOTYPE work, throwaway. The full findings are in `/home/rusiva/dev/denoisifier/.scratch/stripe-detector/handoffs/10-prototype-p2.md`. This file is the pause note.

- **Worktree.** `/home/rusiva/dev/denoisifier/.claude/worktrees/agent-a893b57897cdc4f7a`, branch `worktree-agent-a893b57897cdc4f7a`.
- **Commit `0264a24`.** All P2 work is committed (P2 code first committed at `1e643f5`). BASE is `ca48498`.
- **Validation seeds 111_600-111_999 were not touched**: not generated, not looked at.

## Done

- **Built the fork-first ordering** in `prototypes/p10_forks/p2.py`:
  1. pre-break fork search, no breaks explained;
  2. the field corrected for found forks, with sign −1 (verified noise-free);
  3. the frozen 09 pass run unchanged on that field;
  4. post-break fork search with the found breaks explained away;
  5. an optional round 2, which never triggered.
- **Measured every kill criterion on explore.** Run A used E_pre 0.3 on every set, 2134 frames. Run B used E_pre 0.2 on the fork sets, 1010 frames.
- **Timed PQ8** single-process.
- **Answered the plan's P1 cells, PQ3, PQ6, PQ7, PQ8 and AC 4.**
- **Findings written** to `10-prototype-p2.md`.

## Kill-criteria results (explore)

- **K1, identity: holds.**
  - The gate fired on 0 of 624 fork-free, break-only and 09-test-seed frames. No pre-break candidate at any E.
  - Reports are bit-identical to an unpatched BASE `analyse` on all 624 frames.
  - They are also identical on every gate-silent fork frame: 619/619 in run A, 272/272 in run B.
- **Close-in hole: not closed.** Round 2 never triggers. AC 3 on `nearbig` (run B):

  | Distance | AC 3 |
  |---|---|
  | 1.5 P | 5/60 |
  | 2 P | 10/60 |
  | 3 P | 50/60 |
  | 4 P | **60/60** |
  | 6 P | 58/60 |

  This pins "near" at 4 P.
- **Geometry: rebuilt.** `nearbig` and `pairbig` use a round region with semi-axes max(11 P, 60) px, so every fork is at least 4.5 P from the edge.
- **Residual: holds at 4 P** (break matched 60/60). Two cases where the correction itself does harm:
  - nearbig 6 P 111050: the line was pushed to 3.16 px from the truth against a tolerance of 3.0;
  - weak 111059: the correction added a fake break that BASE did not report.
- **Pass bar "zero fake breaks on single and pair frames": FIRES.**
  - single: 1/200 (111129, where BASE split the region; the gate cannot see the fork);
  - 09-size pairs: 18/160. 9/15 opposite 3 P pairs, 4.3-6.9 P from the edge, unresolved by the finder. The other 9 at 6 P and 8 P have forks 2.2-3.6 P from the edge;
  - pairbig: 0/160.

  So I stopped before freezing and validation.

## In flight

None. Every background run has finished; nothing needs resuming. If a run is needed again, rerun it from the worktree's `prototypes/p10_forks`:

| Run | What it computes | Output | Command |
|---|---|---|---|
| A | every set, E_pre 0.3 | `/tmp/claude-1000/-home-rusiva-dev-denoisifier/a5c31385-01e3-4bc0-bce8-a97c1d5a1f5a/scratchpad/p2/explore_A.pkl`, `.log`; evaluation copied to `prototypes/p10_forks/p2_out/eval_A.txt` | `uv run --locked python p2_harness.py explore <out>.pkl --cfg e_pre=0.3 e_final=0.3 rounds=1 --workers 14` (about 64 min) |
| B | fork sets, E_pre 0.2 | `.../scratchpad/p2/explore_B.pkl`; evaluation in `p2_out/eval_B.txt`, `p2_out/fakes_B.txt` | same with `--only single,nearbig,pair,pairbig,edge,weak --cfg e_pre=0.2 e_final=0.3 rounds=1` (about 21 min) |
| Timing | PQ8 | `p2_out/timing.txt` | `uv run --locked python -c "import p2; p2.CFG.e_pre=0.2; import p2_timing; p2_timing.main()"` |

- **No resume.** The harness does not resume from partial output; a rerun starts over.
- **Pickles may be lost.** The `.pkl` files are in the scratchpad and can be cleared; the `p2_out/` text outputs are committed.

## Next step (orchestrator)

**Rule on the fired pass bar.** Two choices:
- **Accept as stated limits:**
  - forks less than 4 P apart;
  - forks within about 4 P of a region edge;
  - forks on a BASE-split region;
  - the ordering's own cost: one added fake break on a weak frame, and one line pushed just out of tolerance.

  Then freeze the explore candidate and run validation once.
- **Take the owner question in 10-critic-pq5.md**: A split, B re-open, C reword.

**Explore candidate**, ready to freeze: finder A, R 2.0 P, magnitude floor 0.5, break band 2.0 σn, closed domain 3.0 P, E_pre 0.2, E_final 0.3, 1 round. The validation command is in `10-prototype-p2.md`. Set the `P2()` defaults in `p2.py` to these values and commit before running it.

## Seed ranges looked at

- **Explore:**
  - 111_000-111_199: P1's sets;
  - 111_000-111_059: nearbig;
  - 111_000-111_039: pairbig.

  111_200-111_599 are unused.
- **09 test seeds 10-19:** identity check only.
- **Timing:** TIMING_SEED and 111_000.
- **Validation 111_600-111_999: untouched.**

## Open questions

- Is the literal "zero fake breaks on single and pair frames" met by these stated limits? This is the orchestrator's call, or the owner's.
- How common are opposite fork pairs closer than 4 P, and forks near a region edge, in real frames? This needs outside knowledge (owner).
