# Feasibility gate: weak stripes at 1% False Alarms (ticket 03)

**Verdict: PASS.**

| Check | Gate | Measured | Status |
|---|---|---|---|
| Detection, m = 0.2, 256×256 | ≥ 0.90 (point estimate) | 500/500 = **1.000**, exact 95% CI (0.993, 1.000) | PASS |
| Held-out False Alarms, 256×256 | 3-18 of 1000 | **12/1000** = 1.2%, exact 95% CI (0.6%, 2.1%) | PASS |
| Time for one 400×1600 frame | ≤ 10 s (median of 3) | **5.73 s** (5.73, 5.79, 5.59) | PASS |
| Full-frame probe, m = 0.2, 400×1600 | ≥ 0.95 (plan B3) | 100/100 = **1.000**, exact 95% CI (0.964, 1.000) | PASS |

Re-measured for ticket 05 (Striped Regions; the score is now the highest peak ratio of a size-qualifying region) at `317744b`, no tuning on these seeds. Ticket 03's first measurement (detector `c0d99ab`, measuring code `f0c8f6c`) is in git history: detection 490/500, held-out False Alarms 7/1000, Thresholds 74.12 and 105.80, 7.56 s. Raw numbers: [`feasibility-gate.json`](feasibility-gate.json).

## Setup

- Detected at Threshold t means `analyse(frame).score > t`, the rule `analyse` uses for its own verdict.
- Frames: `generate(seed, shape, period, angle_deg, modulation_depth, mottle="scorched", noise=Emccd())`. `Emccd()` defaults: 100 photons at the peak, EM gain 300, read noise 50 e, spurious charge 0.005. Stripes cover the full frame (the profile core included).
- Period and Angle come from `CASES[seed % 10]` in `tests/cases.py`: (3, 10°), (5, 0°), (8, 6°), (12, −8°), (20, −10°), (4, −4°), (16, 10°), (6, −10°), (10, 3°), (14, −6°). Stripe-free frames (m = 0) take a case too; it does not change them.
- Threshold rule: with n Stripe-free calibration scores, k = floor(0.01 · (n + 1)), and the Threshold is the k-th largest score. A new Stripe-free frame then exceeds it with probability k / (n + 1) ≈ 1%.
- The Threshold is set on the calibration seeds alone. The held-out sets are scored only afterwards, against that fixed Threshold.
- Run info: commit `317744b` (clean for `src`, `tests`, `pyproject.toml`, `uv.lock`); AMD Ryzen AI 7 PRO 360 (8 cores, 16 threads), WSL2; Python 3.11.15, NumPy 2.4.6, SciPy 1.17.1; 12 worker processes, single-threaded BLAS/OpenMP in each.

## Seeds

| Set | Shape | Seeds | n |
|---|---|---|---|
| Gate calibration, Stripe-free | 256×256 | 10 000-11 999 | 2000 |
| Gate held-out, Stripe-free | 256×256 | 20 000-20 999 | 1000 |
| Gate held-out, m = 0.2 | 256×256 | 30 000-30 499 | 500 (50 per case) |
| Probe calibration, Stripe-free | 400×1600 | 70 000-70 299 | 300 |
| Probe held-out, Stripe-free | 400×1600 | 71 000-71 199 | 200 |
| Probe held-out, m = 0.2 | 400×1600 | 72 000-72 099 | 100 (10 per case) |
| Timing frame, m = 0.2, Period 8, Angle 0 | 400×1600 | 40 000 | 1 |

These ranges are disjoint from each other and from every seed used before: 0-199 (tests and ticket 02), 1000-1399 and 2000-2031 (planner pre-measurement), 50 000-50 299, 59 999 and 60 000-60 099 (prototype P1). `test_seed_sets_are_disjoint_and_unused` checks this.

## Gate (256×256)

- Threshold **49.72**: k = 20, the 20th largest of 2000 calibration scores (19 calibration scores lie above it). Its true False Alarm rate follows Beta(20, 1982): mean 1.0%, 95% range 0.61-1.48%.
- Held-out False Alarms: **12/1000 = 1.2%**, exact 95% CI (0.62%, 2.09%).
  - Beta-binomial tolerance `betabinom(1000, 20, 1982)`, covering calibration and held-out noise: **3-18** (exact coverage 0.967). This is the band the test asserts.
  - Plain binomial band at p = 0.01, ignoring calibration noise: 4-17.
  - 12 is inside both.
- m = 0.2: **500/500 = 1.000**, exact 95% CI **(0.993, 1.000)**. The whole CI is above 0.90, so the pass is not marginal.

| Period | Angle | Detected | Min score | Min / Threshold |
|---|---|---|---|---|
| 3 | 10 | 50/50 | 66.4 | **1.34** |
| 4 | −4 | 50/50 | 77.5 | 1.56 |
| 5 | 0 | 50/50 | 102.4 | 2.06 |
| 6 | −10 | 50/50 | 108.9 | 2.19 |
| 8 | 6 | 50/50 | 96.8 | 1.95 |
| 10 | 3 | 50/50 | 112.5 | 2.26 |
| 12 | −8 | 50/50 | 104.9 | 2.11 |
| 14 | −6 | 50/50 | 105.7 | 2.13 |
| 16 | 10 | 50/50 | 116.7 | 2.35 |
| 20 | −10 | 50/50 | 67.4 | **1.36** |

The striped frames' minimum scores barely moved from ticket 03 (8/10 cases identical to 0.1); the Threshold fell because Stripe-free frames now score only on size-qualifying regions.

## Full-frame probe (400×1600)

- Threshold **85.17**: k = 3, the 3rd largest of 300. Its true False Alarm rate follows Beta(3, 298), 95% range 0.2-2.4%. (Ticket 03: 105.80; P1: 128.95 on other seeds; a k = 3 threshold is noisy.)
- m = 0.2: **100/100**, exact 95% CI **(0.964, 1.000)**. Above the 0.95 cut (plan B3). With n = 100 the cut is itself noisy: a true rate of 0.97 falls below 95/100 about 8% of the time (review N9).
- Held-out False Alarms: 2/200 = 1.0%, exact 95% CI (0.1%, 3.6%). **Uninformative: tolerance 0-6 includes 0**, so this count cannot show "about 1%" at full frame. Recorded, not asserted.
- Prior evidence: prototype P1 ([`evidence/03-prototype-p1.md`](evidence/03-prototype-p1.md)) gave 98/100, CI (0.930, 0.998), at its own threshold of 128.95. Its two misses were Period 3.

| Period | Angle | Detected | Min score | Min / Threshold |
|---|---|---|---|---|
| 3 | 10 | 10/10 | 116.1 | **1.36** |
| 4 | −4 | 10/10 | 151.6 | 1.78 |
| 5 | 0 | 10/10 | 185.8 | 2.18 |
| 6 | −10 | 10/10 | 191.4 | 2.25 |
| 8 | 6 | 10/10 | 254.2 | 2.98 |
| 10 | 3 | 10/10 | 264.7 | 3.11 |
| 12 | −8 | 10/10 | 232.2 | 2.73 |
| 14 | −6 | 10/10 | 297.6 | 3.49 |
| 16 | 10 | 10/10 | 303.7 | 3.57 |
| 20 | −10 | 10/10 | 308.4 | 3.62 |

## Timing

- `analyse` on one 400×1600 frame, single process, no pool running, generation and a 256×256 warm-up not timed: **5.73, 5.79, 5.59 s, median 5.73 s** (ticket 03: 7.56 s; P1 5.2-6.4 s on the same laptop; the machine load differs between runs).
- The 10 s gate is met. Spec user story 39 asks for "under about 5 seconds"; that is not met and belongs to ticket 13 (speed budget).

## Weak spots (for ticket 07)

- **Period 3** is the weakest case at both sizes: lowest margin at 256×256 (1.34 ×; ticket 03 missed 8/50 there) and at full frame (1.36 ×), and both of P1's misses. Period 4 is next.
- **Period 20** at 256×256 has the next-lowest margin (1.36 ×; ticket 03 missed 2/50), though it is wide at full frame (3.62 ×). Likely cause: a 256-px frame holds only about 12 cycles of Period 20, part of them in the dim surround of the profile, so long Periods have less support in small frames. Not investigated.
- Likely cause for Period 3 (not investigated): few pixels per cycle, so each cycle averages less EMCCD noise away, and the box window and bank widths are set in units of the Period.

## Caveats

- The Threshold depends on frame size: the 1% Threshold is 49.72 at 256×256 and 85.17 at 400×1600 (ticket 03's score: 74.12 and 105.80-128.95). The per-frame maximum over pixels gives the Stripe-free scores a heavier tail in larger frames.
- Neither Threshold replaces `analysis.THRESHOLD = 154`, which stays provisional (ticket 07 stores a calibrated one). At 154, many m = 0.2 frames would not be Striped (pre-measurement: 115/200 above 154 at 256×256; P1: 92/100 above 153.5 at full frame).
- Only scorched Mottle at about 100 photons at the peak was measured, with stripes covering the whole frame. Partial Striped Regions (ticket 05) are evaluated in `region-calibration.json` and `region-evaluation-2.json`, not here.

## Re-run

- `uv run python tests/feasibility.py` (about 39 min on this laptop; `--skip-probe` for the timing and 256×256 gate only; `--workers N`; `--out PATH`). It rewrites `feasibility-gate.json`.
- `tests/test_feasibility_gate.py` checks the gates against the saved `feasibility-gate.json` in the default suite, and fails if the seed plan or frame shapes have changed since it was measured or it came from a dirty tree.

## Evidence

Moved here from the handoffs folder, which gets archived:

- [`evidence/03-prototype-p1.md`](evidence/03-prototype-p1.md), [`.py`](evidence/03-prototype-p1.py), [`.json`](evidence/03-prototype-p1.json): prototype P1, full-frame m = 0.2 at its own 1% threshold.
- [`evidence/03-premeasure.py`](evidence/03-premeasure.py), [`.txt`](evidence/03-premeasure.txt): planner pre-measurement.
