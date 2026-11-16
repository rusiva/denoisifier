# 06 plan: spikes and clipped pixels (settled)

Ticket: `.scratch/stripe-detector/issues/06-spikes-and-clipped-pixels.md`. BASE `4e40bdd`.
Spec: `.scratch/stripe-detector/spec.md` stories 24-28 and 46; "Analysis" (option "clip level (detected automatically by default, can be overridden)"; order "spike rejection, clipped-pixel exclusion, envelope estimation, ..."); "Report" (`spike_pixels`, `clipped_pixels`); forward model "add short bright streaks for spikes"; Testing Decisions; spec.md:112 (separate seeds); spec.md:21 (never changes the frame); spec.md:136 (no tests of internals).
GLOSSARY: **Spike** (_Avoid_ outlier, glitch, hot spot). ADR 0001 (near-vertical stripes, Period 3-20 px). CLAUDE.md Gates.

This plan folds: the plan review (`06-plan-review.md`, B1-B4, P1-P2, O1-O2, N1-N5), critic 1 (`06-critic.md`), critic 2 (`06-critic-2.md`), prototypes P1 and P2 (`evidence/06-prototype-p{1,2}.*`, committed) and the orchestrator's Decisions (`06-orchestrator.md`). Every earlier open question is resolved (section 10). Where the orchestrator's first Q4 disposition (a generator-side clip rule as AC 4's precondition) and critic 2 differ, critic 2's ruling wins (final ruling): fixed clip at 0.4, teeth through `clip_level=inf`.

Downstream: ticket 07 calibrates the threshold with spikes present. This ticket leaves `generate` and `analyse` ready for that and does not change the feasibility, gate, probe or regression frames.

## 1. Where things stand (BASE)

- `synthetic.generate(*, seed, shape, period, angle_deg, modulation_depth, mottle, mottle_strength, noise, peak, regions) -> Synthetic(frame, truth, clean)`. RNG draw order: profile, `phase0`, mottle, noise. `GroundTruth(regions)` is built only in `generate`. `test_default_frames_are_unchanged_by_regions` pins SHA-256 digests (seeds 30-32).
- `analysis.analyse(frame, *, threshold=THRESHOLD) -> Report` (analysis.py:154): validate, `_light`, `estimate_local_stripes`, `_qualifying_regions` -> `_settle_overlaps` (:588), verdict. Depth: `_interior_depth` (:618), median over the region's interior (`distance >= _INTERIOR_FRACTION * max`).
- `Report(striped, score, threshold, regions, labels, transposed=False, reader_notes=None)`; `labels` has no default and `compare=False`. `to_dict` order pinned by `test_report_converts_to_json`; JSON `allow_nan=False`.
- `cli.main`: `FRAME [-o] [--mask] [--drop-axis-column] [--transpose]`.
- Stamped: `analysis.py`, `_local_stripes.py`, `synthetic.py`, `__init__.py`, `_calibration.py`, `tests/protected.py`, ... Not stamped: `cli.py`, `report.py`, `frame_io.py`. `test_stamped_files_cover_the_slow_tier` fails on an unclassified file in `src/denoisifier/`.
- Lockfile: every module- and class-level number in `src/denoisifier` and every number in `tests/protected.py` (a missing line, a stale line or a changed value fails `test_protected_numbers`).
- `TEST_SEED_BLOCK = range(10, 100)`; free at BASE: 34-39, 81-99.
- `tests/test_glossary_terms.py`: no "amplitude", "orientation", "wavelength", "false positive" in docstrings or comments. Spike prose says "brightness" or "excess"; never "outlier", "glitch", "hot spot" ("hot pixel" is fine).
- Timing: full frame (400x1600) median 7.47 s against 10 s. Budget for this ticket: **0.3 s** for spike rejection plus clip detection at 400x1600, idle machine.
- Only real frames in the repo are sCMOS (Andor Zyla, `tests/data/solis/NOTICE.md`), integer-valued, unique maximum (no plateau).

## 2. Design (settled)

### 2.1 Generator (`denoisifier.synthetic`)

`generate(..., spikes: int = 0, clip_level: float | None = None)`.

- **Spike model (D1).** `spikes` = number of events. Each event is a straight streak of `L` pixels, `L` uniform in `1.._SPIKE_MAX_LENGTH`, start pixel uniform, direction uniform in `[0, pi)`. Rasterise by stepping along the dominant axis, Bresenham style (N1: rounding `t*(cos, sin)` repeats a pixel near 45°), so a streak of `L` covers exactly `L` pixels unless it leaves the frame (off-frame pixels dropped). Each pixel's added brightness is uniform in `_SPIKE_BRIGHTNESS` times `clean.max()`. Overlapping hits add.
- **RNG stream (D2).** Spike draws come after the noise draw, in one fixed order (rows, cols, lengths, directions, brightness for `spikes * _SPIKE_MAX_LENGTH` pixels, unused ones discarded), only when `spikes > 0`. So `spikes=0, clip_level=None` is bit-identical to BASE (digests unchanged), and a spiked frame equals the same seed's spike-free frame outside the hit pixels.
- **Clipping (D3).** After spikes: `frame = np.minimum(frame, clip_level)`. Frame units, the same meaning as `analyse(..., clip_level=)`.
- **Validation.** `spikes` a non-negative int; `clip_level` finite. `inf` is rejected by `generate` (use `None`) but accepted by `analyse`; the docstring says so (N4). Spikes are added for Gaussian noise too; docstring says so (N4).
- **Ground truth (D4, O1 ruling).** `GroundTruth` gains `spike_mask` and `clipped_mask` (bool, frame shape) and properties `spike_pixels`, `clipped_pixels`.
  - `spike_mask`: every pixel a spike hit, clipped or not.
  - `clipped_mask`: pixels of the spike-free frame at or above `clip_level`, and not in `spike_mask`. The two masks are disjoint.
  - All-False when there are no spikes or no clip.
- `Synthetic.clean` stays noise-, spike- and clip-free; docstring: "`frame - clean` is pure noise when `spikes == 0` and `clip_level is None`".
- Module constants: `_SPIKE_MAX_LENGTH = 3`, `_SPIKE_BRIGHTNESS = (2.0, 10.0)` (bright only; the 2.0 lower end is the boundary case P1 checked, 2.0-2.2x passes). Dim hot pixels and long tracks are out of the model; docstring limit.

### 2.2 Spike rejection (`src/denoisifier/_data_quality.py`, new, stamped)

Two functions, used only by `analyse`:

```python
def find_clipped(frame: np.ndarray, clip_level: float | None) -> np.ndarray      # bool: at/above the level
def reject_spikes(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]             # (working copy, spike mask)
```

- **Method (D5, P1's recommended constants).** `r = frame - med`, where `med` is the median of the pixel's column neighbours at rows `±1..±_SPIKE_NEIGHBOUR_ROWS` (6 values, self excluded), taking the **upper** middle value (scipy's rank for an even footprint) everywhere. In the top and bottom `_SPIKE_NEIGHBOUR_ROWS` rows the window **shifts inward** (rows `0..6` or `R-7..R-1`, self excluded) instead of reflecting (N2; `mirror` still misses edge streaks).
- A pixel is a Spike pixel when **both** `r > _SPIKE_SIGMAS * s` and `r > _SPIKE_FLOOR_FRACTION * scale`:
  - `s`: robust local scale, `_MAD_TO_SIGMA` (1.4826) times the median of `|r|` over `_NOISE_TILE_PX`-square tiles, bilinearly interpolated to the frame.
  - `scale = peak - baseline` (B3): `m3 = median_filter(frame, 3)`; `peak` = the `_SPIKE_PEAK_RANK`-th largest value of `m3` (overlapping hits cannot lift it, P1); `baseline` = the `_SPIKE_BASELINE_PERCENTILE`-th percentile of `m3`. Bias offsets and constant dark subtraction leave `scale` unchanged.
- **Every pixel is tested, clipped or not, with no component-size rule (O1/B1 ruling).** A saturated spike on a dim column is a spike. A spike saturated inside the plateau cannot pass the floor (`level - med < scale`) and stays clipped: the stated limit.
- **What rejection means (D6).** Flagged pixels are replaced by `med` in a working copy only. Every later step runs on the working copy; the caller's array is never modified (`test_input_frame_is_not_modified`). No hysteresis growth.
- Always on; no option.
- Limits (docstring): the count is reliable from about **30 photons at the peak** (P1: at 10 photons a 2x-peak spike sits in the EM-excursion tail; nothing on the grid met the tolerance); two overlapping hits forming a vertical run longer than `_SPIKE_MAX_LENGTH` are partly missed; dim hot pixels and long tracks are not rejected. `_light`'s zero-level assumption predates this ticket (B3 note), not changed here.
- Module constants: `_SPIKE_NEIGHBOUR_ROWS = 3`, `_SPIKE_SIGMAS = 8.0`, `_SPIKE_FLOOR_FRACTION = 1.0`, `_SPIKE_PEAK_RANK = 10`, `_SPIKE_BASELINE_PERCENTILE = 5.0`, `_NOISE_TILE_PX = 16`, `_MAD_TO_SIGMA = 1.4826`. Each comment cites its evidence (`evidence/06-prototype-p1.md`, seeds 396_000-396_399, numbers), as `analysis.py:89-101` does.

### 2.3 Clipped pixels: detection, override, depth

- **Auto-detection (D7).** `find_clipped(frame, None)`: `M = frame.max()`; clipped = `frame == M` when that holds for at least `_MIN_CLIPPED_PIXELS` pixels **and** `frame.min() < M`; else nothing. A constant frame has no evidence of a level, so nothing is clipped (Q7 ruling). P2: exact on every frame at <= 0.8 except 1/40 at 5000 photons; critic: 1/40 integer frames at 30 photons tie 4+ times at the max (P3 records the false-plateau rate on integer frames).
- **Override (D8).** `analyse(frame, *, threshold=THRESHOLD, clip_level: float | None = None)`. A float: clipped = `frame >= clip_level`. `inf`: nothing clipped. `NaN`: `ValueError("clip_level must be a number or inf, got nan")`.
- **Counts (O1 ruling).** `spike_pixels` = pixels `reject_spikes` replaced. `clipped_pixels` = `find_clipped(...) & ~spike_mask`, counted on the input frame. So on a spike-free frame `clipped_pixels == (frame >= C).sum()` for an override `C`.
- **Where clipped pixels enter (O2 ruling: left out of the modulation depth only).** Detection, Period, Angle, growth and the Mask use the working copy unchanged; only the reported depth leaves clipped pixels out.
- **Depth mechanism: d9_inner_g10 (replaces plan D9; P2's best variant).** `_interior_depth(depth, pixels, clipped, period)`: take the region's own interior (as today); drop pixels where `gaussian_filter(clipped.astype(float), sigma=(_ALONG * P, _ACROSS * P)) >= _CLIPPED_WEIGHT_MAX` (rows along, columns across; `_ALONG`/`_ACROSS` imported from `_local_stripes`, the local_mean window); median of what is left; **fall back to the plain interior** when nothing is left. Run only when `clipped.any()`, so unclipped frames give today's numbers exactly. The clipped mask reaches `_interior_depth` through `_qualifying_regions` -> `_settle_overlaps`.
  - Rejected (P2 evidence): plan D9 (box guard; measures the soft-edge rim, adds partial misses 3/20 at 0.8); global weighted fit over the region or bbox (34-40/40 misses); local normalised convolution (12-19/40). Rejected (critic 2): a per-frame clip rule as AC 4's stimulus.
  - Docstring wording (critic 2): this detector does not recover the depth when a large share of a region is clipped (above about a fifth); the reported depth then drifts toward the flattened value, silently per region; `clipped_pixels` is the frame-level warning (story 27). Never write "the information is gone" or "a saturated core loses its depth": the troughs survive (critic 2's check).
- Module constants: `_MIN_CLIPPED_PIXELS = 4`, `_CLIPPED_WEIGHT_MAX = 0.10` (start value; P3 sweeps 0.05/0.10/0.20 before the freeze). `_CLIP_GUARD_SIGMAS` is dropped (no box).

### 2.4 Report and CLI

- `Report` gains required `spike_pixels: int`, `clipped_pixels: int` after `regions`, before `labels` (no defaults, so no class-level numbers). `in_file_layout` keeps them. Docstring states the O1 counting.
- `to_dict` order: `striped, score, threshold, transposed, regions, spike_pixels, clipped_pixels[, reader_notes]`; plain `int`.
- No `clip_level` in the Report (Q3 ruling: counts only; additive later).
- CLI `--clip-level LEVEL` (`type=float`, so `inf` parses) -> `analyse(..., clip_level=)`. Help: "pixels at or above LEVEL that are not rejected as spikes are clipped (saturated) and left out of the modulation depth; default: detected as a plateau of equal values at the frame's maximum; 'inf' turns clipping off; use it after per-pixel dark subtraction, which breaks the plateau". `nan` -> one `denoisifier: error:` line, exit 1. Module docstring and `--help` name the two JSON keys.
- `__init__.py` unchanged.

### 2.5 Glossary (Q9 ruling, with critic 1's two edits)

Add **Clipped Pixel**: "a pixel at or above the clip level, whose true value the frame does not show". _Avoid_: overexposed (not "saturated pixel"; spec.md:58 says "clipped (saturated)"). Via the domain-modeling skill.

## 3. Acceptance criteria -> tests (real paths)

Real paths: `generate(..., spikes=, clip_level=)` -> `analyse` (library); CSV -> CLI subprocess -> JSON (CLI). "Typical" = `mottle="scorched", noise=Emccd()` (100 photons), 256x256, `CASES[seed % 10]` for Period and Angle. All numbers in `tests/protected.py` (section 4). `C(f)` = `f * clean.max()` of the same frame.

**Stimulus precondition, all spike-count tests:** `truth.spike_mask` has no 8-connected component whose vertical extent exceeds `_SPIKE_MAX_LENGTH` (out-of-model overlap, P1 seed 396_316). It reads the generator's truth only, never the detector. The test seeds are checked against it at step 5a, before any `analyse` call on them.

| AC | Test (file) | Frames / seeds | Assertion |
|---|---|---|---|
| 1 | `test_spikes_add_bright_streaks_and_are_in_the_truth` (test_synthetic) | `SPIKE_GENERATOR_TEST_SEED` (34), typical m 0.5, `spikes=SPIKE_TEST_COUNT` | `frame == spike-free frame` where `~spike_mask`; on the mask `frame - free >= _SPIKE_BRIGHTNESS[0] * clean.max()`; `SPIKE_TEST_COUNT <= spike_pixels <= 3 * SPIKE_TEST_COUNT`; 8-connected component count <= `SPIKE_TEST_COUNT`; `clipped_pixels == 0` |
| 1 | `test_streaks_cover_their_length` (test_synthetic) | seed 34, `spikes=1` repeated over directions via the RNG (or a small loop of seeds 34-39 with `spikes=1`) | an in-frame streak of `L` covers `L` distinct pixels (N1) |
| 1 | `test_clip_level_saturates_the_frame_and_is_in_the_truth` (test_synthetic) | seed 34, typical m 0.5, `clip_level=C(CLIP_LEVEL_FRACTION)` | `frame.max() == clip_level`; `clipped_mask == (unclipped >= level)`; `frame == unclipped` elsewhere; `clipped_pixels > 0` |
| 1 | `test_spike_and_clipped_masks_are_disjoint` (test_synthetic) | seed 34, `spikes=SPIKE_TEST_COUNT`, `clip_level=C(SATURATING_CLIP_FACTOR)` | masks disjoint; every hit pixel is in `spike_mask` whatever its final value; some spike pixels end at the level and some below it |
| 1 | `test_rejects_invalid_settings` (extended) | | `spikes=-1`, `spikes=1.5`, `clip_level=nan`, `clip_level=inf` -> `ValueError`, exact prefixes |
| 1 | `test_default_frames_are_unchanged_by_regions` (unchanged) + `test_spike_free_unclipped_frames_are_unchanged` (new) | `DIGEST_TEST_SEEDS` | digests as pinned; `spikes=0, clip_level=None` equals the default call bit for bit |
| 2 spikes | `test_report_counts_spike_pixels` (test_analyse, parametrized: typical m 0; typical m 0.5; Gaussian noise 0.01 m 0.5; `Emccd(photons_peak=SPIKE_PASS_MARK_PHOTONS)` m 0.5) | `SPIKE_TEST_SEEDS` (81-90), `spikes=SPIKE_TEST_COUNT` | `abs(report.spike_pixels - truth.spike_pixels) <= max(SPIKE_PIXELS_ABS_TOL, SPIKE_PIXELS_REL_TOL * truth.spike_pixels)`; `clipped_pixels == 0`; striped frames: `assert_every_region_matches` |
| 2 spikes | `test_saturated_spikes_are_counted_as_spikes` (test_analyse; B1/O1) | `SPIKE_TEST_SEEDS`, typical m 0 and m 0.5, `spikes=SPIKE_TEST_COUNT`, `clip_level=C(SATURATING_CLIP_FACTOR)`, auto detection | spike count within the spike tolerance; `report.clipped_pixels == truth.clipped_pixels` |
| 2 spikes | `test_spike_count_ignores_the_baseline` (test_analyse; B3) | `SPIKE_TEST_SEEDS[0]`, typical m 0.5, spikes | `spike_pixels` equal for `f`, `f + BASELINE_OFFSET`, `f - C/2` (with `C = f.max()`; the shifted frame has negative values) |
| 2 spikes | `test_dimmest_spikes_are_found` (test_analyse; Q8 boundary) | seed 36, typical m 0.5, spike-free frame plus `SPIKE_TEST_COUNT` hand-placed single pixels at exactly `_SPIKE_BRIGHTNESS[0] * clean.max()` | count within the spike tolerance |
| 2 spikes | `test_spike_free_frames_report_no_spikes` (test_analyse) | `MOTTLED_TEST_SEEDS` typical m 0 and 0.5; `FULL_FRAME` cases at noise 0 and 0.01 (P 3 at 10° included); `PROFILE_ONLY` noise 0; hand-made Phase Break frames (noise 0, m 1, lower half rolled sideways by round(P/2), P 3 and P 20, seed 37) | `spike_pixels <= SPIKE_PIXELS_ABS_TOL`; `clipped_pixels == 0` |
| 2 clipped | `test_report_counts_clipped_pixels` (test_analyse) | `CLIP_TEST_SEEDS` (81-90), typical m 0.5, spike-free, `clip_level=C(CLIP_LEVEL_FRACTION)` | `report.clipped_pixels == truth.clipped_pixels` (exact: the plateau is exact) |
| 2 clipped | `test_clipped_and_spike_totals_match_at_a_peak_level_clip` (test_analyse; O1) | `CLIP_TEST_SEEDS`, same, plus `spikes=SPIKE_TEST_COUNT` | `report.spike_pixels + report.clipped_pixels` within the spike tolerance of `truth.spike_pixels + truth.clipped_pixels` (docstring: a spike saturated inside the plateau is counted as clipped) |
| 2 | `test_report_converts_to_json` (extended key list) | | keys `striped, score, threshold, transposed, regions, spike_pixels, clipped_pixels`; both `type(...) is int`, equal to the Report's |
| 3 | `test_spikes_do_not_change_the_verdict_on_stripe_free_frames` (test_analyse; Q6 ruling) | `MOTTLED_TEST_SEEDS` (20), typical m 0, paired with and without `spikes=SPIKE_STRESS_COUNT`; second param: the spiked frame also clipped at `C(SATURATING_CLIP_FACTOR)` (B1 case, auto detection) | per seed: `abs(score_spiked - score_free) <= SPIKE_SCORE_TOL`; verdict equal at `THRESHOLD` and at `threshold=GATE_STORED_THRESHOLD` |
| 3 (clip, critic 2 item 2) | `test_clipped_stripe_free_frames_are_not_striped` (test_analyse) | `MOTTLED_TEST_SEEDS`, typical m 0, spike-free, `clip_level=C(CLIP_LEVEL_FRACTION)` | `striped is False`, `regions == ()` (empty), at `THRESHOLD`. No score tolerance, no `GATE_STORED_THRESHOLD` assertion (1 crossing in 40 in P2: red on about a third of 20-seed sets) |
| 4 | `test_clipped_stripe_peaks_keep_the_modulation_depth` (test_analyse; critic 2 test 1) | `CLIP_TEST_SEEDS`, full-frame typical m 0.5, spike-free, `clip_level=C(CLIP_LEVEL_FRACTION)` | precondition: `truth.clipped_pixels >= CLIP_MIN_SHARE * frame.size`; `assert_every_region_matches(report, truth)` at the unchanged `DEPTH_TOL`, every seed, no allowance. **Teeth:** the same frames with `clip_level=inf`: per seed `err <= err_inf + CLIP_DEPTH_EPS`, and mean `err` < mean `err_inf` strictly (`err` = abs depth error of the matched region) |
| 4 | `test_clipping_does_not_harm_a_partial_region` (test_analyse; critic 2 test 2) | `CLIP_TEST_SEEDS[:5]`, `regions.single_region` geometry (512x512), m 0.5, `clip_level=C(MILD_CLIP_LEVEL_FRACTION)` | precondition (B4): clipped pixels inside `truth_pixels(region)` >= `AC4_MIN_CLIPPED_PIXELS`; one region; `assert_matches_truth`, `assert_depth_matches`. Docstring: a no-harm guard, no teeth against flattening |
| 4 | `test_heavily_clipped_partial_region_is_no_worse_than_no_exclusion` (test_analyse; critic 2 test 3) | same geometry and seeds, `clip_level=C(CLIP_LEVEL_FRACTION)` | same B4 precondition; per seed `err <= err_inf + CLIP_DEPTH_EPS`. Docstring: AC 4 met only in part (ticket Comments) |
| 5 library | `test_clip_level_override` (test_analyse, parametrized) | `CLIP_TEST_SEEDS[0]`, spike-free, clipped at `C(CLIP_LEVEL_FRACTION)` | `analyse(f, clip_level=C) == analyse(f)`; `C2 = OVERRIDE_LEVEL_FRACTION * C`: `clipped_pixels == (f >= C2).sum()`; `inf`: `clipped_pixels == 0`; `nan` -> `ValueError` |
| 5 library | `test_clipping_is_detected_after_a_constant_dark_subtraction` (B2) | same frame minus `C/2` | `clipped_pixels` equal to the unshifted frame's; the shifted frame has negative pixels |
| 5 library | `test_constant_frame_is_not_striped_and_has_finite_score` (extended) | | `clipped_pixels == 0`, `spike_pixels == 0` |
| 5 CLI | `test_cli_reports_spike_and_clipped_pixels` (test_cli) | `CLI_CLIP_TEST_SEED` (35), 96x160 typical m 0.5, `spikes=CLI_SPIKE_COUNT`, `clip_level=C(SATURATING_CLIP_FACTOR)` | exit 0; JSON `spike_pixels`, `clipped_pixels` equal `analyse(read_frame(csv))`'s |
| 5 CLI | `test_cli_clip_level_flag_overrides_detection` (test_cli, parametrized `C2`, `inf`) | same file | JSON equals `analyse(frame, clip_level=...).to_dict()` |
| 5 CLI | `test_cli_fails_cleanly_on_nan_clip_level` | | `_assert_clean_failure` |

Test sizes for `make test-fast`: AC 4 full: 10 seeds x 2 analyses at 256x256; partial: 5 seeds x 3 analyses at 512x512. If test-fast time grows by more than about 30 s, the implementer reports it (no seed cut without approval: narrowing).

## 4. Protected numbers (all lockfile additions)

`tests/protected.py`:

| Name | Value | Basis | When added |
|---|---|---|---|
| `SPIKE_GENERATOR_TEST_SEED` | 34 | free block seed | step 0 |
| `CLI_CLIP_TEST_SEED` | 35 | free | step 0 |
| `SPIKE_BOUNDARY_TEST_SEED` | 36 | free | step 0 |
| `PHASE_BREAK_TEST_SEED` | 37 | free | step 0 |
| `SPIKE_TEST_SEEDS` | `range(81, 91)` | free | step 0 |
| `CLIP_TEST_SEEDS` | `range(81, 91)` | free (shared with spikes, allowed) | step 0 |
| `SPIKE_TEST_COUNT` | 30 | plan | step 0 |
| `SPIKE_STRESS_COUNT` | 100 | plan | step 0 |
| `CLI_SPIKE_COUNT` | 5 | plan | step 0 |
| `SPIKE_PASS_MARK_PHOTONS` | 30.0 | spec.md:141 low end; P1 | step 0 |
| `SPIKE_PIXELS_ABS_TOL` | 2 | requirement, fixed now (orchestrator) | step 0 |
| `SPIKE_PIXELS_REL_TOL` | 0.05 | requirement, fixed now | step 0 |
| `SPIKE_SCORE_TOL` | set by P3: `ceil(1.25 x` largest paired \|score change\|`)`, over both AC 3 parameters (spikes only; spikes with the 3x clip) on fresh seeds 396_600-396_699. **Ceiling 15** (below the headroom 49.7 - 31.1 ≈ 18 at the working point; BASE stripe-free maximum on 10-29); above it: escalate before 5c | B5 (closing check): no evidence on file for a fixed value; P2 saw +21 to +24 jumps from small perturbations | freeze (step 5) |
| `SATURATING_CLIP_FACTOR` | 3.0 | P1 (clip at 3x clean max: every bright spike saturates) | step 0 |
| `MILD_CLIP_LEVEL_FRACTION` | 0.8 | P2 (no-harm guard) | step 0 |
| `OVERRIDE_LEVEL_FRACTION` | 0.9 | override below the plateau | step 0 |
| `BASELINE_OFFSET` | 1000.0 | B3 (Solis bias order) | step 0 |
| `AC4_MIN_CLIPPED_PIXELS` | 30 | B4, N7: below P2's minimum inside the truth region at 0.8 (37 at 100 photons); named apart from the detector's `_MIN_CLIPPED_PIXELS` | step 0 |
| `CLIP_DEPTH_EPS` | set by P3: `max(0.01, largest per-seed err - err_inf + 0.005)` on P3's full and partial frames. **Ceiling 0.02**; above it: escalate | N6: critic 2's largest excess 0.007 (margin 0.003) came from the prototype's code and seeds | freeze (step 5) |
| `CLIP_LEVEL_FRACTION` | 0.4 (0.5 if P3's margin check fails) | critic 2 test 1 | freeze (step 5) |
| `CLIP_MIN_SHARE` | 0.02 at 0.4 (P2 minimum 2.3%, median 5.2%); re-read from P3 if the fraction moves | critic 2 | freeze (step 5) |
| `USED_SEEDS` additions | `range(396_000, 396_406)`, `range(396_500, 396_700)`, `range(700_000, 700_006)`, `range(700_100, 700_140)` | P1/P2 and critic 2 (396_400-396_405); P3 (reserved before use); critic 1 scratch | step 0 |

`src/denoisifier` module constants: `synthetic._SPIKE_MAX_LENGTH = 3`, `synthetic._SPIKE_BRIGHTNESS = (2.0, 10.0)`; `_data_quality._SPIKE_NEIGHBOUR_ROWS = 3`, `_SPIKE_SIGMAS = 8.0`, `_SPIKE_FLOOR_FRACTION = 1.0`, `_SPIKE_PEAK_RANK = 10`, `_SPIKE_BASELINE_PERCENTILE = 5.0`, `_NOISE_TILE_PX = 16`, `_MAD_TO_SIGMA = 1.4826`, `_MIN_CLIPPED_PIXELS = 4`, `_CLIPPED_WEIGHT_MAX = 0.10` (P3 may set 0.05 or 0.20 before the freeze; same approval). Each lane adds its own module's lines when it introduces the constant.

Reused unchanged: `DEPTH_TOL`, `PERIOD_REL_TOL`, `ANGLE_TOL_DEG`, `GATE_STORED_THRESHOLD`, `THRESHOLD`.

## 5. Seeds

- Prototype seeds: `range(396_000, 396_400)` (P1, P2), 396_400-396_405 (critic 2), 700_000-700_005 and 700_100-700_139 (critic 1): all reserved in `USED_SEEDS`, none in `CALIBRATION_SEEDS` (Q2 ruling: no seed-guard change, no `calibrating(...)` block, no new install).
- P3 (pre-freeze check, section 7 step 5b): `range(396_500, 396_600)`, reserved at step 0 before it is looked at: 396_500-396_539 cutoff sweep; 396_540-396_579 fresh margin check; 396_580-396_599 partial frames; 396_600-396_699 the AC 3 paired score distribution (fresh, not the P1 tuning seeds; B5). All reserved at step 0.
- Test seeds 34-37, 81-90: never generated by any prototype.
- `feasibility.py` and the gate/probe/regression frames stay spike-free and unclipped (ticket 07 adds spikes).

## 6. Weakening moves and approvals

Recorded with the reason in the ticket's Comments before the edit.

| Move | Why | Status |
|---|---|---|
| `tests/slow_stamp.py`: add `src/denoisifier/_data_quality.py` to `STAMPED_FILES` | `test_stamped_files_cover_the_slow_tier` demands it; widens the stamp | **Given** (orchestrator, Q1); recorded in the ticket Comments 2026-11-13 |
| Lockfile additions, `src/denoisifier` constants of section 4 | new detector and generator numbers; loosens nothing; values from P1/P2 evidence | **Given** (orchestrator, 2026-11-13); recorded in the ticket Comments |
| Lockfile additions, `tests/protected.py` names of section 4 and the `USED_SEEDS` reservations | new tests, fixed tolerances, reserved seeds; `tests/protected.py` is stamped | **Given**, same approval. Covers the values P3 sets at the freeze (`CLIP_LEVEL_FRACTION`, `CLIP_MIN_SHARE`, `SPIKE_SCORE_TOL`, `CLIP_DEPTH_EPS`, `_CLIPPED_WEIGHT_MAX`) while within the stated ceilings; above a ceiling, or any loosening after the freeze, is a new ask |
| `GATE_STORED_THRESHOLD`, `PROBE_STORED_THRESHOLD` after `make measure` | `test_stored_thresholds_are_the_saved_measurement` | **Needed only if they move** (P1: 0 false spike flags on 80 typical spike-free frames, so no move expected) |
| Any tolerance loosened, fraction raised, seeds cut or frames softened after the freeze | only if the frozen detector misses | escalate (orchestrator, then owner) |

Not weakening: extending `test_report_converts_to_json`'s keys and `test_rejects_invalid_settings`; new tests. Not touched: digest strings, `seed_guard.py`, `CALIBRATION_SEEDS`, `conftest.py`, the Makefile, timeouts, regression pass counts.

## 7. Steps

Parallel lanes have disjoint file sets. The one shared file is `tests/protected_numbers.lock`, where each lane adds only its own module's block of lines (textual merge only). `tests/protected.py` is edited only in step 0 and step 5c, by one hand.

0. **Seeds and numbers (one hand, sequential).** The lockfile approval is given and recorded (section 6). Add the step-0 names of section 4 and the `USED_SEEDS` reservations to `tests/protected.py` and the lockfile. `make test-fast`.
1. **Plumbing (one hand, sequential).** Files: `src/denoisifier/report.py`, `src/denoisifier/analysis.py` (signature and validation only), `tests/test_analyse.py` (JSON key test, `clip_level` validation). Report fields, `to_dict`, `analyse(..., clip_level=None)` with the NaN `ValueError`, counts passed as 0. `make test-fast`. This fixes the interface lanes A-C build on.
2. **Parallel lanes (after step 1):**
   - **Lane A, generator (tdd).** Files: `src/denoisifier/synthetic.py`, `tests/test_synthetic.py`, synthetic lines of the lockfile. Section 3 AC 1 tests, then D1-D4. Digests stay green untouched.
   - **Lane B, CLI and glossary.** Files: `src/denoisifier/cli.py`, `tests/test_cli.py`, `GLOSSARY.md`. `--clip-level`, help, docstring, CLI tests. Until lane A lands, CLI tests build frames with `np.minimum` on a spike-free `generate` frame; switch to `generate(spikes=, clip_level=)` after the merge (step 4).
   - **Lane C, detector.** Files: `src/denoisifier/_data_quality.py` (new), `src/denoisifier/analysis.py`, `tests/test_data_quality.py` (new: unit tests of `find_clipped` and `reject_spikes` on hand-made frames), `tests/slow_stamp.py` (the approved `STAMPED_FILES` line), `_data_quality` lines of the lockfile. D5-D7, d9_inner_g10 in `_interior_depth`, wired into `analyse` before `_light`. Constants from section 2.
3. **Merge A, B, C**, resolve the lockfile block merge, switch lane B's CLI tests to `generate(spikes=, clip_level=)`, `make test-fast`. The AC 2-4 tests of section 3 are not written yet: they first run on the test seeds after the freeze (5c), so no tuning sees them.
4. (folded into 5c)
5. **Freeze.**
   - a. Stimulus check: with the generator only, check the test seeds' truth for the out-of-model spike precondition (section 3). A failing seed shifts the range before any `analyse` call; record it in Comments.
   - b. **P3 pre-freeze check** (background, alone, idle machine, log to file; script `evidence/06-prototype-p3.py`, results `.md`, `.json`, `.txt`, tracked), with the implemented detector:
     - cutoff sweep `_CLIPPED_WEIGHT_MAX` in {0.05, 0.10, 0.20} on 396_500-396_539 (full, typical, 0.4): misses, worst error, mean error against `inf`;
     - fresh margin check at the chosen cutoff on 396_540-396_579: worst full-frame error at 0.4 must be <= 0.08; else set `CLIP_LEVEL_FRACTION = 0.5` and recheck on the same fresh seeds, keeping the `inf` comparison; record 30 photons (not asserted);
     - per-seed `err - err_inf` (sets `CLIP_DEPTH_EPS`, ceiling 0.02), minimum clipped share (sets `CLIP_MIN_SHARE`);
     - partial frames 396_580-396_599 at 0.8 and 0.4 (no-harm and not-worse checks);
     - AC 3: paired spikes/no-spikes on fresh 396_600-396_699, both parameters (spikes only; spikes with the 3x clip): score changes and the crossing count at `GATE_STORED_THRESHOLD` (sets `SPIKE_SCORE_TOL`, ceiling 15);
     - clipped stripe-free frames at the chosen fraction: regions and scores at `THRESHOLD`;
     - false plateaus on integer-valued EMCCD frames (`em_gain=1, read_noise_e=0`, 30/100/1000 photons) and both Solis fixtures;
     - timing of `reject_spikes` + `find_clipped` at 400x1600, idle: <= 0.3 s, else escalate.
     A required miss goes to the orchestrator before 5c.
   - c. Commit the constants, `CLIP_LEVEL_FRACTION`, `CLIP_MIN_SHARE`, `SPIKE_SCORE_TOL`, `CLIP_DEPTH_EPS` (lockfile lines) and the P3 evidence. Then write the AC 2-5 tests of section 3 in `tests/test_analyse.py` (one hand) and run them as acceptance. Red -> stop and report; no re-tune, no loosening.
6. **Docs.** `analysis` module docstring (spike rejection, clip detection, depth on unclipped pixels and the limit wording of 2.3), `analyse` (`clip_level`), `Report`, `GroundTruth`, `Synthetic`, `generate`, `_data_quality`, CLI help. Prose: "brightness", "excess"; never "amplitude", "outlier", "glitch", "hot spot".
7. **Code review, fixes, then the gates (section 8).**

## 8. Gates

The detector changes (`analysis.py`, stamped `_data_quality.py`, `synthetic.py`), so `make measure` is required. End sequence, once, after the code review's fixes, idle machine (`uptime`), each in the background with output to a log and `; echo "EXIT=$?" >> <log>`:

1. `make test-fast` green; commit (clean tree: the measurement refuses `-dirty`).
2. Fixer: `make measure` (~39 min). Gate frames have no spikes and no clipping; P1 found 0 false spike flags on typical spike-free frames, so the thresholds should be identical (no lockfile edit). If they move: update `GATE_STORED_THRESHOLD` / `PROBE_STORED_THRESHOLD` by hand (approval). The gate statements must hold; a failure is escalated, never tuned on gate seeds. `test_regression_plan_meets_the_operating_rule` red: owner decision.
3. Fixer: `make check-slow` (~6 min).
4. Fixer: `make check`.

No expected-red `make check` anywhere. The handoff quotes each command, exit status, pytest's final summary line and `git rev-parse --short HEAD` (`-dirty` if so), plus P3's numbers (cutoff, worst full-frame error at the fraction, mean error against `inf`, AC 3 score changes, timing).

## 9. Risks

- AC 4 is met only in part: partial regions with a fifth or more of the region clipped report a low depth (critic 2; ticket Comments; follow-up issue 15). The final handoff tells the owner.
- Clipped stripe-free frames: scores move both ways, mean near zero; one crossing of 49.7 in 40 frames per level (seeds 396_085, 396_078). Not ticket 06's AC; ticket 07 carries the rate question (07 note, 2026-11-13).
- Size rule on clipped regions: `_grow` leaves a flattened core out; P2 saw no region-count failure on 960 frames. AC 4 tests catch a regression.
- Real hot pixels dimmer than the floor and long tracks are not rejected; auto-detection misses clipping after per-pixel dark subtraction (the override is the answer).
- Timing: 0.29 s under load against 0.3 s; P3 measures idle. If tight: `median3` serves only the peak scalar, so it can run on a 2x-binned frame.

## 10. Resolved questions

All resolved; no open questions.

1. Code location: new `_data_quality.py`, stamped (approved).
2. Tuning: reserved prototype seeds, evidence tracked under `evidence/`, no seed-guard change.
3. Report: counts only.
4. Exclusion scope: modulation depth only (O2, ticket Comments); mechanism d9_inner_g10.
5. Spike/clip overlap: count by what the detector did (O1).
6. AC 3: paired per-seed score tolerance (set by P3, ceiling 15) plus verdicts; 100-seed paired distribution in P3's evidence; slow-tier rate is ticket 07's.
7. Constant frames: nothing clipped (no evidence of a level).
8. Spike model: bright only, 2-10x, length 1-3; boundary and Phase Break cases tested.
9. Glossary: **Clipped Pixel** with critic 1's edits.
- AC 4 shape (critic 2 item 1): full frame at 0.4 with teeth against `inf`; partial at 0.8 within tolerance (no-harm); partial at 0.4 not worse than `inf`; per-frame rule rejected.
- Clipped stripe-free frames (critic 2 item 2): not striped, no regions, at `THRESHOLD`.
- External, non-blocking: do real frames saturate a fifth or more of a region? In follow-up issue 15; does not change what 06 ships.
