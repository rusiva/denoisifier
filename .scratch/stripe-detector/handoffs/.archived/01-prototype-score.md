Prototype: P1 / B1 / B2 from `01-plan-review.md` (plan §7 score and verdict).

Throwaway code, not committed: `/tmp/claude-1000/-home-rusiva-dev-denoisifier/83d1bee3-b214-4343-a5bf-a4944906335a/scratchpad/proto/`
- `p1_lib.py`: plan §4 generator plus plan §7 steps 1–5 and 7 (argmax, no sub-bin refinement).
- `p2.py`: compares the candidate scores (run: `uv run --no-project --with numpy --with scipy python -I p2.py`).
- `p1.py`: earlier pass, also tries a taper that is continuous at the 0.1 cut-off. It made no useful difference, so it is dropped.

## Answer

**Use a floored ratio as the single score, with `THRESHOLD = 500`.**

```
amp_floor = (A0 * sum(w) / 2) ** 2        # A0 = 1e-3, modulation-depth units
score     = P_peak / max(median(P in band), amp_floor)
striped   = score > THRESHOLD
```

`2·sqrt(P_peak)/sum(w)` estimates the modulation depth of the peak: it measured 0.588–0.61 for m = 0.6 and 0.194–0.205 for m = 0.2. So `amp_floor` is the peak power that a modulation of depth A0 = 0.001 would give.

- When noise is above the leakage level, the median is larger than the floor. The score is then the plan's ratio, unchanged.
- On noise-free frames, the floor takes over. Leakage then scores about 1e-4, and real stripes score about (m/A0)².
- The verdict is still decided by the score alone, so `test_report_has_score_and_threshold` (plan §9) keeps its meaning. No second gate is needed.

## Correction to the review's numbers

Plan §7.3 says to subtract the **weighted** mean. The reviewer's `p.py` subtracted the plain mean instead (`g -= g.mean()`). That leaves a residual shaped like `w`, which leaks into the band. This is what produced the reviewer's 1391–1651 at noise 0.001 and 22–37 at noise 0.01.

With the weighted mean, as the plan specifies, the plain ratio at noise 0.001 and at 0.01 is 9–17, like pure noise. **Only noise 0 still breaks the plain ratio:** 8.2e3–1.7e5, with the peak always at period 19.3–19.7 px (the band edge). B1 therefore still holds, but only for the noise-free case.

## Measured ranges

Calibration seeds are 100–199 (profile-only, 100 frames) and 100–134 (striped). Evaluation seeds are 0–9 (profile-only) and 0–34 (striped). Striped frames cover 35 cases: periods {3, 4, 5, 8, 12, 18, 20} × angles {−10, −6, 0, 3, 10}°. Noise is the Gaussian σ as a fraction of the peak, which is 1000.

| frames | noise | seeds | plain ratio | mod. estimate | **floored score** |
|---|---|---|---|---|---|
| m = 0 | 0 | eval / calib | 1.6e4–1.1e5 / 8.2e3–1.7e5 | 1.2e-5–1.3e-5 | **1.5e-4–1.8e-4** |
| m = 0 | 0.001 | eval / calib | 11.5–16.2 / 9.2–16.9 | 4.5e-5–6.1e-5 | **0.0020–0.0037** |
| m = 0 | 0.01 | eval / calib | 11.9–16.2 / 9.3–16.9 | 4.5e-4–6.1e-4 | **0.20–0.37** |
| m = 0 | 0.1 | eval / calib | 9.2–16.9 | 0.0045–0.0061 | **9.2–16.9** |
| m = 0 | 0.3 | eval / calib | 9.3–16.9 | 0.014–0.018 | **9.3–16.9** |
| m = 0.6 | 0 / 0.001 / 0.01 | both | 1.1e9–5e12 (noise 0.01: 1.4e7–1.9e7) | 0.588–0.609 | **3.46e5–3.70e5** |
| m = 0.6 | 0.1 | both | 1.4e5–1.9e5 | 0.588–0.61 | **1.43e5–1.92e5** |
| m = 0.2 | 0 / 0.001 / 0.01 | both | 1.4e6–4e12 | 0.196–0.203 | **3.84e4–4.12e4** |
| m = 0.2 | 0.1 | both | 1.6e4–2.2e4 | 0.194–0.205 | **1.60e4–2.18e4** |

Rows marked "both" give the range over the evaluation and calibration seeds together.

- **Period and angle:** all 35 striped cases are within ±5% and ±1° at every noise level and for both seed sets, from argmax alone. The score change does not touch the peak location.
- **Threshold, from the calibration seeds only:** the highest profile-only score at any noise was 16.9, and the lowest m = 0.2 score was 1.60e4 (at noise 0.1). The log-midpoint is about 520, so I round it to **500**. That leaves about 30× margin below and about 30× above, and m = 0.6 is about 300× above. The log-midpoint against m = 0.6 alone (noise ≤ 0.01) would be about 360, which is close.
- **A0 = 1e-3:** this is about 80× above the noise-free leakage level (1.3e-5) and 200× below m = 0.2. Any A0 between about 1e-4 and 1e-2 would separate these cases. 1e-3 keeps the score noise-limited (plain ratio) from noise of about 0.01 upward.

Alternatives I measured and rejected:

- **Plain ratio with a log-midpoint threshold (about 1.5e6):** noise-free profile-only frames reach 1.7e5, close to the threshold. At noise 0.1, m = 0.2 scores 1.6e4 and would be missed. There is no threshold that works across all noise levels.
- **The modulation estimate alone as the score (threshold about 0.02):** it separates these cases. But it is not normalised to the noise, so the false-alarm rate would drift with light level. That conflicts with the spec's "1% false alarms" calibration in ticket 07, and it grows without bound on odd frames (3.17 on a mostly-negative frame with one bright pixel).
- **Ratio AND amplitude gate:** works, but it is two conditions, and plan §9 would need rewriting. The floored ratio gives the same effect as one number.

## B2: degenerate frames (recommended method)

| frame | result |
|---|---|
| all zeros, constant −5, all-negative with noise | `env.max() <= 0` → `ValueError("envelope max <= 0: frame has no positive light")`. Recommend the CLI exits 1. |
| constant 1, 1e-300, 1e300 | score 0.0, not striped, no NaN, no warning (run with `warnings` set to error) |
| bright row only on the top edge | P_peak = median = 0, score 0.0 |
| small spot in a corner | finite score, sum(w) = 2.6 > 0 |
| mostly −1 with one bright pixel | finite score of 1.0, not striped |

- On the constant frames, the median is 0, so the floor keeps the denominator positive. Only the plain ratio produces NaN there.
- The guard `sum(w) > 0` is still needed: if it fails, the floor is 0 and the score is 0/0. I could not trigger it, but it would happen if the envelope maximum sat only where the Hann window is 0. Raise `ValueError` for it alongside the `env.max()` check.
- Keep `json.dumps(..., allow_nan=False)` as a backstop.
- Implementation detail: the prototype multiplies `w` by the `env > 0.1·max` mask, so that `sum(w)` normalises only over the analysed pixels. `rel` is already 0 outside the mask, so the spectrum is unchanged; only the floor scale depends on this.

## Plan changes this implies

- §7.3: keep "subtract the weighted mean", and add a comment that a plain mean leaks into the band.
- §7.7: use the floored ratio above, with `A0 = 1e-3` as a named constant. Replace the "roughly 10–20" comment with the measured 9–17 (noise-limited) and about 1e-4 (noise-free).
- §7.8: set `THRESHOLD = 500`, chosen from seeds 100–199 (profile-only) and 100–134 (striped). Tests stay on seeds 0–9 and 0–34.
- §6: add the `env.max() <= 0` and `sum(w) <= 0` checks (each raises `ValueError`).
- §9: parametrise the profile-only test over noise ∈ {0, 0.001, 0.01}, and the striped test over noise ∈ {0, 0.01}. Add a constant-frame test (score 0.0, finite JSON) and a non-positive-frame test (`ValueError` / CLI exit 1).
