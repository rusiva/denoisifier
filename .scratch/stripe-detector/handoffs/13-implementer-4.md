# Ticket 13 implementer-4 handoff

- Continues `13-implementer-3.md`. Plan `13-plan.md`. BASE `aae4084`, G1 `ef79e1f`. Branch `main`.
- `S=/tmp/claude-1000/-home-rusiva-dev-denoisifier/c1df1e95-ed74-413e-bb65-92893398d130/scratchpad` (lost on reboot).

## Landed on main

- `f381d80` step 3 (fast-forward from `t13-step3`).
- `ea359a7` slice 4b (cherry-pick of `e47f134`).
- `53a7871` slice 5 (the two WIP commits squashed, rebased onto `ea359a7`).

## Gates

- `make test-fast` on `ea359a7` (alone, idle, load 1.30 at start): EXIT=0, `969 passed, 653 deselected in 808.95s (0:13:28)` (`$S/tf_main4b.log`). Ruling condition 3 for 4b holds.

## Slice 5

- Harness rows vs 4b: all PASS (`13-implementer-3.md`, `$S/cmp_5_vs_4b.txt`).
- Null screen at slice 5 (`null_s5b.pkl`) vs 4b (`$S/null_cmp_5_vs_4b.txt`) and vs G1 (`$S/null_cmp_5b_vs_g1.txt`): all 6 rows PASS both, max stripe-free shift 1.698e-13.
- `make test-fast` (worktree `$S/wip5` at `53a7871`, alone, load 2.11 at start): EXIT=0, `983 passed, 653 deselected in 539.78s (0:08:59)` (`$S/tf_s5.log`). Main fast-forwarded to it.
- Short timing, `prototypes/p13/timing.py <src> $S/h ac1_worst` (single thread, min of 3; `uptime` 0.86 before, 0.93 after):

| tree | bank | breaks | analyse |
|---|---|---|---|
| G1 `ef79e1f` | 4.484 | 1.403 | 6.799 |
| slice 5 `53a7871` | 2.394 | 1.381 | 4.632 |

## Slice 6 (worktree `$S/s6`, branch `t13-s6`, not on main)

- Approvals (ticket Comments, 2026-11-16): `_BANK_TIE_REL` 1e-9 -> 1e-3 (10x the max float32 rounding of a +-theta energy difference over the top energy, 2.69e-5, rounded up to the next decade; `prototypes/p13/f32_rounding.py` on seed-free frames: p99.99 3.6-6.6e-6, max 9.5e-6 to 2.69e-5); new `SINGLE_PRECISION_REL_TOL = 1e-5` (test measured at most 4.5e-7; 2.8e-3 without the mean subtraction).
- Variant A `2adaffd`: `_Spectrum.single(offset)` (complex64 copy, light mean out at DC, put back as offset x kernel(DC) in float64), bank only. Test `tests/test_single_precision_bank.py`.
- Disk: `/tmp` (16 G tmpfs) filled up during the first run. The pickles now live in `~/.cache/denoisifier/p13-h/`, and `$S/h` is a symlink to it. Deleted: `perturbed.pkl`, `s2.pkl`, `s5.pkl`, `null_s5.pkl`, `g1.pkl` (`g1t.pkl` is equal to it). New cleanup item: `~/.cache/denoisifier/p13-h/`.
- Variant A O3 table (`identity.py compare s5b.pkl s6a.pkl tol slice6`, `$S/cmp_6a.txt`): **FAIL** "found identically". 16 of 58 frames, all break/fork/breakfork frames, have counts and warnings equal but labels differ by 1-6 px at the region edge. Every other row PASS: score 3.3e-7, |dP/P| 5.9e-6, |dA| 5.1e-3 deg, binned 1.9e-8, |dm| 4.4e-5, ratio at peak 2.7e-7, break points 3.4e-5 P, jump 1.74e-4 rad, Fork position 0, no threshold flip. Null screen vs G1 (`$S/null_cmp_6a.txt`): **FAIL** "region count and labels equal" on 8 frames (4 striped, 2 full_free, 2 two_free); the other 5 rows PASS (max stripe-free shift 5.4e-7).
- Variant B `6e8361f` (on A): after the merge, each winning (Period, Angle) pair's response and each winning Period's local mean are recomputed through the float64 seam and written at that pair's pixels. Test `test_bank_reports_the_winning_filters_in_double_precision` (exact equality): red, then green.
- Variant B O3 table (`identity.py compare s5b.pkl s6b.pkl tol slice6`, `$S/cmp_6b.txt`): **FAIL** "found identically", on the same 16 frames with the same 1-6 edge px (`$S/diag6.py`). Every other row PASS, with the same maxima as A. Null screen vs G1 (`$S/null_cmp_6b.txt`): **FAIL** "region count and labels equal" on the same 8 frames. B changes the reports (57 of 58 differ in repr from A) but leaves the labels alone. The edge pixels follow the float32 ratio map, which B does not touch.
- **Slice 6 dropped** per plan step 3, with no amendment to any row. Branch `t13-s6` (`6e8361f`) is kept for the record; nothing from it lands. `_BANK_TIE_REL` stays 1e-9 on main. The two approved slice 6 numbers are not used. The loss is about 1.5 s single-thread on the bank.
- Slice 7's predecessor is now the slice 5 commit (`53a7871`, src equal on `c8e02a5`).

## Slice 7 (worktree `$S/s7`, branch `t13-s7`, rebased onto `c8e02a5`: `b029f7f`)

- Fixing the cap on the explore set: ref (`$S/wip5/src` = slice 5) and candidates 10k/20k/40k/80k, 8 workers, `$S/h/c1/`, log `$S/c1_runs.log`. Running.
- Explore-set runs (8 workers, load ~8, `$S/c1_runs.log`) all EXIT=0. Compare outputs `$S/c1_cmp_<cap>.txt`; per-search diagnostics `$S/c1diag.py` and `$S/c1diag2.py`.
- At every cap, 10k/20k/40k/80k: PASS on same frames, found identical, AC 4 identical, labels, |delta line error| (max 0 P exactly) and per-tag max line error (equal).
- **FAIL "same basin"** at every cap. Mismatched frames and searches (of 216 frames and 627 searches): 10k 115/134, 20k 88/103, 40k 54/65, 80k 27/31. For example, full_break/109401 search 2 has reference -33 deg and candidate -81 deg. The reported breaks are bit-identical, so the mismatches sit on searches that were not accepted (not checked search by search). Any cap below a full frame's ~230k samples gives stride f >= 2, so no cap that saves time can pass the row.
- Sent to the orchestrator: per the plan's "any fail drops slice 7", slice 7 is treated as dropped unless it rules otherwise.

## Slice 4 (worktree `$S/s4`, branch `t13-s4` `0e2d0f0` on `c8e02a5`, not on main)

- Code:
  - `_local_stripes.bank_threads()`: explicit, else `DENOISIFIER_THREADS`, else min(`_MAX_BANK_THREADS`, affinity). An invalid env value raises a ValueError that names it.
  - `_matches()`: ordered Period jobs on a ThreadPoolExecutor, one buffer set per slot, merged in ascending Period order.
  - `analysis._analyse(..., threads)` is private; `analyse` is unchanged.
  - `calibration._stripe_free_score` and `_score_file` run at threads=1 in the pool.
  - `feasibility.run_pool` wraps fn as `_on_one_bank_thread`.
  - evaluate_regions and calibrate_regions set DENOISIFIER_THREADS=1 for their workers.
  - `thread_settings()` and `run_info()` record the bank threads.
  - `speed.time_speed_pipeline(repeats, threads=None)`.
  - `identity.py` skips the tie capture under threads, and its exact compare ignores `tie_gap`.
- Tests: `tests/test_bank_threads.py` (bit-identical at threads 2/4/16, invalid env, env knob) and 2 in `test_feasibility_gate.py` (pool workers at 1 thread, thread settings recorded). All were red, then green.
- Harness exact vs slice 5 (`s5b.pkl`) at threads 1/4/16: 0 differences each (`$S/h4_runs.log`).
- Go/no-go (`prototypes/p13/threads_gonogo.py`, `$S/threads_gonogo.log`, uptime 0.91 -> 0.95): threads 1 median 4.532 s, threads 4 median 3.389 s; gain 1.143 s, ratio 0.748 -> **GO**.
- Waiting on: approval of `_MAX_BANK_THREADS = 4` (lockfile line), then `make test-fast` alone, then landing.

## Next steps (paused here)

1. When `_MAX_BANK_THREADS = 4` is approved: add `denoisifier._local_stripes :: _MAX_BANK_THREADS :: 4` to the lockfile in `$S/s4`, run `make test-fast` there alone, fast-forward main and commit.
2. Slice 7 ruling: if dropped, record it and file the finder follow-up that names the explore set (plan). If adopted, rebase slice 4 onto it and rerun the exact harness at threads 1/4/16.
3. Step 9: `uv run --locked pytest -m wide`. Then the code review and the fixer's heavy sequence.

## Cleanup items

- Worktrees `$S/s3`, `$S/s4b`, `$S/wip5`, `$S/s6`, `$S/s7`, `$S/s4`, `$S/ref_base`, `$S/ref_g1`; branches `t13-step3`, `t13-s4b`, `t13-slice5-wip`, `t13-s6`, `t13-s7`, `t13-s4`.
- `~/.cache/denoisifier/p13-h/` (harness pickles, ~7 G), `~/.cache/denoisifier/p13-c1/`, `.scratch/stripe-detector/p13-c1-ref/`.
