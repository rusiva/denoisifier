# 09 P1 prototype handoff (final: explore + validation + timing; v2 section first)

PROTOTYPE, throwaway. Do not merge.

- Worktree: `/home/rusiva/dev/denoisifier/.claude/worktrees/agent-a89346810ac6ef538`, branch `worktree-agent-a89346810ac6ef538`.
- The frozen config is commit `994e4dc`. No constant changed after validation; no retuning was done.
- This file supersedes `09-prototyper-2.md` (handoff 2) and keeps all of its content below.
- Explore and validation are reported **separately**. The constants were decided on explore only (seeds 109_000-109_599). Validation uses seeds 109_600-109_999, run once.

## v2 (critic-3 rulings; frozen at commit `3768dd2`; validated once on 110_000-110_399)

The v1 sections below stay as they were and are evidence for the v1 config (`994e4dc`) only. v2 was decided on explore (109_000-109_599 plus the v2 extras, `<P3>/explore_v2.pkl`, 1796 frames). Commit `3768dd2` was made **before** the v2 validation BASE run. Nothing changed after validation, and nothing was retuned. `<P3>` = `/tmp/claude-1000/-home-rusiva-dev-denoisifier/85ad64ff-6979-496b-bc0d-89a93d20c47a/scratchpad/p3` (a reboot clears it). Details of the work on the rulings, including the guard table, depth and the 109797/109765 diagnoses, are in `09-prototyper-3.md`. They are summarised here.

### v2 decisions

- **Absorb: "constrained" (kept, not dropped).** Ablation on explore (`summary2.py` diff):
  - **Against off**, constrained keeps 8 frames that off loses: bin2x1 109517, bin1x2 109503, pair3 109446, pair4 109440/109456, pair5 109442/109456, fullcap 109227. So absorb is needed.
  - **On the `two_break` negative**, constrained merges 0/20 and old merges **9/20**.
  - **Against old**, constrained loses 4 frames (bin1x2 109509, 109515; pair2 109442; pair3 109448) and gains 2 (pair4/5 109456).
  - Of handoff 3's four target frames, it recovers 2 (109503, 109446). 109509 and 109448 stay lost. They are the "junction-region" class below.
- **Frame-period gate: kept at 2.5 frame px.** The value is derived from the passband edge at k = π/2: `2(1 + k/2π)`. It replaces `MIN_FRAME_PERIOD_PX` 2.0 for the finder only.
  - Gate seeds 110_400-110_459, full frames, 2x1, Angle 0, 10 break and 10 free frames per P:

    | Frame P | 2.00 | 2.10 | 2.25 | 2.40 | 2.50 | 2.75 |
    |---|---|---|---|---|---|---|
    | gate 2.0: found / AC 4 / free changed | 0 (line 5.6 P) / 0 / **1 fake** | 5 (1.8 P) / 9 / 0 | 8 (1.3 P) / 10 / 0 | 10 (0.63) / 10 / 0 | 9 / 10 / 0 | 10 / 10 / 0 |
    | gate 2.5: found / AC 4 / warned | 0 / 0 / 10 | 0 / 5 / 10 | 0 / 6 / 10 | 0 / 6 / 10 | 9 / 10 / 2 | 10 / 10 / 0 |

  - At 2.0 the finder fakes, and at 2.1-2.25 the lines are 1.3-1.8 P off. 2.4 would have passed, but the gate is not fitted between 2.25 and 2.5: the derived k = π/2 is kept.
  - Cost: binned frames at frame P 2.1-2.4 lose AC 4 (5-6/10). They are not bridged, because no break is searched, and every refusal is in `warnings`.
- **Sample cap: off (`max_samples` 0, stride stays 0.5 P).** The cap moved line accuracy, so the ruling drops it. Explore, cap against capoff, max/p95 line error in P:
  - full + fullcap: P3 0.35/0.29 → 0.17/0.17, P4 0.75/0.54 → 0.17/0.15.
  - bin1x2 P5: 0.94/0.85 → 0.43/0.41.
  - pair2 P4 got worse (0.64 → 0.96 max).
  - fullcap found 39 → 40/40.
  - Cost: `t_post` mean 1.5 → 2.8 s and max 3.7 → 13.4 s on the large frames (15 workers, contended). That is ticket 13.
- **Re-measure guard: "energy"** (needs the orchestrator's OK; the `_compatible` guard put 109/300 ac2 frames over 1°). `remeasure_min_p2` 9.4 P² is a floor. `update_owned` is on. Depth: BASE's is kept (`depth_all` False). All are as in handoff 3.
- **Eval (critic 3 §2):** on full frames, coverage is measured against a generator lit mask (σ 10 sensor px, level 0.1), and overshoot against the frame. An empty side fails.

### v2 constants vs v1 (`994e4dc`)

| Constant | v1 | v2 |
|---|---|---|
| `post.absorb` | old (band = infinite line + `same_line`) | **constrained**: (a) a region with no break of its own and ≥ 0.6 of its pixels in the fill bins (`slit`), Period ratio ≤ 1.2; (b) a second bridge round after the re-measure, `_compatible` on the re-measured values, ≤ 3 rounds |
| `post.remeasure_min_p2` | none | 9.4 P² (one bank Gabor footprint) |
| `post.remeasure_guard` | `_compatible` with the start | **energy** (the mean \|Gabor\| on the re-measure pixels must not drop) |
| `post.update_owned` | False | True |
| `post.depth_all` | False | False (unchanged; measured worse) |
| `finder.min_frame_period` | 2.5 | 2.5 (justified, with a warning per refused region) |
| `finder.max_samples` | 40 000 | **0** (off) |
| `finder.coh` / `min_coherence` | none | output only; off (rejected) |

### Explore (v2 frozen, `explore_v2.pkl.v2f.eval.pkl`) vs v2 validation (`base_validate2.pkl.v2val.eval.pkl`)

- `harness2.py validate2` ended with `done 1276 1311.2` and EXIT=0.
- `eval2.py ... v2val` ended with EXIT=0.

| Check | Explore v2 | **Validation v2** |
|---|---|---|
| AC 2 found (5.1) | 300/300 | **199/200** |
| AC 2 full frame found | 20/20 | **19/20** |
| AC 3 found | 300/300 | 200/200 |
| AC 4 region frames | 599/600 (109221, R2) | 400/400 |
| AC 4 full frames | 20/20 | **18/20** |
| Split-type (P 3, line 45°, π) | split 10/10, splitx 50/50 | **39/40** found and AC 4 (7 merged) |
| Angle ≤ 1°, region break frames | 600/600, max 0.76 (BASE max 3.43) | 400/400, max **0.93** (BASE max 3.57) |
| Angle, full | 20/20, max 0.42 | 20/20, max 0.32 |
| Period ≤ 5% | 620/620, max 0.8% | 420/420, max 1.3% |
| IoU ≥ 0.8 | 599/600, min 0.308 (BASE 497) | **398/400**, min 0.746 (BASE 326/400) |
| Depth within 0.1 | 549/620 (= BASE) | 364/420 (= BASE) |
| Fakes (free / free_ms / full_free / two_free) | 0/600, 0/100, 0/20, 0/20 | 0/400, 0/100, 0/20, 0/20 |
| `two_break` negative: merges | 0/20 (17 stay 2; 3 are BASE's counts) | **0/20** (17 stay 2; 110340/110356 BASE 3, 110342 BASE 1) |
| small8 Angle > 1° | 4/20 (BASE 20) | 2/20 (BASE 20) |
| small 3-6 changed | 0 each | small6 1/20 (as v1) |
| bin2x1 found / AC 4 | 15/18, 18/18 | 14/18, 17/18 |
| bin1x2 found / AC 4 | 17/18, 16/18 | 17/18, **15/18** |
| `t_post` mean / max (contended) | 0.55 / 13.0 s | 0.67 / 15.1 s |

Pairs (both found, out of 20):

| Separation | 2 P | 3 P | 4 P | 5 P | 6 P | 8 P |
|---|---|---|---|---|---|---|
| Explore v2 | 1 | 15 | 20 | 19 | 19 | 18 |
| **Validation v2** | 0 | 16 | 20 | 17 | **20** | 19 |

Line error, validation, max (p95) in P: P3 **1.15** (0.64), P4 0.45, P5 0.88, P6 0.74, P8 0.83, P10 0.48, P12 0.55, P14 0.58, P16 0.38, P20 0.51.

### v2 validation failures (diagnosed with `diag_v2val.py`; not tuned)

1. **Junction region carries its own break (4 frames: full_break 110319, split 110370, bin1x2 110383, bin1x2 110385).** This is the main v2 finding.
   - BASE reports a separate region along the phase-jump zone, with a biased Angle:
     - 110319: P 14.08, A 0.81 against the true −6;
     - 110383: A −0.62 against −8;
     - 110385: A −10.38 against −4;
     - 110370: P 2.85, A 5.57 against 10.
   - The finder finds the same line again inside it, at E 0.49-0.79. In 110319 that is Y0 200.1 / 0.04° against the main region's 199.4 / 0.50°.
   - Constrained absorb (a) skips any region that has a break of its own, and round-2 bridging refuses it as not `_compatible` (Angle 4-7° off). It stays a second region, so AC 4 fails.
   - In 110319, 110370 and 110383 it also **owns the line's pixels**. So the main region's fill cannot reach them (`owned & ~pix`), the main break gets no segment, and 5.1 found fails. That accounts for the AC 2 full miss and the split miss.
   - The class was already on explore: bin1x2 109509 and 109515, and pair3 109448, are the frames constrained lost against old. Old's `same_line` branch would catch 110319, 110383 and 110385 by geometry (≤ 2°, ≤ 1 P). 110370's two lines are 12.6° apart.
   - Candidate rule for the orchestrator, not tested: absorb (a) also takes a region whose own breaks all lie on a break of the absorbing region (same line within the fill reach). That still never fires without a found break, and `two_break` has one break per region pair on a different line. Deciding it needs a fresh explore/validation cycle.
2. **ac2 110120 (P 3, stripes 10°, line 5°, π): line 1.15 P off.** The found angle is 8.15° against 5°, with cover 0.95 and jump error 0.08. AC 4 and IoU hold. This is the same near-parallel resolution limit as 109765: the line lies 5° from the stripes, and the region is ~37 P long. A finder resolution risk for AC 2 at small P.
3. **full_break 110303 (P 12): AC 4.** BASE reports a second, compatible 1708 px region in the frame corner (rows 64-111, cols 2-47), 44 px (3.7 P) from the main region and far from the break. The break-free twin (full_free 110303) has the same 2 BASE regions. This is BASE fragmentation, unrelated to the break: ticket 17. bin1x2 110392 is the same: a 410 px corner fragment at rows 0-12.
4. **bin2x1 misses:**
   - 110385 and 110395 (P 4) are refused by the gate, with warnings, as designed.
   - 110393 (P 12): BASE has one region on one side only, so nothing is found and AC 4 fails. This is R2 / ticket 17, as with v1's 109972.
   - 110398 (P 10): line 1.02 P.
5. **IoU < 0.8:** 110044 (P 20, 0.783; BASE 0.756) and 110172 (P 8, 0.746; BASE 0.579). Both are better than BASE.

### v2 open questions

1. **The junction-region rule** (failure 1): accept 4 of the 96 validation full, split and binned frames as ticket-17 material, or extend absorb (a) with the "same-line break" condition, which needs a new explore/validation cycle and fresh seeds.
2. **The energy guard** in place of critic 3's `_compatible` guard (handoff 3 table).
3. **Cap off costs speed:** `t_post` max up to 13-15 s contended on 400x1600 break frames. That is ticket 13.
4. **The AC 2 resolution limit at small P with near-parallel lines** (110120, 109765). Fixed test seeds need checking.
5. **Pairs:** 6 P is 20/20 on validation v2. 5 P is 17/20, with misses at P 14/16/20.

Files: `prototypes/p09_breaks/{post,finder,eval2,harness2,summary2,gate_summary,diag_v2val}.py` at `3768dd2` and later. The summaries are `<P3>/sum_v2f.txt` and `<P3>/sum_v2val.txt`.

---

# v1 (config `994e4dc`, validation 109_600-109_999)

## Verdict

- **On the fresh seeds, AC 3, Angle (max 0.97°), Period and break-free fakes hold.** AC 2 found is 199/200 (one finder miss) and 19/20 on full frames (one overshoot-metric artefact). IoU is 398/400 (two marginal P 20 frames, both better than BASE).
- **AC 4 fails on 1/400 validation region frames (109797).** This is **not** a bridging failure. BASE reports a second, false region at the frame edge, and the pass then reports **3 fake breaks** in it. See validation failure 2.
- **Bridging was not exercised.** Validation has no split frames, so no bridge fired on a break frame (`bridges` empty on every failure). Bridging evidence is explore only: split seeds 10/10.

## Validation results (seeds 109_600-109_999; `summary.py` on `base_validate.pkl.frozen.eval.pkl`)

`harness2.py validate` finished with `done 1216 1338.3` and EXIT=0. `eval2.py ... frozen` finished with EXIT=0.

| Check | Validation | Explore (for comparison) |
|---|---|---|
| AC 2 found (5.1) | **199/200** | 300/300 |
| AC 2 full frame found | **19/20** | 20/20 |
| AC 3 found | 200/200 | 300/300 |
| AC 4, region frames | **399/400** | 599/600 |
| AC 4, full frames | 20/20 | 20/20 |
| AC 4, split seeds | not in validation | 10/10 |
| Angle within 1°, region break frames | 400/400, max **0.97°** | 600/600, max 0.76° |
| Angle within 1°, full | 20/20, max 0.31° | 20/20, max 0.42° |
| Period within 5% | 420/420, max 0.7% | 620/620, max 0.8% |
| Mask IoU >= 0.8 | **398/400**, min 0.786 (BASE 319/400, min 0.679) | 599/600, min 0.308 (BASE 497/600) |
| Fakes on break-free frames | free 0/400, multiscale 0/100, full 0/20, two-region 0/20 | 0/600, 0/100, 0/20, 0/20 |
| bin2x1 | found 14/18, AC 4 16/18 | 15/18, 18/18 |
| bin1x2 | found 18/18, AC 4 18/18 | 17/18, 18/18 |

The Angle max of 0.97° is close to the 1° tolerance. Explore's margin (0.76°) did not carry over.

Line error by Period, max (p95), in Periods: P3 0.53 (0.45), P4 0.90 (0.73), P5 0.83 (0.47), P6 0.75 (0.44), P8 0.57 (0.48), P10 0.48 (0.38), P12 0.86 (0.46), P14 0.47 (0.44), P16 0.78 (0.43), P20 0.40 (0.33). All are under 1 P.

### Pairs (validation; both found, out of 20)

| Separation | 2 P | 3 P | 4 P | 5 P | 6 P | 8 P |
|---|---|---|---|---|---|---|
| Validation | 1 | 13 | 17 | 18 | 18 | 17 |
| Explore | 1 | 15 | 18 | 16 | 17 | 15 |

At 6 P the misses are P 4 (1/2) and P 16 (1/2). So "all P >= 5 pass at 6 P" from explore does **not** hold on validation: P 16 missed one. The recommended test (full frame, P >= 5, 6 P) would need its seeds checked.

### Small regions (validation)

Output changed, out of 20: 3 P 0, 4 P 0, 5 P 0, 6 P **1**, 8 P 20 (found 19). On explore, 6 P was 0/20. One 6 P frame changed with no matched break, which is a small fake. It sits above `BREAK_SMALL_REGION_PERIODS` = 5, so the proposed test is not affected.

### Validation failures

1. **ac2 109765 (P 4, case Angle −4; true line 1°, jump 2π/3): finder miss.** The break was found at line angle 7.44°, 6.4° off, with cover 0.34. The jump was right (error 0.05). AC 4 still holds (one region) and IoU is 0.806.
2. **ac2 109797 (P 6, Angle −10; line −10°, jump −3π/4): AC 4 fails, with fake breaks.**
   - The true break was found well: line error 0.19 P, cover 0.91, angle −9.82°.
   - BASE also reports a **second, false region**: P 4.28, A −0.65, area 944 px, rows 440-511 (the bottom frame edge, far from the centred true region).
   - The finder reports **3 breaks** in it, all with high E: 0.80, 0.76, 0.54 at angles 15.9°, 26.5° and 10.2°. The pass emits those as breaks.
   - Why the fakes metric missed it: it counts only break-free frames, and it counts output changes rather than breaks on non-truth regions.
   - Finding: the finder trusts any reported region. A gate on region quality or size, for example `BREAK_SMALL_REGION_PERIODS` measured across the line, or a minimum line length in Periods, might refuse it; this is untested. **Not tuned** (no retuning after validation).
3. **full_break 109910 (P 3, Angle 10, horizontal π/2): 5.1 found fails on overshoot only.** Line error 0.15 P, cover 1.0, overshoot flag 1.0. This is the full-frame lit-mask chord artefact at P 3-4 (open question 2).
4. **IoU < 0.8:** 109694 (P 20, 0.799; BASE 0.768) and 109794 (P 20, 0.786; BASE 0.710). Both are marginal, P 20, and better than BASE.
5. **bin2x1 misses:**
   - 109965 and 109975 are P 4: the frame-period gate refuses by design. 109965 also fails AC 4: there are 2 regions 11 px apart that are not bridged, because no break was found.
   - 109972 (P 8, A 6): nothing found, and AC 4 fails with sides 0.0. BASE has one region on one side only, so it is R2 or growth (ticket 17).
   - 109979 (P 14): line error 1.19 P (explore had 109509 at 1.06 P, the same pattern).

## Step-6 timing (frozen config; `timing.py '{}' '{}'`, seeds 109_580-109_584)

Single process, 400x1600. The run started at a 1-minute load of 8.6, which was decaying from the validation run that had just finished; no other heavy processes were running. It ended at 1.7.

| Frame | Post-pass added time | BASE `analyse` |
|---|---|---|
| 1 region, horizontal π break | mean **0.32 s**, max 0.50 | 5.80 s |
| 1 region, no break | mean 0.08 s, max 0.09 | 5.52 s |
| 3 regions (P 6/10/14), π break each | mean **0.66 s**, max 0.99 | 7.33 s |
| 3 regions, no break | mean 0.16 s, max 0.17 | 6.86 s |

- This lands between the steps-4 and steps-8 numbers, as expected: steps 4 gave 0.25 / 0.53-0.56 s, and steps 8 gave 0.38 / 0.80 s.
- The pass adds about 6% (1 region) to 9% (3 regions) to `analyse` at worst.
- On the 3-region break frames, BASE reported 3-5 regions and the pass finished with 3 every time. Breaks were found in only 1-3 of the 3 regions. The P 6 and P 14 regions often keep 0 breaks, which is the ticket-17 one-side-lost finding below.

## Validation artefacts

All are in the scratchpad `p2/` directory (see below): `validate.log`, `base_validate.pkl`, `ev_val.log`, `base_validate.pkl.frozen.eval.pkl` and `timing_s6.log`.

---

Everything below is handoff 2's content, unchanged apart from headings. The numbers are **explore** numbers.

## Where things are

- Worktree: `/home/rusiva/dev/denoisifier/.claude/worktrees/agent-a89346810ac6ef538`
- Branch: `worktree-agent-a89346810ac6ef538`. Throwaway; do not merge.
- Commits:
  - `994e4dc` "PROTOTYPE 09 P1-2: scope-C post pass, constants frozen before validation". The frozen constants are the defaults in that commit.
  - `1bf7b8d` is handoff 1, and `861fc14` is P1 v1.
- Code is in `prototypes/p09_breaks/`. The scripts that matter now:
  - `harness2.py`: generation plus BASE `analyse`, which captures every survivor.
  - `finder.py`: the break finder.
  - `post.py`: the scope-C pass.
  - `eval2.py`: the 5.1 metric, the AC 4 reading and the per-cell table.
  - `summary.py`: the headline numbers.
  - `estats.py`: the E margin.
  - `timing.py`: 400x1600 timing with 1 and 3 regions.
  - `dbg.py`: a per-frame dump.
  - The handoff-1 scripts are kept but superseded.
- Scratch data lives in `/tmp/claude-1000/-home-rusiva-dev-denoisifier/85ad64ff-6979-496b-bc0d-89a93d20c47a/scratchpad/p2/` (about 0.6 GB; a reboot clears it):
  - `all_explore.pkl`: the explore BASE cache, 1686 frames.
  - `all_explore.pkl.s6.eval.pkl` and `ev_s6.log`: the frozen-config explore evaluation.
  - `estats.log`
  - `sweep1.log`: the re-measure sweep.
  - Validation (done): `validate.log`, `base_validate.pkl`, `ev_val.log`, `base_validate.pkl.frozen.eval.pkl`; timing: `timing_s6.log`.


## Setup (harness2, plan-shaped)

- **Explore seeds:** 109_000-109_599.
- **Break frames.** Single-region `tests/regions.py` geometry, 512x512, typical EMCCD noise, scorched Mottle, depth 0.5, line through the centre.
  - First 300 seeds (AC 2 shape): line angle = case Angle + {0, 5, −5}[seed % 3]; jump cycles {π/2, 2π/3, π, −π/2, −3π/4}.
  - Next 300 seeds (AC 3 shape): (line angle, jump) cycles over {45, 90, −60} x {π/2, π}.
- **Break-free frames:**
  - the same 600 seeds;
  - 100 multiscale-Mottle frames;
  - 20 full frames;
  - 20 frames with two compatible same-Period regions at a 2 P or 3 P gap (R1).
- **Full frames (400x1600):** 20 with a horizontal break through the centre, jump π/2 and π alternating (seeds 109_400-109_419, which include 109405).
- **`split`:** the handoff-1 split frames: seeds 109530 and 109550 plus 8 more P = 3 seeds, line 45°, jump π.
- **`pair{2..8}`:** full frames, two horizontal breaks `sep` P apart, jumps π/2 and π, 20 seeds each.
- **`small{3..8}`:** a region H P tall with a horizontal π/2 break.
- **`bin2x1` / `bin1x2`:** full frame, horizontal π break; P = 3 seeds skipped.
- **`weak`:** depth 0.25.
- **Validation seeds:** 109_600-109_999, with the same layout and fewer frames: 400 break frames, 400 break-free, 100 multiscale, 20+20 full, 20 two-region, pairs, small and bins. There are no split or weak frames.

## The pass (`post.py`, after `reported`; score path untouched)

1. **Bridge.**
   - Which pairs: reported regions only (R2 is ruled out), that are `_compatible` and within `bridge_gap` = 4 P of each other.
   - Domain: the union of the two regions plus the pixels within the gap of both, inside `light`.
   - The finder runs on that domain, at the Period and Angle of the higher-peak region.
   - Merge rule: a found break with the smaller region at least 0.8 on one side and the larger at least 0.5 on the other side. When the re-find on the merged region returns nothing, the bridge's own break is reported.
2. **Find** in every final region, with the finder's own narrow Gabor at the region's Period and Angle.
3. **Re-measure.**
   - Pixels: the region's pixels outside ±`excl_k` = 2.0 times the bank σn of each break.
   - Method: `_phase_steps(spec.gabor(...))`, 6 steps, starting from the reported (biased) Period and Angle.
   - No re-find afterwards (`refind` = False; re-find measured worse).
4. **Fill.** Add pixels within ±`fill_k` = 1.0 times the bank σn of the line, limited to:
   - the along-line bins (0.5 P) where the region has pixels on both sides within the band + 1 P;
   - `light`;
   - pixels not owned by another region.
5. **Absorb slit regions (new; not in the plan).** A smaller final region joins a region that has a found break when all of these hold:
   - the period ratio is at most `_MERGE_PERIOD_RATIO`;
   - it lies within `bridge_gap`;
   - either its own found break is the same line (within 2° and within 1 P at its centroid), or at least 0.6 of its pixels lie within the fill band + 1 P.

   Why: on binned and full frames, BASE grows an incompatible region along a π break; for example bin1x2 109509 had a region at A 1.27° beside A −6°. Without the Period and gap conditions it wrongly merged distinct regions crossed by one frame-wide break (found on the 3-region timing frame).
6. **Segment.** Region pixels within 0.75 x max(bins) sensor px of the line, after the fill and the absorb. A σn-wide band overshot the chord on full frames, so it was dropped.
7. **No break accepted anywhere: BASE is returned untouched.** This held by construction on every break-free frame: fakes are 0, below.

## Frozen constants (decided on explore only; commit `994e4dc`)

Finder (`finder.FINDER`), with the plan's §10 names:

| Constant | Value |
|---|---|
| `_BREAK_SIGMA_ACROSS_PERIODS` / `_ALONG` | 1.0 / 0.5 (filter and σn model) |
| `_BREAK_MIN_DEPTH_FRACTION` | 0.5 (samples where \|z\| >= 0.5 x median \|z\| on the domain) |
| `_BREAK_COARSE_STEP_DEG` | 3 |
| `_BREAK_FINE_SPAN_DEG` | ±3 |
| `_BREAK_FINE_STEP_DEG` | 0.5 |
| angle refinement (new) | golden-section search within ±0.25°, down to `line_tol` = 0.1 P at the region's length. Without it, long lines in 400x1600 frames were 1-1.7 P off at the ends. |
| `_BREAK_BIN_PERIODS` | 0.25 |
| `_BREAK_SAMPLE_STRIDE_PERIODS` | 0.5 |
| sample cap (new, speed) | `max_samples` = 40 000; the stride grows on large domains |
| `_BREAK_FIT_HALF_WINDOW_PERIODS` | 4 |
| samples per side (new) | at least 6 P² of area per side in the window |
| `_BREAK_MIN_EVIDENCE` | 0.1 |
| `_BREAK_MIN_JUMP_RAD` | π/4 |
| `_BREAK_SEGMENTS` | 3 |
| `_BREAK_JUMP_SPREAD_RAD` | π/4 |
| `_BREAK_EXPLAIN_SIGMAS` | 2 |
| `_BREAK_MAX_PER_REGION` | 4 |
| `_BREAK_MIN_FRAME_PERIOD_PX` (new) | 2.5 frame px along the stripe normal. Below it the finder returns nothing. P 4 under 2x1 aliases, and without the gate it gave fake breaks with E 0.16-0.18. |

Pass (`post.POST`):

| Constant | Value |
|---|---|
| `_BRIDGE_GAP_PERIODS` | 4 |
| bridge side shares | 0.8 smaller / 0.5 larger |
| gap domain | pixels within the gap of both regions, inside `light` |
| `_BREAK_FILL` | ±1.0 x bank σn (fill reach + 1 P, both-sides bins 0.5 P) |
| `_REMEASURE_EXCLUDE` | ±2.0 x bank σn (≈ 3 P for a horizontal line at stripe Angle ~0) |
| `_REMEASURE_STEPS` | 6 |
| `_REMEASURE_START` | the reported values |
| `_BREAK_REFIND_AFTER_REMEASURE` | False |
| absorb | 2°, 1 P, 0.6 |
| segment | 0.75 px |

Decisions:
- **Keep step 3 (fill)** and **step 4 (re-measure)**: both meet the tolerances on explore (below).
- **Protected (proposed):**
  - `BREAK_CHORD_COVER_MIN` = 0.6 (min cover over matched breaks 0.776, p1 0.799);
  - `BREAK_SIDE_COVER_MIN` = 0.5 and `BREAK_SIDE_EXCLUDE_PERIODS` = 2.5 confirmed (one-region frames min 0.785, apart from the R2 frame 109221 at 0.14);
  - `BREAK_SMALL_REGION_PERIODS` = 5 (heights 3-6 P: 0/20 changed each; 8 P: 20/20 changed, 18/20 found);
  - `BREAK_PAIR_SEPARATION_PERIODS` = 6, with the test at P >= 5 (see pairs);
  - `BREAK_VALIDATION_SEEDS` = `range(109_600, 110_000)`.

## Explore results (frozen config; `summary.py` on `all_explore.pkl.s6.eval.pkl`)

Steps 4 gave identical counts with max Angle error 0.88°.

| Check | Result |
|---|---|
| AC 2 found (5.1, with overshoot and direction alignment) | 300/300 |
| AC 2 full frame | 20/20 |
| AC 3 found | 300/300 |
| AC 4 (striped, one region, both sides >= 0.5 beyond 2.5 P), region frames | **599/600** |
| AC 4, full frames | 20/20 |
| AC 4, split seeds (109530, 109550 + 8) | 10/10, all bridged or merged |
| Angle within 1°, region break frames | **600/600, max 0.76°** (BASE: 268/600 over 1° in handoff 1) |
| Angle within 1°, full | 20/20, max 0.42° |
| Period within 5% | 620/620, max 0.8% |
| Mask IoU >= 0.8 | **599/600**, min 0.308 (BASE 497/600) |
| Fakes (any output change) | free 0/600, multiscale 0/100, full 0/20, two-region 0/20 |
| Weak (depth 0.25) | found 52/60 (information only) |
| bin2x1 | found 15/18, AC 4 18/18 |
| bin1x2 | found 17/18, AC 4 18/18 |

The single AC 4 / IoU failure is **109221** (P 5, jump π, ac2): BASE reports only a 1830 px piece (BASE IoU 0.21). The rest of the stripes are survivors below the threshold, or at P 3.97 and incompatible. That is R2 plus growth, so it belongs to ticket 17. It is a frame of the plan's AC 2 test shape, so a test seed like it would go red: risk for the orchestrator.

Binned misses:
- 109505 and 109515 are P 4 under 2x1, where the frame-period gate refuses by design (frame period 2 px).
- 109515 under 1x2 also misses.
- 109509 under 2x1 (P 14): line error 1.06 P at a found angle of −0.54°.

### (b) Line error by Period

Max over AC 2, AC 3 and full frames, in Periods:

| P | 3 | 4 | 5 | 6 | 8 | 10 | 12 | 14 | 16 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|
| max line error | 0.72 | 0.75 | 0.89 | 0.85 | 0.54 | 0.55 | 0.68 | 0.44 | 0.59 | 0.61 |

- The worst is 0.89 P at P 5. P 3 is not the worst; the 0.5° grid plus the golden refinement is enough there.
- Handoff 1's 3 line errors of 1.01-1.21 P at π are gone. They are not reproducible: the old data and geometry are gone after the reboot, so the 594/600 versus per-cell versus failure-list counts **cannot be reconciled**. The new counts all come from one script.

### Evidence margin (B4; `estats.log`, gates off, two greedy rounds)

- **Break-free top E:** n 754, p99 0.010, max 0.082.
  - The max is full-frame 109410 at P 3; its \|jump\| 0.72 fails the jump gate.
  - **No break-free candidate passes the jump and spread gates.**
- **True breaks:** min E at π/2 is 0.18.
- **Second candidate on break frames:** max E 0.034; none passes the gates.
- So E = 0.1 sits 1.22x above the largest break-free E and 1.8x below the smallest true one.

### Re-measure sweep (explore; max Angle error on AC frames)

| Steps / exclusion | Max Angle error |
|---|---|
| 4 / 1.5σn | 1.11° (8 frames over 1°) |
| 8 / 1.5σn | 0.96° |
| 4 / 2.0σn | 0.88° |
| **6 / 2.0σn** | **0.76°** (frozen) |
| 8 / 2.0σn | 0.75° |
| 8 / 2.5σn | 0.83° |
| re-find (4 / 1.5σn) | 1.11° |

### Pairs (full frames, jumps π/2 and π)

Both found, out of 20:

| Separation | 2 P | 3 P | 4 P | 5 P | 6 P | 8 P |
|---|---|---|---|---|---|---|
| Both found | 1 | 15 | 18 | 16 | 17 | 15 |

- At 6 P every miss is at P <= 4: P 3 0/2, P 4 1/2, all P >= 5 2/2.
- At P 3-4 the misses are overshoot of the segment past the truth lit-mask chord, by 1.3-2.3 P = 4-7 px. That is a metric artefact of the lit-mask definition at the frame's lit edge, and it needs the orchestrator's look (open question 2).
- At 8 P, P 14-20 lose the second break to a 1-1.7 P line error.
- In region geometry (handoff-1 style) pairs cannot work at P >= 8: the region is 10 P tall.
- Recommendation: `test_two_parallel_phase_breaks_are_both_found` on a full frame at P >= 5, separation 6 P.

### Timing

Single process, 400x1600, seeds 109_580-109_584. Steps 4 and 8 below; steps 6 (frozen) is in the step-6 timing section above.

| Frame | Steps | Post-pass added time | BASE `analyse` |
|---|---|---|---|
| 1 region, horizontal π break | 4 | mean 0.25 s, max 0.41 | ~5.4-6.0 s |
| 1 region, horizontal π break | 8 | mean 0.38 s, max 0.55 | |
| 1 region, no break | | 0.08 s | |
| 3 regions (P 6/10/14), π break each | 4 | mean 0.53-0.56 s, max 0.83 | ~7.2-7.7 s |
| 3 regions, π break each | 8 | mean 0.80 s, max 1.23 | |
| 3 regions, no break | | 0.16 s | |

- Steps 6 should land between the two.
- Cost drivers: full-frame FFT filters on the shared `_Spectrum`. A crop-local spectrum for the re-measure would cut it; that is ticket 13 material.
- **Finding for ticket 17:** on the 3-region frames, BASE often reports a P 6 or P 14 region on one side of its π break only, with the other side lost entirely and not even an unreported survivor (seeds 109580, 109582). No bridge can fix that.

## Open questions for the orchestrator

1. **Is the absorb step OK?** It goes beyond the ruling's "merge across a found break". It merges a region that lies on a found break's line or slit. It is needed for full and binned frames, never fires on break-free frames, and is gated by Period ratio and gap.
2. **Full-frame chord definition (5.1 overshoot).** The truth lit mask (here `gaussian(clean, P) >= 0.1 max`) ends a few px before the region at P 3-4. Either define the chord from a lit mask closer to `analyse`'s light, or accept the overshoot on full frames.
3. **109221-type frames.** In the plan's AC 2 shape, BASE reports a fragment at a π break with the rest below the threshold. That is R2 and ticket 17 territory, but a fixed test seed could hit it. One in 600 on explore.
4. **The new gates** (`_BREAK_MIN_FRAME_PERIOD_PX`, the sample cap, the angle refinement) need lockfile lines like the other `_BREAK_*`.
5. **Fake breaks in a BASE false region (validation 109797).** The finder reported 3 breaks with E 0.54-0.80 in a 944 px P 4.28 region at the frame edge, which BASE reported but which is not truth. The break-free fakes metric cannot see this. A region-size or line-length gate is a candidate; it was not tuned (post-validation).
6. **Angle margin on validation.** The max Angle error is 0.97° against the 1° tolerance (explore 0.76°). A test seed could go red at the tolerance.
7. **Pairs at 6 P, P 16:** validation missed 1/2. The test seeds need checking before `test_two_parallel_phase_breaks_are_both_found` is pinned.

## v2 speed (follow-up; no retuning, and the v2 config is unchanged)

- Measured on an idle machine (load < 2), single process, `OMP_NUM_THREADS=1`, with `timing_v2.py` (commit `934297a`; `cap_min_period` defaults to 0, so v2 behaviour is unchanged).
- Frames are 400x1600 with seeds 109_580-109_584 and one π break each: full frames at P 3, 4, 5 and 10 (Angle 3), and `timing.py`'s 3-region frame (P 6/10/14).
- `analyse` runs once per frame. The post pass then runs under each finder config, each time on a fresh `_Spectrum`.
- `P09_PROFILE=1` wraps the stages; the stage times are means.
- Log: `<P3>/timing_v2.log`.

| Frame | BASE `analyse` | v2 (cap off): post mean / max | v1 cap 40k (all P) | P-aware cap (P ≥ 6) | finder.find in v2 | FFT (gabor + narrow_z) |
|---|---|---|---|---|---|---|
| full P 3 | 5.10 s | **1.09 / 1.39** | 0.34 / 0.45 | 1.08 / 1.40 | **0.85** | 0.17 |
| full P 4 | 5.13 | 0.61 / 1.02 | 0.37 / 0.48 | 0.61 / 1.02 | 0.36 | 0.17 |
| full P 5 | 5.20 | 0.57 / 0.78 | 0.44 / 0.68 | 0.57 / 0.79 | 0.26 | 0.20 |
| full P 10 | 5.21 | 0.32 / 0.46 | 0.32 / 0.46 | 0.32 / 0.46 | 0.06 | 0.19 |
| 3 regions (P 6/10/14) | 6.73 | 0.70 / 1.07 | 0.71 / 1.08 | 0.71 / 1.06 | 0.07 | 0.50 |

The worst contended frames were re-timed idle, single process, through `eval2.evaluate`:
- pair2/3/4 at P 3 (109450, 109440): v2 **2.41-2.50 s**, capped 0.60-0.66 s;
- fullcap 109270 (P 3): 1.18 s, capped 0.31 s.

**The 13-15 s `t_post` maxima came from contention.** They were measured with 15 workers on a loaded machine, about 5-6x the idle time.

**P-aware cap (`cap_min_period` 6), explore evaluation** (`explore_v2.pkl.pcap.eval.pkl`, tags full_break, fullcap, pair*, bin*, 216 frames):
- P < 6: 80/80 frames are identical to v2 cap-off (found, AC 4, n, changed, line errors).
- P ≥ 6: 135/136 are identical to v2 with the v1 cap. fullcap 109237 has the same found and AC 4 but slightly different line errors; its region's measured Period sits at the 6 boundary.
- So it reproduces both accuracy profiles. It buys **no speed**: at P ≥ 6 the 40k cap hardly binds (finder 0.06-0.07 s either way), and the slow frames are all P < 6, where it leaves the cap off.

**Where the time goes:** at P 3-4, the finder's samples. The count scales as area/(0.5 P)², which is about 230k on a full 400x1600 frame at P 3. Every coarse angle (3° steps), fine angle and golden-section step re-bins all of them, and the greedy rounds repeat this per break, so pairs pay twice. The FFT filters cost a flat 0.17-0.20 s per region, which is ticket 13's crop-local spectrum.

**Cheapest principled fix (not implemented or measured):**
- **Change:** run the coarse angle scan on the capped (strided) samples, then do the fine scan, golden-section refinement and fit on full-density 0.5 P samples restricted to the fit window (±`window` = 4 P) around the coarse line.
- **Why this should keep accuracy:** the cap's accuracy loss is in the line position and angle, which the fine stage sets. That stage needs only samples within ±4 P of the line: about 8 P × line length / (0.5 P)², a few thousand samples at P 3 instead of about 230k.
- **Expected cost:** roughly the capped time (about 0.3-0.6 s worst case).
- **Requirement:** the coarse 3° scan must still pick the right basin with the capped samples. That needs one explore check (a found/line-error diff against v2, as above) before it is adopted.

**Recommendation:**
- Do not adopt the P-aware cap: it is a no-op for speed.
- Keep v2 cap-off as the validated config: about 1.1-1.4 s full-frame and about 2.5 s pair worst case at P 3, idle.
- Prototype the coarse-capped / fine-windowed finder above as a ticket-09 speed item. Do not defer it whole to ticket 13, because ticket 13 cannot recover it from the FFT side.
