# 09 plan: phase breaks (final)

**Status: final, ready for implementers.** Every value is filled from P1 v2 (`09-prototype-p1.md`, sections "v2" and "v2 speed"; config frozen at worktree commit `3768dd2`, validated once on 110_000-110_399). The orchestrator's rulings are folded in: "Rulings after Fable critic", the scope ruling (option C), "critic-3 done" items 1-5, "My rulings" after P1-5 v2, and the final rulings (section 9). A departure from this file is a finding for the orchestrator, not a silent fix.

The prototype code (`/home/rusiva/dev/denoisifier/.claude/worktrees/agent-a89346810ac6ef538/prototypes/p09_breaks/{finder,post}.py` at `3768dd2`) is a **reference for behaviour only**. Do not copy it: it carries ablation switches (`absorb` "old"/"off", `remeasure_guard` "compatible"/"none", `refind`, `depth_all`, `max_samples`, `coh`/`min_coherence`, `bridge_unreported`, `_FIXED`) that are not part of the config and must not be built. Where this plan and the code differ, this plan wins; where this plan is silent on a detail of the frozen behaviour, the code at `3768dd2` is the reference.

Ticket: `.scratch/stripe-detector/issues/09-phase-breaks.md`. BASE `b7c6731`.
Spec: `.scratch/stripe-detector/spec.md` stories 16-19, 22, 23, 43, 48; "Report" (spec.md:106: `phase_breaks` is a list of polyline plus jump in radians); the forward model (spec.md:123-125: `+ jump * [pixel lies beyond break line]`); tolerances (spec.md:162: break position within one Period, jump within ±π/4).
GLOSSARY: **Phase Break**, **Striped Region**, **Period**, **Angle**, **Frame pixel**, **Modulation Depth**. ADR 0001: local phase is the shared foundation for breaks and forks.
Sibling: ticket 10 (forks) adds to the same module and to `_break_phase`. Nothing in this ticket is fork-specific (section 2.6).
Downstream: ticket 11 calibrates the evidence threshold; ticket 12 draws the lines; ticket 13 owns speed (the coarse-scan/fine-fit speedup is noted in its Comments). Follow-up: ticket 17 (`issues/17-region-growth-under-phase-breaks.md`, needs-triage) owns everything score-moving and the known limitations of section 8.

Evidence for the rulings: `09-plan-review.md` (B1-B6, O1, N1-N6), `09-critic.md` (C1-C5), `09-prototyper-1.md` (Q2 STOP), `09-critic-2.md` (F1-F3, scope C, 3.1-3.4), `09-critic-3.md` (absorb, chord, seeds, gates, re-measure), `09-prototyper-3.md` (guard table, depth, diagnoses), `09-prototype-p1.md` (v2, v2 speed).

## 0. Scope (ruled: option C)

- **The score path is untouched.** `score`, `striped`, `threshold` and the set of `reported` groups (`analysis.py:286`) are settled before anything in this ticket runs. No change to `_grow`, `_merge`, `_settle_overlaps`, the body of `_phase_steps`, `_refined`, the bank, or any score-path constant (F1).
- **After the threshold**, a report-level pass (section 2.3), all steps kept (P1 v2):
  1. **bridges** adjacent compatible reported regions across a break found in their union (round 1);
  2. **finds** breaks inside each resulting region;
  3. **re-measures** Period and Angle away from the found breaks, under the energy guard;
  4. **fills** the slit along each found break;
  5. **absorbs** a break-free region lying in another region's slit (constrained absorb), then runs a **second bridge round** on the re-measured values.
- **Frames with no found break: `analyse` output is identical to BASE** (every field, `labels` included), with one stated exception: a `Report.warnings` entry for each reported region whose stripes are under the finder's frame-period limit (section 2.2, step 0). Absorb and bridging cannot fire without a found break, so the pass returns its inputs unchanged when no break is accepted.
- **Out of scope, ticket 17:** overgrowth when the seed area straddles a break; `_phase_steps`' weighted mean folding the blurred jump into the candidate and merge Angle; weak breaks below the finder's limits staying Angle-biased (R5); a half-region below the threshold (R2); and the known limitations of section 8 (BASE corner fragments, a BASE separate region along a break with its own break, fake breaks inside a BASE false region). Score-moving, so `make measure`, a re-store and the held-out tests live there.
- **Straight lines only** (Q4). Record the scope note in the ticket Comments.
- **No speed work here.** The pass costs up to ~1.4 s single-process on a 400x1600 single-break frame and ~2.5 s on P 3 pairs, ~0.1 s on break-free frames (section 6). Accepted; the speedup is ticket 13's.

## 1. Where things stand (BASE)

- `synthetic.generate`: the stripe phase is `_phase(x, y, period, angle_deg, phase0) = 2π/P (x cos t + y sin t) + phase0` (`synthetic.py:398-400`): the phase grows with the column. RNG draw order: profile, phase0, mottle, noise, spikes. `GroundTruth` has `regions`, `spike_mask`, `clipped_mask`. EMCCD noise rescales by `clean.max()` (`:318`) and draws Poisson and Gamma counts that depend on the values (`:429-433`); Spikes use `clean.max()` (`:347`).
- `analyse` (`analysis.py`): bank -> candidates -> merge -> size and leakage rules -> `_settle_overlaps` -> `_refined` -> `reported` (`:286`) -> sort (`:287`) -> labels. `filters` lives only inside `_qualifying_regions` (`:438-454`); `analyse` holds no `_Filters`. `_refined` computes `gabor(period, angle_deg)` and then updates both, so its last response is tuned to the estimate before the final one (C2).
- `Report` (`report.py`, in `NOT_STAMPED_SRC`): `to_dict` order `striped, score, threshold, transposed, bin_factors, units, regions, spike_pixels, clipped_pixels, unresolved_period_px, warnings[, reader_notes]`, pinned by `test_analyse.py::test_report_converts_to_json`. `UNITS` pinned by `REPORT_UNITS`. `in_file_layout` transposes `labels` and bboxes (`report.py:220-230`). Locations (bbox, mask) are in frame px; measurements in sensor px (ticket 08 AC 4).
- Existing warnings: `_unresolved_warning` (`analysis.py:323`, Periods under `MIN_FRAME_PERIOD_PX` = 2.0 frame px, `_local_stripes.py:61`) and `_coverage_note`.
- `tests/protected.py:191`: `PHASE_BREAK_TEST_SEED = 37` (ticket 06's hand-rolled frames). It stays as it is.
- P1 at BASE (`09-prototyper-1.md`): AC 4 by the bbox reading fails 23/600; Angle misses `ANGLE_TOL_DEG` on 268/600 break frames (0/800 break-free); Period within tolerance everywhere; mask IoU < 0.8 on 123/600, mostly at π (critic-2 F2).

## 2. Seams

### 2.1 Generator: `denoisifier.synthetic`

```python
@dataclass(frozen=True)
class PhaseBreakLine:
    """A straight Phase Break across the whole frame. ``point`` (row, col) is
    any point on the line, in px. ``line_angle_deg`` is the line's direction in
    degrees from horizontal, positive descending to the right (row 0 is the
    top), so a line at ``line_angle_deg == t`` is perpendicular to stripes of
    Angle ``t``. ``jump_rad`` is the stripe phase on the positive side of the
    directed line minus the phase on the other side (see BreakTruth for the
    positive side). The stripe phase grows with the column, so a positive jump
    moves the stripes on the positive side toward column 0 by jump / 2π
    Periods."""
    point: tuple[float, float]
    line_angle_deg: float
    jump_rad: float

@dataclass(frozen=True)
class BreakTruth:
    point: tuple[float, float]        # as given
    line_angle_deg: float             # canonical, in (-90, 90]
    jump_rad: float                   # canonical: sign follows the canonical direction, wrapped to (-π, π]
    shifted: np.ndarray               # bool, frame shape: the canonical positive side, strict (> 0)
```

- `generate(..., phase_breaks: Sequence[PhaseBreakLine] = ())`. Works with and without `regions`; every Striped Region's phase gets the same breaks. Without `regions` the break applies wherever stripes are drawn, i.e. the whole frame (critic-3 §2; the implementer confirms this in `synthetic.py` and states it in the docstring).
- **Canonicalise first (B2, option B).** When `a` is outside `(-90, 90]`, flip the direction (`a ± 180`) and negate the jump; then wrap the jump to `(-π, π]`. The generator adds the canonical jump on the canonical positive side.
- **Side test.** With `d = (cos a, sin a)` in `(x = col, y = row)`, `side = d_x (y - y0) - d_y (x - x0)`; positive side is `side > 0` (strict). Pixels exactly on the line are not shifted; the docstring says so. Tests place `point` at half-integer coordinates where the tie matters. (Same rule as the prototype harness, `harness2.py:39-45`.)
- Phase: `_phase(...) + _break_phase(x, y, breaks)`, `_break_phase = Σ_b jump_b · [side_b > 0]`, a hard step (spec.md:124). Ticket 10 adds its term beside it. No "defect" in names (B6).
- **No RNG draws.** The implementation branches on `if phase_breaks:`, so the empty path does no arithmetic.
- **Identity claims (B1), stated in the `generate` docstring:**
  1. `phase_breaks=()` is bit-identical to BASE for every noise kind (the existing `_BASE_DIGESTS`, which include `scorched-emccd`).
  2. With breaks, Gaussian noise, `spikes=0`, no clip: `frame` and `clean` are bit-identical off `shifted`.
  3. With breaks and EMCCD noise: no pixel claim (C5).
- Truth: `GroundTruth.phase_breaks: tuple[BreakTruth, ...] = ()`.
- Validation (`ValueError`): every field finite, `point` a pair. A jump of 0 is allowed (no-op).

### 2.2 Detection: new module `src/denoisifier/_local_phase.py`

One deep module, unit-testable on hand-built phasor fields. Name and docstrings describe what exists now (local phase, breaks); no fork-specific API. Ticket 10 adds to the same file. Prose avoids "amplitude" (in `CURATED`), "defect" and "contrast" (B6, C4): say "magnitude", "depth", "phase difference between the two sides".

```python
def break_response(spectrum, period, angle_deg) -> np.ndarray:
    """z = 2 · (finder Gabor) / (local mean with the same window), complex,
    frame shape. Window sigmas _BREAK_SIGMA_ACROSS_PERIODS across and
    _BREAK_SIGMA_ALONG_PERIODS along the stripes, on the shared _Spectrum
    (sensor-px frequencies). Prototype: finder.narrow_z."""

@dataclass(frozen=True)
class FoundBreak:
    point: tuple[float, float]   # (Y, X) on the line, scaled sensor coordinates (see Coordinates)
    line_angle_deg: float        # canonical, (-90, 90], in the scaled sensor geometry
    jump_rad: float              # (-π, π], positive side minus the other
    evidence: float              # E, for ticket 11; not in the Report

def frame_period(period, angle_deg, bins) -> float:
    """The Period in frame px along the stripe normal."""

def find_phase_breaks(z, domain, period, angle_deg, bins) -> list[FoundBreak]:
    """Greedy, at most _BREAK_MAX_PER_REGION. [] when frame_period(...) <
    _BREAK_MIN_FRAME_PERIOD_PX (the caller reports the refusal)."""
```

**Coordinates.** The finder and the pass work in scaled sensor coordinates `Y = v · row`, `X = h · col` (frame pixel index times its bin factor; `pixel_size(bins)`), as the prototype does. Reported points are converted back with `_local_stripes.frame_px` (never divide by bins by hand; ticket 08 rule). This is an exact inverse, so the reported line is in frame-px index coordinates; the test's half-pixel centre formula (5.1) maps those to the generator's sensor coordinates. All lengths below are in Periods times the region's sensor Period, so in sensor px.

The algorithm (prototype `finder.find` at `3768dd2`; constants in section 10):

0. **Frame-period gate.** If `frame_period(P, A, bins) < _BREAK_MIN_FRAME_PERIOD_PX` (2.5), return `[]`. The constant's comment states the derivation (critic-3 §4): the finder's across window (1 P) puts the passband edge at `k` sigma at `(1/P)(1 + k/2π)`, which reaches the frame Nyquist at a frame Period of `2(1 + k/2π)` = 2.5 for `k = π/2`; it is a second, stricter limit beside `MIN_FRAME_PERIOD_PX` (2.0) for the finder only, and the bridge (which calls the finder) is disabled with it. Measured (gate seeds 110_400-110_459, 2x1): frame P 2.0 fakes, 2.1-2.25 lines 1.3-1.8 P off. Every refusal is visible (2.3 step 7).
1. **Domain samples.** Crop to the domain's bbox. Keep pixels with `|z| >= _BREAK_MIN_MAGNITUDE_FRACTION · median |z|` over the domain (the "interior"). Return `[]` if the interior has fewer than `_BREAK_MIN_INTERIOR_PX` pixels, or fewer than `_BREAK_MIN_NEIGHBOUR_PAIRS` horizontal or vertical interior neighbour pairs.
2. **Demodulate.** Carrier `kx`, `ky` = median wrapped phase step of horizontal / vertical interior neighbour pairs; `w = z · exp(-i(kx·col + ky·row))` on samples of the interior on a grid of stride `_BREAK_SAMPLE_STRIDE_PERIODS · P` (per axis, `max(1, int(stride·P / bin))` frame px, anchored at the crop origin). **No sample cap** (ruled; the cap moved line error at P 3-5).
3. **Two-magnitude fit (GLRT) per candidate line.** For line angle `a`, offsets `s` of each sample from a line through the sample mean, binned at `_BREAK_BIN_PERIODS · P`; skip the angle when the offset extent is under `2 · _BREAK_FIT_HALF_WINDOW_PERIODS` (the small-region rule). Within ±`_BREAK_FIT_HALF_WINDOW_PERIODS · P` of each offset, fit `z(s) = c-·(1 - Φ(s/σn)) + c+·Φ(s/σn)` with `σn = hypot(σa·P·sin(A - a), σl·P·cos(A - a))` from the finder's own sigmas (`_BREAK_SIGMA_*`). Evidence `E = [Re(c-*·B1 + c+*·B2) - |B1 + B2|²/N] / (N · mean|w|²)`; jump `angle(c+ · conj c-)`. A window is valid only with at least `_BREAK_MIN_SIDE_AREA_P2 · P²` of sample area on each side.
4. **Search.** Coarse angles every `_BREAK_COARSE_STEP_DEG` over `(-90, 90]`; the best (angle, offset) by E. Fine angles `a0 ± _BREAK_FINE_SPAN_DEG` every `_BREAK_FINE_STEP_DEG`, offsets within `_BREAK_FINE_OFFSET_SPAN_PERIODS · P` of the coarse one. Then, only when the angle tolerance `degrees(_BREAK_LINE_TOL_PERIODS · P / L)` (L = the samples' diagonal extent) is under half the fine step, a golden-section search over `a ± _BREAK_FINE_STEP_DEG / 2`, offsets within `_BREAK_REFINE_OFFSET_SPAN_PERIODS · P`, down to that tolerance; it replaces the fine result only when E rises. The docstring states it assumes one E peak in that interval (critic-3 §4). Canonicalise the angle to `(-90, 90]` (flip offset and jump with it).
5. **Accept** when `E >= _BREAK_MIN_EVIDENCE`, `|jump| >= _BREAK_MIN_JUMP_RAD`, and the spread is within `_BREAK_JUMP_SPREAD_RAD`: the samples in the two side bands (`2σn <= |s| < 2σn + max(1 P, window - 2σn)`) are cut into `_BREAK_SEGMENTS` equal pieces along the line; each piece with at least `_BREAK_MIN_PIECE_SAMPLES` on each side gives a per-piece jump; the spread is the largest wrapped difference from the jump (inf when no piece qualifies). E is the one scalar ticket 11 calibrates; the jump and spread rules stay fixed. The first rejected candidate ends the search.
6. **Explain away.** After each accepted break, multiply `w` on its positive side by `exp(-i·jump)`, zero `w` within ±`_BREAK_EXPLAIN_SIGMAS · σn` of the line, rescan. At most `_BREAK_MAX_PER_REGION` breaks (stated in the docstring).
7. **Small regions.** The rule of step 3 means a region shorter than about `2 · _BREAK_FIT_HALF_WINDOW_PERIODS` across a line gets no break on it. The docstring states it. Measured: heights 3-5 P changed 0/20 each (explore and v2 validation); 6 P 1/20 on validation; 8 P found 18-19/20. The test pins 5 P (`BREAK_SMALL_REGION_PERIODS`); 6-7 P is stated as undefined in the docstring and the ticket Comments.

All `_BREAK_*`, `_BRIDGE_*`, `_REMEASURE_*`, `_ABSORB_*` constants are module-level numbers, so each needs a lockfile line (approved, section 7).

### 2.3 Wiring in `analyse`: the post-threshold pass

`_qualifying_regions` also returns its `_Filters` (C2; `_Survivor` untouched). A private function, e.g. `_with_phase_breaks(survivors, reported, filters, light, clipped, bins) -> (regions, breaks, refused)`, is called between `reported = ...` (`:286`) and the sort (`:287`). `score`, `striped`, `threshold` are computed before it and never read from it. Bank σn below means `σn` with the bank's `_ACROSS`, `_ALONG` (1.0, 1.5) at the region's Period and Angle; the finder's own σn is only inside `_local_phase`. The finder's response is computed once per distinct (Period, Angle) and cached for the pass.

1. **Bridge, round 1.** For each pair of reported regions that are `_compatible` (BASE values) and whose sensor-px EDT distance (`_edt`) is at most `_BRIDGE_GAP_PERIODS · max(P_a, P_b)`: the domain is the union plus the gap pixels (pixels within that distance of both regions, inside `light`). Run the finder on it at the Period and Angle of the higher-`peak_ratio` region. Merge when one accepted break has the smaller region's share `>= _BRIDGE_SMALL_SIDE_SHARE` on one side and the larger region's share `>= _BRIDGE_LARGE_SIDE_SHARE` on the other (shares by pixel count; "line through the gap" is this side rule, no separate test). Union-find over all merging pairs. Only reported regions take part (R2 to ticket 17).
2. **Find.** For each final group (members' pixels; the domain adds the round-1 gap pixels of its merged pairs): the finder at the top member's Period and Angle. If it finds nothing and the group was merged, the round-1 bridge breaks are its breaks. No breaks: the group is unchanged.
3. **Re-measure.** Exclusion: pixels within `_REMEASURE_EXCLUDE_SIGMAS · bank σn` of any found break. If the region's pixels outside it cover at least `_REMEASURE_MIN_AREA_P2 · P²` (sensor px²), run `_phase_steps(spec.gabor(P, A), area, P, A, bins)` `_REMEASURE_STEPS` times from the reported Period and Angle (a new call path; `_refined`'s body untouched). **Energy guard** (ruled): keep the result only if the mean `|spec.gabor(P', A')|` on those pixels is at least the mean `|spec.gabor(P0, A0)|`; otherwise keep BASE's values. No re-find afterwards.
4. **Fill.** For each found break, at the region's (re-measured) Period and Angle: `half = _BREAK_FILL_SIGMAS · bank σn`, `reach = half + _BREAK_FILL_REACH_PERIODS · P`. Along-line bins of `_BREAK_FILL_BIN_PERIODS · P`; a bin qualifies when the region has pixels within `reach` on both sides of the line in it. The region's slit is the qualifying bins within `reach`. Add pixels of qualifying bins within `half` of the line that are in `light` and not owned by another region. **`owned` is updated after each fill** (critic-3 §5), so fills never overlap.
5. **Constrained absorb, then bridge round 2** (critic-3 §1, measured in v2).
   - (a) Regions in descending area: a region with a found break absorbs each smaller region **with no break of its own** whose Period ratio is at most `_MERGE_PERIOD_RATIO` and which has at least `_ABSORB_SLIT_SHARE` of its pixels in the absorber's slit.
   - (b) Then up to `_BRIDGE_ROUNDS` rounds: for each pair of current regions, the round-1 rule (step 1) on the **re-measured** Period and Angle (`_compatible`, distance, finder on union plus gap, side shares). A merged pair is reprocessed by steps 2-4 from the higher-peak region's re-measured values, with domain gap plus both slits; its pixels are the union of both plus the new fill. One merge per round; stop when none.
   - Neither can fire without a found break. The `two_break` negative (5.4) checks that two distinct regions crossed by one break stay apart.
6. **Settle.** If no region has a break and none merged, return the inputs unchanged (same objects). Otherwise, for each region with a break or a merge: `area_px`, `bbox`, `first_pixel` from its final pixels; `peak_ratio` of the top member (sort tiebreak only). **Depth:** BASE's depth is kept for a region that only gained breaks (every recompute measured worse, `09-prototyper-3.md` "Depth"); a merged region's depth is `_interior_depth` of `_depth(spec.gabor(P, A), spec.local_mean(P), light)` on its pixels outside the exclusion (all its pixels if none remain), at its final Period and Angle. Then the existing sort (area, peak, first pixel) and labelling run. `PhaseBreak.region` refers to the final labels.
7. **Refusals.** For every reported region with `frame_period < _BREAK_MIN_FRAME_PERIOD_PX`, one `Report.warnings` entry, built after labelling with its final label, placed after `_unresolved_warning`'s entry and before `_coverage_note`'s, in label order: `region {label} (Period {P:.3g} px): phase breaks were not searched at {bins} binning: its stripes fall under 2.5 frame pixels along their normal ({frame_period:.3g})` (number from the constant). Same sentence in the `analyse` docstring. This is the only change a frame with no found break can show against BASE.
8. **Segment.** For each break of a final region: the run of the region's final pixels within `_BREAK_SEGMENT_HALF_WIDTH_FRAME_PX · max(pixel_size(bins))` sensor px of the line; its two extreme points projected onto the line, converted to frame px, col increasing (top to bottom when vertical). A break with no such pixel is not reported.

Ordering of `phase_breaks`: by region label, then descending `|jump|`, then the first point in row-major order.

### 2.4 Report: `denoisifier.report`

```python
@dataclass(frozen=True)
class PhaseBreak:
    """One reported Phase Break. ``line`` is a polyline of (row, col) points in
    frame px (two points in this version: the break's run across its region).
    ``jump_rad``, in (-π, π], is the local stripe phase on the positive side
    minus the other side; the positive side is where
    cross(end - start, p - start) > 0, with cross(a, b) = a_col·b_row - a_row·b_col.
    The stripe phase grows with the column, so a positive jump moves the stripes
    on the positive side toward column 0 by jump / 2π Periods (toward row 0 in
    file layout when transposed). In the analysed frame the points are in
    col-increasing order, so the positive side is below a horizontal line; in
    file layout they are row-decreasing. Near vertical, point order and the
    sign flip together. ``region`` is the label of its Striped Region."""
    region: int
    line: tuple[tuple[float, float], ...]
    jump_rad: float
```

- `Report.phase_breaks: tuple[PhaseBreak, ...] = ()`. `to_dict` puts `"phase_breaks"` right after `"regions"`; entries `{"region": k, "line": [[row, col], [row, col]], "jump_rad": j}`. Ticket 10 puts `"forks"` after it.
- **Frame px (O1).** `UNITS["line"]`: `"frame px, (row, col) points; file layout when transposed (points swapped and order reversed)"`. `UNITS["jump_rad"]`: `"radians, phase on the positive side (cross-product rule) minus the other; same value in both layouts"`.
- **`in_file_layout` (B3):** swap each point's (row, col) **and reverse the point order**; keep `jump_rad`.
- Export `PhaseBreak` from `denoisifier.__init__`; add it to the `Report` docstring.

### 2.5 CLI

The JSON gains the key. No new flag; stderr unchanged; help unchanged. The refusal warning reaches the JSON through the existing `warnings`.

### 2.6 Ticket 10

`_local_phase.py` and `_break_phase` are where ticket 10 adds. `Report.forks` goes after `phase_breaks`. The spread rule (2.2 step 5) keeps a fork from reading as a break; no fork code here.

## 3. Prototype P1: done

Frozen v2 at `3768dd2`, decided on explore (109_000-109_599 plus the v2 extras), validated once on 110_000-110_399 with nothing changed after. Headline, explore / **v2 validation**: AC 2 300/300 / **199/200**; AC 2 full 20/20 / **19/20**; AC 3 300/300 / 200/200; AC 4 region 599/600 / 400/400; AC 4 full 20/20 / **18/20**; split-type 60/60 / 39/40; Angle max 0.76° / **0.93°** (BASE 3.57°); Period max 0.8% / 1.3%; IoU 599/600 / 398/400 (BASE 326/400); fakes 0 on every break-free set; `two_break` merges 0/20 / 0/20. Every validation miss is diagnosed in `09-prototype-p1.md` "v2 validation failures" and is either a section-8 limitation (ticket 17) or the near-parallel resolution limit (110120). The test seeds (`PHASE_BREAK_TEST_SEEDS`) have not been run by anyone.

## 4. Implementation steps (each ends on `make test-fast` green; test-first)

0. **Protected numbers and BASE evidence.**
   - In `tests/protected.py`, add the numbers of section 7; `BREAK_PROTOTYPE_SEEDS` and `BREAK_VALIDATION_SEEDS` appended to `USED_SEEDS`; `PHASE_BREAK_TEST_SEEDS` inside `TEST_SEED_BLOCK`. Lockfile lines (approved, section 7).
   - Run a BASE-output script (scratchpad, not committed) before any detector edit. It saves `to_json()` and `labels` (`.npy`) for: clear stripes; two regions; spikes plus clipped; Stripe-free mottled; one 2x1 binned frame **with frame Period >= 2.5** (e.g. `BINNING_TEST_SEEDS[2]`, P 8: otherwise the refusal warning is an expected diff); one typical EMCCD region frame; and two compatible neighbouring regions from `tests/regions.py`'s `two_regions` at equal Periods (critic-2 R1). It also records the region count of the refusal-test frame (5.4, B7), which must be exactly one. The diff in step 6 is this script, quoted in the handoff; no committed fixture (N3).
1. **Generator.** Tests first (AC 1, section 5), then `PhaseBreakLine`, `BreakTruth`, `_break_phase`, `phase_breaks=`. Export `PhaseBreakLine` from `denoisifier.synthetic`. `generate` docstring states B1's three claims and the full-frame extent.
2. **Report.** `PhaseBreak`, `Report.phase_breaks`, `to_dict`, `UNITS`, `in_file_layout` (swap + reverse), export. Extend the key list in `test_report_converts_to_json` and `REPORT_UNITS`. Unit tests on a hand-built Report, including the side of a pixel in both layouts.
3. **Test helpers.**
   - `tests/breaks.py`: `break_region_case(seed, jump, line_angle_deg, *, noise=...)` cached with `normalised_cache` on the `regions.single_region` geometry, line through the region centre (half-integer `point`); `break_full_frame_case(...)` (400x1600, `PROBE_SHAPE`); `break_pair_case(...)`; `two_break_case(seed)` (5.4); a Gaussian-noise variant for the paired checks; binned frames through `tests/binning.py` (generated at sensor size, block-summed).
   - `tests/truth_match.py`: `assert_break_matches(found, truth, chord_mask, overshoot_mask, period, bins)` (5.1), `assert_region_covers_both_sides(region_mask, truth, line, period, bins)` (5.3; **an empty side fails**, critic-3 §5) and `truth_lit_mask(synthetic, bins)` (5.1, generator side, never `analysis._light`, N4).
   - Helper unit tests on hand-built `PhaseBreak` objects, including the empty-side failure.
4. **`_local_phase.py`, on synthetic phasor fields.** Tests first on noise-free `z = exp(i(k·r + j·[side > 0]))`:
   - line angles 0, 30, 60, 90, 135 and jumps ±π/2, π: line within `BREAK_EXACT_POSITION_TOL_PERIODS`, jump within `BREAK_EXACT_JUMP_TOL_RAD`, **and the sign of a +π/2 jump is +** for a line at 10° (direction-aligned, 5.1; the noise-free sign test at the finder level);
   - break-free field → `[]`; a ±1 winding → `[]`;
   - two half-discs with a dim gap band and a jump between them, run on the union plus gap → one break through the gap (the bridge's unit test);
   - a region shorter than `2 · _BREAK_FIT_HALF_WINDOW_PERIODS` across the line → `[]`;
   - `frame_period(...) < _BREAK_MIN_FRAME_PERIOD_PX` → `[]`.
   Then the implementation with section 10's constants. Add `_local_phase.py` to `STAMPED_FILES` (approved).
5. **The post-threshold pass in `analyse`** (2.3), test-first: unit tests that the pass returns the same objects when nothing is accepted, that fills of two regions never overlap (`owned` update), and that absorb never fires on a region with its own break; then the AC tests of section 5.
6. **BASE diff.** Re-run step 0's script; the diff (all keys, `labels` included) must be empty on every frame. Quote it.
7. **AC tests on the real path** (section 5), the supporting tests (5.4) and the CLI test.
8. **Docs.**
   - `analyse` docstring: breaks are found after the threshold, in reported regions and between adjacent compatible ones; a found break may merge two regions, fill the slit, absorb a break-free region in the slit, and re-measure Period and Angle (kept only when it fits the stripes at least as well); depth is BASE's unless regions merged; the score never depends on breaks; the frame-period refusal and its warning; E's threshold is conservative on purpose until ticket 11 (no rate claimed).
   - `Report` / `PhaseBreak` docstrings (C1 direction sentence).
   - GLOSSARY: **Phase Jump**: "the stripe phase difference across a Phase Break, in radians, in (-π, π]; a jump of π shifts the stripes by half a Period", with C1's direction sentence. `_Avoid_`: phase step, shift size.
   - ADR 0001, Consequences, one line: "Phase breaks are found from the demodulated local phase of each reported region (a two-magnitude fit across straight lines), after the threshold."
9. **Ticket Comments** (`issues/09-phase-breaks.md` gains a `## Comments` section; each entry dated, with its reason):
   - **Approvals** (orchestrator): adding `src/denoisifier/_local_phase.py` to `STAMPED_FILES` (strengthens the stamp; forced by `test_stamped_files_cover_the_slow_tier`); lockfile additions for every new detector constant of section 10 and every new protected number and seed range of section 7 (new pins, nothing loosened; the `USED_SEEDS` edit extends an existing line).
   - The AC 4 reading (5.3) and the separate measurement test (critic-3 §3).
   - The 5.1 chord definition for full frames (critic-3 §2): coverage against the generator-side lit mask, overshoot against the frame-clipped line (vacuous on full frames; region frames carry the bound).
   - Straight lines only (Q4). Frame px for break lines, departing from the literal spec.md:114, with the proposed one-line spec edit for the owner at close (O1).
   - Scope C and ticket 17; the config (v2 at `3768dd2`): constrained absorb, frame-period gate 2.5 with its warning, energy guard (replacing critic-3's `_compatible` guard, which put 109/300 frames over 1°), `remeasure_min_p2` floor, `update_owned`, BASE depth kept, no sample cap.
   - Speed accepted (section 6 numbers); the speedup noted in ticket 13.
   - The measured P1 v2 rates (section 3) and the known limitations sent to ticket 17 (section 8).
   - Seed policy: pre-declared seeds, no pass counts, no exclusion in advance. A red seed by a ticket-17 mechanism is a finding; only then may the orchestrator approve a `xfail(strict=True)` on that one parameter, citing ticket 17, recorded here.
   - The undefined region heights 6-7 P (2.2 step 7).
10. **Closing sequence**, after the review fixes (section 6): `make check-slow`, then `make check`. Nothing else. Owner notes at close: ticket 17; the AC 4 reading; the spec.md:114 line; straight lines only.

## 5. Acceptance criteria -> tests (real path)

Every AC frame is built by `generate(..., phase_breaks=[...])` and run through `analyse(s.frame)` (binned frames: the block-summed frame with its bin factors) at the default calibration. The CLI test goes through `denoisifier` on a written CSV.

Seeds: `PHASE_BREAK_TEST_SEEDS = range(10, 20)` (test seeds may share; never run before this plan). The case is `CASES[seed % 10]`: P 3, 5, 8, 12, 20, 4, 16, 6, 10, 14 for seeds 10-19. `inner(...)` takes the first `INNER_LOOP_SEED_COUNT` seeds and the rest are `wide`. No test gets a `wide` mark by hand. A red seed is a finding for the orchestrator, never a re-pick, never a pass count, never an exclusion in advance (section 4 step 9).

### 5.1 Break match metric (`truth_match.assert_break_matches`)

A true break is found when exactly one reported break in its region satisfies all of:
- **Line.** Every point of the reported segment, sampled every frame pixel, lies within `BREAK_POSITION_TOL_PERIODS · P` of the true infinite line, distance in sensor geometry. A frame pixel `r` has its centre at sensor `v·r + (v - 1)/2` (rows; likewise cols with `h`).
- **Coverage.** The segment's projection onto the true line covers at least `BREAK_CHORD_COVER_MIN` of the true chord: the extent along the line of the chord-mask pixels within `0.5 · max(pixel_size)` sensor px of it. Chord mask: region frames, the truth region (`mask >= 0.5`, binned with `bin_truth_mask`); full frames, the generator-side lit mask `truth_lit_mask`: `gaussian_filter(s.clean, BREAK_LIT_SIGMA_PX)` at sensor size, block-meaned to the frame, `>= BREAK_LIT_LEVEL · max` (one fixed sigma, critic-3 §2).
- **Overshoot.** Neither end lies more than `BREAK_POSITION_TOL_PERIODS · P` beyond the overshoot chord: region frames, the truth region's chord; full frames, the frame-clipped true line, so the bound is vacuous there (stated in the helper's docstring; region frames carry it).
- **Jump.** Align directions first: flip the found jump iff the reported direction (point order, cross-product rule) and the truth's direction have a negative dot product (critic-2 3.2). Never "try both signs". Then `|wrap(found - truth)| <= BREAK_JUMP_TOL_RAD`.
- **No extras.** No other reported break in that region.

### 5.2 Table

| AC | File :: test | Asserts |
|---|---|---|
| 1 | `test_synthetic.py::test_phase_break_shifts_every_stripe_on_one_side[angle, jump]` | `angle` in {0, 10, 45, 90, -60, 135}, `jump` in {π/2, π, 2.0}; noise 0, `PHASE_BREAK_TEST_SEEDS[0]`. `shifted` equals the strict side test from the returned `point` and canonical angle; `truth.jump_rad` is the canonical, wrapped jump; off `shifted`, `clean` bit-equal to the break-free `clean`; on `shifted`, `c_j = clean_j / env - 1` equals `c_0 cos j + c_{π/2} sin j` within `BREAK_PHASE_ATOL` (`env` from `modulation_depth=0`). |
| 1 (identity) | `test_synthetic.py::test_no_phase_breaks_leaves_frames_unchanged` | `phase_breaks=()` keeps every `_BASE_DIGESTS` entry (EMCCD included). With one break, Gaussian noise, `spikes=0`, no clip: `frame` and `clean` bit-identical off `shifted`. No EMCCD pixel claim (B1). |
| 1 (truth) | `test_synthetic.py::test_phase_break_truth_is_canonical[a]` | `a` in {100, 270, -90}: canonical angle in (-90, 90], jump negated and wrapped, `shifted` is the canonical positive side; `(a, j)` and `(a - 180, -j)` give the same truth and frames that differ by a global phase only. Breaks apply inside `regions` and over the whole frame without them; invalid fields raise; a pixel on the line is not shifted. |
| 1 (sign, C1, noise-free) | `test_synthetic.py::test_positive_jump_moves_stripes_toward_column_zero` | Noise-free `clean`, seed `PHASE_BREAK_TEST_SEEDS[0]` with explicit P 20 and stripe Angle 0, line at 10°, jump +π/2: along a row on the positive side, the stripe term of the break frame is the break-free stripe term moved toward column 0: the best cross-correlation lag is `-P/4` columns (5 px, exact on the integer grid). A wrong sign gives `+P/4`. |
| 2 | `test_analyse.py::test_phase_breaks_are_found_and_measured[seed]` | `regions` geometry, typical (EMCCD) noise, scorched Mottle, depth 0.5. One break through the region centre at `line_angle = case Angle + {0, 5, -5}[seed % 3]`; jump cycles {π/2, 2π/3, π, -π/2, -3π/4} by seed. 5.1 only. |
| 2 (full frame) | `test_analyse.py::test_phase_break_in_full_frame_stripes_is_found[seed]` | `PHASE_BREAK_TEST_SEEDS[:4]` (P 3, 5, 8, 12), 400x1600, jump π/2 and π alternating, line angle 0 through the centre. 5.1 with the full-frame chord. |
| 2 (sign end to end) | `test_analyse.py::test_reported_jump_sign_matches_the_generator` | Seed `BREAK_SIGN_TEST_SEED` (= `PHASE_BREAK_TEST_SEEDS[0]`), `regions` geometry, explicit Period `BREAK_SIGN_TEST_PERIOD` (10) and stripe Angle 0, Gaussian noise at the generator's default Gaussian level, `spikes=0`, no clip; line at 10° through the region centre, jump +π/2 → reported jump within `BREAK_JUMP_TOL_RAD` of +π/2 without direction flipping needed (C1). |
| 3 | `test_analyse.py::test_phase_break_at_an_unusual_angle_is_found[line_angle, jump]` | `line_angle` in {45, 90, -60}; `jump` in {π/2, π}; region frames `PHASE_BREAK_TEST_SEEDS[0:2]`, `inner`/diagonal covering subset. 5.1; along a vertical line the chord is the region's height. |
| 4 | `test_analyse.py::test_frame_with_phase_breaks_is_one_striped_region[...]` | Every frame of AC 2 and AC 3 (shared cache). 5.3 only: `striped`, exactly one region, both sides covered. Plus the invariant: each region's `area_px == (labels == k).sum()`. |
| 4 (full frame) | `test_analyse.py::test_phase_break_does_not_split_full_frame_stripes[seed]` | The AC 2 full frames: 5.3 against the truth lit mask. Not described as "the same frame plus a break" (EMCCD, C5). |
| 4 (paired) | `test_analyse.py::test_phase_break_does_not_split_paired_gaussian_frames[seed]` | Gaussian-noise variant, `PHASE_BREAK_TEST_SEEDS[:2]`: the frame with and without the break are bit-identical off `shifted`; both give exactly one region; the break frame covers both sides. |
| 4 (measurements) | `test_analyse.py::test_phase_break_frames_keep_period_angle_and_mask[...]` | The AC 2 and AC 3 region frames (shared cache). The region with the most truth pixels: Period within `PERIOD_REL_TOL`, Angle within `ANGLE_TOL_DEG`, mask IoU `>= MASK_IOU_MIN`. Its own test (critic-3 §3), so a ticket-17 mechanism reddens this, not AC 2. Depth not asserted (BASE depth kept; 364/420 within `DEPTH_TOL`, equal to BASE). |
| 5 | `test_analyse.py::test_report_lists_phase_breaks` | On the AC 2 frame of `PHASE_BREAK_TEST_SEEDS[0]`: `to_dict()["phase_breaks"]` is a list of `{"region", "line", "jump_rad"}`; `line` a list of [row, col] pairs; `jump_rad` a float; `region` a reported label; `json.loads(to_json())` round-trips; the extended key order is pinned (`test_report_converts_to_json`). A break-free frame gives `[]`. |
| 5 (CLI) | `test_cli.py::test_cli_reports_phase_breaks` | A CSV with one break: the JSON has one entry. With `--transpose` on a transposed file: points swapped and order reversed, `jump_rad` equal, and a known pixel on the shifted side is on the positive side by the cross-product rule in file layout (B3). stderr empty. |

### 5.3 AC 4 reading (critic-2 §1, ruled; record in the ticket Comments)

"Not split into fake separate regions" means: `report.striped`; exactly one reported region; and that region covers both sides of the true line: on each side, at least `BREAK_SIDE_COVER_MIN` (0.5) of the truth pixels (`mask >= 0.5`; truth lit mask for full frames) farther than `BREAK_SIDE_EXCLUDE_PERIODS · P` (2.5) from the line are in the region. **A side with no such truth pixels fails** (critic-3 §5). The bbox reading is dropped (F2). Period, Angle and IoU on break frames are asserted in their own test (5.2, "4 (measurements)").

### 5.4 Supporting tests

- `test_frames_without_a_found_break_match_the_pass_free_analysis[frame]` (**identity to BASE on the real path**): for the `REGION_TEST_SEEDS` single-region frames (`single_region_case`), the `TWO_REGION_TEST_SEEDS` frames, one 2x1 binned full frame at `BINNING_TEST_SEEDS[2]` (P 8, frame Period above the gate) and one Stripe-free frame: `analyse` as built and `analyse` with `_with_phase_breaks` monkeypatched to return its inputs and no breaks or refusals give equal `to_dict()` and equal `labels`; `phase_breaks == ()`. Zero fakes is required (B4). Complemented by step 6's BASE-commit diff.
- `test_two_regions_crossed_by_one_break_stay_apart[seed]` (**the `two_break` negative**, critic-3 §1.3): `PHASE_BREAK_TEST_SEEDS`, `k = seed - 10`: `two_regions(p, p, angle_deg=(A, A + offset), gap_windows=g)` on a 640x1024 frame with `p = (5, 8, 12, 6)[k % 4]`, `g = (2/3, 1.0)[(k // 4) % 2]` (2 or 3 P), `offset = (3, 10)[(k // 2) % 2]`, `A = CASES[seed % 10].angle_deg`, one horizontal break through the frame centre with jump `(π, π/2)[k % 2]` (prototype `harness2.two_break`). Asserts: no reported region covers at least `BREAK_SIDE_COVER_MIN` of both truth regions' cores (`mask >= 0.5`). The handoff lists per seed whether a break was found (evidence the negative is live).
- `test_phase_breaks_are_not_searched_under_the_frame_period_limit` (plan-review B7): a 2x1 full frame at sensor Period `BREAK_REFUSAL_TEST_PERIOD` (4.7; frame Period 2.35, strictly between `MIN_FRAME_PERIOD_PX` 2.0 and the 2.5 gate, away from the frame Nyquist), Angle 0, with a horizontal π break, `BINNING_TEST_SEEDS[0]`: `phase_breaks == ()` and `warnings` holds the refusal sentence for region 1 with its frame Period. Not a skip. **Before step 7**, confirm at BASE (step 0's script) that this frame reports exactly one region; if not, stop: that is a finding for the orchestrator, not a seed re-pick.
- `test_two_parallel_phase_breaks_are_both_found[seed]`: full 400x1600 frames, two horizontal breaks `BREAK_PAIR_SEPARATION_PERIODS` apart about the centre, jumps π/2 and π; seeds: the `PHASE_BREAK_TEST_SEEDS` whose case Period is at least `BREAK_PAIR_MIN_PERIOD` (5), i.e. 11, 12, 13, 14, 16, 17, 18, 19 by the case table, via `inner`. Both matched (5.1, full-frame chord), no extras.
- `test_phase_breaks_only_in_reported_regions`: at `threshold=inf`, no regions and `phase_breaks == ()`.
- `test_binned_phase_break_is_found[bins, seed]`: 2x1 and 1x2 through `tests/binning.py`, full frame, horizontal π break, `BINNING_TEST_SEEDS[2:]` (P 8, 12: frame Period above the gate at every Angle; P 3 is ticket 08's unresolved range, P 5 sits on the gate). 5.1 in sensor geometry with the half-pixel centre formula and AC 4 (5.3).
- `test_small_region_reports_no_phase_break`: a region `BREAK_SMALL_REGION_PERIODS` (5) Periods tall (the `single_region` geometry with that height, horizontal π/2 break through the centre, `PHASE_BREAK_TEST_SEEDS[1]`): `phase_breaks == ()` and the report equals the pass-free analysis (monkeypatch as above).
- The `_local_phase` unit tests of step 4 (including the finder-level sign test) and the pass unit tests of step 5.

## 6. Do scores move? Gates

**No. The score is not meant to move, and cannot by construction.**
- `score`, `striped`, `threshold` and `reported` are computed before the pass; the pass never feeds back into them. No score-path code or constant changes (F1).
- Frames with no found break give `analyse` output identical to BASE, apart from the refusal warning under the frame-period limit (2.3 step 7). Default generator frames (no `phase_breaks`) are bit-identical to BASE, so every slow-tier, calibration and feasibility frame is unchanged.
- The slow tier asserts scores and verdicts, which the pass cannot touch.
- So: no `make measure`, no stored-threshold update, no calibration re-store, no `make check-held-out`. Ticket 09 is not a measure milestone.
- **Closing sequence (the fixer runs exactly these):** `make check-slow` (stamped files change: `synthetic.py`, `analysis.py`, `_local_phase.py`, `tests/protected.py`, `tests/slow_stamp.py`), then `make check`. Background, idle machine, per CLAUDE.md. The handoff quotes the step-6 BASE diff and both gate lines.
- **Speed (ruled: accepted as is).** Single process, idle, 400x1600: post pass ≤ ~1.4 s on single-break frames (P 3 worst: mean 1.09, max 1.39 s; P 10: 0.32 s), ~2.5 s on P 3 pair frames, ~0.1 s on break-free frames (one finder response per region, no break found). `make bench` frames are break-free, so unaffected; `make check-slow`'s timed probe frames (`SLOW_TIMING_LIMIT_S`) are break-free too. The per-test 60 s timeout is far above a full-frame AC test (~5 s `analyse` + ≤ 2.5 s). The coarse-scan / fine-window finder speedup is ticket 13's (noted in its Comments). No cap or speed change in this ticket.
- **If the plan has to change:** any step that touches the score path is ticket 17's work. If one is still needed here, stop and escalate.

## 7. Approvals and protected numbers

**Approved by the orchestrator** (record each in the ticket Comments with its reason, step 9):
- adding `src/denoisifier/_local_phase.py` to `STAMPED_FILES` in `tests/slow_stamp.py` (strengthens the stamp; forced by `test_stamped_files_cover_the_slow_tier`);
- lockfile additions for every detector constant of section 10 (in `_local_phase.py` and `analysis.py`) and every protected number below: new pins, nothing loosened.

**Lockfile additions in `tests/protected.py`:**

| Number | Value | Notes |
|---|---|---|
| `BREAK_POSITION_TOL_PERIODS` | `1.0` | spec.md:162 |
| `BREAK_JUMP_TOL_RAD` | `math.pi / 4` | spec.md:162 |
| `BREAK_MIN_FOUND_JUMP_RAD` | `math.pi / 2` | AC 2; smallest test jump |
| `BREAK_CHORD_COVER_MIN` | `0.6` | 5.1; matched min 0.776, p1 0.799 (explore v1) |
| `BREAK_SIDE_COVER_MIN` | `0.5` | 5.3; one-region frames min 0.785 apart from R2 frames |
| `BREAK_SIDE_EXCLUDE_PERIODS` | `2.5` | 5.3 |
| `BREAK_LIT_SIGMA_PX` | `10.0` | 5.1 full-frame lit mask, sensor px (critic-3 §2) |
| `BREAK_LIT_LEVEL` | `0.1` | 5.1 full-frame lit mask |
| `BREAK_PHASE_ATOL` | `1e-9` | generator identity and sign |
| `BREAK_EXACT_POSITION_TOL_PERIODS` | `0.25` | noise-free unit tests |
| `BREAK_EXACT_JUMP_TOL_RAD` | `0.05` | noise-free unit tests |
| `BREAK_PAIR_SEPARATION_PERIODS` | `6` | 5.4; v2 validation 20/20 at 6 P (5 P 17/20) |
| `BREAK_PAIR_MIN_PERIOD` | `5` | 5.4; P <= 4 misses at 6 P on v1 |
| `BREAK_SIGN_TEST_SEED` | `PHASE_BREAK_TEST_SEEDS[0]` | 5.2 "2 (sign end to end)" (N7) |
| `BREAK_SIGN_TEST_PERIOD` | `10` | same test; stripe Angle 0, line 10°, jump +π/2 |
| `BREAK_REFUSAL_TEST_PERIOD` | `4.7` | 5.4 refusal test, sensor px under 2x1 (B7) |
| `BREAK_SMALL_REGION_PERIODS` | `5` | 2.2 step 7; 3-5 P 0/20 changed, explore and validation |
| `PHASE_BREAK_TEST_SEEDS` | `range(10, 20)` | test seeds may share |
| `BREAK_PROTOTYPE_SEEDS` | `range(109_000, 109_600)` | explore (incl. v2 extras); in `USED_SEEDS` |
| `BREAK_VALIDATION_SEEDS` | `range(109_600, 110_460)` | v1 validation 109_600-109_999, v2 validation 110_000-110_399, gate seeds 110_400-110_459; in `USED_SEEDS` |

The `USED_SEEDS` edit extends an existing lockfile line, as in ticket 08. `test_seed_sets_are_disjoint_and_unused` must stay green (the orchestrator checked these ranges are unused).

**Expected-value extensions** (no check removed): the `test_report_converts_to_json` key list gains `phase_breaks`; `REPORT_UNITS` gains `line` and `jump_rad`.

**Not touched:** existing tolerances (`MASK_IOU_MIN`, `ANGLE_TOL_DEG`, `PERIOD_REL_TOL` reused unchanged; `BBOX_TOL_PERIODS` not used); `skip`/`xfail` (except the after-a-red rule of step 9, which needs its own approval), warning or lint suppression, hand-added `wide`; timeouts and gate config; the seed guard and `CALIBRATION_SEEDS` (P1 seeds are reserved, not registered); the stored calibration, its digest, and the pass counts; `MIN_FRAME_PERIOD_PX`.

## 8. Residual risks and known limitations

Known limitations, measured on P1 v2 and appended to ticket 17 (not fixed here; a test seed hitting one is a finding, step 9):
- **BASE corner fragments**: BASE reports a second compatible region far from the break (full_break 110303, bin1x2 110392); present in the break-free twin. AC 4 full frames 18/20 on validation.
- **BASE separate region along a break, with its own break** ("junction region"; 110319, 110370, 110383, 110385; explore 109509, 109515, 109448): constrained absorb skips a region with its own break, round 2 refuses it as not `_compatible`; it may also own the line's pixels so the main break gets no segment. The "same-line break" absorb extension was not adopted (needs a new explore/validation cycle).
- **Fake breaks inside a BASE false region** (109797: a 944 px P 4.28 BASE false positive at the frame edge, 3 accepted breaks at E 0.54-0.80). No principled finder guard found (coherence measured, no separation). Also a ticket-11 note: a fake region gets fake breaks.
- **Sub-threshold halves (R2)**: one half of a broken region under the threshold is not bridged (109221, bin2x1 110393, 109972; one-sided regions on the 3-region timing frames 109580, 109582).
- **Half-bin offset bias on grid-aligned lines** (added at implementation, `09-critic-4.md` 1b): in `_Samples.scan`, `lo = s.min()` is itself a sample, so on a line at 0° or 90° every sample sits on the left edge of its `_BREAK_BIN_PERIODS` bin while the fit treats it as the bin centre. Measured (noise-free, P 8, line 0°, point moved over one Period in 0.5 px steps): centre error mean -0.125 P (-1.0 px), max 0.25 P; tilted lines unbiased. A scratch trial `lo = s.min() - bin / 2` removes the centre bias at 0° (mean -0.15 px) but not the 90° angle error (max 1.5°, end 0.46 P). Not changed in 09 (it would un-validate the frozen finder); inside every P1 number and AC 2's 1 P. Sent to ticket 17.
- **Frame Period under 2.5 frame px (AC 4 not held)** (added at implementation, `09-critic-4.md` 2): the finder and the bridge are disabled there, so a break is not found and a region BASE splits at it stays split; the refusal warning per region is the only sign. Measured on the refusal-test frame (2x1, sensor P 4.7, horizontal π break, `BINNING_TEST_SEEDS[0]`): 2 regions, 2 warnings; its break-free twin, 1 region, 1 warning. Stated in the `analyse` docstring.

Other risks:
- Near-parallel lines at small P (line 5° from the stripes, P 3-4): the line can be 1.15-6.4° off (110120, 109765), a resolution limit; AC 2 at seeds 10 and 15 (P 3, 4) carries it.
- Angle margin: validation max 0.93° against 1°.
- E's threshold is conservative and uncalibrated until ticket 11; no fake rate is claimed. A fake break has side effects on regions (merge, fill, re-measured Angle), never on the score.
- Weak breaks keep their Angle bias (R5); overgrowth remains; ticket 17.
- Binned frames at frame Period 2.0-2.5 are not searched (warned) and lose AC 4 when BASE splits them.
- Curved breaks: reported as their best straight run or as two breaks.
- Demodulation's median carrier assumes no strong Period drift within a region.

## 9. Rulings folded (for the record)

| Item | Ruling |
|---|---|
| Q1 | P1's finder: own narrow Gabor, two-magnitude GLRT, explain-away |
| Q2 / C3 | Scope C (section 0); ticket 17 for the score-moving part |
| Q3 | Accept, with B3, C1, O1 |
| Q4 | Straight lines only; scope note in Comments |
| Q5 | Superseded by B4: zero fakes with margin; E is ticket 11's scalar |
| Q6 | `_local_phase.py`; stamp edit approved |
| Q7 | Accept: reported regions (and bridges between them) only |
| Q8 | Strict reading plus overshoot bound; loosening only by the owner |
| Q9 | Phase Jump, with C1's sentence |
| B1-B6, O1, C2 | 2.1, 2.4, B4, step order, names; frame px; `_qualifying_regions` returns `_Filters` |
| AC 4 | 5.3 (critic-2 §1); measurements in their own test (critic-3 §3) |
| critic-3 1 | Constrained absorb (slit bins, no own break, Period ratio) + round-2 bridge; `two_break` negative; kept (8 frames lost without it) |
| critic-3 2 | Full-frame chord: generator lit mask (fixed σ), overshoot vs frame-clipped line; empty side fails |
| critic-3 3 | Pre-declared seeds; no pass count; no exclusion in advance; strict `xfail` only after a red, with approval |
| critic-3 4 | Gate 2.5 derived and measured, refusal in `Report.warnings`, tested; golden section accepted; cap measured and dropped |
| critic-3 5 | Re-measure floor `remeasure_min_p2`; `owned` updated; depth: BASE kept (measured) |
| P1-5 v2 | Energy guard accepted; 109797 and the validation failures to ticket 17 |
| Final | Config = v2 at `3768dd2`, no sample cap; speed accepted, speedup to ticket 13; limitations to ticket 17 |

## 10. Constants (P1 v2, `3768dd2`; were placeholders)

Detector, `_local_phase.py` (prototype name in brackets):

| Constant | Value | Prototype |
|---|---|---|
| `_BREAK_SIGMA_ACROSS_PERIODS` | `1.0` | `s_across` (filter and fit σn) |
| `_BREAK_SIGMA_ALONG_PERIODS` | `0.5` | `s_along` |
| `_BREAK_MIN_MAGNITUDE_FRACTION` | `0.5` | `amp_frac` (was `_BREAK_MIN_DEPTH_FRACTION`) |
| `_BREAK_MIN_INTERIOR_PX` | `50` | literal in `find` |
| `_BREAK_MIN_NEIGHBOUR_PAIRS` | `8` | literal in `find` |
| `_BREAK_SAMPLE_STRIDE_PERIODS` | `0.5` | `stride`; no cap (`max_samples` 0) |
| `_BREAK_BIN_PERIODS` | `0.25` | `bin` |
| `_BREAK_FIT_HALF_WINDOW_PERIODS` | `4.0` | `window` |
| `_BREAK_MIN_SIDE_AREA_P2` | `6.0` | `min_side` |
| `_BREAK_COARSE_STEP_DEG` | `3.0` | `coarse_deg` |
| `_BREAK_FINE_SPAN_DEG` | `3.0` | `coarse_deg` (fine scan ± one coarse step) |
| `_BREAK_FINE_STEP_DEG` | `0.5` | `fine_deg` |
| `_BREAK_FINE_OFFSET_SPAN_PERIODS` | `2.0` | literal (`<= 2 * period`) |
| `_BREAK_LINE_TOL_PERIODS` | `0.1` | `line_tol` (golden section) |
| `_BREAK_REFINE_OFFSET_SPAN_PERIODS` | `1.0` | literal (`<= period`) |
| `_BREAK_MIN_EVIDENCE` | `0.1` | `min_evidence` (break-free max 0.082, true min at π/2 0.18). Kept at 0.1 (N9): the margin over 0.082 is narrow, but that break-free maximum (109410, \|jump\| 0.72) also fails the jump gate, and no break-free candidate passed the jump and spread gates. |
| `_BREAK_MIN_JUMP_RAD` | `math.pi / 4` | `min_jump` |
| `_BREAK_SEGMENTS` | `3` | `segments` |
| `_BREAK_MIN_PIECE_SAMPLES` | `3` | literal |
| `_BREAK_JUMP_SPREAD_RAD` | `math.pi / 4` | `max_spread` |
| `_BREAK_EXPLAIN_SIGMAS` | `2.0` | literal `g = 2 * sn` (explain-away zone and side-band gap) |
| `_BREAK_MAX_PER_REGION` | `4` | `max_breaks` |
| `_BREAK_MIN_FRAME_PERIOD_PX` | `2.5` | `min_frame_period` (derivation in 2.2 step 0) |

Pass, `analysis.py` (or `_local_phase.py`; either way stamped and locked):

| Constant | Value | Prototype |
|---|---|---|
| `_BRIDGE_GAP_PERIODS` | `4.0` | `bridge_gap` (max of the pair's Periods, sensor-px EDT) |
| `_BRIDGE_SMALL_SIDE_SHARE` | `0.8` | `side_frac` |
| `_BRIDGE_LARGE_SIDE_SHARE` | `0.5` | `side_frac_large` |
| `_BRIDGE_ROUNDS` | `3` | round-2 loop bound |
| `_BREAK_FILL_SIGMAS` | `1.0` | `fill_k` (bank σn) |
| `_BREAK_FILL_REACH_PERIODS` | `1.0` | `fill_reach` |
| `_BREAK_FILL_BIN_PERIODS` | `0.5` | `fill_bin` |
| `_REMEASURE_EXCLUDE_SIGMAS` | `2.0` | `excl_k` (bank σn) |
| `_REMEASURE_STEPS` | `6` | `steps`; start = the reported values; guard = energy; no re-find |
| `_REMEASURE_MIN_AREA_P2` | `9.4` | `remeasure_min_p2` (one bank Gabor footprint, 2π·`_ACROSS`·`_ALONG` ≈ 9.42; a floor, never hit on explore) |
| `_ABSORB_SLIT_SHARE` | `0.6` | `absorb_frac` (constrained); Period ratio `_MERGE_PERIOD_RATIO` (existing) |
| `_BREAK_SEGMENT_HALF_WIDTH_PIXELS` | `0.75` | `0.75 * max(bins)` sensor px (`seg_k` 0) |

Decisions: fill kept; re-measure kept (energy guard, floor); absorb constrained kept; `update_owned` on; depth BASE (merged regions re-measured); no re-find; no sample cap; gate 2.5 with warning.
Protected: section 7 (all filled).
