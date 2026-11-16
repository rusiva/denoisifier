# 06 critic 3: the AC 3 score tolerance (`SPIKE_SCORE_TOL` above its ceiling)

Read at `5bdbab8` (tree dirty only in `.scratch/`). Checks used seeds 396_600-396_699 only (asserted against `CALIBRATION_SEEDS`); no gate was run and no file but this one was written. Scripts were throwaway (scratchpad), about 60 `analyse` calls.

## Decisions

| Item | Decision |
|---|---|
| 1. Detector defect to fix in this ticket? | **No.** The jumps come from the score's hard group gating, not from spike rejection. |
| 2. Test of "at the same rate" | **Replace** the per-seed tolerance; do not just drop it. Keep the per-seed verdict assertions at both thresholds and add the **median of the paired \|score change\|** over the 20 seeds, at most 5. |
| 3. Weakening move needing the owner? | **No human needed.** A new approval from the orchestrator, recorded in Comments before the change. |
| 4. Seed move in `a1948ad` | **Legitimate**, not seed-picking. One wording deviation to record. |

## 1. Not a spike-rejection defect

Six seeds, 256x256, `SPIKE_STRESS_COUNT` spikes. "Same-pixel fill" is the spike-free frame with the truth spike pixels replaced by their column median: no spike was ever present. "Other fills" replace three unrelated 200-pixel sets (the spike masks of seeds 396_610-612) the same way.

| Seed | Missed / false spike pixels | Spike-free | With spikes | Same-pixel fill | Other fills |
|---|---|---|---|---|---|
| 396_698 | 2 / 0 | 39.0 | 0.0 | 39.0 | 33.1, 39.0, **79.4** |
| 396_640 | 0 / 0 | 0.0 | 22.7 | 20.9 | 0.0, 12.7, 0.0 |
| 396_670 | 3 / 0 | 26.0 | 0.0 | 0.0 | 25.8, 26.0, 26.0 |
| 396_664 | 0 / 0 | 5.0 | 30.8 | 30.9 | 30.4, 30.3, 5.0 |
| 396_633 | 0 / 0 | 22.4 | 4.3 | 0.0 | 0.0, 0.0, 6.5 |
| 396_601 (quiet pair) | 0 / 0 | 22.1 | 22.2 | 22.2 | 22.1, **0.0**, 22.2 |

- The paired frames are identical outside the spike mask on all six seeds, and rejection finds no false spike pixel on any spike-free frame.
- On four of the five jumping seeds the jump is reproduced with no spike present. Replacing 0.3% of the pixels with a plausible value is enough, and unrelated pixel sets do the same, even on a quiet pair.
- The exception is 396_698: there the jump comes from the 2 missed spike pixels (the same-pixel fill keeps 39.0). That is the documented overlap limit, and it moves the score down.
- Across the 100 P3 pairs the change has no direction: 7 above +15, 6 below -15, mean -0.27, median 0.0, 44 up and 44 down.
- The cause is the score itself: the peak ratio of the best surviving group, with hard size and leakage rules. That predates ticket 06 and no fill can remove it. It belongs to ticket 07 (calibrated score). One fill took a stripe-free frame from 39.0 to 79.4, across `GATE_STORED_THRESHOLD`; ticket 07 should get that as a note.

## 2. The strongest test that does not depend on the tuning

Teeth check: seeds 396_600-396_619 with `reject_spikes` turned off (monkeypatched in the script, not in the source).

| Statistic over 20 seeds | Rejection on | Rejection off |
|---|---|---|
| Median paired \|score change\| | **0.55** | **58.5** |
| Pairs with \|change\| above 15 | 1 | 18 |
| Frames above `GATE_STORED_THRESHOLD` (49.7); spike-free: 0 | 0 | 13 |
| Frames above `THRESHOLD` (154); spike-free: 0 | 0 | 2 |

Medians of P3's five 20-seed blocks, both parameters: 0.18-1.35. Pairs above 15 per block: 1-5.

- **Option (a) alone is too weak.** The verdict at `THRESHOLD` catches broken rejection on 2 of 20 frames; only the verdict at the gate threshold has teeth (13 of 20). It would also undo review note N3 (the score change is asserted, not only recorded).
- **Option (b) is rejected**: the implementer's counterexamples hold, and the rule would be fitted to the detector's gating.
- **Option (c) is rejected**: 49 is above the 18 headroom, so it allows a change larger than the distance to the threshold.
- **Recommended:** per seed, verdict equal at `THRESHOLD` and at `GATE_STORED_THRESHOLD` (as drafted); per parameter, `median(|score_spiked - score_free|) <= SPIKE_SCORE_MEDIAN_TOL = 5`.
  - The median ignores the gating jumps as long as fewer than half the pairs jump (P3: 13%).
  - 5 is about 4 times the largest P3 block median and about 12 times below the value with rejection off. It is under the approved ceiling of 15 and is fixed here, before any `analyse` call on `MOTTLED_TEST_SEEDS` with spikes.
  - It works on the fast tier: 20 seeds, no extra analysis.
- A count statistic (pairs above 15 at most k) also separates (1-5 against 18), but it keeps the level 15, which is tied to the gating. The median needs no such level. Counts at fixed score levels are weaker: 35 against 36 at 20, with or without a real effect on a few seeds.
- **Risk at 5c:** a gate-threshold verdict can flip from the gating alone (the 79.4 above). P3 saw 0 in 200. If it happens on the test seeds, that is a red result to report, not a reason to loosen.

## 3. Who decides

- `SPIKE_SCORE_TOL` was never frozen or committed, so no existing check is loosened. The ticket's approval already says a value above the ceiling is a new ask.
- The change swaps one asserted statistic for another with measured teeth and adds one lockfile number. That is the orchestrator's approval under CLAUDE.md (a Codex adversarial review plus its own reading), recorded with the reason in the ticket's Comments before 5c.
- It is not taste, not external knowledge and not hard to revert. **No human needed.**
- The plan (section 3 AC 3 row, section 4, step 5b, summary item 6) and the drafted patch need the new statistic and name.

## 4. The seed move (`a1948ad`)

- The plan's step 5a allows it: a failing seed moves the seeds before any `analyse` call, recorded in Comments. The commit changes only `tests/protected.py`, the lockfile and the ticket.
- The rule is mechanical (the first ten passing seeds from 81) and reads the generator's truth only, so it cannot select for detector results.
- The precondition excludes a documented limit of the method (overlapping hits), not a detector outcome.
- **Deviation to record:** the plan says the range shifts; the result is a non-contiguous tuple, because no contiguous ten-seed range passes in the free block. The Comment already says so. Four of 19 seeds fail the precondition, so AC 2's count claim covers in-model frames only; the module docstring states that limit.
- Not re-verified by me: the failing-seed list itself (82, 87, 96, 98), and that no `analyse` call touched seeds 81-99 before the commit.
