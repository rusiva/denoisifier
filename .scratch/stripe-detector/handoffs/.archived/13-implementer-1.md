# Ticket 13 implementer-1 handoff (paused on the coordinator's request)

- Plan: `13-plan.md` (settled). BASE `aae4084`. Branch `main`, HEAD `1257fee` (clean apart from the orchestrator's uncommitted ticket Comments in `issues/13-speed-budget.md`, left alone).
- Machine: 16 logical CPUs, WSL2. `make test-fast` takes ~13 min here (963 passed, 652 deselected).

## Done (commits on main)

| commit | step | proof |
|---|---|---|
| `f1eae1f` | step 0: C1 explore set persisted | `prototypes/p13/c1/explore.py`: cache path, sha256, size, recipe; 216 C1-tag records load |
| `57ac55c` | slice 1: lazy `scipy.stats`, `scipy`, `multiprocessing`, `ProcessPoolExecutor` | new `test_cli_import_does_not_load_scipy_stats` (red, then green); `make test-fast` EXIT 0, `963 passed, 652 deselected in 790.60s` at 57ac55c |
| `386c65d` | equality harness `prototypes/p13/identity.py` (+ `tol.py`, `timing.py`) | BASE vs BASE exact PASS; a 1e-12 ratio perturbation is caught (FAIL) |
| `df3c78b` | slice 2: A1 bank loop (`_BankBuffers`, `_match_period`) | harness exact vs BASE: 58 frames, 0 differences |
| `ef79e1f` | slice 3: one shared spectrum = **G1** | harness exact vs BASE: 58 frames, 0 differences; `make test-fast` EXIT 0, `963 passed, 652 deselected in 802.57s` at ef79e1f |
| `1257fee` | step 3 (part): `USED_SEEDS` reserves 601_000-601_099, 602_000-602_159, 603_000-603_099 (orchestrator approval, ticket Comments); `prototypes/p13/null_screen.py` | lockfile updated for USED_SEEDS only; `test_protected_numbers` + `test_seed_sets_are_disjoint_and_unused` green. **Full `make test-fast` not yet run on this commit.** |

### Timings (foreground, AC 1 worst frame = harness `ac1_worst`, seed 601_000, min of 3, load 1-3)

| | bank | break pass | analyse |
|---|---|---|---|
| BASE `aae4084` | 5.02 | 1.40 | 7.33 |
| slice 2 | 4.47 | 1.40 | 6.80 |

- CLI import (`python -c "import denoisifier.cli"`, wall, 5 runs): 0.64-0.70 s at BASE -> 0.34-0.36 s after slice 1.

## In flight

- **Null screen at G1** (`null_screen.py run <scratch>/ref_g1/src ... null_g1.pkl 8`) was running in the background when paused; output `/tmp/claude-1000/-home-rusiva-dev-denoisifier/c1df1e95-ed74-413e-bb65-92893398d130/scratchpad/h/null_g1.pkl`, log `/tmp/claude-1000/-home-rusiva-dev-denoisifier/c1df1e95-ed74-413e-bb65-92893398d130/scratchpad/null_g1.log` (ends with EXIT=). If the pickle is missing, rerun it (~10 min, 8 workers).
- **Slice 5 code** is parked on local branch **`t13-slice5-wip`** (`daca07d`, not on main): `_Spectrum.gaussian(period|None, angle, sigma_across, sigma_along, truncate=True)` with value-picked support box and pruned `scipy.fft` inverse; `gabor`, `local_mean`, `_Filters.size_depth`, `break_response` go through it; `filtered`, `_window`, `_size_window` removed. New `tests/test_spectrum_filters.py` (10 support-box cases: P3 wrap +-10, DC local mean, 2x1/1x2 at P3/P6, references; 2 `break_response` vs an independent full-grid ifft2): red before, green after (12 passed). mypy/ruff clean. Not yet run: harness `tol slice5` vs G1, null screen vs G1, timing, `make test-fast` (will be red on the lockfile until `_GAUSS_TRUNC_SIGMAS` is approved).

## Scratch state (session scratchpad, lost on reboot)

- `/tmp/claude-1000/-home-rusiva-dev-denoisifier/c1df1e95-ed74-413e-bb65-92893398d130/scratchpad/h/frames.pkl` (58 harness frames), `base.pkl` (BASE run), `g1.pkl` (G1 run), `null_frames.pkl` (160 null-screen frames).
- Worktrees: `/tmp/claude-1000/-home-rusiva-dev-denoisifier/c1df1e95-ed74-413e-bb65-92893398d130/scratchpad/ref_base` (aae4084), `/tmp/claude-1000/-home-rusiva-dev-denoisifier/c1df1e95-ed74-413e-bb65-92893398d130/scratchpad/ref_g1` (ef79e1f). Remove with `git worktree remove` at the close.

## Next steps

1. `make test-fast` on main HEAD (seeds commit).
2. Approvals needed before slice 5 lands on main and before the rest of step 3 (all lockfile / stamp edits):
   - `_GAUSS_TRUNC_SIGMAS = 8.0` in `_local_stripes.py` (new lockfile entry; plan slice 5);
   - `FULL_GRID_REL_TOL = 1e-12` (slice 5 tests' bound; now a local constant in `tests/test_spectrum_filters.py`, should move to `tests/protected.py`);
   - step 3's protected numbers: `SPEED_TEST_SEED` (from TEST_SEED_BLOCK), `SPEED_CASE = (3.0, 3.0)`, the two break lines, the Fork point, `SPEED_SPIKES = 30`, plus the `TARGET_TIMING_S` comment text;
   - `tests/speed.py`, `tests/test_speed.py` added to `STAMPED_FILES` (`tests/slow_stamp.py`).
   - Later in the plan: the C1 sample cap (slice 7) and `_MAX_BANK_THREADS = 4` (slice 4, on measured gain).
3. Then: cherry-pick `t13-slice5-wip` (or merge), harness `compare g1.pkl s5.pkl tol slice5`, null screen `compare null_g1.pkl null_s5.pkl slice5`, timing, `make test-fast`, go/no-go per plan; then step 3 scaffolding, slices 6, 7, 4 in plan order.

## Cleanup items

- `~/.cache/denoisifier/p13-c1/` (N8): delete at ticket 13's close (or at the finder follow-up's close if slice 7 is dropped).
- Branch `t13-slice5-wip` once slice 5 is on main; worktrees `ref_base`, `ref_g1`.
- `.scratch/stripe-detector/p13-c1-ref/` (verbatim ticket 09 harness2/eval2, outside ruff).

## File pointers

- `prototypes/p13/identity.py`, `tol.py`, `timing.py`, `null_screen.py`, `c1/explore.py`
- `src/denoisifier/_local_stripes.py` (slices 2-3; slice 5 on the WIP branch), `src/denoisifier/analysis.py` (`_front_half`, `_qualifying_regions`), `src/denoisifier/_calibration.py`, `calibration.py` (slice 1)
- `tests/test_cli.py` (slice 1 test), `tests/protected.py` + `tests/protected_numbers.lock` (USED_SEEDS)
