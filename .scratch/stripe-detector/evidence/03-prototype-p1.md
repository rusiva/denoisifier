# 03 prototype P1: m = 0.2 at full frame (400×1600)

Question (plan review P1): at full frame 400×1600, does m = 0.2 clear 90% detection at its own 1% false-alarm threshold, set on separate calibration seeds?

**Verdict: clear PASS.** 98/100 detected, exact 95% CI **0.930 to 0.998**. The CI lower bound is above 0.90. All misses and near-misses are at Period 3 and 4.

Under the review's O1 rule ("B if full-frame m = 0.2 is below about 95%, otherwise A"), the 98% point estimate points to **A**. The CI lower bound (0.93) is below 0.95, so the evidence for A is the point estimate, not a margin.

## Setup

- Detector `analyse(frame).score` at c0d99ab, unchanged. A frame counts as detected when `score > threshold`.
- `generate(seed, shape=(400, 1600), period, angle_deg, modulation_depth, mottle="scorched", noise=Emccd())`. The shape is rows × cols: the sensor is 1600 wide and 400 tall. The stripes cover the full frame.
- Period/Angle come from `CASES[seed % 10]`, copied from `test_analyse.CASES`. That gives 10 frames per case.
- Threshold rule (plan §3.1): k = floor(0.01 · (n + 1)), and the threshold is the k-th largest calibration score.
- Machine: AMD Ryzen AI 7 PRO 360 (8C/16T), WSL2, Python 3.11.15, `.venv` SciPy 1.17.1.
- Pool: 16 `ProcessPoolExecutor` workers with `OMP/OPENBLAS/MKL_NUM_THREADS=1`. Another session's pytest was running during the run (load average about 19).
- Run command: `PYTHONPATH=src OMP_NUM_THREADS=1 python 03-prototype-p1.py 300 100 16`. Raw per-frame output: `03-prototype-p1.json`.

## Seeds

These ranges are fresh. They are disjoint from 0-199 (02), 1000-1399 and 2000-2031 (plan §2), and 10 000-40 000 (the plan §3.2 gate ranges).

- Calibration, stripe-free (m = 0): **50 000-50 299** (n = 300).
- Held-out, m = 0.2: **60 000-60 099** (n = 100). These were scored only after the threshold was fixed.
- Timing frame: seed 59 999, m = 0.2, Period 8, Angle 0.

## Threshold and null-score tail

The threshold is k = 3, the 3rd largest of 300: **128.95**. The true false-alarm rate of a threshold set this way follows Beta(3, 298), with 95% range **0.21% to 2.39%**. A threshold from 300 frames is noisy, which is why the sensitivity table below exists.

| Stripe-free n = 300 | Score |
|---|---|
| median | 36.7 |
| 90th percentile | 60.3 |
| 95th percentile | 72.1 |
| 98th percentile | 95.7 |
| 99th percentile (interpolated) | 117.1 |
| top 10 | 153.5 (seed 50118), 141.4 (50244), 129.0 (50097), 117.0 (50083), 104.8 (50233), 98.8, 95.6, 90.7, 90.2, 82.9 |

The tail is heavy: the median is 37, while the top 1% runs from 117 to 154. This agrees with plan §2, where the full-frame stripe-free maximum of 32 frames was 115.3.

## Detection, m = 0.2

At the threshold 128.95: **98/100 = 0.98, Clopper-Pearson 95% CI (0.930, 0.998).**

The m = 0.2 scores have minimum 99.7, 5th percentile 148.1, 10th percentile 175.8, and median 324.5.

Sensitivity to the threshold, using neighbouring order statistics of the same calibration set:

| Threshold | Order stat | Detected | 95% CI |
|---|---|---|---|
| 117.0 | k = 4 | 99 | 0.946-1.000 |
| **128.95** | **k = 3 (the rule)** | **98** | **0.930-0.998** |
| 141.4 | k = 2 | 95 | 0.887-0.984 |
| 153.5 | k = 1 (max of 300, about 0.3% FA) | 92 | 0.848-0.965 |

Even at the stricter end of the threshold's plausible range, about 0.3% FA, the point estimate stays above 0.90. The CI straddles 0.90 only at that extreme.

### Per Period/Angle (n = 10 each, threshold 128.95)

| Case | Detected | Minimum | Median | Minimum / threshold |
|---|---|---|---|---|
| P3 / 10° | **8/10** | **99.7** | 159.5 | **0.77** |
| P4 / −4° | 10/10 | 136.5 | 185.9 | **1.06** |
| P5 / 0° | 10/10 | 199.4 | 240.4 | 1.55 |
| P6 / −10° | 10/10 | 195.3 | 257.8 | 1.51 |
| P8 / 6° | 10/10 | 292.6 | 354.7 | 2.27 |
| P10 / 3° | 10/10 | 227.6 | 350.1 | 1.76 |
| P12 / −8° | 10/10 | 270.8 | 358.7 | 2.10 |
| P14 / −6° | 10/10 | 349.9 | 563.7 | 2.71 |
| P16 / 10° | 10/10 | 370.5 | 460.7 | 2.87 |
| P20 / −10° | 10/10 | 328.7 | 462.1 | 2.55 |

The two misses are seeds 60030 (score 99.7) and 60090 (128.2), both Period 3. The 10 lowest m = 0.2 scores all come from Period 3 or Period 4. Period 3 and 4 together score 18/20 = 90%. The pooled pass comes from Periods 5 to 20, all at 1.5× the threshold or more. Period 3 is the weak spot at full frame, as it was at 256×256.

## Timing

- Single-process `analyse` on one 400×1600 frame, after a warm-up on 256×256, with generation not timed: **6.23, 6.24, 6.39 s** (median 6.24 s). Another session's pytest was loading the machine at the time. An earlier smoke run on a quieter machine gave 5.36, 5.27, 5.24 s. Both pass the 10 s gate and miss the about-5 s user story (review N6).
- Throughput with the 16-worker pool: 400 frames in 942.6 s wall, about **2.36 s per frame**. Calibration took 688 s and the striped set 254 s. Generation is included.
- Inside a worker, one `analyse` call took 36 s at the median (p90 40.8 s, max 45.5 s). That is 16 processes contending for 8 cores and memory bandwidth, so it is not a per-frame cost. Use the single-process number for the gate and the throughput number for sizing batches.
- Sizing for O1 option B: 3500 full frames at about 2.4 s each is about **2.3 h** on this laptop.

## Caveats

- n = 100 striped frames and 300 calibration frames. The CI lower bound clears 0.90, so the run was not enlarged. The threshold's own noise (FA 0.2-2.4%) is the larger uncertainty. The sensitivity table bounds its effect.
- Only 10 frames per case, so per-case rates are about ±20%. Period 3's 8/10 is a signal, not a measured rate.
- The held-out false-alarm rate was not measured. It was not part of P1.
