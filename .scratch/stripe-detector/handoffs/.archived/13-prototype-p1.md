# Ticket 13 P1 prototype: A1+A3 timed end to end

Answers review item P1 (`13-plan-review.md`) against `13-plan.md`, A1 + A3.

**Verdict:** A1+A3 does **not** reach the plan's numbers. The worst frame (P3, two breaks, one Fork) is at **6.2 s** median at 4 threads, idle. That is above P1's 4.5 s line, so by P1's rule **C1 is required** for Q3(a). Even with C1's −1.0 to −1.3 s, it would land at about 4.9-5.2 s, not 3.5 s, so Q4 is (b). The break-free P6 frame is at 3.95 s at 4 threads, idle. Under load most of the gain is lost: 11.3 s on the worst frame with 12 busy cores, and 7.0 s with 2. The output is bit-identical at 1, 2, 4 and 16 threads.

## Setup

- **Machine:** 16 logical CPUs (`nproc` with no OMP env; AMD Ryzen AI 7 PRO 360, WSL2). numpy/scipy from the locked env, Python 3.11.15.
- **BLAS:** `OMP/OPENBLAS/MKL_NUM_THREADS=1`.
- **Load averages:**
  - before: 0.06 / 0.37 / 0.43 at 23:43;
  - during the idle phase: 0.1 → 2.0 (the timed process itself);
  - 12-spinner phase: about 13-14 (1 min);
  - 2-spinner phase: started at 10.5 (decaying from the 12-spinner phase) and fell to about 3.7;
  - end: 4.9 / 6.3 / 7.7 at 00:16.
- No other heavy job ran. `ps` showed only the timed process during the idle phase.
- **Code (BASE `aae4084`):** `prototypes/p13_threads/` on branch `prototype/13-p1-threads`.
  - `patch_a1a3.py`, monkeypatched over `analysis.estimate_local_stripes`:
    - A1: a preallocated 5-response buffer, `np.abs(out=)`, `energy **= 2`, `max` instead of `take_along_axis`, and `best_response` set from `stripe[ai, r, c]` at the `better` pixels only;
    - A3: one `ThreadPoolExecutor` job per Period, at most `n` jobs in flight, merged serially in ascending Period order.
  - The other scripts: `timeit_p1.py`, `cli_p1.py`, `run_all.sh`, `identity.py`, `stages.py`.
- **Frames (400x1600):** m 0.5, scorched Mottle, `Emccd()`, 30 spikes. Seeds 601234 / 601240 are outside every registered range.
  - **worst** (the plan's Q3(a) frame): P3, A3. Breaks: π at (130, 500) tilted A+4°, and −2 rad at (280, 1100) tilted A−3°. One Fork at (200.5, 800.5). Found: 2 breaks, 1 Fork, 1 region.
  - **free:** P6, A−5, no breaks and no Forks. Found: 0 / 0, 1 region.
- **Timed region:** `read_frame(csv) → analyse → Report.to_json`, in a warm process after one untimed warm-up. Each cell is the median of 5 runs.
- **"base":** unpatched BASE code, single-threaded.

## Warm pipeline (read → analyse → to_json), median of 5, seconds

| frame | load | base | A1+A3 1 thr | 2 thr | 4 thr |
|---|---|---|---|---|---|
| worst P3 2b+1f | idle | 8.68 | 8.97 | 6.72 | **6.20** (min 5.48, max 6.75) |
| worst P3 2b+1f | 2 spinners | 10.85 | 10.52 | 8.03 | 7.03 |
| worst P3 2b+1f | 12 spinners | 19.79 | 18.41 | 13.35 | 11.33 |
| free P6 | idle | 7.31 | 7.61 | 5.02 | **3.95** (min 3.83, max 4.34) |
| free P6 | 2 spinners | 8.39 | 9.38 | 5.64 | 4.78 |
| free P6 | 12 spinners | 17.42 | 18.79 | 11.57 | 8.95 |

## Cold CLI, worst frame, wall time from process start to the report on disk, median of 5, seconds

`python -m denoisifier f.csv -o r.json`, or `cli_p1.py` with `THREADS=n`.

| load | base | A1+A3 1 thr | 4 thr |
|---|---|---|---|
| idle | 9.46 | 10.07 | **6.65** |
| 12 spinners | 22.22 | 25.00 | 14.71 |

The cold start adds about 0.4-0.5 s over the warm call (import plus the first call).

## Where the 4-thread time goes (worst frame, idle, `analyse` only, median of 3)

| stage | base | A1+A3 1 thr | 4 thr |
|---|---|---|---|
| bank `estimate_local_stripes` | 5.63 | 6.72 | 2.89 |
| `_with_phase_breaks` | 1.61 | 1.77 | 1.71 |
| `_qualifying_regions` | 0.35 | 0.41 | 0.37 |
| Fork searches (pre + post) | 0.39 | 0.37 | 0.37 |
| spikes + `_light` + other | 0.21 | 0.12 | 0.51 |
| **`analyse`** | **8.20** | **9.38** | **5.83** |

## Findings

1. **A3 scales worse than the plan's bank microbenchmark.** The bank goes 5.63 → 2.89 s at 4 threads (1.95x). The plan measured 2.6x, from 4.64 → 1.98 on its P6 frame (`bank.py`). Going from 2 to 4 threads gains only about 0.5 s on the full pipeline. The likely causes are memory bandwidth (each job streams about 70 MB of complex arrays) and turbo clocks dropping as cores wake up.
2. **The non-bank part of the worst frame is about 2.9 s and does not thread.** Of that, the break pass is 1.6-1.7 s. So even a free bank would leave the worst frame near 3 s, and 3.5 s idle is out of reach without C1.
3. **This machine ran 5-10 % slower than in the planner's runs.** BASE on the worst frame is 8.2-8.7 s here, against 7.9 s in the plan. The seed differs too. So treat the absolute numbers as ±10 %. The ratios stand.
4. **A1 as prototyped is slower at 1 thread** (+0.3 s pipeline, +1.1 s bank on the worst frame). That is because the per-Period job allocates a fresh (5, H, W) complex buffer and energy array in every Period. The plan's serial A1 reuses one buffer, and it measured −0.36 s. **Implementation note:** the threaded version needs per-worker reusable buffers (one set per thread, for example `threading.local`), or the 1-thread path should fall back to the plan's serial loop. This does not change the 4-thread conclusion much: allocation is a small part of 2.9 s.
5. **Load sensitivity:**
   - 2 busy cores slow everything by 15-25 %, BASE included. The worst frame at 4 threads goes 6.2 → 7.0 s, and the free frame 3.95 → 4.78 s.
   - 12 busy cores (SMT siblings shared) roughly double every time. The 4-thread run is still the fastest (11.3 s), but the target is lost.
   - A 5 s assertion inside `make check-slow` would therefore only hold on the free/P6-type frame, and only idle. This supports Q4(b) / O2-B (bench gates the target, idle).
6. **Bit-identity: all identical.**
   - The `Report.to_json()` text and `labels` (`array_equal`) are identical to BASE at 1, 2 and 4 threads, on both frames, idle and loaded.
   - The 5 `LocalStripes` arrays are `array_equal` to BASE at 1, 2, 4 and 16 threads, on both frames.
   - The cold CLI JSON is identical at base, 1 and 4 threads.

## Against P1's decision rule

- The worst frame at 4 threads, idle, is 6.2 s. That is above 4.5 s, so **C1 is required** for Q3(a). The estimate after C1 is about 4.9-5.2 s, which is not ≤ 3.5 s, so **Q4(b)**.
- If C1 is to be avoided, Q3(b) (a P6-type frame) gives 3.95 s idle with A1+A3. That is 21 % under 5 s, not 30 %, so it is still Q4(b).
- The loaded runs lose most of the gain (worst frame 11.3 s, free frame 9.0 s with 12 busy cores). Per P1, this reopens **Q1 / O1**: the 5 s claim holds only on an idle laptop with ≥ 4 free cores.
