# 03 plan: feasibility gate, weak stripes at 1% false alarms

Ticket: `.scratch/stripe-detector/issues/03-feasibility-gate-weak-stripes.md`. Base: `c0d99ab`.
Inputs read: spec, ADR 0001, GLOSSARY, issues 02/05/07/13, `.archived/02-plan.md` §4.4, `.archived/02-implementer-handoff.md` ("Flag for ticket 03").

**Revision 2.** This revision folds in `03-plan-review.md` and the owner's rulings:

- **Breaks:** B1-B4.
- **Owner rulings:** review O1-O5.
- **Notes:** N2, N3, N4, N5, N6 and N8.
- **Unchanged:** N1 and N7 (no change needed).
- **Evidence:** prototype P1, `03-prototype-p1.md`.

All design questions are now settled; §9 records the rulings.

## 1. Scope

In:
- a measurement of the **current** detector (`analyse` at c0d99ab), with no change to the detector;
- a small private statistics module;
- a driver that can run as a script or as slow tests;
- a written result next to the spec;
- the gate-fail path.

Out:
- Tuning the detector (§9 R1).
- Changing `analysis.THRESHOLD` (§9 R2).
- Partial Striped Regions in the generator (ticket 05).
- Stored thresholds and the false-alarm-rate option (ticket 07).
- Spikes (ticket 06).
- Speed work (ticket 13).

The measurement only uses `analyse(frame).score`, so `analyse` needs no change. A frame is "detected at threshold t" when `score > t`, the same rule `analyse` uses for its own verdict.

## 2. Evidence so far (planner pre-measurement and prototype P1)

Setup for all runs below:
- Current code, scorched mottle, `Emccd()` defaults, stripes covering the full frame.
- Period/Angle cycle over `CASES`.
- Laptop: AMD Ryzen AI 7 PRO 360 (8 cores / 16 threads), WSL2.

**Pre-measurement.** Script and raw output: `handoffs/03-premeasure.py` and `03-premeasure.txt`.

| Set | Shape | n | Scores |
|---|---|---|---|
| stripe-free, seeds 1000-1399 | 256×256 | 400 | median 22.0, empirical 99th percentile **61.0**, max 124.1 |
| m = 0.2, seeds 1000-1199 | 256×256 | 200 | min **69.8** (Period 3 / 10°); 200/200 above 61.0; 115/200 above THRESHOLD 154 |
| stripe-free, seeds 2000-2031 | 400×1600 | 32 | median 40.0, max 115.3 |
| one `analyse` call, single process | 400×1600 | 1 | 5.9 s |

**Prototype P1.** Files: `handoffs/03-prototype-p1.{md,py,json}`. Run at 400×1600: calibration seeds 50 000-50 299 (n = 300, threshold 128.95), held-out m = 0.2 seeds 60 000-60 099.

- **98/100 detected, exact CI (0.930, 0.998).**
- Both misses are at Period 3; Periods 3 and 4 together are 18/20.
- Single-process timing: median 6.24 s with the machine loaded, 5.3 s when quiet.
- Pool throughput: about 2.4 s wall per full frame (16 workers).

Consequences:
- Full-frame m = 0.2 is at or above about 95%, so under the owner's ruling the **gate is judged at 256×256**. A full-frame probe still runs, to inform the result (§3.4, §6).
- Period 3 is the weak case at both sizes. Carry this forward as a note for ticket 07.
- Timing passes the 10 s gate but misses the "under about 5 s" of spec user story 39 (N6). Record this for ticket 13.

## 3. Seams and files

```
src/denoisifier/_calibration.py     NEW  private: pure statistics on score arrays (07 may promote it)
tests/test_calibration.py           NEW  fast unit tests of the statistics
tests/cases.py                      NEW  shared CASES (N8); test_analyse.py imports it from here
tests/feasibility.py                NEW  gate driver: setup constants, batch scoring, timing, probe, main()
tests/test_feasibility_gate.py      NEW  slow tests, one per AC, on the real path
pyproject.toml                      register `slow` marker; addopts = "-m 'not slow'"
.scratch/stripe-detector/feasibility-gate.md    NEW  written result
.scratch/stripe-detector/feasibility-gate.json  NEW  raw numbers written by the driver
.scratch/stripe-detector/evidence/  NEW  P1 prototype + pre-measurement files moved here from handoffs/ (N4)
```

`_calibration` is private, but `tests/test_calibration.py` tests it directly. This is a deliberate exception to the 02 convention that tests never import private modules. The module is pure statistics with no detector internals, and the only alternative is testing it through a 15-minute slow run.

### 3.1 `denoisifier._calibration`

```python
def threshold_for_false_alarm_rate(scores: ArrayLike, rate: float) -> float
    """Order-statistic threshold: with n scores and k = floor(rate * (n + 1)),
    return the k-th largest score. If the scores are exchangeable, a new
    stripe-free frame exceeds it with probability k / (n + 1) (≈ rate).
    Raises ValueError if k < 1 (too few scores for this rate) or scores non-finite."""

def false_alarm_tolerance(n_calibration: int, n_held_out: int, rate: float,
                          level: float = 0.95) -> tuple[int, int]
    """Central interval of the held-out false-alarm COUNT, given a threshold set
    from n_calibration scores by the rule above. The distribution is
    d = betabinom(n_held_out, k, n_calibration + 1 - k), and the interval is
    (d.ppf((1-level)/2), d.ppf((1+level)/2)). Because the count is discrete,
    its exact coverage d.cdf(hi) - d.cdf(lo - 1) is >= level."""

def rate_interval(k: int, n: int, level: float = 0.95) -> tuple[float, float]
    """Clopper-Pearson (exact) interval for a binomial proportion:
    binomtest(k, n).proportion_ci(confidence_level=level, method="exact")  (B2)."""
```

Tests in `tests/test_calibration.py` (fast, test-first):
- Threshold on `arange(1, 2001)` at rate 0.01 → k = 20 → 1981.
- `ValueError` for 50 scores at rate 0.01 (k = 0), and for NaN input.
- `false_alarm_tolerance(2000, 1000, 0.01) == (3, 18)`. Its exact coverage is 0.967.
- `rate_interval(450, 500)` ≈ (0.8703, 0.9249) to 1e-3.
- Monte Carlo coverage (B1). Seeded, 2000 trials of uniform scores: draw 2000 calibration scores and 1000 held-out scores, set the threshold, count held-out exceedances. Let `mc` be the fraction of trials that fall inside `(lo, hi)`. With `d` the same beta-binomial, `exact = d.cdf(hi) - d.cdf(lo - 1)` and `sd = sqrt(exact * (1 - exact) / 2000)`. Assert `abs(mc - exact) <= 4 * sd` and `exact >= 0.95`.

### 3.2 `tests/cases.py` (N8)

Move `CASES` here from `test_analyse.py:15`, unchanged:

```python
CASES = [(3, 10), (5, 0), (8, 6), (12, -8), (20, -10), (4, -4), (16, 10), (6, -10), (10, 3), (14, -6)]
```

`test_analyse.py` and `feasibility.py` both use `from cases import CASES`.

### 3.3 `tests/feasibility.py` (driver)

It can be imported by the tests and run as `uv run python tests/feasibility.py`. Guard `main()` with `if __name__ == "__main__"`.

Constants (one place, used by the tests and the script):

```python
RATE = 0.01
TYPICAL = dict(mottle="scorched", noise=Emccd())   # ~100 photons at the peak, gain 300, read 50 e, cic 0.005
DEPTH = 0.2

# Gate (256x256)
SHAPE = (256, 256)
CALIBRATION_SEEDS = range(10_000, 12_000)       # 2000 stripe-free
HELD_OUT_FREE_SEEDS = range(20_000, 21_000)     # 1000 stripe-free
HELD_OUT_STRIPED_SEEDS = range(30_000, 30_500)  # 500 at m = 0.2, CASES[seed % 10] -> 50 per case

# Full-frame probe (400x1600, rows x cols), informs only unless below PROBE_MIN_RATE (§6)
PROBE_SHAPE = (400, 1600)
PROBE_CALIBRATION_SEEDS = range(70_000, 70_300)     # 300 -> k = 3
PROBE_FREE_SEEDS = range(71_000, 71_200)            # 200
PROBE_STRIPED_SEEDS = range(72_000, 72_100)         # 100, 10 per case
PROBE_MIN_RATE = 0.95

TIMING_SEED = 40_000   # one 400x1600 frame, m = 0.2, Period 8, Angle 0
```

All ranges must be disjoint from each other and from the seeds already used:
- 0-199 (tests and 02);
- 1000-1399 and 2000-2031 (pre-measurement);
- 50 000-50 299, 59 999 and 60 000-60 099 (P1).

Functions:
- **`score_batch(seeds, depth, shape, workers=None) -> np.ndarray`**
  - For each seed, call `generate(seed=s, shape=shape, period=p, angle_deg=a, modulation_depth=depth, **TYPICAL)` with `(p, a) = CASES[s % 10]`, then take `analyse(frame).score`.
  - Workers default to three quarters of the logical CPUs, `n - n // 4` with `n = os.cpu_count()` (12 of 16). Set `OMP/OPENBLAS/MKL_NUM_THREADS=1` in the workers, as P1 did.
  - Use `ProcessPoolExecutor.map`, which keeps the order, so results are deterministic whatever the worker count.
  - Stripe-free frames also take a Period/Angle, which does not change them (N3). The generator always draws `phase0` (profile, phase0, mottle, noise), so the RNG stream is the same, and `m = 0` multiplies `cos(phase)` by zero.
- **`time_full_frame(repeats=3) -> list[float]`**
  - Generate the 400×1600 frame first (not timed).
  - Make one warm-up `analyse` call on a 256×256 frame.
  - Time `analyse(frame)` 3 times with `time.perf_counter` in a single process, with no pool running.
- **`measure(cal_seeds, free_seeds, striped_seeds, shape) -> RateResult`**, frozen dataclass. Order:
  1. Score `cal_seeds` at m = 0.
  2. Set the threshold with `threshold_for_false_alarm_rate`.
  3. Only then score the held-out sets.

  Contents:
  - threshold, k, calibration count above it;
  - held-out free: n, false-alarm count, rate, `rate_interval`, `false_alarm_tolerance`;
  - striped: n, detected count, rate, `rate_interval`;
  - per case: detected/n, minimum score, minimum / threshold.

  `measure_gate()` and `measure_probe()` call it with the gate and probe constants.
- **`run_info() -> dict`**
  - commit from `git describe --always --dirty` (N5), so a run on a dirty tree shows;
  - CPU model from `/proc/cpuinfo`;
  - Python, NumPy and SciPy versions;
  - all seed ranges and settings.
- **`main()`**
  1. Run the timing first.
  2. Run `measure_gate()`, then `measure_probe()`.
  3. Write `ROOT / ".scratch/stripe-detector/feasibility-gate.json"`, with `ROOT = Path(__file__).resolve().parents[1]` (N5). `--out` overrides the path.
  4. Print a markdown table.

  Flags:
  - `--skip-probe` for a quick re-run;
  - `--workers N`.

### 3.4 `tests/test_feasibility_gate.py`

| AC | Test | Marker | Assertion |
|---|---|---|---|
| 1 threshold only on calibration seeds | `test_seed_sets_are_disjoint_and_unused` | not slow | All gate and probe ranges are pairwise disjoint and disjoint from the used seeds listed in §3.3. Sizes are as stated. |
| 1 (path) | built into `measure` (§3.3 order) | — | The threshold comes from the calibration scores alone. |
| 4 1600×400 ≤ 10 s | `test_full_frame_is_analysed_within_10_s` | slow | Median of 3 `<= 10.0`. Placed first in the file, so no pool is running. |
| 2 held-out FA ≈ 1% | `test_held_out_false_alarm_rate_is_about_one_percent` | slow | `lo <= fa_count <= hi`, with `false_alarm_tolerance(2000, 1000, 0.01)` = (3, 18). |
| 3 m = 0.2 ≥ 90% | `test_weak_stripes_are_detected_at_least_90_percent` | slow | `detected / 500 >= 0.90` (point estimate, R4). The failure message includes the exact CI and the per-case rates. |
| 3 (full-frame condition, B3) | `test_full_frame_probe_detects_at_least_95_percent` | slow | `probe detected / 100 >= 0.95`. Its false-alarm count is recorded but not asserted (B4). |
| 6 repeatable, slow | all slow tests above, plus `python tests/feasibility.py` | slow | — |

Module-scoped fixtures run the batches once:
- `gate = measure_gate()`;
- `probe = measure_probe()`.

AC 5 (the written result) and AC 7 (status on fail) are implementer steps (§5, §6).

Cost on this laptop:
- gate: 3500 frames at 256×256, about 10-20 min;
- probe: 600 frames at 400×1600 × about 2.4 s, about 24 min;
- timing: about 25 s.

The whole slow run takes about 35-45 min. `-m 'not slow'` keeps the default suite at about 80 s.

## 4. Statistics behind the batch sizes

**Gate calibration, n = 2000.**
- k = 20, so the threshold is the 20th-largest score.
- The threshold's true false-alarm rate follows Beta(20, 1982): mean 1.0%, sd 0.22%.

**Gate held-out stripe-free, n = 1000.**
- Expected false alarms: 10.
- The plain binomial 95% `ppf` region at p = 0.01 is **4-17** (coverage 0.976, N2). It ignores the calibration noise.
- The beta-binomial interval **3-18** (exact coverage 0.967) covers both calibration and held-out noise. This is the "binomial tolerance" asserted.
- Report both in the doc.

**Gate held-out m = 0.2, n = 500 (50 per case).**
- Clopper-Pearson half-width is about ±1.6% at a rate of 0.95.
- 450/500 gives (0.870, 0.925).
- Per case, about ±8%, enough to name a weak Period.

**Probe, n = 300 / 200 / 100.**
- Threshold k = 3; its false-alarm rate follows Beta(3, 298), 95% range 0.2-2.4% (P1).
- Held-out false-alarm tolerance: `betabinom(200, 3, 298)` 95% = **0-6**, exact coverage 0.976.
  - A count of zero passes, so this check **cannot show "about 1%"** at full frame.
  - The doc labels it uninformative and gives the band (B4).
- Detection at n = 100:
  - 95/100 gives CI (0.887, 0.984);
  - 98/100 gives CI (0.930, 0.998), as in P1.
- The probe is kept small on purpose (owner, B4): it confirms P1, it does not calibrate.

**Timing.** Median of 3 single-process runs. P1's quiet and loaded runs (5.3 s and 6.2 s) are both well inside 10 s.

## 5. Written result (`.scratch/stripe-detector/feasibility-gate.md`)

Written by the implementer from the JSON. Contents:

1. **Verdict.** One line: PASS or FAIL, with the per-gate status: detection 256×256, false alarms 256×256, timing, full-frame probe ≥ 95%.
2. **Setup.**
   - Shapes, generator settings, `CASES`.
   - Run info from `run_info()`, with a clean, committed tree.
3. **Seed ranges** for the gate and the probe, plus the used ranges they avoid.
4. **Gate.**
   - Threshold and k.
   - Held-out false alarms: count/n, rate, exact CI, both tolerance bands.
   - m = 0.2: count/n, exact CI, and a per-case table (rate, minimum score, minimum / threshold).
   - Mark it "marginal" if the CI straddles 0.90.
5. **Full-frame probe.**
   - Threshold and k.
   - m = 0.2 count/n with its exact CI, and the per-case table.
   - False-alarm count, labelled **"uninformative: tolerance 0-6 includes 0"**.
   - The P1 result as prior evidence (`evidence/03-prototype-p1.md`).
6. **Timing.**
   - Median and all runs.
   - Note that the 10 s gate is met but spec user story 39 asks for about 5 s, which is ticket 13 (N6).
7. **Weak spots.** Period 3 (and 4) margins at both sizes, as a note for ticket 07.
8. **Caveats.**
   - The threshold depends on frame size: the 1% threshold at 256×256 differs from the one at 400×1600.
   - Neither threshold replaces `analysis.THRESHOLD = 154` (R2).
9. **Re-run.**
   - `uv run python tests/feasibility.py`
   - `uv run pytest -m slow tests/test_feasibility_gate.py`
10. **Evidence (N4).**
    - Move `handoffs/03-prototype-p1.{md,py,json}` and `handoffs/03-premeasure.{py,txt}` to `.scratch/stripe-detector/evidence/`, and link them.
    - Handoffs get archived, so the evidence must not live there.

Commit the JSON and the evidence files along with the code.

## 6. Pass and fail paths

**PASS** needs all of:
- gate m = 0.2 point estimate ≥ 0.90 (R4);
- gate held-out false alarms inside 3-18;
- timing median ≤ 10 s;
- probe m = 0.2 ≥ 0.95 (B3).

On PASS:
1. Tick the ACs.
2. The doc says PASS and includes the probe numbers and its uninformative false-alarm band.
3. The ticket status stays as the orchestrator sets it.

**FAIL** is any of:
- gate detection < 0.90;
- timing > 10 s;
- probe detection < 0.95 (B3), even if the 256×256 gate passes.

Gate false alarms outside 3-18 means the measurement is broken. Handle it on the same path, and name it as such.

On FAIL:
1. Do **not** tune the detector, change seeds or re-run to get a pass (R1).
2. Still commit the measurement code, the JSON, the evidence and the result doc.
3. In the doc:
   - Mark each failing check FAIL. If the probe failed, add a "Why this is a fail" paragraph: the owner's ruling makes full-frame m = 0.2 below 95% a gate fail, because experimenter frames are full-sensor (spec user stories 34 and 39).
   - Rank the likely causes using the per-case tables. The candidates:
     - short Periods (3-4 px) score lowest;
     - the per-frame maximum over pixels gives the stripe-free scores a heavy tail, which grows with frame area;
     - the box window and bank widths (`_ACROSS` 1.0p, `_ALONG` 1.5p);
     - the `_A0` floor.
   - List the owner's options: accept a lower rate, raise the minimum m, or change the method.
4. Mark each failing gate test with `@pytest.mark.xfail(strict=True, reason="03 gate failed: see .scratch/stripe-detector/feasibility-gate.md")`. With `strict=True` the test turns red once a later change makes it pass, and then someone has to remove the marker.
5. Set `Status: ready-for-human` in the ticket, and append a `## Comments` entry with the headline numbers and the doc pointer.
6. Ticket 05 (and so 04 onward) stays blocked.

## 7. TDD order

1. `tests/test_calibration.py` → `_calibration.py`: threshold rule, tolerance, interval, then the Monte Carlo coverage (B1).
2. Move `CASES` to `tests/cases.py`. The existing suite must stay green.
3. In `pyproject.toml`, register `slow` under `markers` (needed under `-W error`) and set `addopts = "-m 'not slow'"`. Then write `test_seed_sets_are_disjoint_and_unused` → the constants in `feasibility.py`.
4. The timing test → `time_full_frame`.
5. The gate rate tests → `score_batch`, `measure`, `measure_gate`.
6. The probe test → `measure_probe`.
7. `main()` → JSON. Commit the code first, so `git describe` is clean. Run `main()`, write the doc, move the evidence files, then follow §6.
8. Run `uv run pytest -W error` (the slow tests are skipped by default), then `uv run pytest -W error -m slow`, then `mypy` as in 02.

## 8. Conventions

- Use glossary terms: Stripe-free, False Alarm, Threshold, Stripe Score, Modulation Depth, Period, Angle.
- "Calibration seeds" and "held-out seeds" are spec wording, not glossary terms. Leave the glossary alone.
- "Detection rate" is plain wording for the fraction of m = 0.2 frames scoring above the threshold. It is not a glossary term.

## 9. Settled decisions (were open questions in revision 1)

- **R1. No tuning in 03.** Measure the detector as it is. The ticket says "do not push on" (review N1).
- **R2. `analysis.THRESHOLD` stays 154.** The calibrated thresholds live only in the doc and the JSON. Ticket 07 owns the stored threshold (N1).
- **R3. Frame size** (owner, review O1):
  - The gate is judged at 256×256, because P1 measured full-frame m = 0.2 at 98% (≥ about 95%).
  - A small full-frame probe still runs and informs the result.
  - If the probe falls below 95% in the final run, that is a gate fail (B3).
- **R4. "At least 90%"** means the point estimate ≥ 0.90, with the exact Clopper-Pearson CI reported (owner, review O4).
- **R5. Statistics module.** It is private: `denoisifier._calibration` (owner, review O2).
- **R6. Failed gate tests** get `xfail(strict=True)` with a reason pointing at the result doc (owner, review O3).
- **R7. Slow tests.** Register `slow` and set `addopts = "-m 'not slow'"`. Run the slow tests with `-m slow` (owner, review O5).
- **R8. Stripe range.** The m = 0.2 sets use the fixed `CASES`, shared from `tests/cases.py`. The rate is pooled over the cases, and each case is reported (N1, N8).
