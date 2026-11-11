# 05 plan: striped regions and mask

Ticket: `.scratch/stripe-detector/issues/05-striped-regions-and-mask.md`. BASE `87005b9`.
Spec: `.scratch/stripe-detector/spec.md` stories 6, 7, 8-13, 37, 43, 49; "Report" and "Synthetic generator" modules; "Search range" (3x2-period minimum, Period roughly constant +-20% within a region); Further Notes (mask IoU >= 0.8, Period +-5%, Angle +-1 deg, Modulation Depth +-0.1); "Calibration and evaluation always use separate seeds" (spec.md:112).
ADR 0001 (periodicity, not size). GLOSSARY: Striped Region, Verdict ("Striped if it finds at least one striped region anywhere"), Threshold ("the stripe score above which the verdict is Striped").
Orchestrator log and rulings: `.scratch/stripe-detector/handoffs/05-orchestrator.md`. Review: `05-plan-review.md`. Prototypes: `05-prototype-p1.md` (size rule), `05-prototype-p2.md` (IoU, timing).

This version folds the review (B1-B6, P1-P2, O1-O3, N1-N8), the orchestrator's rulings, and the height ruling (P1 follow-up, option D; "Height ruling" and "Codex on height" in the orchestrator log). Everything is settled.

## 1. Where things stand

- `synthetic.generate(seed, shape, period, angle_deg, modulation_depth, mottle, mottle_strength, noise, peak) -> Synthetic(frame, truth, clean)`. Stripes cover the whole frame. RNG draw order is fixed: profile, `phase0`, mottle, noise. `GroundTruth(period, angle_deg, modulation_depth)`.
- `analysis.analyse(frame) -> Report`. `light = gaussian_filter(frame, 10) > 0.1 * max`; `estimate_local_stripes` gives per-pixel `ratio`, bank `period`, `angle_deg`, complex `response`, `local_mean`. `score = ratio.max()`, `striped = score > THRESHOLD (154.0)`. `_measure` takes the area `ratio > THRESHOLD` with bank Period within x1.25 of the peak's, then the neighbour-product sum (fine Period and Angle) and a re-tuned `gabor_at` filter (Modulation Depth).
- `_local_stripes._Spectrum(frame)` already holds one forward FFT with `.gabor(period, angle_deg)` and `.local_mean(period)`; `gabor_at` builds a new one per call (0.08 s at 400x1600).
- `Report(striped, score, threshold, period_px, angle_deg, modulation_depth, reader_notes=None)`; `to_dict` has a fixed key order (pinned by `test_report_converts_to_json`).
- `cli.main`: `FRAME [-o OUT] [--drop-axis-column] [--transpose]`; writes JSON only.
- `tests/feasibility.py` (the `make measure` driver and the `make check-slow` regression check) uses `analyse(frame).score > t` as "detected".
- Seed registries in `tests/protected.py`: `TEST_SEED_BLOCK = range(10, 100)` (free at BASE: 30-39, 66-99), `CALIBRATION_SEEDS` (guarded), `USED_SEEDS`.
- Stamped files (`tests/slow_stamp.py` `STAMPED_FILES`): `__init__.py`, `analysis.py`, `_local_stripes.py`, `synthetic.py`, `_calibration.py`, `tests/protected.py`, ... Not stamped: `cli.py`, `report.py`, `frame_io.py`.

## 2. Seams

### 2.1 Generator: `denoisifier.synthetic`

New public dataclass (frozen), all fields **required** (no numeric defaults, so no class-level numbers enter the protected-number lockfile):

```python
@dataclass(frozen=True)
class StripedRegion:
    """One soft-edged elliptical Striped Region with its own stripes."""
    center: tuple[float, float]       # (row, col), px
    semi_axes: tuple[float, float]    # (rows, cols) before rotation, px, to the 0.5 contour
    rotation_deg: float               # ellipse rotation (not the stripe Angle)
    edge_px: float                    # soft-edge width along the minor axis: mask goes 0.9 -> 0.1 over about this many px
    period: float
    angle_deg: float
    modulation_depth: float
```

`generate(..., regions: Sequence[StripedRegion] | None = None)`. Signature change:

- `period`, `angle_deg`, `modulation_depth` become `float | None = None`. With `regions=None` they take today's defaults (8.0, 0.0, 0.6) inside the body, and the frame is **bit-identical to BASE** (full-frame stripes, same RNG stream). This keeps every seeded test, the borderline seeds and `make measure`'s frames unchanged by the generator part of the ticket.
- With `regions` given, passing any of `period`/`angle_deg`/`modulation_depth` raises `ValueError("period, angle_deg and modulation_depth go in each StripedRegion when regions are given")`. `regions=()` is allowed (a Stripe-free frame).
- Validation per region: `period > 0`, `0 <= modulation_depth <= 1`, semi-axes `> 0`, `edge_px > 0`. After building masks: `sum_i m_i * mask_i <= 1` everywhere, else `ValueError` (keeps `clean >= 0`; overlapping regions are otherwise allowed).
- Model: `mask_i = 0.5 * (1 - tanh(d_i / w_i))`, `d_i` = approximate signed distance to the ellipse in px (`(r_i - 1) * min(semi_axes)`, `r_i` the normalised elliptical radius), `w_i = edge_px / (2 * atanh(0.8))`. Because `d_i` scales by `min(semi_axes)`, the 0.9 -> 0.1 band is `edge_px` wide **along the minor axis** and `edge_px * min/max` along the major axis (N2); the docstring says so.
  `clean = envelope * (1 + sum_i m_i * mask_i * cos(phase_i))`, `phase_i = 2 pi / p_i * (x cos t_i + y sin t_i) + phase0`. One shared `phase0` (the existing draw); no new RNG draws, so the stream (profile, phase0, mottle, noise) is the same with or without regions.
- `GroundTruth` gains `regions: tuple[RegionTruth, ...]`; `RegionTruth(period, angle_deg, modulation_depth, mask)` with `mask` the soft float mask (frame shape). The full-frame default yields one `RegionTruth` with `mask = np.ones(shape)`, also at m = 0. `GroundTruth.period/angle_deg/modulation_depth` become properties that return the single region's value and raise `ValueError` when there is not exactly one region; existing tests and `truth_match.assert_matches_truth` keep working (RegionTruth has the same attribute names).
- `GroundTruth`'s docstring says that at m = 0 the default truth still holds one all-ones `RegionTruth` with depth 0, which is not a Striped Region; tests must not iterate `truth.regions` as "the striped set" without filtering on `modulation_depth > 0` (N7).
- Not exported from `denoisifier/__init__.py` (the generator is a developer tool).

### 2.2 Report: `denoisifier.report`

```python
@dataclass(frozen=True)
class BoundingBox:
    row_start: int; row_stop: int; col_start: int; col_stop: int   # half-open, like slices

@dataclass(frozen=True)
class Region:
    label: int               # 1-based; the value of this region's pixels in labels / the mask CSV
    period_px: float
    angle_deg: float
    modulation_depth: float
    bbox: BoundingBox
    area_px: int

@dataclass(frozen=True)
class Report:
    striped: bool
    score: float
    threshold: float
    regions: tuple[Region, ...]
    labels: np.ndarray = field(compare=False, repr=False)  # int32, frame shape, 0 = not striped
    transposed: bool = False
    reader_notes: tuple[str, ...] | None = None
    def mask(self) -> np.ndarray: ...            # bool, labels > 0 (the union of the regions)
    def in_file_layout(self) -> Report: ...      # see below
```

- Invariants (docstring, asserted by tests): `striped == bool(regions) == (score > threshold)`; labels take values `0..len(regions)`, each label's pixels lie inside its `bbox` and the bbox is tight; `area_px == (labels == label).sum()`; regions ordered by descending area, ties by higher peak ratio, then by the first pixel in row-major order (deterministic).
- The top-level `period_px`, `angle_deg`, `modulation_depth` are **removed** (settled, 7.3).
- `in_file_layout()` (used by the CLI for `--transpose`, 2.4): returns a Report with `labels.T`, each bbox's rows and columns swapped, `transposed=True`; Period, Angle, depth, score and labels' values unchanged. Lives in `report.py`, not in the CLI, so the coordinate contract has one home.
- `to_dict()`: keys `striped, score, threshold, transposed, regions[, reader_notes]`; each region `{"label", "period_px", "angle_deg", "modulation_depth", "bbox": {"row_start", "row_stop", "col_start", "col_stop"}, "area_px"}`. `labels` is not in the JSON (the mask CSV carries it). Plain Python types only; `allow_nan=False` stays.
- Export `Region` and `BoundingBox` from `denoisifier/__init__.py` (stamped; the ticket needs `make check-slow` anyway).

### 2.3 Analysis: `denoisifier.analysis`

`analyse(frame, *, threshold: float = THRESHOLD) -> Report`. The keyword lets the verdict-invariant test sweep thresholds on the real path (and ticket 07 needs it). `threshold` must be finite or `inf` and `>= 0`, else `ValueError`: with `score = 0.0` for "no qualifying group", a negative threshold would make `score > threshold` true with `regions == ()`. `_local_stripes.py` is unchanged; `analysis.py` builds **one `_Spectrum` per frame** and reuses it for every candidate's re-tuned filter (N4), and takes `local_mean` once per distinct Period (P2: it does not depend on Angle).

Candidates are built **without reference to the threshold** (ruling O1). The threshold only filters at the end, so `striped == bool(regions) == (score > threshold)` holds by construction for every threshold, ties included.

1. **Seeds.** Local maxima of `ratio` inside `light` (`ratio == maximum_filter(ratio, footprint)` and `ratio > 0`), footprint `_PEAK_FOOTPRINT_PX`. Visit them in descending ratio. Skip a peak already inside an earlier candidate's grown extent (dedup: P2 saw identical copies otherwise). Stop after `_MAX_CANDIDATES` candidates have been grown (bounds the time; see section 6). Because candidates are visited by peak ratio descending, the cap only ever drops lower peaks, but on a large mottled frame high non-qualifying blobs could use it up before a lower qualifying stripe candidate (N9). So: size `_MAX_CANDIDATES` on the region calibration range with headroom (at least twice the largest number of grown candidates any calibration frame needed to reach its last qualifying group, including probe-shaped 400x1600 frames at m = 0.2), and when the cap is hit with peaks left unvisited, log it (`logging.getLogger(__name__).info`, naming the count and the highest unvisited peak ratio; not a warning, so no test filter is involved). For each visited peak, the seed area is the connected component of `ratio >= _SEED_FRACTION * peak_ratio` that holds the peak (relative to its own peak, so it is strength-free and T-free).
2. **Period split.** If the seed area's bank Periods have a gap of `_SPLIT_LOG_STEPS` or more bank grid steps (x1.12 per step; P2 used 2), split it at the gap and keep the part holding the peak.
3. **Period and Angle** of the candidate: the existing neighbour-product sum on the **seed area** (not the grown area: in two-region frames the grown area takes in the neighbour's leaked response, N5). Keep the `_MIN_PAIRS` fallback.
4. **Growth (the reported extent).** Re-tune the shared `_Spectrum` to the candidate's Period and Angle; depth map `2|tuned| / local_mean`. The grown extent is the connected part of `{depth >= _GROW_FRACTION * median depth on the seed area} & light` that touches the seed area. **No distance cap** (P2: the 2P cap breaks short Periods, IoU 0.34-0.87 at P <= 6; uncapped 0.93-0.97). If the two-region calibration frames show a leak into the neighbour, add a pixel cap tuned there (one more lockfile addition, covered by the approval). Half-depth growth matches the truth (soft mask >= 0.5 means local depth >= m/2).
5. **Merge fragments (ruling O3).** Group grown candidates by **complete linkage**: a group is valid only if every pair of its members has Period ratio `max/min <= _MERGE_PERIOD_RATIO` and Angle difference `<= _MERGE_ANGLE_DEG`, and each member's grown extent touches or lies within `_MERGE_GAP_PERIODS` Periods of another member's (about one window). Complete linkage, so no chaining. Merge greedily in descending peak order; the group's peak ratio is its highest member's. The pairs (5, 12), (8, 16), (4, 10) must stay separate (ratios 2-2.5, far above the merge ratio).
   The group is the unit from here on: its seed area and grown extent are the members' unions; Period and Angle are re-measured on the union of seed areas (neighbour-product sum); its depth map is re-tuned once to that Period and Angle.
6. **Size rule** (on the group, measured on the re-tuned depth map, in the group's measured Period P):
   - **Width (settled, P1):** the **sub-pixel half-peak width** of the depth map: along the frame row through the depth peak on the seed area, find the linear-interpolated crossings of `0.5 * peak depth` on each side; width = distance between them. Pass if `width >= MIN_HALF_DEPTH_WIDTH_PERIODS * P` with `MIN_HALF_DEPTH_WIDTH_PERIODS = 3.24`. The 0.5 is part of the measure, not a knob (inline it). P1 fitted 3.24 on seeds 390_000-390_007 (outside every test range), checked it on three other sets (480 frames per factor): 0.8x never passes, 1.25x and 1.4x always pass, at every Period 3-20 and Angle -10/0/+10, m 0.3 and 0.6, noise 0 and 0.01. Docstring: on an exactly 3P-wide region the measure gives about 3.1 P, so the rule reports from about 1.05x the minimum width up; it is a blur correction for the across window (sigma 1 P), and the spec's 3 P is the quantity it stands for. If the implementer re-derives 3.24, that happens inside the region calibration range (2.5), never on test seeds.
   - **Height (settled, height ruling: option D):** today's along-window (sigma 1.5 P, FWHM about 3.5 P) cannot resolve 2 P, so height is measured with a **separate, size-only filter**: the bank's Gabor formula at the group's measured Period and Angle with the along-stripe sigma `SIZE_ALONG_PERIODS = 0.5` P (across stays 1 P), plus its own local mean (the same window at DC). Depth `2|resp| / mean`. It runs **on the input frame**, through the frame's shared `_Spectrum` (two inverse FFTs per group), not on the blurred depth map. Height = the sub-pixel half-peak height of that depth: along the frame column through that filter's depth peak on the seed area, the linear-interpolated crossings of `0.5 * peak depth` on each side. Pass if `height >= MIN_HALF_DEPTH_HEIGHT_PERIODS * P` with `MIN_HALF_DEPTH_HEIGHT_PERIODS = 1.93`. P1-D fitted it on seeds 391_000-391_007 and checked it on 391_100-391_107: at low noise, 0.8x never passes and 1.25x/1.4x always pass, on every Period 3-20 and Angle -10/0/+10, for both the scaled and the wide/short shape, margins about x1.10 each side; a region's width does not leak into its height. The short filter is used **only** for the size test: detection, the score's peak ratio, Period, Angle and depth are unchanged. Docstring: on an exactly 2P-tall region the measure gives about 1.9 P, so 1.93 is about 1.0x the minimum.
   - A group passes the size rule only if it passes **both** width and height. The same qualified groups feed `score` and `regions` (step 7), so the verdict invariant is unaffected.
   - Known limits, carried as risks to watch in slice 4: P1-D did not cover the two-region case (whether a neighbour's leak raises the short filter's height), Mottle at low noise, frames other than 256x256, or tilted and elongated cores where the peak column misses the region's centre.
7. **Qualifying groups, overlaps, score, regions (B7: everything before the threshold is T-free).**
   - A group qualifies when it passes the size rule. Size and measurement do not depend on the threshold.
   - **Overlaps are settled among all qualifying groups, before the threshold applies:** a pixel in more than one qualifying group's grown extent goes to the group with the higher re-tuned depth there. A qualifying group whose assigned area becomes empty is dropped. The rest are the **survivors**; each survivor's pixel set, bbox and `area_px` are fixed here and never depend on the threshold.
   - `score` = the highest peak ratio over the **survivors**; **`0.0` when there are none**, including when `light` is empty or `ratio.max() == 0` (B6: constant and all-zero frames).
   - `regions` = the survivors with `peak ratio > threshold`, measured (step 8) and numbered (step 9). `striped = score > threshold`. A lower threshold only adds survivors; it never changes the pixels, bbox or area of a region already reported.
   - Score scale: close to today's max ratio on striped frames, lower on stripe-free frames (small blobs fail the size rule). `make measure` re-stores the gate thresholds (section 6).
8. **Measurement** per reported region: Period and Angle from step 5's neighbour-product sum on the seed areas; Modulation Depth = median of the re-tuned depth over lit seed-area pixels (`_measure` generalised to take an area and a shared `_Spectrum`).
9. **Labels.** `labels` holds the reported survivors' pixels (from step 7), numbered `1..N` in the region order of 2.2. Label numbers can change with the threshold (the order is over the reported set); pixels, bbox and area cannot.

Module-level numbers (each a lockfile line; adding them is approved, section 5): `MIN_HALF_DEPTH_WIDTH_PERIODS = 3.24` (P1), `MIN_HALF_DEPTH_HEIGHT_PERIODS = 1.93` and `SIZE_ALONG_PERIODS = 0.5` (P1-D), `_SEED_FRACTION`, `_PEAK_FOOTPRINT_PX`, `_MAX_CANDIDATES`, `_SPLIT_LOG_STEPS` (start 2), `_GROW_FRACTION` (start 0.5; P2 saw 0.6 lift the P16-20 worst case from 0.79 to 0.83), `_MERGE_PERIOD_RATIO` (start 1.2, the spec's +-20%), `_MERGE_ANGLE_DEG` (start 2: twice the +-1 deg measurement tolerance), `_MERGE_GAP_PERIODS` (start 2, about one window across). All but the three size constants are tuned in the region calibration (2.5); the size constants come from P1/P1-D and are re-derived, if ever, only inside that range. Inline literals that are not tuning knobs.

`THRESHOLD = 154.0` stays. Its comment (analysis.py:15-24) derives it from max-ratio scores, which is stale under the new score; rewrite the comment to say it is **carried over from ticket 03, not re-derived on the ticket-05 score, and replaced by ticket 07's calibration** (N6). Re-measuring it would need `calibrating(THRESHOLD_CALIBRATION_SEEDS)` and is out of scope unless the test margins (stripe-free < T < m = 0.5 on test seeds) break; then stop and ask.

### 2.4 CLI: `denoisifier.cli` (+ `frame_io`)

- New option `--mask PATH`: write the labels as a CSV grid, no header, one row per grid row, integers (`0` = not striped, `k` = the region with `"label": k` in the JSON). Without `--mask`, no mask is written (stdout JSON mode unchanged).
- **Aliasing (Codex finding):** before reading or writing anything, refuse a `--mask` path that is the input `FRAME` or the `-o` path, including existing filesystem aliases: equal `Path.resolve()`, or `os.path.samefile` when both exist (catches symlinks and hard links). Raise `ValueError` inside the existing `try`, so the user sees one `denoisifier: error: --mask ... is the same file as ...` line, exit 1, and no file is written or truncated.
- **Layout and coordinate contract (ruling Q7):** the mask has the rows and columns of the grid in the file with the axis column dropped (`--drop-axis-column`); no axis column, no metadata lines. With `--transpose`, the CLI writes `report.in_file_layout()`: the mask is `labels.T` and the JSON bboxes index the **written mask** directly (file orientation). Period and Angle stay in today's convention (measured on the analysed, transposed frame), and the JSON's `"transposed": true` records that a transpose happened.
- Writer: `frame_io.write_mask_csv(labels, path)` (`np.savetxt(..., fmt="%d", delimiter=",")`), next to `write_frame_csv`; it reads back with `read_frame`. No module-level numbers.
- Order: alias check, read, analyse, JSON, mask; all inside the existing `try`, so an `OSError` (missing directory) gives one `denoisifier: error:` line and exit 1. Help text: "write the Striped Region mask here as a CSV laid out like the input: 0 outside regions, k inside the region labelled k in the report; with --transpose the mask and the bboxes follow the file's layout".
- The CLI's module docstring and `--help` description note the JSON change (no top-level `period_px`/`angle_deg`/`modulation_depth`; per-region values under `regions`; new `transposed` key). No README documents the JSON at BASE.
- No analysis logic in the CLI (`report.labels` is the source).

### 2.5 Region calibration (ruling B3)

The growth, merge and seed knobs (and any re-derivation of the size constant) are tuned on a **new registered calibration range**, never on test seeds (spec.md:112).

- `tests/protected.py`: `REGION_CALIBRATION_SEEDS = range(90_000, 90_600)`, added to `CALIBRATION_SEEDS` (guarded move, approved) and so to the disjointness check. Tuning uses `range(90_000, 90_400)`; the informational numbers of 7.2 and 7.8 use `range(90_400, 90_600)`, after the freeze.
- Reserve the seeds the review and prototypes already looked at, by adding them to `USED_SEEDS`: `range(300_001, 300_006)`, `range(310_000, 310_400)`, `range(320_000, 320_200)`, `range(330_000, 330_100)`, `range(340_000, 340_004)`, `range(350_000, 350_002)`, `range(360_000, 360_060)` (N8); `range(390_000, 390_008)`, `range(390_100, 390_108)`, `range(390_200, 390_208)`, `range(390_300, 390_308)` (P1); `range(391_000, 391_008)`, `range(391_100, 391_108)`, `range(391_200, 391_208)` (P1-D, height); `range(410_000, 410_080)`, `range(411_000, 411_004)` (P2).
- Driver: `tests/calibrate_regions.py` with `main()` that calls `seed_guard.install()` (as `feasibility.main()` does) and runs every generate call inside `with seed_guard.calibrating(range(...)):`. It writes the chosen knob values, the seed range, the per-Period IoU (median and worst) and the two-region outcomes to `.scratch/stripe-detector/region-calibration.json` (tracked, committed with the constants). Calibration frames use the test geometries of section 3 (single region in Periods; the two-region pairs; full-frame mottled frames for the merge rule), with fresh seeds from the range.
- **Freeze:** commit the constants and the JSON before the held-out tests (IoU, two-region, full-frame) are run against them as acceptance. A red acceptance test after the freeze is brought to the orchestrator; it is not a reason to re-tune.

## 3. Acceptance criteria -> tests (real path)

Real paths: `generate(...)` with `regions=` -> `analyse` (library seam), and file -> CLI subprocess -> JSON + CSV (CLI seam). "Typical" = `mottle="scorched", noise=Emccd()` (about 100 photons at the peak). "Low noise" = `mottle="none"`, Gaussian `noise=0.01` (generate's defaults). New test seeds go in `TEST_SEED_BLOCK` with names ending `_TEST_SEEDS` / `_TEST_SEED` (`test_seed_sets_are_disjoint_and_unused` checks the block); prefer the free 30-39 and 66-99. Truth mask for IoU = `RegionTruth.mask >= 0.5`. New test-side numbers live in `tests/protected.py`.

Geometry in Periods (ruling P2): the test region's semi-axes are `max(5P, 45) x max(6.6P, 60)` px (rows x cols), constants `REGION_SEMI_AXES_PERIODS = (5.0, 6.6)` and `REGION_SEMI_AXES_FLOOR_PX = (45, 60)` in `tests/protected.py`, `edge_px = 6`, centred, in a 512x512 frame (holds P = 20 at 200x264 px). A shared helper `tests/regions.py` (not stamped) builds the regions from these, and holds `iou(a, b)` and `match(report_regions, labels, truth_regions)` (pairs by largest overlap of `labels == k` with each truth mask).

Two-region geometry: pairs (5, 12), (8, 16), (4, 10), each region sized by the rule above for its own Period, side by side in a wide frame with a gap of at least two windows at the longer Period. Start at `shape=(512, 1024)`; before writing the test, confirm on calibration seeds (2.5) that both truth masks lie inside `envelope >= 0.5 * max`, and pick the shape and centres there. The geometry goes into `tests/regions.py` as `TWO_REGION_LAYOUT` (numbers in `tests/protected.py`).

| AC | Test (file) | Frame | Assertion |
|---|---|---|---|
| 1 generator regions | `test_regions_have_soft_edged_elliptical_masks` (test_synthetic) | one region, noise 0 | `mask` = 1 at the centre, 0 far outside, monotone along a ray, 0.5 within 1 px of the ellipse, the 0.9->0.1 band `edge_px` +-1 px wide **along the minor axis** (N2); area of `mask >= 0.5` within 2% of `pi*a*b` |
| 1 | `test_each_region_has_its_own_period_and_angle` (test_synthetic) | LEFT P=5 A=4, RIGHT P=12 A=-6, mottle none, noise 0 | `spectrum.band_peak` on a crop inside each region matches that region's truth (`assert_matches_truth(peak.period, peak.angle_deg, region)`); `clean` equals the envelope (same seed, `regions=()`, noise 0) where both masks are `< 1e-12` (N3: tanh never reaches 0) |
| 1 | `test_default_frames_are_unchanged_by_regions` (test_synthetic) | `generate(seed)` for 3 seeds, Gaussian and Emccd, scorched | SHA-256 of `frame.tobytes()` equals digests computed at BASE (strings pinned in the test; not protected numbers); `regions=()` equals `modulation_depth=0` with the same seed bit for bit. Docstring (N1): the digests are tied to the numpy/scipy pinned in `uv.lock`; after a dependency bump re-pin them with the reason recorded |
| 1 | `test_rejects_invalid_regions` (test_synthetic, parametrized) | | regions + `period=`; `semi_axes <= 0`; `edge_px <= 0`; depth > 1; two overlapping m=0.6 regions (sum > 1) -> `ValueError` with exact message prefix |
| 1 | `test_ground_truth_lists_regions` (test_synthetic) | default and two-region | default: one `RegionTruth`, mask all ones, `truth.period` works; two regions: `truth.period` raises `ValueError` |
| 2 report lists regions | `test_partial_region_is_reported_with_its_measurements` (test_analyse, `REGION_TEST_SEEDS`, 10 seeds, Period/Angle `CASES[seed % 10]`) | single region in Periods, m=0.5, typical | `striped`; exactly 1 region; `assert_matches_truth` and `assert_depth_matches` on it; bbox within `BBOX_TOL_PERIODS` (1 Period) of the truth bbox of `mask >= 0.5` on each side |
| 2 verdict | `test_verdict_is_striped_exactly_when_a_region_is_reported` (test_analyse, parametrized over frames x thresholds) | frames: stripe-free and m=0.5 of `MOTTLED_TEST_SEEDS`, the borderline frames, a two-region frame, a constant frame, an all-zero frame. Thresholds: 0, `THRESHOLD`, `report.score` (tie), `nextafter(score, inf)`, `nextafter(score, -inf)` (only when `score > 0`), `inf`; plus `analyse(frame, threshold=-1.0)` and `nan` raise `ValueError` | `analyse(frame, threshold=t)`: `striped == bool(regions) == (score > t)`; `score` does not depend on `t`; regions at a lower `t` include those at a higher `t` (same measurements); labels invariants of 2.2 (tight bbox, area, `0..N`). Constant and all-zero frames: `score == 0.0`, `regions == ()`, `not mask().any()` (B6) |
| 2 verdict | `test_lowering_the_threshold_keeps_reported_regions_unchanged` (test_analyse, B7) | the two-region frame, the full-frame m=0.5 frames of `MOTTLED_TEST_SEEDS`, and a frame with two qualifying regions whose grown extents overlap (two same-Period regions with Angles beyond `_MERGE_ANGLE_DEG`, side by side) | for each pair of thresholds `t_high > t_low` from the sweep above: every region reported at `t_high` is reported at `t_low` with the same bbox, `area_px`, Period, Angle and depth, and the same pixel set (`labels == k` at each); matched by bbox, not by label number (numbers may change) |
| 2 JSON | `test_report_converts_to_json` (rewritten) | m=0.6 and 0 | key list `striped, score, threshold, transposed, regions`; region keys and types; round-trip equals the dataclass fields |
| 3 IoU | `test_mask_overlaps_the_true_region` (test_analyse, `REGION_TEST_SEEDS`, CASES Periods/Angles, parametrized over mottle `scorched` and `multiscale`) | single region in Periods, m=0.5, typical | `iou(report.mask(), truth.mask >= 0.5) >= MASK_IOU_MIN` (0.8) on every frame. A red multiscale case is a detector finding to surface to the orchestrator, not a reason to loosen (ruling Q8) |
| 4 two regions | `test_two_regions_with_different_periods_are_reported_separately` (test_analyse, `TWO_REGION_TEST_SEEDS`, parametrized over the three pairs) | two-region layout, m=0.5, typical | exactly 2 regions; `match` pairs each to a different truth region; each matches its truth Period and Angle (`assert_matches_truth`); each region's labels have IoU >= `MASK_IOU_MIN` with its truth mask |
| 5 below minimum | `test_region_below_the_minimum_is_not_reported` (test_analyse, `MIN_SIZE_TEST_SEEDS`; Periods 3, 8, 20 x Angles -10, +10; parametrized over shapes) | one region, `edge_px = 1`, m=0.6, **low noise** (ruling O2), 0.5-contour bbox per shape, `f = MIN_SIZE_BELOW_FACTOR` (0.8): **both** `semi_axes = (f*P, 1.5*f*P)` (`2fP` tall, `3fP` wide); **wide/short** `(f*P, 2*P)` (`2fP` tall, 4 P wide: fails on height only); **4Px1P** `(0.5*P, 2*P)` (1 P tall, 4 P wide); **narrow/tall** `(2*P, 1.5*f*P)` (4 P tall, `3fP` wide: fails on width only) | `report.regions == ()` and `striped is False` |
| 5 above minimum | `test_region_above_the_minimum_is_reported` (same seeds, Periods, Angles) | the both, wide/short and narrow/tall shapes with `f = MIN_SIZE_ABOVE_FACTOR` (1.4): the controls that pass on both axes | exactly 1 region; Period matches truth. Thinnest margins (P1, P1-D): width x1.036 below / x1.13 above at 1.4x; height about x1.10 below / x1.24 above at 1.4x. P1-D tested both and wide/short; narrow/tall rests on the width rule's results, so run it in slice 5 before anything else |
| 6 partial | covered by AC 2 and 3 (the region covers part of the lit area); add `test_stripes_on_one_flank_of_the_envelope_are_found` (`REGION_TEST_SEEDS[:3]`) | one region in Periods centred on the left flank of the spot, m=0.5, typical | `striped`; 1 region, its bbox inside the left half; Period matches |
| 6 dark never striped | `test_dark_area_is_never_reported_as_striped` (test_analyse, parametrized: full-frame default m=0.6 noise 0; full-frame m=0.6 typical; one region with `semi_axes = (200, 200)` spilling far past the spot) | `ENVELOPE_TEST_SEEDS`, 256x256 | `not report.mask()[dark].any()` where `dark = envelope < DARK_FRACTION * envelope.max()`, envelope from the same seed with `regions=()` / m=0 and noise 0 |
| 7 CLI mask | `test_cli_writes_mask_csv_laid_out_like_the_frame` (test_cli) | 96x160 frame, one off-centre region (P 5, semi-axes (30, 40)), m=0.6, low noise, `CLI_MASK_TEST_SEED` | exit 0; `read_frame(mask).frame.shape == frame.shape`; values are integers in `0..len(regions)`; equals `analyse(frame).labels`; each label's tight bbox equals its JSON `bbox`; `"transposed": false` |
| 7 | `test_cli_writes_all_zero_mask_for_stripe_free_frame` | m=0 | mask all 0, JSON `regions == []` |
| 7 transpose | `test_cli_mask_and_bboxes_follow_the_file_layout_when_transposing` | the same 96x160 frame written **transposed** (160x96 file), run with `--transpose --mask` | mask shape == the file's shape (160x96); mask == `analyse(frame).labels.T`; each JSON bbox equals the tight bbox of `mask == label` (file orientation); Period and Angle equal `analyse(frame)`'s; `"transposed": true`. The off-centre region makes a missing or doubled transpose fail |
| 7 | `test_cli_mask_follows_the_solis_crop_layout` | real crop `tests/data/solis/xpos_ypos_crop.asc` with `--drop-axis-column --transpose --mask` | mask shape == the file's grid shape without the axis column |
| 7 | `test_cli_fails_cleanly_when_mask_dir_missing` | | `_assert_clean_failure(result, str(mask_path))` |
| 7 aliasing | `test_cli_refuses_a_mask_path_that_aliases_the_input_or_output` (parametrized: `--mask` = FRAME path; a symlink to FRAME; `--mask` = `-o` path; a symlink to the `-o` file) | | exit 1, one `denoisifier: error:` line naming the clash; FRAME's bytes unchanged; the `-o` file unchanged (or not created when it did not exist) |

Existing tests that change (normal ticket work, each keeps or raises its strength):

- `test_analyse.py`: `report.period_px` etc. -> the regions. **Full-frame frames (ruling O3):** `striped`; **every** reported region matches truth Period, Angle and Depth; no count assertion. The merge (2.3 step 5) is what makes "every" hold: B5 saw 41/60 full-frame frames split into 2-5 passing fragments and 4/60 with a mis-measured fragment under the unmerged rule. Written this way from the start, never relaxed later. Stripe-free tests: `regions == ()` and `not report.mask().any()`.
- `test_modulation_depth_is_relative_to_local_envelope`: depths of the largest region of each crop.
- `test_constant_frame_is_not_striped_and_has_finite_score`: also asserts `score == 0.0` and `regions == ()`.
- `test_borderline_striped_frame_has_finite_measurements` and `test_cli_reports_borderline_frame`: the finite checks move to `regions[0]`. If the new score or the size rule moves these frames out of `(THRESHOLD, 1.5 * THRESHOLD)`, the borderline seeds must be re-picked: that changes `BORDERLINE_TEST_CASES` (a pinned number), so it needs an approval with its reason before the edit (not covered by the lockfile-addition approval). `tests/borderline.py` already notes two entries with measured areas of 8 and 14 px; expect a re-pick.
- `test_cli.py`: `test_cli_writes_json_report_for_striped_csv` reads `report["regions"]`; the Solis-crop equality tests stay (they compare whole reports).

## 4. Order of work (tdd red-green slices)

1. **Generator.** Red: AC 1 tests (digest test first, against digests taken at BASE before any edit). Green: `StripedRegion`, `RegionTruth`, `GroundTruth.regions` and properties, masks, validation. `make test-fast`.
2. **Report shape, no behaviour change yet.** Red: rewritten JSON test, verdict-invariant test (threshold sweep). Green: `Region`, `BoundingBox`, `labels`, `mask()`, `transposed`, `in_file_layout()`, `to_dict`, `analyse(..., threshold=)`; `analyse` emits one region from today's `_measure` area. Migrate existing tests off the top-level fields.
3. **Calibration range and driver.** Register `REGION_CALIBRATION_SEEDS` and the `USED_SEEDS` reservations (approved; record the Comments first, section 8). Skeleton `tests/calibrate_regions.py` that builds the calibration frames.
4. **Candidates, growth, merge (two-region early, rulings P2 and height).** Red: two-region, partial-region, flank, dark-area and full-frame "every region" tests. Early in this slice, on calibration seeds with the driver, check what the prototypes did not cover: two-region frames (does a neighbour's leak widen the width or raise the short filter's height?) and Mottle (scorched, multiscale) at low noise through the size rule. A miss there is reported to the orchestrator before slice 5. Before the freeze, the driver also counts on the tuning range (N9): (a) frames where `_MAX_CANDIDATES` was hit, and (b) full-frame calibration frames that still have a qualifying fragment left unmerged because its Angle missed by more than `_MERGE_ANGLE_DEG` (B5's mis-measured fragments). Both counts go into `region-calibration.json` and the handoff. Green: seeds, split, shared `_Spectrum`, uncapped growth, merge, labels, per-group measurement. Tune `_SEED_FRACTION`, `_PEAK_FOOTPRINT_PX`, `_GROW_FRACTION`, the merge knobs (and a pixel cap, if the two-region frames leak) **only on `range(90_000, 90_400)`** with the driver.
5. **Size rule.** Red: AC 5 tests (all shapes). Green: the width rule (3.24) and the height rule (short filter, 1.93), both required; shared `_Spectrum`.
6. **Freeze.** Commit constants and `region-calibration.json`. Run the IoU test (scorched and multiscale) and every slice-4 test as acceptance. Red -> stop and report to the orchestrator; do not re-tune, do not loosen.
7. **Informational numbers** (driver, `range(90_400, 90_600)`, after the freeze): detection and report rates against region size (f = 0.8 ... 3 x the minimum, both and wide/short shapes) at typical noise and the operating T (rulings O2 and height; P1-D saw 1/240 0.8x frames reported at typical noise); m = 0.2 IoU (ruling Q8). Into the handoff, not into tests.
8. **CLI.** Red: CLI mask, transpose, aliasing tests. Green: `--mask`, alias check, `write_mask_csv`, `in_file_layout()`.
9. **Docs.** Module, `analyse`, `Report`, `LocalStripes` ("ticket 05 replaces" note removed), `THRESHOLD` comment (N6), CLI docstring/help (JSON change). `GLOSSARY.md`: add **Mask** (7.10) via the domain-modeling conventions. Avoid the curated terms ("orientation", "amplitude", "wavelength", "false positive").
10. Gates, section 6.

## 5. Protected numbers and weakening moves

All need an approval before the edit, recorded with the reason in the ticket's Comments (CLAUDE.md). Status as of this plan:

| Move | Why | Kind | Status |
|---|---|---|---|
| New lockfile lines for the `analysis.py` constants of 2.3 (`MIN_HALF_DEPTH_WIDTH_PERIODS`, `MIN_HALF_DEPTH_HEIGHT_PERIODS`, `SIZE_ALONG_PERIODS`, `_SEED_FRACTION`, `_PEAK_FOOTPRINT_PX`, `_MAX_CANDIDATES`, `_SPLIT_LOG_STEPS`, `_GROW_FRACTION`, `_MERGE_PERIOD_RATIO`, `_MERGE_ANGLE_DEG`, `_MERGE_GAP_PERIODS`, a pixel cap if needed) | size rule and segmentation knobs | lockfile edit (add) | **approved** (orchestrator) |
| New `tests/protected.py` names: `MASK_IOU_MIN = 0.8`, `BBOX_TOL_PERIODS = 1.0`, `MIN_SIZE_BELOW_FACTOR = 0.8`, `MIN_SIZE_ABOVE_FACTOR = 1.4`, `DARK_FRACTION = 0.05` (below `_MASK_FRACTION` 0.1, leaving a smoothing margin), `REGION_SEMI_AXES_PERIODS`, `REGION_SEMI_AXES_FLOOR_PX`, the two-region layout numbers, `REGION_TEST_SEEDS`, `TWO_REGION_TEST_SEEDS`, `MIN_SIZE_TEST_SEEDS`, `CLI_MASK_TEST_SEED`, the `USED_SEEDS` reservations | spec tolerances, new tests, reserved seeds | lockfile edit (add); `protected.py` is stamped | **approved** (orchestrator) |
| `REGION_CALIBRATION_SEEDS` in `CALIBRATION_SEEDS`; the new `seed_guard.install()` in `calibrate_regions.main()`; its `calibrating(...)` blocks | calibration/evaluation separation (B3) | seed-guard surface | **approved** (orchestrator) |
| Removing or renaming existing pinned constants (`_PERIOD_SPREAD`, `_MASK_FRACTION`, `_MIN_PAIRS`) | refactor | lockfile edit (remove/change) | ask at the time |
| `BORDERLINE_TEST_CASES` re-pick | new score / size rule | changing an expected value | ask at the time, with the measured reason |
| `THRESHOLD = 154.0` value | only if test margins break | changing an expected value | not planned (comment only, N6) |
| `GATE_STORED_THRESHOLD`, `PROBE_STORED_THRESHOLD` after `make measure` | `test_stored_thresholds_are_the_saved_measurement` | lockfile edit, by hand to the new JSON values | ask after `make measure` |
| `MASK_IOU_MIN` below 0.8, wider AC 5 factors, or any spec tolerance relaxed | only if the frozen detector misses | changing a tolerance | escalate (orchestrator, then owner: spec value) |

Not weakening: changing existing tests to read `regions` (same or stronger assertions), new tests, the generator API. Never: editing the regression pass counts, `slow_stamp.py`, the Makefile, timeouts (a test nearing the 60 s per-test timeout is reported, not given a longer one).

## 6. Gates: where `make measure` and `make check-slow` fit

Ticket 05 is a `make measure` milestone (CLAUDE.md): detector output is meant to move. Touched stamped files: `analysis.py`, `synthetic.py`, `__init__.py`, `tests/protected.py`.

1. During slices: `make test-fast` after each change. No heavy job runs meanwhile (the calibration driver counts as heavy: run it alone, in the background, log to a file).
2. Detector done, all fast tests green, approvals recorded: `make check` (lint, types, every non-slow test). It will report the slow stamp stale; that is expected.
3. Commit the detector (clean tree: `test_saved_measurement_is_from_clean_code_and_the_current_seed_plan` refuses a `-dirty` measurement).
4. `make measure` in the background (about 39 min, idle machine, nothing else running; output to a log, `; echo "EXIT=$?" >> <log>`). It rewrites `.scratch/stripe-detector/feasibility-gate.json` and runs `tests/test_feasibility_gate.py`. The score is now the T-free qualifying-peak score, so the thresholds move; the gate's statements (detection >= 0.90, held-out false alarms 3-18 of 1000, full frame <= 10 s, probe >= 0.95) must still hold.
   - **If the gate fails** (detection, false alarms or time): stop, record in the ticket, escalate to the owner (spec: feasibility failure is a human decision). Do not tune on gate seeds.
   - Time: up to `_MAX_CANDIDATES` growths at about 0.08 s each at 400x1600 (P2, idle estimate), plus the height filter at 55-92 ms per group (P1-D, loaded machine), on top of 7.4 s (bench median). Pick `_MAX_CANDIDATES` so the worst case stays well under 10 s (8 candidates is about +0.65 s growth, plus the height filter on the groups that reach the size test). Cheap wins if needed (P2): `local_mean` once per Period; label/EDT on a cropped window.
5. Update `feasibility-gate.md` from the new JSON (numbers, commit), re-store `GATE_STORED_THRESHOLD` / `PROBE_STORED_THRESHOLD` and their lockfile lines (approval). If `test_regression_plan_meets_the_operating_rule` goes red: owner decision, do not touch pass counts.
6. `make check-slow` in the background (about 6 min). Red here after a fresh measure means the regression check disagrees with the new measurement: diagnose, never edit pass counts.
7. `make check` again: must be green including the stamp. Handoff quotes the command, exit status, pytest's final summary line and `git rev-parse --short HEAD` (`-dirty` if applicable), plus the informational numbers of slice 7, the N9 counts (cap hits, angle-unmerged fragments) and the calibration JSON's pointer.

## 7. Settled decisions

1. **Score and verdict (O1/Q1, B7): T-free candidates; overlaps settled and emptied groups dropped among all size-qualifying groups; `score` = highest peak ratio over the survivors (0.0 if none); `regions` = survivors with peak > threshold.** Reason: Codex showed the size predicate is not monotone in the level, so any level-based score can disagree with the verdict; this construction makes `striped == bool(regions) == score > T` exact and keeps a reported region's pixels, bbox and area independent of T; it also keeps the score near today's scale, and ticket 07 has not calibrated on it yet.
2. **Size rule (Q2, B1, P1): width = sub-pixel half-peak width of the re-tuned depth map, cut at 3.24 P.** Reason: core-at-T and median-depth extents depend on stripe strength (P1); the half-peak width is strength- and noise-free and separates 0.8x from 1.25x/1.4x on every Period and Angle tested.
2a. **Height (height ruling, option D): sub-pixel half-peak height of a size-only filter with a 0.5 P along-window, run on the input via the shared spectrum, cut at 1.93 P; both axes required; detection unchanged.** Reason: today's along-window cannot resolve 2 P; width-only would break story 13 and the spec's 3x2 rule (Codex), while the short filter separates with about x1.10 margins and leaves detection alone.
3. **Top-level Period/Angle/Depth removed from the Report (Q3).** Reason: one source of truth; re-adding them later is additive and cheap.
4. **Mask = core grown to the half-depth contour, no distance cap (Q4, P2).** Reason: the ratio core alone gives IoU 0.10-0.77; a 2P cap breaks short Periods; uncapped half-depth growth reaches 0.93-0.97 there and matches the truth's 0.5 contour.
5. **Mask CSV holds region labels (Q5, owner).** Reason: ties each pixel to its JSON entry; binary is `> 0` away.
6. **Mask written only with `--mask PATH`, aliasing with FRAME or `-o` refused (Q6, Codex).** Reason: explicit, works with stdout JSON, and an alias would silently destroy the input or the report.
7. **Mask and bboxes in the file's layout; Period/Angle in today's convention; `transposed` recorded in the JSON (Q7, Codex).** Reason: one coordinate system for everything that indexes pixels, without changing what Angle means.
8. **IoU tested at typical noise on scorched and multiscale Mottle, m = 0.5, at the spec's 0.8; m = 0.2 informational (Q8).** Reason: "typical noise" covers both Mottle kinds; m = 0.2 IoU is not asked for.
9. **Fragments of one stripe set merged by complete linkage on Period, Angle and proximity (O3/Q9).** Reason: one entry per stripe set (story 7), without chaining across different Periods; the report format is unchanged.
10. **Glossary gains Mask (Q10):** "**Mask**: An array the shape of the Frame that labels each pixel with the Striped Region it belongs to: 0 for none, k for region k of the report. The boolean mask is the union of the regions (label > 0)." Reason: the spec and the CLI use the word; "map" is an avoided term for Frame.
11. **Region knobs tuned on a new registered calibration range, frozen before the held-out tests (B3).** Reason: spec.md:112, calibration and evaluation use separate seeds.
12. **AC 5 tested at low noise, 0.8x vs 1.4x, each axis varied on its own (wide/short incl. 4Px1P, narrow/tall, controls passing both); typical-noise detection against size recorded as a measured number (O2, height ruling).** Reason: at typical noise, regions near 3x2 Periods are below detection (B1), so the minimum only binds where the detector can see them; 1.4x gives headroom (x1.13 vs x1.05 at 1.25x).
13. **Test region geometry in Periods, `max(5P, 45) x max(6.6P, 60)`, 512x512 (B2, P2).** Reason: fixed-pixel regions put long Periods under the IoU ceiling (oracle 0.65-0.77 at P16-20); this geometry clears 0.8 on every Period with about 0.03-0.05 to spare.
14. **Score 0.0 for frames with no qualifying group, including constant and all-zero frames (B6).** Reason: gives degenerate frames a defined, finite score.
15. **`analyse(frame, *, threshold=THRESHOLD)`.** Reason: lets the verdict invariant be tested across thresholds on the real path; ticket 07 needs it.
16. **`THRESHOLD = 154` kept, comment marks it as carried over (N6).** Reason: re-deriving it is ticket 07's job; the stale derivation must not mislead.

## 8. Comments to record on the ticket

Copy into `.scratch/stripe-detector/issues/05-striped-regions-and-mask.md` under Comments before the edits they cover:

```
- Approval (orchestrator, <date>): register REGION_CALIBRATION_SEEDS = range(90_000, 90_600) in
  tests/protected.py CALIBRATION_SEEDS, add seed_guard.install() to tests/calibrate_regions.main(),
  and use seed_guard.calibrating(...) blocks there (90_000-90_399 tuning, 90_400-90_599
  informational). Reason: the growth, seed, merge and size-rule knobs must be tuned on seeds the
  acceptance tests do not use (spec.md:112, review B3); this strengthens calibration/evaluation
  separation. The review's and prototypes' seeds (N8; P1 390_000-390_307; P1-D 391_000-391_207;
  P2 410_000-410_079, 411_000-411_003) are reserved in USED_SEEDS. Tuning is frozen (constants committed) before the
  held-out tests run.
- Approval (orchestrator, <date>): add the ticket-05 module constants of analysis.py
  (MIN_HALF_DEPTH_WIDTH_PERIODS = 3.24, MIN_HALF_DEPTH_HEIGHT_PERIODS = 1.93,
  SIZE_ALONG_PERIODS = 0.5, and the seed/growth/merge knobs) and the new
  tests/protected.py numbers (MASK_IOU_MIN 0.8, BBOX_TOL_PERIODS 1.0, MIN_SIZE_BELOW_FACTOR 0.8,
  MIN_SIZE_ABOVE_FACTOR 1.4, DARK_FRACTION 0.05, region geometry, test seeds, USED_SEEDS
  reservations, REGION_CALIBRATION_SEEDS) to tests/protected_numbers.lock. Reason: records new
  numbers, loosens nothing. Changing or removing existing pinned numbers (borderline re-pick,
  stored thresholds after make measure, dropped constants) is not covered and is asked for
  separately with its reason.
```
