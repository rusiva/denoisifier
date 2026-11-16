# Ticket 13 implementer-2 handoff (paused on the coordinator's request)

- Continues `13-implementer-1.md`. Plan `13-plan.md`. BASE `aae4084`, G1 `ef79e1f`. Branch `main`, HEAD `2f38fd8`. The orchestrator's uncommitted ticket Comments in `issues/13-speed-budget.md` are left alone.
- `S=/tmp/claude-1000/-home-rusiva-dev-denoisifier/c1df1e95-ed74-413e-bb65-92893398d130/scratchpad` (lost on reboot).

## Approvals (orchestrator, 2026-11-16, ticket Comments): granted, conditions applied

1. `_GAUSS_TRUNC_SIGMAS = 8.0`: the docstring now says the box is picked by `fftfreq` value. A DC box is two index runs; a P3 box past Nyquist is clipped there, as the full-grid kernel is. Plan lines 95, 119 and 333 were reported to the orchestrator, who fixes the plan.
2. `FULL_GRID_REL_TOL = 1e-12` is in `tests/protected.py`. New `test_bank_gabor_matches_independent_full_grid` (P3 -10, P6 +5) checks against plain `np.fft.ifft2`. Mutation check: with `_inverse`'s crop off by one column, it fails (with the break-response cases), while the 10 box cases stay green.
3. Speed numbers match plan section 1. `SPEED_TEST_SEED = 38` was free in `TEST_SEED_BLOCK`. `SPEED_CASE = (3.0, 3.0)`; `SPEED_BREAK_LINES` holds (point, tilt from the Angle, jump); `SPEED_FORK_POINT = (200.5, 800.5)`; `SPEED_SPIKES = 30`. The `TARGET_TIMING_S` edit touches its comment only. Not in protected.py: depth 0.5 and Fork direction 1, literals in `tests/speed.py`. The stage timer's typical P 6 frame also uses seed 38, which the seed's comment says. Flag this to the orchestrator if "used nowhere else" is meant strictly.
4. `STAMPED_FILES` gains exactly `tests/speed.py` and `tests/test_speed.py`.

## Done

| item | where | proof |
|---|---|---|
| G1 null screen. The predecessor's run had been killed and left no pickle. | `$S/h/null_g1.pkl` | rerun EXIT=0, 160 records |
| slice 5, approved items | branch `t13-slice5-wip` `7c8269a` (on `daca07d`, base `1257fee`), worktree `$S/wip5` | `tests/test_spectrum_filters.py` 14 passed; `test_protected_numbers` green; ruff and mypy clean |
| step 3 scaffolding (not on main yet) | branch `t13-step3` `557780b` (base `e04b377`), worktree `$S/s3` | `tests/speed.py`, `test_speed.py` (fast `test_speed_frame_exercises_every_stage` at 100x400 finds 1 region, 2 breaks, 1 Fork; slow `test_speed_pipeline_meets_the_slow_limit`, not yet run), `stage_timings.py` + `test_stage_timings.py`, bench rule: 3 new `test_bench.py` cases (red, then green). Targeted tests: 53 passed. `make test-fast` not yet run on it. |
| slice 4b measurement | main `2f38fd8` `prototypes/p13/tie_bound.py` | output `$S/tie_g1.txt` |

## Slice 5 go/no-go (data in)

Harness `identity.py compare g1.pkl s5.pkl tol slice5`, 58 frames. Every row passes except "Period and Angle maps array_equal": one edge-column Angle pixel on each of region_601026 and break_601036 flips -10 -> +10 (an exact +-10 tie at P 4.19). Ratio max diff 5.88e-12 (bound 1e-11). Score max diff 2.96e-14. Null screen `compare null_g1.pkl null_s5.pkl slice5`: all 6 rows pass, max stripe-free shift 1.698e-13.

**Ruling (option C, ticket Comments):** a new slice 4b goes before slice 5. In `_match_period`, energies within relative eps of the max count as tied, and the first index wins. eps is a new protected number. Slice 4b is checked against G1 (null screen + harness rows; Period and Angle may differ only at pixels G1 shows within eps). Slice 4b then becomes slice 5's baseline, with every slice 5 row unchanged. Slice 6 re-derives eps in float32.

## Open question: eps (sent to the orchestrator, no reply yet)

The tie bound does not exist. On G1, mirror-line light pixels have +-theta relative energy differences spread over every decade from exact 0 up to 1. Reflect padding mirrors only 32 px, and the padded FFT wraps beyond that, so long Periods lose the symmetry. The max per Period runs from 2.7e-5 at P3.75 up to 1.0 at P >= 10. Off the mirror lines, an eps changes no Angle index up to 1e-9 (3 changes at 1e-8, 36 at 1e-7, 4174 at 1e-5). Proposed: `_BANK_TIE_REL = 1e-9`, and about 1e-5 for slice 6. Full numbers are in `$S/tie_g1.txt` and the message to the orchestrator.

## In flight

- `make test-fast` on `e04b377` (HEAD before `2f38fd8`, which only adds a prototype script): background, log `$S/tf_head.log` (ends with `EXIT=`). It was still running at the pause, with no failure so far.

## Next steps

1. Read `$S/tf_head.log`, and quote EXIT and the summary line.
2. Land step 3: `git rebase main t13-step3` (in `$S/s3`), fast-forward `main`, run `make test-fast`, and run `uv run --locked pytest tests/test_speed.py -m slow` once on an idle machine.
3. After the eps ruling, slice 4b test-first, in `_match_period` (`src/denoisifier/_local_stripes.py`): `angle_index = argmax(energy >= e_max * (1 - eps), axis=0)`. Test: a constructed tie picks the first index. Lockfile entry. Then harness `tol` vs G1 (needs a 4b profile in `tol.py`: Period and Angle may differ only at pixels where G1's energies are within eps), null screen vs G1, `make test-fast`.
4. Rebase slice 5 (`t13-slice5-wip`) onto 4b. Run harness `tol slice5` and the null screen vs 4b (null screen against G1 per plan; check the ruling's wording), timing (`uptime` first; `prototypes/p13/timing.py <src> $S/h ac1_worst`), `make test-fast`, commit on main.
5. Slice 7 (allowed now, on main). Explore set at `~/.cache/denoisifier/p13-c1/explore_v2.pkl` (216 C1 records, all `kind == "full"`; tags full_break, fullcap, pair2-8, bin2x1, bin1x2). Note that `explore.py`'s docstring mentions `prototypes/p13/c1/frames.py`, which does not exist yet. Design notes:
   - Regenerate frames with the shipped `generate(phase_breaks=...)` from the job: center = ((H*v-1)/2, (W*h-1)/2); a break offset `off` in Periods along the normal gives point (cy + off·P·cos t, cx - off·P·sin t).
   - Match with `tests/truth_match.py` (`break_problems`, `assert_region_covers_both_sides`, `truth_lit_mask`) instead of eval2, which is coupled to ticket 09's prototype post-pass.
   - "Same basin" hook: wrap `_Samples.scan` when called with the 60 coarse angles. Record the absolute coarse line (angle, y0 + o cos t, x0 - o sin t).
   - Candidate design: the coarse scan runs on a spatially strided subset (grid stride x f, f = ceil(sqrt(n/cap)), keeping the parent's y0/x0, min_side scaled by f^2). The fine scan, golden search and fit run on full-density samples within a band around the coarse line that covers every window they can reach (4P + 2P + R·sin(3.25°) + margin). Take `lo` and `nb` from the full set, so bins align and fine results are bit-identical whenever the basin matches.
   - Fix the cap before looking at the data: candidates {10k, 20k, 40k, 80k}; pick the smallest that passes all (b) criteria on all 216 frames. Then the fresh seeds 603_000-603_099. The cap needs approval.

## Branches, worktrees, scratch

- Branches: `t13-slice5-wip` (7c8269a), `t13-step3` (557780b).
- Worktrees: `$S/wip5`, `$S/s3`, `$S/ref_base` (aae4084), `$S/ref_g1` (ef79e1f).
- Pickles in `$S/h`: `frames.pkl` (58 harness frames), `base.pkl`, `g1.pkl`, `s2.pkl`, `s5.pkl`, `perturbed.pkl`, `null_frames.pkl`, `null_g1.pkl`, `null_s5.pkl`. Logs: `$S/null_g1.log`, `$S/null_s5.log`, `$S/s5_run.log`, `$S/tf_head.log`, `$S/tie_g1.txt`.

## Cleanup items

- `~/.cache/denoisifier/p13-c1/` (N8) at ticket close.
- Branches `t13-slice5-wip` and `t13-step3` once landed; worktrees `$S/wip5`, `$S/s3`, `$S/ref_base`, `$S/ref_g1` (`git worktree remove`).
- `.scratch/stripe-detector/p13-c1-ref/`.
