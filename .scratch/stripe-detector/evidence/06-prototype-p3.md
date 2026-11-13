# 06 prototype P3: pre-freeze check (plan step 5b)

Script `06-prototype-p3.py`, raw results and summary `06-prototype-p3.json`, run log `06-prototype-p3.txt`. Run at `a1948ad` (clean `src/`), idle machine (load 0.4 before the start), 12 workers, 683 s plus timing. During the run only docstrings in `analysis.py` and `synthetic.py` were edited (no behaviour change). The script also wrote `06-prototype-p3.raw.json`, a duplicate of the JSON's raw sections; it was deleted. Seeds 396_500-396_699 only (reserved in `USED_SEEDS` at step 0).

The rules were fixed in the script before it ran (plan sections 4 and 7.5b; the cutoff rule is the script's: fewest misses, then smallest worst error, keeping 0.10 unless another cutoff is better by more than 0.002).

## Results

| Item | Result | Value set by the rule | Ceiling / requirement | Status |
|---|---|---|---|---|
| Cutoff sweep, 396_500-539, full, 0.4, 100 photons | misses: inf 5, 0.05 **0**, 0.10 0, 0.20 0; worst err 0.116 / **0.036** / 0.049 / 0.077; mean err 0.049 / **0.015** / 0.023 / 0.036 | `_CLIPPED_WEIGHT_MAX = 0.05` | 0.05, 0.10 or 0.20 | ok |
| Margin, fresh 396_540-579, 0.4, 100 photons, cutoff 0.05 | 0 misses (inf: 3); worst err **0.060**; mean 0.016 vs inf 0.044 | `CLIP_LEVEL_FRACTION = 0.4` | worst <= 0.08 | ok |
| Margin at 30 photons (recorded, not asserted) | 0.4: 2 misses (inf 9), worst 0.141; 0.5: 1 miss (inf 2) | | | info |
| Per-seed `err - err_inf`, full (80) and partial at 0.4 (20) | largest **0.00076** (396_560, full) | `CLIP_DEPTH_EPS = 0.01` (max(0.01, 0.0058)) | <= 0.02 | ok |
| Teeth, full at 0.4 (80 frames) | mean err 0.015 < mean err_inf 0.047; 0 misses; auto clip count exact on all 80 | | | ok |
| Clipped share, full at 0.4 | min **2.07%**, median 4.8% | `CLIP_MIN_SHARE = 0.02` | | ok |
| Partial 396_580-599 at 0.8 (no harm) | 20/20 within tolerance (inf 20/20); clipped pixels in the region min **18** (396_588, 396_592: 18 < `AC4_MIN_CLIPPED_PIXELS` 30) | | | info: the test seeds pass the precondition (below) |
| Partial at 0.4 (not worse) | 20/20 `err <= err_inf + 0.01`; within `DEPTH_TOL` 14/20 (inf 11/20): the known partial limit | | | ok |
| **AC 3 paired score change, 396_600-699** | spikes only: largest \|change\| **38.99** (396_698: 39.0 -> 0.0), 13/100 above 15; with the 3x clip: largest 25.98, 12/100 above 15. Percentiles of \|change\| (spikes): 50% 0.8, 90% 16.2, 95% 19.2, 99% 26.1. Verdict changes: **0/100** at `THRESHOLD`, **0/100** at `GATE_STORED_THRESHOLD`, both parameters | `SPIKE_SCORE_TOL = ceil(1.25 x 38.99) = 49` | **<= 15** | **MISS: above the ceiling** |
| Clipped stripe-free, 396_600-699, 0.4 and 0.5 | 0/100 striped, 0 with regions; max score 62.4 | | not striped | ok |
| False plateaus, integer EMCCD (em_gain 1, read noise 0), 396_500-599, m 0 and 0.5 | 30 photons **2/200**; 100: 0/200; 1000: 0/200 | | record | info |
| Solis fixtures | `xpos_ypos_crop.asc`: unique max, 0 clipped, 0 spike pixels (with and without the axis column). `kinetic.asc`: refused by `read_frame` (kinetic series) | | record | info |
| Timing, `reject_spikes` + `find_clipped`, 400x1600, alone after the pool | median **0.144 s** (min 0.131, max 0.190; 21 runs) | | <= 0.3 s | ok |

### AC 3: what the large changes are

Every change above 15 is a weak sub-threshold candidate appearing or vanishing: one side of the pair scores 0.0 (no surviving group) or near it, the other 15-39, all far below `THRESHOLD` and `GATE_STORED_THRESHOLD` (no verdict changed). Examples: 396_698 39.0 -> 0.0; 396_670 26.0 -> 0.0; 396_640 0.0 -> 22.7; 396_664 5.0 -> 30.8. The spike-free scores reach 58.4 on this set (one frame striped at the gate threshold, with and without spikes). The score is the peak ratio of the best surviving group, so it jumps when a borderline group passes or fails the size or leakage rule; replacing the 100 events' pixels moves that. P2 saw +21 to +24 jumps from small perturbations (plan section 4, B5).

## Stimulus preconditions on the test seeds (generator only)

- `CLIP_TEST_SEEDS` (81, 83-86, 88-92), full at 0.4: clipped share 3.4%-7.2%, all >= 0.02.
- `CLIP_TEST_SEEDS[:5]`, partial: clipped pixels in the truth region at 0.8: 73, 46, 328, 40, 542; at 0.4: 1342-10955; all >= 30.

## Freeze status

Not frozen. `SPIKE_SCORE_TOL` by the plan's rule is 49, above its ceiling 15: escalated to the orchestrator before step 5c. The other values are set by their rules and within their ceilings: `_CLIPPED_WEIGHT_MAX = 0.05`, `CLIP_LEVEL_FRACTION = 0.4`, `CLIP_MIN_SHARE = 0.02`, `CLIP_DEPTH_EPS = 0.01`.
