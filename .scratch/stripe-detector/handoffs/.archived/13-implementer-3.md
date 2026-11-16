# Ticket 13 implementer-3 handoff (paused on the coordinator's request)

- Continues `13-implementer-2.md`. Plan `13-plan.md`. BASE `aae4084`, G1 `ef79e1f`. Branch `main`.
- `S=/tmp/claude-1000/-home-rusiva-dev-denoisifier/c1df1e95-ed74-413e-bb65-92893398d130/scratchpad` (lost on reboot).
- `SPEED_TEST_SEED = 38` is shared by `tests/speed.py` (AC 1 frame) and `tests/stage_timings.py` (typical P 6 frame): orchestrator ruled 2026-11-16 this meets the approval's condition (the seed stays out of calibration, accuracy and held-out sets).

## Gates

- Predecessor's `make test-fast` on `e04b377` (`$S/tf_head.log`) was terminated without `EXIT=`; no leftover processes. Rerun on `2f38fd8`: `$S/tf_head3.log` EXIT=2, a 60 s timeout in `test_analyse.py::test_frames_without_forks_report_none` (inside the bank FFT) while I ran two harness pools beside it (load ~5). My fault: from here `make test-fast` runs alone on an idle machine.

## Slice 4b: deterministic Angle tie-break (pre-stated before data)

- Code: `_match_period`: `angle_index = argmax(energy >= e_max * (1 - _BANK_TIE_REL))`, `_BANK_TIE_REL = 1e-9` (approved, max-relative rule). Test `tests/test_bank_ties.py` (seed-free mirror-symmetric frame; red at G1 code: +5 and +10 at the mirror column; green after).
- Harness `tol` profile `slice4b` vs G1, criteria fixed before running:
  - found identically (counts, labels, warnings);
  - ratio map `array_equal` and Period map `array_equal` (4b changes only the index, never the energies or ratios);
  - Angle map differs only at pixels where G1's top-two stripe energy gap `(e1-e2)/e1 <= _BANK_TIE_REL` at the winning Period (count reported);
  - score rel diff <= 1e-9; report fields rel diff <= 1e-9 (slice 5's bounds, as the ruling's "harness rows").
- Null screen vs G1: its section 3.3 criteria with slice 5's score bound 1e-9.
- Slice 5 vs 4b (ruling): `array_equal` everywhere except pixels whose 4b top-two gap lies in `[eps(1-1e-3), eps(1+1e-3)]`; ratio within 1e-11 at exempt pixels; exempt count reported; every other slice 5 row unchanged. Fail -> drop slices 5 and 6.

### Slice 4b results (harness: `identity.py compare $S/h/g1t.pkl $S/h/s4b.pkl tol slice4b|slice6`)

- G1 rerun with the tie-gap capture (`$S/h/g1t.pkl`) is `exact`-equal to the old `g1.pkl` (58 frames, 0 differences), so the capture changes nothing.
- Pre-stated rows: PASS ratio `array_equal`, Period `array_equal`, Angle changes only at G1 eps-tied px (769 px changed of 1488 G1-tied px; every one on a frame edge row or column, row 0 included), score rel diff 0 on all 58. FAIL "found identically": `breakfork_601052` region area 6893 -> 6892 px (labels differ), Period 8.105326 -> 8.105382 (6.9e-6 rel), Angle +2.4e-4 deg, depth equal, no breaks or Forks. FAIL "report fields rel diff <= 1e-9": max 1.26e-5 (fork_601041 Angle).
- Orchestrator ruling 2026-11-16 (ticket Comments): accept 4b on the O3 decision rows (no threshold flip; fine shifts <= 1 % of each tolerance), conditional on the 4b null screen vs G1 passing unamended, then `make test-fast` green before landing.
- Replacement rows (`tol slice6` profile, 4b vs G1): no stripe Threshold flip PASS; score rel diff 0 (bound 1e-5); |dP/P| 2.35e-8 (5e-4); |dA| 1.26e-5 deg (0.01); binned |dA| 0 (1e-4); |dm| 2.36e-6 (1e-3); ratio at region peak 0; break points 1.04e-8 P (0.005); jump 6.72e-8 rad (5e-4); Fork position 0; Fork direction equal. breakfork_601052 (skipped by the profile because labels differ): dP/P 6.9e-6, dA 2.4e-4 deg, dm 0, all inside the same bounds.
- Null screen 4b vs G1 (`null_screen.py compare null_g1.pkl null_s4b.pkl slice4b`, 160 frames): all 6 rows PASS, max stripe-free shift 0. Condition 1 of the ruling holds.
- Branch `t13-s4b` `e47f134` (worktree `$S/s4b`). `make test-fast` there: `$S/tf_4b.log`, started on an idle machine (load ~3.9 falling, nothing else running), still running at the pause; read its `EXIT=` line and summary.

## Slice 5 vs 4b (final rows, ruling condition 2)

- `t13-slice5-wip` rebased onto `e47f134`: `ba0fbd9`, `5b7a620` (no conflicts; `test_spectrum_filters.py`, `test_bank_ties.py`, `test_protected_numbers.py` 25 passed).
- Harness `compare s4b.pkl s5b.pkl tol slice5` (58 frames): exempt px 0; found identically PASS; ratio rel diff 5.88e-12 (1e-11) PASS; Period and Angle `array_equal` outside the band PASS; score rel diff 2.96e-14 (1e-9) PASS; report fields 1.28e-14 (1e-9) PASS.
- Null screen vs 4b: pending.

## Slice 7 (worktree `$S/s7`, branch `t13-s7` `34e8f8f` off `2f38fd8`, WIP; not on main)

- Code: `_BREAK_COARSE_MAX_SAMPLES` (placeholder 20_000 until the cap is fixed on the explore set; needs approval). `_Samples` gains the grid indices, the row-end samples (`ends`: the whole set's extreme offsets at any angle, so every subset scans on the whole set's bins), `coarse()` (every f-th grid row and column, f = ceil(sqrt(n / cap)), min_side scaled by f^2, same y0/x0/extent) and `band()` (samples within (2 + 1 + 4 + 0.25 + 1) P + extent * sin(3.25 deg) of the coarse line); A4's nonzero/magnitude cache in `weights()`. Fine scan and golden run on the band: bit-identical to the full set whenever the coarse basin matches.
- Test `tests/test_break_finder_cap.py` (seed-free phasor field, 240x960, P 3, two breaks): red (no constant), green; capped (2_000) == uncapped == the pre-slice-7 finder exactly; finder 2.5 s -> 0.44-0.51 s on that field.
- Comparison tool `prototypes/p13/c1/compare.py` (run/compare; per-search coarse line via a `_Samples.scan` hook; truth metrics via `tests/truth_match.py`; optional candidate cap). Fresh-frame jobs (c) fixed before any fresh frame was generated, in `fresh_jobs()`: 136 frames on seeds 603_000-603_099 (full_break 20, fullcap 20 at the P 3/4/5/6 CASES, pair2/3/4 on one shared 20-seed range as harness2 does, bin2x1/bin1x2 18 each).

## Nothing landed on main this session

main is still `2f38fd8`. Uncommitted in the main tree: only the orchestrator's ticket edits and this handoff.

## Next steps

1. Read `$S/tf_4b.log`. If `EXIT=0`, 4b meets ruling condition 3. If it times out again, check `uptime`; rerun alone.
2. Land step 3 and 4b on main: `git merge --ff-only t13-step3` (`f381d80`, already rebased onto `2f38fd8`), then cherry-pick or rebase `e47f134` on top. Run `make test-fast` on main alone (nothing else running), then commit the handoff.
3. Slice 5: run the null screen at slice 5 (`null_screen.py run $S/wip5/src $S/h $S/h/null_s5b.pkl 4`) and compare it against `null_s4b.pkl` with `slice5`. The harness rows already pass (above). If the null screen passes, rebase `t13-slice5-wip` onto main, squash the two WIP commits, run `make test-fast` alone, and commit. Then do the short timing: `uptime` first, then `prototypes/p13/timing.py <src> $S/h ac1_worst`.
4. Slice 6: fix its float32 eps from the float32 rounding size before any harness look, and send it to the orchestrator for approval with the numbers. Then variant A, its O3 table (`tol slice6` vs the slice 5 commit, null screen `slice6` vs G1), and variant B if A fails.
5. Slice 7: rebase `t13-s7` onto its predecessor. Fix the cap on the explore set: run `compare.py run <pred src> explore ref.pkl 8`, then `compare.py run $S/s7/src explore cand_<cap>.pkl 8 <cap>` for cap in 10k, 20k, 40k, 80k. Pick the smallest whose `compare` is ALL PASS, and send it for approval. Then set the constant, run the fresh frames (c) (`fresh`, ref vs cand), the null screen (`slice7`), and the wide ids of the finder and Fork tests.
6. Slice 4 (threads): note that `identity.py`'s tie-gap capture wraps `_match_period` with shared state, so under threads > 1 it must be disabled or made per-call.

## Open questions

- None pending with the orchestrator. Approvals still due: the slice 6 float32 eps, the slice 7 cap (`_BREAK_COARSE_MAX_SAMPLES`), and `_MAX_BANK_THREADS`.
- Slice 7 fresh-frame layout is my reading of the plan's "100 frames, ... the rest bin": 136 frames on 100 seeds (pair tags share a seed range, as harness2 does). The orchestrator should confirm it before the fresh run.

## Branches, worktrees, scratch

- Branches: `t13-step3` (`f381d80`), `t13-s4b` (`e47f134`), `t13-slice5-wip` (`5b7a620`, on 4b), `t13-s7` (`34e8f8f`).
- Worktrees: `$S/s3`, `$S/s4b`, `$S/wip5`, `$S/s7`, `$S/ref_base`, `$S/ref_g1`.
- Pickles in `$S/h`: `g1t.pkl` (G1 with tie gaps), `s4b.pkl`, `s5b.pkl` (slice 5 on 4b), `null_s4b.pkl`, plus the predecessor's pickles. Comparison outputs are in `$S/cmp_4b.txt`, `$S/cmp_4b_o3.txt`, `$S/cmp_5_vs_4b.txt` and `$S/null_cmp_4b.txt`.

## Cleanup items

- `~/.cache/denoisifier/p13-c1/` at ticket close (N8); `.scratch/stripe-detector/p13-c1-ref/`.
- All the branches and worktrees above once landed (`git worktree remove`).
