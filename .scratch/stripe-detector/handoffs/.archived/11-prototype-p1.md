# 11 P1 measurement (plan §7 step 1; stop point)

- BASE `e06a902`, no change under `src/` or `tests/` (tree clean there; the ticket file's
  modification predates this step).
- Seeds: `BREAK_FORK_PROTOTYPE_SEEDS` 112_000-112_199 only, every arm (n = 200 per arm, 20 per
  case). Seed guard installed (`seed_guard.install()`, workers via `feasibility.run_pool`).
- Scripts: `p1_measure_11.py` (arms, evidence scalars, fakes, timing; output
  `11-prototype-p1.json`, log `11-p1-measure.log`, `EXIT=0`), `p1_recorder_11.py` (pytest plugin:
  true break / Fork E on the 09/10 test frames; output `11-p1-recorder.jsonl`, log
  `11-p1-recorder.log`), `p1_recorder_summary_11.py` (m_b, m_f). All in this folder.
- Machine: idle at start (load 0.94); 12 workers; phase-1 wall 4035 s for 800 frames (four
  arms; evidence + `analyse` + crossing checks per frame).

## How the scalars were computed (scratch copy of plan §2)

Front half = a copy of `analysis.py:315-345` (stored 1 % stripe threshold; arm iii at
`false_alarm_rate=0.05`), gated field at the fixed `_FORK_GATE_EVIDENCE`.
`S_b`: per reported region `E_1` of the finder with no evidence limit and `max_lines=1` when
the first line passes the jump and spread rules (`_accepted` with the evidence check disabled),
else 0; per bridge pair (copy of `_BreakPass.bridge`) max over side-share-meeting lines j of
min(E_1..E_j); max over all. `S_f`: max E of all `find_forks` candidates in
`_region_forks(..., min_evidence=-inf)` on the raw responses, refused regions skipped.
Thresholds applied to `analyse` by setting `_local_phase._BREAK_MIN_EVIDENCE` and
`analysis._FORK_MIN_EVIDENCE` to `nextafter(T, inf)` in each worker (the planned strict `E > T`).

Checks of the scratch scalars against the real path:
- **Crossing (T7-style)** on every frame of every arm with S > 0: 14 frames (4 break, 13 Fork
  checks). In each, the real `_with_phase_breaks` / `_post_break_forks` find 0 at T = S and ≥ 1
  at `nextafter(S, 0)`. 0 failures.
- **Implications (AC 2 at-scale check)** on all 800 frames at the candidate thresholds: reported
  break ⇒ S_b > T_b; reported Fork ⇒ S_f > T_f or a break; both ≤ ⇒ none. 0 violations.

## Base arm (calibration recipe) and candidate thresholds

| | S_b | S_f |
|---|---|---|
| max | 0.000 | 0.000 |
| rank 2.5 % (k = 5 of 200) | 0.000 | 0.000 |
| rank 5 % (k = 10) | 0.000 | 0.000 |
| frames > floor | 0 | 0 |
| frames > 0 | 0 | 0 |

At 400x1600 with 30 Spike events, depth 0.5, **no** base frame has any Fork candidate (S_f = 0
on all 200) and no first line that passes the jump and spread rules (S_b = 0 on all 200; the
best line's E on break-free frames, up to 0.082 in 09's P1 v2, fails the π/4 jump rule).

**Candidate thresholds at r = 0.05 (r/2 each, k = 5): T_b = 0.1, T_f = 0.3. The floors bind.**
Smallest rate at which either threshold leaves its floor: **none** (no frame above a floor,
so every valid rate r ≥ 2/(n+1) gives the floors; at n = 300 the same holds unless the
Calibration Set has frames above a floor, which 0 of 200 here makes unlikely, not impossible).

Fakes at the candidate thresholds: 0 of 200 striped frames (200 striped, 0 not striped);
total fakes 0; per case 0 everywhere.

## Arms at the candidate thresholds (rates over striped frames)

| arm | striped / not | fake frames | rate | total fakes (breaks, Forks) | multiplicity | fakes in fake regions | S_b max | S_f max |
|---|---|---|---|---|---|---|---|---|
| base | 200 / 0 | 0 | 0.0 % | 0 (0, 0) | – | 0 | 0.000 | 0.000 |
| (i) depth 0.2 full frame | 200 / 0 | 1 | 0.5 % | 1 (1, 0) | 1.0 | 0 (n/a, full frame) | 0.132 | 0.104 |
| (ii) partial region | 200 / 0 | 1 | 0.5 % | 3 (3, 0) | 3.0 | 3 | 0.670 | 0.010 |
| (iii) stripe rate 0.05 | 200 / 0 | 0 | 0.0 % | 0 (0, 0) | – | 0 | 0.000 | 0.000 |

- (i) fake: seed 112000 (case 0, P 3, Angle 10), one break, E 0.132, jump −1.03 rad, in the
  stripe region at the frame's bottom edge. 12 of 200 frames have S_f > 0 (max 0.104, all far
  under 0.3; 11 of the 12 in case 0, P 3); 3 frames have S_b > 0 (0.132, 0.097, 0.082).
  Arm (i) at m = 0.2 had no non-striped frame on these seeds (plan expected about 10 %).
- (ii) region: `regions.single_region(P, Angle, depth=0.5, centre)` with `semi_axes`
  replaced by (180, 566) px (π·180·566 = 0.50 of the frame), scorched Mottle, Emccd(), 30 Spike
  events. The fake: seed 112065 (case 5, P 4, Angle −4): a second, false region at the top
  frame edge (cols ~1420-1490), 3 accepted breaks in it, S_b 0.670. This is the 109797 kind
  (fake region carries fake breaks), at 1 of 200 frames. 1 of 200 frames has a fake region.
- (iii): same frames as base, at the 5 % stripe threshold: 0 fakes, S_b = S_f = 0 on all.

## True break / Fork E on every 09/10 test frame (B4)

`pytest -p p1_recorder_11 -m "not slow"` on `tests/test_analyse.py`,
`tests/test_phase_break_pass.py`, `tests/test_local_phase.py` (all parameters, `wide` included):
`1099 passed in 1694.17s (0:28:14)`, `EXIT=0` (a recording run, not a gate quote). 200 tests
recorded a finder result.

- Accepted breaks: 182 (test_analyse 162, min 0.267; test_phase_break_pass 1, 0.985;
  test_local_phase 19, min 0.419). Smallest: 0.2669
  (`test_phase_breaks_are_found_and_measured[18]`, the same frame in
  `test_phase_break_frames_have_no_fork[region-18-…]`), then 0.284 / 0.287 (two-break 19).
- Found Forks (reported side, E ≥ 0.3, and direct test calls): 84; smallest 0.3395
  (`test_forks_are_found_with_their_direction[10]`), then 0.383 (fork pair 10).
- **m_b = min(0.18, 0.267) = 0.18; m_f = min(0.31, 0.340) = 0.31.**

## Stop rules (plan §7 step 1)

1. `T_b > 0.1 and T_b > m_b − 0.02 (0.16)`, or `T_f > 0.3 and T_f > m_f − 0.02 (0.29)`:
   **not fired** (T_b = 0.1, T_f = 0.3, both at the floors).
2. Total fakes > 1.5 × frames-with-fakes (O2), at the candidate thresholds: **not fired on the
   calibration recipe** (base: 0 fakes, 0 frames). **For the orchestrator:** on the arms the
   ratio is above 1.5: arm (ii) 3 fakes on 1 frame (3.0); arms pooled 4 on 2 (2.0). The plan
   states the rule for the calibration count model (base recipe), so this reads as not fired,
   but the only multi-fake frame is the fake-region kind, which the AC 2 recipe cannot see.
3. Any arm (i)-(iii) above 5 % of its striped frames: **not fired** ((i) 0.5 %, (ii) 0.5 %,
   (iii) 0.0 %).
4. Any case at the P1 per-case alarm level (≥ 5 fake frames of 20): **not fired** (max 1 of 20,
   on every arm).

Floors bind → proceed per plan, recorded for ADR 0003 and the ticket Comment (OQ1): "the floors
set the thresholds; measured 0 of 200 prototype frames with a fake".

## Runtime and OQ8

Per-frame worker time (12 workers, contended), base arm: generate 0.56 s, evidence pass 29.2 s
(median; front half + finders), `analyse` 29.1 s (median). Arms (i)-(iii) are similar (26-34 s).
So the evidence pass costs about one `analyse`; it repeats the front half. Wall per frame at 12
workers ≈ worker time / 12: reproduction (generate + evidence) 30.1 s / 12 = 2.51 s per frame.

- Full 300 reproduction: 300 × 2.51 s ≈ 12.5 min. `make check-slow` today ≈ 20 min (module
  docstring of `test_slow_regression.py`) → **≈ 32-33 min, above the ~25 min cap.**
- Prefix 60 frames: ≈ 2.5 min → `make check-slow` **≈ 22-23 min.**
- **OQ8 branch: prefix** (60 frames, 113_000-113_059, in check-slow; full 300 in
  `make check-held-out`).
- Projected `make check-held-out` (prefix branch): today ≈ 20 min + full reproduction 12.5 min
  + AC 2 (300 × (generate + analyse + evidence) 58.7 s / 12 ≈ 24.5 min; less if the test shares
  one front half per frame) + AC 3(c) 200 frames at 512x512 twice (plan estimate 3-5 min, not
  measured here) **≈ 60-62 min**. (Full branch: check-slow ≈ 32-33 min, check-held-out ≈ 48-50
  min.)
