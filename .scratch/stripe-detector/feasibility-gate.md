# Feasibility gate: weak stripes at 1% False Alarms (ticket 03)

**Verdict: PASS.**

| Check | Gate | Measured | Status |
|---|---|---|---|
| Detection, m = 0.2, 256×256 | ≥ 0.90 (point estimate) | 490/500 = **0.980**, exact 95% CI (0.964, 0.990) | PASS |
| Held-out False Alarms, 256×256 | 3-18 of 1000 | **7/1000** = 0.7%, exact 95% CI (0.3%, 1.4%) | PASS |
| Time for one 400×1600 frame | ≤ 10 s (median of 3) | **7.56 s** (7.72, 7.56, 7.14) | PASS |
| Full-frame probe, m = 0.2, 400×1600 | ≥ 0.95 (plan B3) | 100/100 = **1.000**, exact 95% CI (0.964, 1.000) | PASS |

The detector was measured as it is at `c0d99ab` (no tuning); the measuring code is at `f0c8f6c`. Raw numbers: [`feasibility-gate.json`](feasibility-gate.json).

## Setup

- Detected at Threshold t means `analyse(frame).score > t`, the rule `analyse` uses for its own verdict.
- Frames: `generate(seed, shape, period, angle_deg, modulation_depth, mottle="scorched", noise=Emccd())`. `Emccd()` defaults: 100 photons at the peak, EM gain 300, read noise 50 e, spurious charge 0.005. Stripes cover the full frame (the profile core included).
- Period and Angle come from `CASES[seed % 10]` in `tests/cases.py`: (3, 10°), (5, 0°), (8, 6°), (12, −8°), (20, −10°), (4, −4°), (16, 10°), (6, −10°), (10, 3°), (14, −6°). Stripe-free frames (m = 0) take a case too; it does not change them.
- Threshold rule: with n Stripe-free calibration scores, k = floor(0.01 · (n + 1)), and the Threshold is the k-th largest score. A new Stripe-free frame then exceeds it with probability k / (n + 1) ≈ 1%.
- The Threshold is set on the calibration seeds alone. The held-out sets are scored only afterwards, against that fixed Threshold.
- Run info: commit `f0c8f6c` (clean for `src`, `tests`, `pyproject.toml`, `uv.lock`); AMD Ryzen AI 7 PRO 360 (8 cores, 16 threads), WSL2; Python 3.11.15, NumPy 2.4.6, SciPy 1.17.1; 8 worker processes, single-threaded BLAS/OpenMP in each.

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

- Threshold **74.12**: k = 20, the 20th largest of 2000 calibration scores (19 calibration scores lie above it). Its true False Alarm rate follows Beta(20, 1982): mean 1.0%, 95% range 0.61-1.48%.
- Held-out False Alarms: **7/1000 = 0.7%**, exact 95% CI (0.28%, 1.44%).
  - Beta-binomial tolerance `betabinom(1000, 20, 1982)`, covering calibration and held-out noise: **3-18** (exact coverage 0.967). This is the band the test asserts.
  - Plain binomial band at p = 0.01, ignoring calibration noise: 4-17.
  - 7 is inside both.
- m = 0.2: **490/500 = 0.980**, exact 95% CI **(0.964, 0.990)**. The whole CI is above 0.90, so the pass is not marginal.

| Period | Angle | Detected | Min score | Min / Threshold |
|---|---|---|---|---|
| 3 | 10 | **42/50** | 66.4 | **0.90** |
| 4 | −4 | 50/50 | 77.5 | 1.05 |
| 5 | 0 | 50/50 | 102.4 | 1.38 |
| 6 | −10 | 50/50 | 108.9 | 1.47 |
| 8 | 6 | 50/50 | 98.1 | 1.32 |
| 10 | 3 | 50/50 | 112.5 | 1.52 |
| 12 | −8 | 50/50 | 104.9 | 1.42 |
| 14 | −6 | 50/50 | 114.9 | 1.55 |
| 16 | 10 | 50/50 | 116.7 | 1.57 |
| 20 | −10 | **48/50** | 67.4 | **0.91** |

## Full-frame probe (400×1600)

- Threshold **105.80**: k = 3, the 3rd largest of 300. Its true False Alarm rate follows Beta(3, 298), 95% range 0.2-2.4%. It is well below P1's 128.95 from other seeds, which shows how noisy a k = 3 threshold is.
- m = 0.2: **100/100**, exact 95% CI **(0.964, 1.000)**. Above the 0.95 cut (plan B3). With n = 100 the cut is itself noisy: a true rate of 0.97 falls below 95/100 about 8% of the time (review N9).
- Held-out False Alarms: 3/200 = 1.5%, exact 95% CI (0.3%, 4.3%). **Uninformative: tolerance 0-6 includes 0**, so this count cannot show "about 1%" at full frame. Recorded, not asserted.
- Prior evidence: prototype P1 ([`evidence/03-prototype-p1.md`](evidence/03-prototype-p1.md)) gave 98/100, CI (0.930, 0.998), at its own threshold of 128.95. Its two misses were Period 3.

| Period | Angle | Detected | Min score | Min / Threshold |
|---|---|---|---|---|
| 3 | 10 | 10/10 | 116.1 | **1.10** |
| 4 | −4 | 10/10 | 151.6 | 1.43 |
| 5 | 0 | 10/10 | 185.8 | 1.76 |
| 6 | −10 | 10/10 | 191.4 | 1.81 |
| 8 | 6 | 10/10 | 254.2 | 2.40 |
| 10 | 3 | 10/10 | 264.7 | 2.50 |
| 12 | −8 | 10/10 | 232.2 | 2.20 |
| 14 | −6 | 10/10 | 297.6 | 2.81 |
| 16 | 10 | 10/10 | 303.7 | 2.87 |
| 20 | −10 | 10/10 | 308.4 | 2.91 |

## Timing

- `analyse` on one 400×1600 frame, single process, no pool running, generation and a 256×256 warm-up not timed: **7.72, 7.56, 7.14 s, median 7.56 s**. P1 measured 5.2-6.4 s on the same laptop.
- The 10 s gate is met. Spec user story 39 asks for "under about 5 seconds"; that is not met and belongs to ticket 13 (speed budget).

## Weak spots (for ticket 07)

- **Period 3** is the weakest case at both sizes: 42/50 at 256×256 (min 0.90 × Threshold), lowest margin at full frame (1.10 ×), and both of P1's misses. Period 4 is next (1.05 × at 256×256).
- **Period 20** at 256×256 missed 2/50 (min 0.91 ×), though it has a wide margin at full frame (2.91 ×). Likely cause: a 256-px frame holds only about 12 cycles of Period 20, part of them in the dim surround of the profile, so long Periods have less support in small frames. Not investigated.
- Likely cause for Period 3 (not investigated): few pixels per cycle, so each cycle averages less EMCCD noise away, and the box window and bank widths are set in units of the Period.

## Caveats

- The Threshold depends on frame size: the 1% Threshold is 74.12 at 256×256 and about 106-129 at 400×1600. The per-frame maximum over pixels gives the Stripe-free scores a heavier tail in larger frames.
- Neither Threshold replaces `analysis.THRESHOLD = 154`, which stays provisional (ticket 07 stores a calibrated one). At 154, many m = 0.2 frames would not be Striped (pre-measurement: 115/200 above 154 at 256×256; P1: 92/100 above 153.5 at full frame).
- Only scorched Mottle at about 100 photons at the peak was measured, with stripes covering the whole frame. Partial Striped Regions are ticket 05.

## Re-run

- `uv run python tests/feasibility.py` (about 39 min on this laptop; `--skip-probe` for the timing and 256×256 gate only; `--workers N`; `--out PATH`). It rewrites `feasibility-gate.json`.
- `uv run pytest -W error -m slow tests/test_feasibility_gate.py` runs the same measurement as tests (slow tests are skipped by default). At `ffffbed` (12 worker processes) all 4 slow tests passed (37.2 min); the default suite passed 203 tests with `-W error`.

## Evidence

Moved here from the handoffs folder, which gets archived:

- [`evidence/03-prototype-p1.md`](evidence/03-prototype-p1.md), [`.py`](evidence/03-prototype-p1.py), [`.json`](evidence/03-prototype-p1.json): prototype P1, full-frame m = 0.2 at its own 1% threshold.
- [`evidence/03-premeasure.py`](evidence/03-premeasure.py), [`.txt`](evidence/03-premeasure.txt): planner pre-measurement.
