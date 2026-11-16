# Ticket 13 plan: speed budget (settled)

- Ticket: `.scratch/stripe-detector/issues/13-speed-budget.md`. BASE `aae4084`.
- This plan folds in: plan review `13-plan-review.md` (B1-B4 accepted), the orchestrator's Decisions (`13-orchestrator.md`: Q2-Q5, B1-B4, and the "Rulings on re-plan": O1-O3, Risk 1, Risk 3, slice 5's test), the owner ruling of 2026-11-15 (ticket Comments), and prototype P1 (`13-prototype-p1.md`). Nothing in it is open; section 7 lists the rulings.
- **Goal (owner, 2026-11-15):** cut the runtime as far as possible through better computation. The budget includes a cold per-frame CLI start, on a laptop with at most 8 cores. About 1 s per frame is welcome; going below that is unnecessary. Threads are an extra on top, never the main lever.
- **Scope (O2 ruling):** the ticket closes at this plan's result (about 2.8 s cold at 4 threads, projected). The levers beyond it are follow-up tickets, filed `needs-triage`: 19 multirate bank, 20 crop-local region and Fork spectra, 21 batch/watch mode. Each extra score-moving lever costs its own ~3 h re-store, so none is pulled in here.
- **AC 1 stays at ≤ 5 s,** the ticket's AC, for both the warm pipeline and the cold per-frame CLI call (B5; `make bench` gates both). Every faster number is recorded beside it (AC 3), never asserted.
- **Measurement:** short single-process foreground runs only. No `make bench/measure/check-slow/check-held-out` before step 11.
  - Planner scripts (throwaway scratchpad): `prof.py`, `bank.py`, `variants.py`, `profvar.py`. The implementer recreates what it needs under `prototypes/p13/`.
  - P1's scripts: `prototypes/p13_threads/` on branch `prototype/13-p1-threads`.
- **Noise:** ±10-20 % run to run on this WSL2 box. P1's BASE on the worst frame, 8.2-8.7 s, is the reference; the earlier 7.9 s profile ran warmer. Variant timings below are the min of 3 runs, at load 0.7-1.0.
- **Go/no-go rule:** every adopt/drop criterion below is stated before its data is seen. A criterion is never loosened after a look. A failed criterion drops the slice (slice 6: first its pre-stated fallback), and the drop goes into the ticket Comments with the numbers.

## 1. Where the time goes (P1 reference, worst frame)

- **Worst frame (AC 1, Q3(a)):** 400x1600; P3, A3; m 0.5; scorched Mottle; `Emccd()`; 30 spikes.
  - Breaks: π at (130, 500) tilted A+4°, and −2 rad at (280, 1100) tilted A−3°.
  - One Fork at (200.5, 800.5).
  - Found: 2 breaks, 1 Fork, 1 region.
- **Typical frame:** P6, A−5, with no breaks and no Forks.

| stage (worst frame, idle) | BASE s | share |
|---|---|---|
| cold start: interpreter + imports | ~0.8-1.1 (wall, `import denoisifier.cli`), of which `scipy.stats` 0.39 (`-X importtime`) | |
| `read_frame` (CSV) | 0.12-0.15 | |
| bank `estimate_local_stripes` | 5.63 | 69 % of `analyse` |
| `_with_phase_breaks` | 1.61 (finder `_Samples.scan` + `line_side` ≈ 1.65 s cumulative in cProfile; `break_response` only 0.09) | 20 % |
| `_qualifying_regions` | 0.35 | |
| Fork searches (pre + post) | 0.39 | |
| spikes (`rank_filter` 0.13) + `_light` + other | 0.21 | |
| **`analyse`** | **8.20** | |
| warm read → analyse → to_json | 8.68 | |
| **cold CLI** (`python -m denoisifier f.csv -o r.json`) | **9.46** | |

Inside the bank (cProfile, BASE):
- 198 inverse FFTs of the 464x1664 padded spectrum (numpy, ~12-15 ms each). 464 = 16·29, so the column pass is slow.
- `_window`: 0.9 s. It evaluates `np.exp` over the full 464x1664 grid per filter, although each Gaussian is non-negligible on a small box only.
- The full-grid product in `filtered`: 0.4 s.
- `np.stack` / `take_along_axis` / `argmax`: 0.7 s.
- `uniform_filter`: 0.33 s.

P1's thread result: A1+A3 at 4 threads is bit-identical at every count, but the bank only goes 5.63 → 2.89 s (1.95x, memory-bound). Under load, most of the gain is lost. That is why this plan cuts the computation first and adds threads last, on measured gain only.

## 2. Slices

Three groups, in this implementation order (section 5 has the full work order):
- **Group I (slices 1-3), bit-identical.** Regular gates only, no re-store. Its last commit is the **G1 baseline** (record the hash in the handoff). G1 is the reference for every Group II null screen.
- **Group II (slices 5-7), score-moving.** One `make measure` → re-store sequence at the end covers all of them (section 5).
- **Slice 4 (threads), bit-identical, after Group II** (Risk 3 ruling). It is adopted only on its measured gain over the final, smaller bank.
- Slice 8 (multirate bank) is **not in this ticket** (O1 ruling): follow-up ticket 19 carries it and its prototype P2.

Savings are on the worst frame, single thread, unless marked. "Measured" means a planner or P1 foreground run; "estimated" means derived.

### Group I: bit-identical

**Slice 1. Cold-start imports** (`_calibration.py`, `calibration.py`)
- Import `scipy.stats` (`betabinom`, `binomtest`) inside the functions that use it. The analyse/CLI path does not need it.
- Also make these lazy in `calibration.py`: `import scipy` (used only for `scipy.__version__`), `multiprocessing` and `ProcessPoolExecutor`.
- Saving: **−0.39 s cold, measured** (`-X importtime`: `scipy.stats` 392 ms of 795 ms).
- What remains is numpy + `scipy.ndimage/fft/special` ≈ 0.45-0.55 s of wall time (measured). That is the import floor; see section 6.
- Proof:
  - output is untouched;
  - add the fast test `test_cli_import_does_not_load_scipy_stats`: a subprocess `python -c "import denoisifier.cli, sys; assert 'scipy.stats' not in sys.modules"`.

**Slice 2. A1 bank loop restructure** (`_local_stripes.estimate_local_stripes`)
- As before:
  - one preallocated `(5, H, W)` buffer;
  - `np.abs(out=)` and `energy **= 2` (keep `abs**2`, never `re²+im²`);
  - `energy.max(axis=0)`;
  - `best_response` set only at the `better` pixels.
- Per P1 finding 4, the buffers are allocated **once per worker**, never per Period. Write the loop body as a per-Period function that takes its buffer set, so slice 4 can later hand each thread its own set (`threading.local` or one set per job slot) without restructuring again.
- Saving: **−0.36 s measured** (serial, reused buffer).
- Proof: the equality harness (section 3.1), mode `exact`, with `LocalStripes` arrays `array_equal`.

**Slice 3. A2 one forward spectrum** (`analysis._front_half`, `_qualifying_regions`)
- Build `_Spectrum(work)` once and hand it to the bank and to `_Filters`.
- Do not seed `_Filters._means` from the bank (review N5: about 90 MB kept alive for 0.03 s).
- Saving: −0.03 s, estimated.
- Proof: the equality harness, mode `exact`.
- **Commit = G1.**

### Group II: score-moving (one measure → re-store sequence covers it)

Every slice in this group moves bits. The exact reproductions in `test_slow_calibration` (AC 7) and `test_slow_break_fork_calibration` are red by design until the re-store. Each slice is therefore proven in three steps, all in the foreground, before the next slice starts:
1. its own equivalence check against the previous commit, with the stated tolerances (harness mode `tol`);
2. the **null screen** (section 3.3) against G1, with its pre-stated criteria (Risk 1 ruling);
3. all accuracy tests green: `make test-fast` per slice, and every `wide` id at step 9.

The re-store is legitimate here because these changes are meant to move scores (CLAUDE.md, "After a score-moving change"). **Stop rule (Risk 1 ruling):** after the re-store, an AC 7 red (`tests/test_slow_calibration.py`, or its break/Fork twin) or a held-out red is a **finding**: stop and report to the orchestrator. No second re-store, no second look at the held-out seeds, no tolerance change.

**Slice 5. FFT engine and Gaussian-on-support filtering** (`_local_stripes._Spectrum`, `_local_phase.break_response`, `analysis._Filters.size_depth`)
- **One seam:** `_Spectrum.gaussian(period | None, angle_deg, sigma_across, sigma_along)`. Every Gaussian filter uses it: the bank's `gabor`/`local_mean` (stripe and 90° reference filters alike), `size_depth` (both windows), and `break_response` (both windows).
- How it works:
  - It evaluates the kernel only on the index box where it exceeds `exp(-K²/2)`, with `_GAUSS_TRUNC_SIGMAS = K = 8` (1.3e-14 of the peak). The box is selected on the 1D `fftfreq` vectors, so binned grids work unchanged.
  - **Box by frequency value:** the box is picked by `fftfreq` value. The low-pass `local_mean` box around DC is therefore two index runs, one at each end of the axis. A P3 box reaching past ±0.5 is clipped at Nyquist, exactly as the old full-grid kernel was, which is not periodic (corrected 2026-11-16 per the approval review).
  - It multiplies only that box.
  - It runs a **pruned 2D inverse**: the x-pass (`scipy.fft.ifft`, axis 1) on the box's rows only, cropped to the frame's columns; then the y-pass on those columns only, cropped to the frame's rows.
  - Forward and inverse go through `scipy.fft`.
- **Keep the padded shape** (`_PAD = 32`, 464x1664). A 5-smooth padded shape (next_fast_len with extra reflect pad) was measured and **rejected**:
  - it changes the circular wrap at the edges: ratio up to +190 % at edge pixels, 0.04 % of Period-map pixels changed;
  - its extra gain is only about 0.2 s on top of pruning.
- `_GAUSS_TRUNC_SIGMAS` is a new lockfile entry and needs an approval.
- **Measured (bank, min of 3, single thread):**

| variant | P3 | P6 | ratio max rel. diff | Period / Angle maps |
|---|---|---|---|---|
| BASE | 6.03 | 5.79 | | |
| scipy.fft only | 5.56 | 5.48 | 4.2e-13 | identical |
| + support box | 4.39 | 4.27 | ≤ 5.2e-13 | identical |
| **+ pruned inverse** | **3.34** | **3.48** | ≤ 3.7e-13 | identical |

- Saving: **bank −2.3 to −2.7 s, measured.** The region, size-rule, leakage, `_BreakPass.depth`, `break_response` and Fork filters (~23 more inverse FFTs) get the same seam: about −0.2 s, estimated.
- **Go/no-go (adopt only if all hold):**
  - harness vs G1: `LocalStripes.ratio` relative difference ≤ 1e-11 on light pixels; Period and Angle maps `array_equal`; `Report` score, regions, breaks and forks equal within 1e-9 relative on every harness frame; `labels` equal;
  - null screen vs G1: its criteria (section 3.3), with the score bound 1e-9 relative;
  - `make test-fast` green.
- Fast tests (permanent, seeds from `TEST_SEED_BLOCK`):
  - `test_support_box_filter_matches_full_grid`, parametrized over three filter kinds, each vs a full-grid reference kernel through the same engine, ≤ 1e-12 relative:
    - **Nyquist clip at P3:** a P3 stripe filter whose box reaches the Nyquist edge, at bank Angles −10° and +10°, plus the `local_mean` box around DC;
    - **binned:** the same P3 and a P6 filter on a 2x1 and a 1x2 grid (`BinFactors`), so the `fftfreq` box selection is tested on non-unit frame frequency scales;
    - **reference-angle filters:** the 90° reference of a P3 and a P6 bank filter;
  - `test_break_response_matches_full_grid`: `break_response` through the seam vs the full grid, same bound.

**Slice 6. Single-precision bank FFTs** (`_Spectrum`, bank path only; O3 ruling)
- **Shipped variant (A):** the forward spectrum, the box products and the pruned inverses run in `complex64`. Energies, `uniform_filter`, ratio and the merge stay in float64.
  - Subtract the frame's light mean before the forward FFT to cut the DC term's dynamic range. The local mean is restored exactly by adding the constant back to `local_mean`.
  - The region, finder and Fork filters stay in float64: they measure fine Period, Angle and phase.
- **Fallback variant (B), pre-stated:** variant A, plus the winners' `response` recomputed in float64. After the merge, for each (Period, Angle) pair that wins at some pixel, recompute that filter's response through slice 5's seam in complex128 and write it into `best_response` at that pair's pixels. `local_mean` likewise in float64 for the winning Periods. This feeds `_phase_steps` (`analysis.py:920` single region, `analysis.py:1025` merged group) with float64 phase, so the fine Period and Angle no longer see float32 rounding. Cost: one float64 inverse per winning pair (estimated 5-15 pairs on harness frames, ~0.1-0.3 s).
- **Measured (variant A without the mean subtraction, on top of slice 5):** bank 3.34 → **1.80 s** (P3) and 3.48 → **1.86 s** (P6).
  - ratio max relative difference 6.1e-6 / 6.6e-6;
  - Period map identical;
  - Angle map 99.994 % identical at P6. The changes are near-ties between bank Angles.
- Saving: **−1.5 to −1.6 s, measured** (variant A).
- **Go/no-go (O3 ruling), on the shipped code, with mean subtraction:**
  1. Run variant A on the **full** harness (section 3.1, mode `tol` vs the slice 5 commit) and the null screen (section 3.3, vs G1). Variant A is adopted only if all hold:
     - **no threshold flip:** no harness or null-screen frame changes side of the stored stripe Threshold (`PACKAGE_STORED_THRESHOLD`), and none changes side of the stored break or Fork thresholds (`PACKAGE_BREAK_FORK_BREAK_THRESHOLD`, `PACKAGE_BREAK_FORK_FORK_THRESHOLD`), compared frame by frame;
     - regions, breaks and forks are found identically (same count, labels `array_equal`);
     - **fine shifts ≤ 1 % of each accuracy tolerance**, per region, break and Fork, on every harness frame:
       - Period: |ΔP / P| ≤ 5e-4 (`PERIOD_REL_TOL` 0.05);
       - Angle: |ΔA| ≤ 0.01° (`ANGLE_TOL_DEG` 1.0), and ≤ 1e-4° on the binned harness frames (`BINNED_FRAME_ANGLE_TOL_DEG` 0.01);
       - Modulation Depth: |Δm| ≤ 1e-3 (`DEPTH_TOL` 0.1, absolute);
       - break segment points: ≤ 0.005 P (`BREAK_EXACT_POSITION_TOL_PERIODS` 0.5); break jump: ≤ 5e-4 rad (`BREAK_EXACT_JUMP_TOL_RAD` 0.05);
       - Fork position: ≤ 0.0025 P (`FORK_EXACT_POSITION_TOL_PERIODS` 0.25);
     - the reported score within 1e-5 relative; ratio relative difference ≤ 1e-5 at every region peak;
     - ticket 01's noise-free profile frames still score below the stored threshold;
     - `make test-fast` green.
  2. If any criterion fails, build variant B and run **the same criteria, once**, on the same frames. Adopt B if all hold.
  3. If B fails too, drop slice 6. The loss is about 1.5 s single thread. Record it in the ticket Comments.
- The criteria are printed by the harness and the null screen as one pass/fail table per criterion. The orchestrator reads the table; it does not re-judge the bounds.

**Slice 7. C1: ticket 09's coarse-strided / fine-windowed finder** (`_local_phase.find_phase_breaks`, `_best_line`, `_golden`, `_samples`; with A4, the `nonzero`/`magnitude` cache in `_Samples.scan`)
- Required (P1 verdict, Q5 ruling).
- Run the coarse 3° scan on strided samples, capped. Run the fine scan, the golden section and the fit on full-density 0.5 P samples within ±`_BREAK_FIT_HALF_WINDOW_PERIODS`·P of the coarse line.
- The cap is a new protected number and needs an approval. Fix its value on the explore set only (below); never on the fresh frames.
- Saving: **−1.0 to −1.3 s, estimated** from ticket 09's capped timings (pairs 0.60-0.66 s vs 2.4-2.5 s). The measured target: the finder's scans ≈ 1.65 s → ≤ 0.6 s on the worst frame. There is nothing to save at P ≥ 6.
- **The explore set (Risk 3 ruling): persisted at step 0**, before any work (section 3.4).
- **Go/no-go (pre-stated, Risk 3 ruling).** Reference = the shipped code at the slice 6 commit (its predecessor); candidate = slice 7. Adopt only if all hold:
  - (a) `tests/test_local_phase.py`, `tests/test_phase_break_pass.py` and the Fork tests are green, including the `wide` ids;
  - (b) on the 216 explore-set frames (tags full_break, fullcap, pair*, bin*):
    - the coarse scan picks the **same basin** on every frame (the coarse line's angle bin and offset within the fit window of the reference's);
    - found and AC 4 are **identical**, frame by frame, and so is the changed region;
    - per-frame **|Δ line error| ≤ ε = 0.05 P** (a tenth of the 0.5 P sample stride), line error measured as ticket 09's eval does (`git show 108e150:prototypes/p09_breaks/eval2.py`);
    - the **max line error per tag is not worse** than the reference's;
  - (c) on **fresh frames** generated after the cap is fixed: 100 frames, seeds `603_000`-`603_099`, the same tag mix as (b) (harness2 job layouts: 20 full_break, 20 fullcap, 20 per pair2/pair3/pair4, the rest bin2x1/bin1x2, skipping `s % 10 == 0` for the bins as harness2 does), the same four conditions as (b);
  - (d) the null screen (section 3.3) vs G1: no new break or Fork on any break-free frame.
- If any of (a)-(d) fails on any frame, slice 7 is dropped. Record that in the ticket Comments, file a follow-up ticket for the finder speedup that names the persisted explore set (Q5 ruling), and the AC 1 frame then relies on slices 1-6 and 4 (section 6 shows it still meets 5 s).

### Slice 4: threads across Periods (bit-identical; after Group II)

**Slice 4. A3 threads across Periods** (`_local_stripes.estimate_local_stripes`)
- Per-Period jobs, at most `n` in flight, merged serially in ascending Period order. The per-Period function from slice 2 takes one buffer set per job slot.
- **Thread count (B2, Q2 ruling):**
  - read lazily inside a function, never at import;
  - `estimate_local_stripes(..., threads: int | None = None)` is internal. `None` resolves to `DENOISIFIER_THREADS` if set, else `min(_MAX_BANK_THREADS, len(os.sched_getaffinity(0)))`;
  - `_MAX_BANK_THREADS = 4` is the only new module-level number. It is a new lockfile entry and needs an approval, which the orchestrator gives on the measured gain below and records in the ticket Comments;
  - an invalid `DENOISIFIER_THREADS` (non-integer, ≤ 0) raises `ValueError` naming the variable;
  - the env knob stays private and undocumented (Q2 ruling).
- **Pools run their workers at 1 thread:**
  - `feasibility.run_pool`, by wrapping `fn` (N3). Never touch `initializer=seed_guard.install_worker` or its `initargs`;
  - `tests/evaluate_regions.py:277` and `tests/calibrate_regions.py:565`;
  - **the package pool, `calibration.calibrate_folder` (B1):** `threads=1` reaches `_score_file`, and through it the pipeline → `estimate_local_stripes`. **N9:** the public `analyse` signature does not change. Move its body into a module-private `analysis._analyse(frame, ..., threads: int | None)`; `analyse` calls it with `threads=None`, and `_score_file` calls it with `threads=1`. No `_threads` keyword shows in `help(analyse)` or the stubs.
- `feasibility.thread_settings()` and `bench.py` record the effective count (N1). `regression_check` and `make measure` record it too, in their JSON (N2).
- Expected: P1 measured −2.7 s on the BASE bank (5.63 → 2.89 s at 4 threads). On the final bank (~1.8 s with slice 6) about −0.9 s, estimated with P1's 1.95x scaling.
- **Go/no-go (pre-stated; Risk 3 ruling: approved on the measured final gain).** On the slice-7 tree, idle machine (`uptime` 1-min load < 1), foreground, one session: `speed.time_speed_pipeline(5)` on the AC 1 frame at `threads=1` and at `threads=4`, interleaved (1, 4, 1, 4, ...). Adopt slice 4 only if
  - the 4-thread median is ≥ 0.3 s below **and** ≤ 0.85x the 1-thread median; and
  - the harness, mode `exact` vs the slice 7 commit, is bit-identical at threads 1, 4 and 16.
  - Otherwise drop slice 4 whole: no constant, no env knob, no pool changes. Record the numbers in the ticket Comments either way.
- Proof (all bit-identical, the same in P1):
  - `test_threaded_bank_is_bit_identical_to_serial`: threads 1 vs 4 on a small generated frame;
  - `test_calibrate_folder_workers_match_serial` (B1): `workers=2` vs `workers=1` scores, exactly;
  - `test_invalid_thread_env_raises`: `DENOISIFIER_THREADS` = `"x"`, `"0"`, `"-1"` each raise `ValueError` naming the variable;
  - optional: `test_bounded_bank_jobs`.
- Slice 4 moves no bits, so it does not disturb Group II's single re-store; it lands before the code review and the heavy sequence.

### Not adopted (measured, reasoned or ruled)

- **5-smooth padded shape / `_PAD` change:** edge results move a lot (above), for about 0.2 s.
- **C2, crop-local `break_response`:** it costs only 0.09 s on the worst frame (cProfile). Slice 5's seam already makes it cheaper.
- **A faster CSV reader:** `read_frame` is 0.13 s.
- **Slice 8, multirate bank (O1 ruling):** unmeasured, a ~1e-3 score shift (100x slices 5-6), and a gain inside the projection's noise. Deferred to ticket 19 with its prototype P2.
- **Crop-local region and Fork spectra (~0.75 s) and a batch/watch mode (O2 ruling):** tickets 20 and 21.

## 3. Proof machinery

1. **Equality harness** (`prototypes/p13/identity.py`, kept in the repo for the ticket).
   - It runs `analyse` on a fixed frame set at a reference commit (`git worktree add <scratch>/ref <commit>`) and at the working tree, pickles the `Report`s and the `LocalStripes`, and compares them.
   - Comparison: `score`; `labels` (`array_equal`); regions, phase breaks, forks and warnings; `LocalStripes` ratio/Period/Angle maps.
   - Mode `exact` for Group I and slice 4 (dataclass equality, exact floats). Mode `tol` for Group II, with the per-slice criteria above; it prints one pass/fail row per criterion and the max differences.
   - **Frame set**, seeds `601_000`-`601_099` (P1's `601_234`/`601_240` are outside it):
     - the AC 1 frame and the typical P6 frame;
     - the bench timing frame (`TIMING_SEED`);
     - 10 CASES x {full-frame typical, single region, break, fork, break + fork};
     - binned 2x1 and 1x2;
     - a clipped frame, a 256x256 crop, and a stripe-free frame.
   - Its output goes in each slice's handoff section.
2. **Permanent fast tests:** listed per slice. Every generated frame uses a seed from `TEST_SEED_BLOCK`, recorded in `tests/protected.py` with approval (N4).
3. **Null screen** (`prototypes/p13/null_screen.py`; Risk 1 ruling). Foreground, single process or a small pool at 1 thread per worker, run once per Group II commit (and once for slice 6's variant B if it is built), always against **G1** (slices 1-3; slice 4 is bit-identical, so G1 stands for the "slice-4 baseline" of the ruling). G1's outputs are computed once, at step 4, and cached.
   - **Frames (160, unregistered, reserved in `USED_SEEDS` at step 3):**
     - 100 stripe-free frames, seeds `602_000`-`602_099`: the stripe calibration recipe (`threshold_calibration.synthetic`/`settings`: 400x1600, typical settings, 30 spikes, unclipped);
     - 30 break-free striped full frames, seeds `602_100`-`602_129`: the break/Fork calibration recipe (`break_fork_calibration.settings`, depth `BREAK_FORK_CALIBRATION_DEPTH`, `CASES[seed % 10]`, no breaks, no Forks), scored with `break_fork_calibration.reported_with_evidence` (report, S_b, S_f);
     - 30 break-free frames on ticket 09's tags, seeds `602_130`-`602_159`, 10 each of `free` (region), `full_free` (full frame), `two_free` (two compatible regions), from harness2's job layouts (`git show 108e150:prototypes/p09_breaks/harness2.py`, `generate_job`, copied into `prototypes/p13/`).
   - **Criteria (all must hold; pre-stated):**
     - stripe-free: no frame changes side of `PACKAGE_STORED_THRESHOLD` vs G1; the max relative score shift is within the slice's bound (slice 5: 1e-9; slice 6: 1e-5; slice 7: exact, it does not touch the score);
     - break-free striped: no break or Fork reported that G1 did not report; no S_b or S_f changes side of the stored break or Fork threshold; the region count and `labels` equal G1's;
     - every frame: no new warning.
   - A failure drops the slice (slice 6: go to variant B first). It never changes a bound.
4. **C1 explore set** (step 0; Risk 3 ruling).
   - Source: `explore_v2.pkl` (334,506,898 bytes; ticket 09's explore BASE, 1796 frames = `p2/all_explore.pkl` + `base_v2extra.pkl`, per `.archived/09-prototyper-3.md`; C1 uses its 216 frames on the full_break, fullcap, pair* and bin* tags) in ticket 09's scratchpad, `/tmp/claude-1000/-home-rusiva-dev-denoisifier/85ad64ff-6979-496b-bc0d-89a93d20c47a/scratchpad/p3/`. A reboot clears it. Copy the whole pickle; filter by tag at read time.
   - **Persist to `~/.cache/denoisifier/p13-c1/explore_v2.pkl`**: outside the repo, so it is never committed and no `.gitignore` edit is needed, and outside `/tmp`, so a reboot keeps it. Record its `sha256sum` in `prototypes/p13/c1/explore.py`.
   - **Recipe**, in that script's docstring, for when the cache is lost: `git worktree add <scratch>/p09 108e150`, then `uv run --locked python prototypes/p09_breaks/harness2.py <out> explore` and `... <out> v2extra` there (job layouts `jobs("explore")` and `jobs_v2_extra()`, seeds in `BREAK_PROTOTYPE_SEEDS`, already reserved); the full_break, fullcap, pair* and bin* tags come from these two. The cache holds generated frames and BASE outputs, so a regeneration is deterministic; check the 216-frame subset's truth against the recorded hash's file if both exist. Also copy `harness2.py` and `eval2.py` from `108e150` into `prototypes/p13/c1/` (eval2's line-error and AC 4 metrics are the comparison).
   - If the pickle is already gone at step 0, regenerate it with the recipe before slice 7 starts.
   - **Cleanup (N8):** the step 0 handoff names `~/.cache/denoisifier/p13-c1/` as a cleanup item. It is deleted at ticket 13's close, or, if slice 7 is dropped, at the close of the finder follow-up ticket that names it.
5. **The slow tier** after the re-store:
   - `test_slow_calibration` (300 frames) and `test_slow_break_fork_calibration` (60) reproduce the **re-stored** files exactly;
   - `make check-held-out` covers 300 + 400 more frames;
   - the regression plan must still meet its operating rule. If `test_regression_plan_meets_the_operating_rule` goes red after the GATE/PROBE update, re-deriving the pass counts is the owner's decision (CLAUDE.md);
   - an AC 7 or held-out red after the re-store is a finding: stop and report (section 2, stop rule).
6. **`make measure`:** detector quality (GATE/PROBE thresholds and pass rates) is compared with BASE's stored measurement in the handoff. A drop beyond the measurement's own noise is a finding: stop and report; do not re-store.

**Seed check (done at planning, against `tests/protected.py` at BASE):** `601_000`-`601_099`, `601_234`-`601_240`, `602_000`-`602_159` and `603_000`-`603_099` overlap no `CALIBRATION_SEEDS` entry (all below 114_000), no held-out range (`CALIBRATED_FREE_SEEDS` 101_000+, `CALIBRATED_STRIPED_SEEDS` 102_000+, `BREAK_FORK_*_HELD_OUT*` 114_000-115_399), no `USED_SEEDS` range (the nearest are `410_000`-`411_003` and `700_000`+), and no seed ticket 18 holds free (`111_200`-`111_599`, `111_733`-`111_999`). Step 3 adds the four ranges to `USED_SEEDS` with a "Ticket 13" comment (one lockfile approval with step 3's other protected numbers), so `test_seed_sets_are_disjoint_and_unused` keeps them apart from now on.

## 4. AC tests on their real paths

**AC 1: performance** (`tests/speed.py`, `tests/test_speed.py`, `tests/bench.py`)
- `tests/speed.py`:
  - `speed_frame()`: the worst frame's recipe (section 1), generated and not timed;
  - `time_speed_pipeline(repeats, threads=None)` (B4): one function times **`read_frame(csv) → analyse → Report.to_json`**. The CSV is written beforehand and not timed. One untimed warm-up at `GATE.shape`, then `perf_counter`, median. `threads` reaches the private `analysis._analyse` (N9; slice 4's go/no-go uses it; `None` = the shipped default);
  - `time_cold_cli(repeats)`: wall time of a fresh `python -m denoisifier f.csv -o r.json` subprocess on the same frame, at the shipped default thread count; median. **Gated in `make bench` (B5)**, never in pytest's slow tier.
- Protected numbers in `tests/protected.py` (lockfile edit, approval, additive):
  - `SPEED_TEST_SEED` from `TEST_SEED_BLOCK`;
  - `SPEED_CASE` = (3.0, 3.0);
  - the two break lines, the Fork point, and `SPEED_SPIKES = 30`.
- `test_speed_pipeline_meets_the_slow_limit` (`pytest.mark.slow`; Q4(b) ruling):
  - asserts the median ≤ `SLOW_TIMING_LIMIT_S` (30 s, "real slowdowns only", owner 2026-11-10);
  - asserts the report has ≥ 1 break and ≥ 1 Fork, so the frame cannot silently skip stages.
- **`make bench` gates the 5 s AC:**
  - it times `speed.time_speed_pipeline(BENCH_REPEATS)` at the shipped default thread count;
  - it records `speed_median_s`, `cold_cli_s` (median of `BENCH_REPEATS` cold runs), `speed_meets_target`, `cold_cli_meets_target` and the thread count;
  - it **exits 1 when `speed_median_s > TARGET_TIMING_S` (5.0) or when `cold_cli_s > TARGET_TIMING_S` (B5:** the owner's budget includes the cold per-frame CLI start, 2026-11-15**)**, next to the existing 10 s rule. This is a strengthening.
  - Update the `TARGET_TIMING_S` comment (`tests/protected.py:82`; a lockfile-file edit of a comment only) and the `tests/bench.py` docstring (N1).
  - `tests/test_bench.py` covers the new rule, both halves: with the timers stubbed, a warm median over 5 s exits 1, a cold-CLI median over 5 s with a warm median under it exits 1 (B5), and both under 5 s exit 0.
- Fast, unmarked: `test_speed_frame_exercises_every_stage`. It runs the recipe at reduced shape, checks the breaks and the Fork are found, and stays under 2 s.
- `tests/test_speed.py` and `tests/speed.py` are added to `STAMPED_FILES` (an approval, since it edits `tests/slow_stamp.py`).
- No Makefile, marker, `addopts` or timeout change.
- **Tracked record:** `uv run --locked python tests/bench.py --out .scratch/stripe-detector/bench.json` at the close (allowed at ticket 13).

**AC 2: calibration and accuracy**
- Every accuracy test stays green, `wide` included, with no tolerance change.
- The stored thresholds are re-calibrated through section 5's sequence, because slices 5-7 move the output. If every Group II slice is dropped, there is no re-store (section 5, step 11).

**AC 3: per-stage timings next to the spec** (`tests/stage_timings.py` → `.scratch/stripe-detector/stage-timings.md`)
- The driver wraps the stage functions in the `analysis` namespace: `reject_spikes`, `find_clipped`, `_light`, `estimate_local_stripes`, `_qualifying_regions`, `_pre_break_forks`, `_with_phase_breaks`, `_post_break_forks`. Around them: `read_frame`, `to_json` and `write_mask_csv`.
- It records separately:
  - interpreter + import time (`-X importtime` total and wall);
  - **the cold CLI wall time** (`speed.time_cold_cli`).
- Frames: the AC 1 worst frame, the P6 typical frame, and the bench timing frame. Median of 5.
- Columns: BASE (P1's table, quoted), then the final HEAD at threads 1 and at the default.
- It also records commit, CPU, `len(sched_getaffinity)`, load average, versions and the slices adopted and dropped.
- `spec.md` user story 39 gets a one-line pointer to the file.
- Fast test `test_stage_timer_wraps_live_functions`: each wrapped name exists in `analysis`, and a tiny frame's stage sum is ≤ its total.
- Runs at the close on an idle machine, in the background (about 1-2 min).

## 5. Work order and end-of-ticket gates

0. **Persist the C1 explore set** (section 3.4) → `~/.cache/denoisifier/p13-c1/`, `sha256sum` and recipe in `prototypes/p13/c1/explore.py`. Before any code change.
1. Slice 1 → `make test-fast`.
2. Equality harness (TDD: BASE vs BASE, exact) → slice 2 → slice 3 → `make test-fast` after each; harness `exact` vs BASE. **Commit G1**; record its hash.
3. AC scaffolding: `tests/speed.py`, `tests/test_speed.py`, `tests/bench.py` rule, `tests/stage_timings.py`, protected numbers, the four `USED_SEEDS` ranges (section 3) and `STAMPED_FILES` (approvals) → `make test-fast`.
4. Null screen script (section 3.3); run it at G1 once and cache G1's outputs.
5. Slice 5 → harness `tol` vs G1 → null screen → `make test-fast` → go/no-go. Short foreground timing.
6. Slice 6 variant A → its go/no-go → variant B if needed → adopt or drop → `make test-fast`.
7. Slice 7: fix the cap on the explore set → explore-set comparison → fresh frames `603_000`-`603_099` → null screen → go/no-go → `make test-fast`.
8. Slice 4 (threads, pools, B1/B2 tests) → harness `exact` at threads 1/4/16 vs the slice 7 commit → the timed go/no-go → adopt (approval for `_MAX_BANK_THREADS`) or drop → `make test-fast`.
9. Run every `wide` id directly (`uv run --locked pytest -m wide`). The heavy gates come later, so this catches seed-specific reds early.
10. Code review → fixes.
11. **One heavy sequence**, background, idle machine (`uptime`), one at a time, each logged `; echo "EXIT=$?" >> <log>`:
    1. `make measure` (~39 min; less after the speedup) → set `GATE_STORED_THRESHOLD` / `PROBE_STORED_THRESHOLD` (approval);
    2. stripe driver `uv run --locked python tests/threshold_calibration.py --out src/denoisifier/stripe_free_calibration.json` (~14 min) → `PACKAGE_STORED_THRESHOLD`, `_5PCT`, `PACKAGE_CALIBRATION_DIGEST` (approval);
    3. break/Fork driver `uv run --locked python tests/break_fork_calibration.py --out src/denoisifier/break_fork_free_calibration.json` (~13 min) → `PACKAGE_BREAK_FORK_*` (approval);
    4. `make check-slow` (~23 min, less after the speedup);
    5. `make check-held-out` (~60 min);
    6. `make check`;
    7. `make bench` → tracked `bench.json`; `tests/stage_timings.py` → `stage-timings.md`. Commit both.
    - **Stop rule:** a red at 4 (AC 7 or its break/Fork twin) or at 5 (held-out) is a finding: stop and report. No second re-store, no second held-out look.
    - A second `make measure` is only for a fix the first measure forces, with its reason in the ticket Comments (owner ruling 2026-11-12).
    - If all of Group II is dropped, steps 2-3 are skipped. Thresholds then must equal the stored ones exactly; any change is a finding.

The handoff quotes each command, its EXIT, pytest's final summary line and `git rev-parse --short HEAD` (+`-dirty`).

## 6. Projection (worst frame, idle; ±15 %)

| | import + start | read | bank | break pass | regions + Forks + other | warm pipeline | **cold CLI** |
|---|---|---|---|---|---|---|---|
| BASE (P1) | ~0.8 | 0.13 | 5.63 | 1.61 | 0.95 | 8.68 | **9.46** |
| slices 1-3, 5-7, 1 thread | ~0.45 | 0.13 | 1.8 | ~0.5 | ~0.75 | ~3.2 | **~3.7** |
| + slice 4, 4 threads | ~0.45 | 0.13 | ~0.9 | ~0.5 | ~0.75 | ~2.3 | **~2.8** |
| without slice 6, 4 threads | ~0.45 | 0.13 | ~1.7 | ~0.5 | ~0.75 | ~3.1 | ~3.6 |
| without slice 7, 4 threads | ~0.45 | 0.13 | ~0.9 | ~1.6 | ~0.75 | ~3.4 | ~3.9 |

- AC 1 (≤ 5 s for both the warm pipeline and the cold CLI, both gated in `make bench`, B5) is met with margin on every row except BASE: the worst cold CLI row is ~3.9 s. It also holds single-threaded (~3.7 s cold).
- **About 1 s cold is not reached, by ruling (O2).**
  - The import floor (numpy + `scipy.ndimage/fft/special`, ~0.45-0.55 s measured) plus `read_frame` already takes 0.6 s.
  - The break pass and the region/Fork steps add about 1.2 s that neither threads nor the bank work touch.
  - The follow-ups: ticket 19 (multirate bank, ~0.4-0.5 s), ticket 20 (crop-local region and Fork spectra, ~0.75 s), ticket 21 (batch/watch mode: removes the ~0.5 s import from every frame after the first).

## 7. Rulings (settled; from `13-orchestrator.md`, Decisions)

- **O1:** slice 8 (multirate bank) is deferred to ticket 19, with prototype P2. Unmeasured, ~1e-3 score shift (100x slices 5-6), gain within projection noise; it keeps the one-look score-moving set smaller.
- **O2:** the ticket closes at this plan's result. Follow-ups filed `needs-triage`: 19 multirate bank; 20 crop-local region and Fork spectra; 21 batch/watch mode (a new public interface: the owner triages it there). The owner's ruling already covers the cold per-frame CLI "as far as possible"; each extra score-moving lever costs its own ~3 h re-store.
- **O3:** float32 (slice 6) is adopted only on its decision-based go/no-go (section 2): the shipped variant with mean subtraction, full harness + null screen; no threshold flip; fine Period/Angle/depth (and break/Fork position) shifts ≤ 1 % of each accuracy tolerance. Else variant B (winners' `response` in float64 for `_phase_steps`), same criteria once; else drop.
- **Risk 1:** a foreground null screen per Group II commit on unregistered seeds vs G1, before the end sequence (section 3.3). An AC 7 or held-out red after the re-store is stop-and-report: a finding, no re-store, no second look.
- **Risk 3:** step 0 persists the 09 explore set (section 3.4). C1's criterion is pre-stated (same basin; found/AC 4 identical; per-frame |Δerror| ≤ 0.05 P; max not worse; plus 100 fresh unregistered frames). Slice 4 moves after Group II; `_MAX_BANK_THREADS` is approved on the measured final gain.
- **Slice 5:** its fast test covers the Nyquist clip at P3, the two-run DC box, binned grids and the reference-angle filters.
- **Closing check (`13-plan-review.md`):** B5, `make bench` gates the cold CLI median at `TARGET_TIMING_S` as well as the warm pipeline (section 4); N8, the explore-set cache is a named cleanup item (section 3.4); N9, threads go through the private `analysis._analyse`, never a keyword on the public `analyse` (slice 4).
- Earlier: Q2 (lazy env read, internal `threads=`, private knob), Q3 (AC 1 gates on the P3 two-break + Fork frame; P6 recorded), Q4 (5 s in `make bench`, check-slow keeps 30 s), Q5 (C1 in scope on P1's numbers), B1-B4 accepted.

## File pointers

| file | role |
|---|---|
| `src/denoisifier/_calibration.py`, `calibration.py` | slice 1 lazy imports; `calibrate_folder` pool at 1 thread (B1, slice 4) |
| `src/denoisifier/_local_stripes.py` | `estimate_local_stripes` (slices 2, 4, 6), `_Spectrum.gaussian` seam (slice 5), `_MAX_BANK_THREADS`, `_GAUSS_TRUNC_SIGMAS` |
| `src/denoisifier/analysis.py` | `_front_half` (slice 3), private `_analyse(..., threads)` (slice 4, N9), `_Filters.size_depth` (slice 5), `_phase_steps` call sites `:920`, `:1025` (slice 6 variant B) |
| `src/denoisifier/_local_phase.py` | `break_response` (slice 5); `find_phase_breaks`, `_best_line`, `_golden`, `_samples`, `_Samples.scan` (slice 7) |
| `tests/feasibility.py:202`, `tests/evaluate_regions.py:277`, `tests/calibrate_regions.py:565` | pools at 1 thread (slice 4) |
| `tests/threshold_calibration.py`, `tests/break_fork_calibration.py` | recipes the null screen reuses (`synthetic`, `settings`, `reported_with_evidence`) |
| `tests/speed.py`, `tests/test_speed.py`, `tests/stage_timings.py` (new) | AC 1, AC 3 |
| `tests/bench.py`, `tests/test_bench.py`, `tests/protected.py`, `tests/slow_stamp.py` | 5 s rule, protected numbers, `USED_SEEDS` reservations, stamp |
| `.scratch/stripe-detector/stage-timings.md` (new), `spec.md` story 39 | AC 3 |
| `prototypes/p13/` (new) | equality harness `identity.py`, `null_screen.py`, `c1/` (explore-set script, harness2/eval2 copies) |
| `~/.cache/denoisifier/p13-c1/explore_v2.pkl` | persisted C1 explore set (not in git) |
| `.scratch/stripe-detector/issues/19-*.md`, `20-*.md`, `21-*.md` | follow-ups (O1, O2) |
