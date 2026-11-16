# 02 implementer handoff

What plan §4.4, §7.2 and §7.4 asked the implementer to record. The fixer wrote it after the code-review fixes (02-fix-list.md). All numbers come from the committed code.

## Threshold (§4.4)

`THRESHOLD = 154.0`. This is the log-midpoint rule from plan §4.4, as the owner ruled in fix-list item P4. It was measured on calibration seeds 100-199 with 256×256 frames, EMCCD defaults (~100 photons at the peak), and Periods/Angles cycling through the 10 `CASES` of `test_analyse.py` (seed i takes entry i % 10).

| Set | Seeds | Score |
|---|---|---|
| scorched, m = 0 | 100-199 | max **83.7** (seed 114) |
| multiscale, m = 0 | 100-199 | max 62.8 (seed 188) |
| scorched, m = 0.5 | 100-199 | min 362.9 (seed 100, 3 px / 10°) |
| multiscale, m = 0.5 | 100-199 | min **284.8** (seed 195, 4 px / -4°) |
| scorched, m = 0.2, Periods 3/5/8/20, Angle 0 | 100-119 | 70.8-810 |

The log-midpoint is √(83.7 · 284.8) = 154.4, rounded to 154. The margin is 1.84× above the stripe-free maximum and 1.85× below the m = 0.5 minimum.

The fix list's estimate of ~174 used a lowest m = 0.5 score of 363, which was measured on seeds 100-119 only. Over 100-199, the multiscale minimum is 284.8. If only scorched frames count (the AC's working point), the result is √(83.7 · 362.9) ≈ 174.

Margins on the test seeds at 154:
- scorched m = 0 (seeds 0-19): max 76.3, 2.0× below.
- scorched m = 0.5 batch (seeds 0-19): min 495, 3.2× above.

## Borderline set (§7.2), re-chosen for 154

`tests/borderline.py` holds frames with m = 0.2, scorched mottle, EMCCD, Angle 0. The test asserts that each score lies in (THRESHOLD, 1.5·THRESHOLD).

| (seed, Period) | Score | Measured area | Path |
|---|---|---|---|
| (0, 20) | 155.0 | 3 px, 0 pairs | bank fallback |
| (13, 5) | 159.4 | 8 px, 5 h / 4 v pairs | bank fallback |
| (13, 8) | 159.8 | 14 px, 12 h / 7 v pairs | bank fallback |
| (12, 20) | 158.4 | 20 px | neighbour-product phase |
| (16, 8) | 159.7 | 14 px | neighbour-product phase |

The CLI borderline test uses (0, 20).

## Bright/dim crops (§7.2 `test_modulation_depth_is_relative_to_local_envelope`)

Setup: 256×640 frame, Period 8, Angle 4, m = 0.5, scorched mottle, rows 64:192, 128-column crops. Level is the crop's mean Profile divided by the Profile peak.

| Seed | Bright c0 / level | Dim c0 / level | Noise-free depth bright / dim (diff) | EMCCD depth bright / dim (diff) |
|---|---|---|---|---|
| 0 | 256 / 0.819 | 80 / 0.295 | 0.501 / 0.484 (0.017) | 0.495 / 0.478 (0.017) |
| 1 | 264 / 0.807 | 56 / 0.288 | 0.490 / 0.493 (0.003) | 0.490 / 0.489 (0.001) |
| 2 | 256 / 0.812 | 48 / 0.293 | 0.488 / 0.488 (0.000) | 0.484 / 0.484 (0.000) |

Margins:
- Depth error is at most 0.022, against a tolerance of 0.1.
- The bright-dim difference is at most 0.017, against a limit of 0.05.
- The lowest crop score is 421 (seed 0, dim, EMCCD), 2.7× above the threshold.

## Runtime (§7.4)

Full suite: `uv run pytest -W error`, 187 passed in 78 s (WSL2, single process). The slowest test is about 1.3 s.

## Flag for ticket 03

m = 0.2 is not reliably Striped. Scores on calibration seeds 100-119 span 70.8-810, and on test seeds 0-19 they span 63.5-436. At Period 3, every test seed is below 154 (63.5-116). Plan §4.4 lists the levers for 03: bank widths `1.0p`/`1.5p`, the box window, and the per-frame max.

## Deviations from the plan

- Spectral oracle band: `tests/spectrum.py` uses ±12°, not the ±10° of plan §7.1. The extra 2° is a frequency-grid margin. With ±10°, the 20 px / -10° clean case lost its peak at the band edge.
- Dim crop: chosen from the profile-only `clean` (a `mottle="none"` frame of the same seed and shape), not from the mottled `clean` of plan §11 O3. This matches the AC wording "parts of the profile". The code reviewer passed it as P5.
