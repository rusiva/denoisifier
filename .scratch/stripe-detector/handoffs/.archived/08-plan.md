# 08 plan: bin factors (settled)

**Status: settled 2026-11-14.** This is not a draft. Every question is ruled and every review item is folded into the body.

Sources:
- `08-orchestrator.md`, section "Decisions".
- `08-critic.md`: Q1-Q7, B1-B3, N1-N6, M1-M6.
- `08-plan-review.md`: B1-B3, P1, O1, O2, N1-N6.
- Prototype P1: `08-prototype-p1.md`, on branch `worktree-agent-a429ed8e080a02714` at `d5e81b8`, throwaway and not merged.
- The orchestrator's rulings on P1: Q2 = A; the 2x1 limit stays 4 px; M3 = no compensation; M5 = no change.

Implementers follow this file. A departure from it is a finding for the orchestrator, not a silent fix.

Ticket: `.scratch/stripe-detector/issues/08-bin-factors.md`, including its Comment from ticket 07 plan Q9. BASE `0032d7f`.
Spec: `.scratch/stripe-detector/spec.md` story 35, "Analysis" (options), "Pixel geometry" (spec.md:114), and Testing Decisions spec.md:142.
GLOSSARY: **Period**, **Angle**, **Striped Region**. ADR 0001 (stripe vs 90-deg reference ratio). ADR 0002 (Threshold as an order statistic).

## 1. Where things stand (BASE)

- `analyse(frame, *, false_alarm_rate, calibration, threshold, clip_level) -> Report`. Every length in the detector is in **frame (array) pixels** and every frequency in **cycles per frame px**. These equal sensor units only at 1x1.
- Frequency grid: `_local_stripes._Spectrum.__init__` takes `fx` and `fy` from `np.fft.fftfreq`. Every filter (`gabor`, `local_mean`, `analysis._Filters.size_depth`) is a Gaussian in `(fx, fy)`.
- Bank: `_PERIODS` (18 Periods, 3 to 20) x `_STRIPE_ANGLES_DEG` (-10 to 10 every 5), with references at +90 deg.
- Lengths given in Periods and converted to px in place:
  - the ratio box in `estimate_local_stripes`;
  - `_passes_size_rule`;
  - `_near`;
  - `_interior_depth`: the edt and the clipped-share sigma;
  - `_phase_steps`: phase steps per px to Period and Angle.
- Lengths in plain px: `MIN_SIDE`, `_PAD`, `_ENVELOPE_SIGMA`, `_LIGHT_PEAK_SIGMA`, `_PEAK_FOOTPRINT_PX`, `_data_quality`.
- `Report` / `Region` / `BoundingBox` live in `report.py` (`NOT_STAMPED_SRC`). The `to_dict` key order is pinned by `test_analyse.py::test_report_converts_to_json`.
- `Calibration` records `shape` and `settings`. `settings` are compared and are part of the digest. `calibrate_folder` already records read options there (`calibration.py:276-285`), and `test_calibration.py:167` pins them exactly. The stored calibration is 300 frames, 400x1600, unbinned.
- `pyproject.toml:58` sets `filterwarnings = ["error"]`. CLI tests require that stderr carries exactly one line, and only on errors (`test_cli.py:43-45`).
- `tests/calibrate_regions.py:33, 261, 264` calls `estimate_local_stripes(frame, light)` and `analysis._Filters(_Spectrum(frame), light)` directly.

## 2. Design

### 2.1 Library option

- New public frozen dataclass `BinFactors(horizontal: int = 1, vertical: int = 1)` in `report.py`, exported from `denoisifier.__init__`.
  - `__post_init__` refuses anything but a plain `int >= 1`: a non-int or a `bool` raises `TypeError`, a value `< 1` raises `ValueError`.
  - `to_dict() -> {"horizontal": h, "vertical": v}`. `from_dict(d)` parses that shape and raises `ValueError` on anything else.
  - Why named fields: `Calibration.shape` is `(rows, cols)`. A bare `(h, v)` tuple beside it would be in the opposite order, and a swap would silently give wrong Periods and Angles.
  - Why `report.py`, which is unstamped: `BinFactors` is data plus validation only; every computation from it happens in stamped files. The lockfile pins its defaults. The slow tier runs only at 1x1. Record this reasoning in the ticket Comments.
- `analyse(..., bin_factors: BinFactors | None = None)`. `None` means `BinFactors()`.
  - `horizontal` bins along a row (the analysed frame's columns); `vertical` bins along a column (its rows).
  - Under the CLI's `--transpose`, the factors refer to the analysed frame's axes, which are the sensor's.
- `calibration.stripe_free_score`, `calibrate` and `calibrate_folder` get the same keyword (`bin_factors: BinFactors | None = None`). They pass it to `analyse` and record it (2.6).
- Only the public functions default `bin_factors`. Internals require `bins` (2.3).

### 2.2 CLI flag

- `--bin HxV`, for example `--bin 1x2`.
  - Order: horizontal first. This is the ticket's and spec's own notation: in issue line 9, 1x2 turns 10 deg into 19.4 deg, so the 2 is vertical.
  - Parsing: an argparse `type=` function matches `^\d+x\d+$` (case-insensitive `x`) and builds a `BinFactors`. A malformed or zero value is an argparse error (exit 2).
  - Help: "bin factors of the frame as HORIZONTALxVERTICAL (default 1x1). Period, Angle and the 3x2-Period minimum are in sensor pixels; bboxes, areas and the mask are in frame pixels."
- `python -m denoisifier.recalibrate` gets the same `--bin` (2.6).
- Add one sentence each to the `cli.py` module docstring, the main `description` and the `--transpose` help.
- Warnings go into the JSON only, like `reader_notes`; nothing is echoed to stderr (CLI stderr rule above).
- `Report.in_file_layout()` transposes only `labels` and the bboxes. `bin_factors`, `unresolved_period_px` and `warnings` are kept as they are.

### 2.3 Where the conversion to binned-array coordinates happens

Rule: every Period and Angle inside the detector is in **sensor** units. Conversion happens at three seams, all in stamped files.

**(a) Frequency grid: `_Spectrum(frame, bins)` in `_local_stripes.py`, with `bins` required.**
- `fx = fftfreq(cols) / bins.horizontal` and `fy = fftfreq(rows) / bins.vertical`, both in cycles per sensor px.
- Every filter built on this grid (`gabor`, `local_mean`, `_Filters.size_depth`, `gabor_at`) is then specified by a sensor Period and Angle, and is exactly the binned-array filter at the converted array Period and Angle. This is where the **period range (3-20 px) and angle range (+-10 deg)** are converted. For example, a bank filter at 10 deg sits at `atan(2 tan 10 deg) = 19.4 deg` in the frame under 1x2.
- `_Filters` takes no new argument and reads `self.spec.bins`.
- Every `_Spectrum` call passes `bins`:
  - `estimate_local_stripes`;
  - `_qualifying_regions` (`analysis.py:351`);
  - `_is_leakage`'s spectrum of the frame with the stronger candidate taken out (`analysis.py:656`). A forgotten `bins` here would silently analyse that spectrum at 1x1, which is why `bins` is required.
  - `gabor_at` (`bins` required).
- `tests/calibrate_regions.py` lines 261 and 264 get `BinFactors()`: a two-line edit, not a protected or stamped file.

**(b) Searched Periods: `searched_periods(bins)` and `unresolved_period_range(bins)` in `_local_stripes.py`.**
- `MIN_ARRAY_PERIOD_PX = 2.0` is a new module constant (lockfile addition).
- A bank Period `p` is searched only when every bank filter at `p` keeps a frame Period of at least `MIN_ARRAY_PERIOD_PX`. That means the stripe filter at each Angle `a`, **and** its 90-deg reference.
  - The frame Period is `p / hypot(h cos t, v sin t)`, where `t` is the filter's wavevector angle in sensor coordinates (`a` for stripe filters, `a + 90` for references).
  - The result keeps `_PERIODS` order. At 1x1 it is `_PERIODS` itself.
- Ruling Q2 = A: the references count.
  - Without them, every 1x2 Stripe-free frame scored 1216 median and 2198 at most at Period 3 (P1a, 40 of 40 frames). With them it scored median 22.8, max 39.2.
  - Under 1x2, A gives up only physical Periods near 3 px. 3.4 and 3.8 px are still found and measured within 1% through the 4.19 filter (P1b).
- `unresolved_period_range(bins) -> tuple[float, float] | None` returns `(3.0, limit)` with `limit = 2 * max over the bank filters of hypot(h cos t, v sin t)`, or `None` when `limit <= 3.0`.
  - It also returns which filters set the limit: stripe filters, references, or both.
  - Under 2x1 the result is `(3.0, 4.0)` from the stripe filters (AC 3). Under 1x2 it is `(3.0, 4.0)` from the references. Under 2x2 it is `(3.0, 4.0)` from both.
  - P1b: under 2x1, 4.2 px resolves 8 of 8 at 0 and 10 deg, with errors of 0.1% in Period and 0.02 deg in Angle. Phase-step wrap: 0.7% of single pairs, summed step 0.95 pi. So the 2-frame-px minimum stands.
- `estimate_local_stripes(frame, light, bins)` (`bins` required) loops over `searched_periods(bins)`.
- `analyse` raises `ValueError` naming the factors when `not searched_periods(bins)` (for example 11x1). It does not test `limit > 20`: one source of truth.
- Fine Periods from `_phase_steps` are not clamped. The warning covers a region reported just under the limit.

**(c) Spatial lengths: in-place conversions in `analysis.py` and `_local_stripes.py`.**
- Ratio box: `(max(3, round(2p / v)), max(3, round(3p / h)))`.
- Size rule (**the 3x2-Period minimum**):
  - Width: `width * h < MIN_HALF_DEPTH_WIDTH_PERIODS * p`.
  - Height: `height * v >= MIN_HALF_DEPTH_HEIGHT_PERIODS * p`.
  - `_half_peak_span` still measures frame px along rows and columns. The constants are unchanged.
  - P1 M5: with the existing 0.8 and 1.4 factors, 48/48 below-minimum frames were rejected and 36/36 above-minimum frames reported, under 2x1 and under 1x2, as at 1x1. No change.
- `_phase_steps(response, area, period, angle_deg, bins)` (`bins` required):
  - `fx = angle(cx) / (2 pi) / h` and `fy = angle(cy) / (2 pi) / v`, then Period and Angle as now.
  - Both are sensor units, so `Region.period_px` and `Region.angle_deg` need no conversion.
- `_near`:
  - The gap stays `_MERGE_GAP_PERIODS * period`, in sensor px.
  - `distance_transform_edt(..., sampling=(v, h))` **only when binned**; at 1x1 the call is unchanged.
  - The window pad is `ceil(gap / min(h, v)) + 1` frame px.
- `_interior_depth(depth, pixels, clipped, period, bins)` (`bins` required):
  - The edt gets `sampling=(v, h)` only when binned.
  - The clipped-share sigma is `(_ALONG * p / v, _ACROSS * p / h)`.
- `_refined` and `_grow_candidates` pass `filters.spec.bins` to `_phase_steps`.

**Kept in frame px (ruling Q3):** `MIN_SIDE`, `_PAD`, `_light` (both sigmas), `_PEAK_FOOTPRINT_PX`, `_MIN_PAIRS`, seed and core connectivity, and all of `_data_quality`. Each is a property of the array: FFT padding validity, per-pixel noise averaging, seed spacing, or readout spikes.

**Modulation Depth (ruling M4):** it is reported as measured on the frame as given, with no correction.
- Block summing damps a component across the binned axis by `|sin(pi h f) / (h sin(pi f))|`. Under 2x1 the depth comes out about x0.97 at 12 px, x0.87 at 6 px and x0.73 at 4.2 px.
- `units`, `Region`'s docstring and `analyse`'s docstring say so and give the factor.
- Not corrected in this ticket: a correction amplifies noise at short Periods and would need its own validation.

**Mottle anisotropy (ruling M3): measured, not compensated.**
- Binning makes isotropic Mottle directional in the frame. Under 1x2 the Stripe-free max ratio rises 1.88x at 4.19 px (prediction 1.87x) and 1.06-1.27x at 4.69-12.8 px. Under 2x1 it changes by 0.91-1.43x.
- Compensating with the bin-transfer factor over-corrects: 0.8-0.9x at 4.69-6.55 under 1x2, and up to 1.91x under 2x1.
- Scores under rule A stay below the stored Threshold of 100.8: at most 43 under 1x2 and 67-80 under 2x1.
- Binned frames are outside the calibration's rate claim anyway (2.6). No reference scaling is added.

### 2.4 1x1 is byte-identical

- Conversions divide or multiply by `1` or `1.0`, which is exact in IEEE 754, and `round(2p / 1) == round(2p)`.
- `sampling=` is passed only when binned.
- `searched_periods(BinFactors())` is `_PERIODS` in the same order.
- So `analyse(f)`, `analyse(f, bin_factors=BinFactors(1, 1))` and BASE agree exactly.
- **Evidence the handoff must carry (N2 / M6):**
  1. **BASE outputs, saved before step 2.** Save `to_json()` and `labels` (`.npy`) for the four AC 5 kinds (2.5 table) to the scratchpad, by a script run at BASE, before any detector edit.
  2. **The diff, run after step 3 and again at the end.** It must be empty, except for the new JSON keys, which the script strips (`bin_factors`, `units`, `unresolved_period_px`, `warnings`).
  3. **`make check-slow`'s calibration reproduction.** `tests/test_slow_calibration.py` rescores 300 full frames and checks the scores exactly. This proves Stripe-free identity; the diff proves striped identity. Quote both.

### 2.5 Report fields and units

New `Report` fields, all with defaults:
- `bin_factors: BinFactors = BinFactors()`. Lockfile line `denoisifier.report :: Report.bin_factors`.
- `unresolved_period_px: tuple[float, float] | None = None`: the part of the 3-20 px range that was not searched, in sensor px.
- `warnings: tuple[str, ...] = ()`: frame-level analysis warnings, separate from `reader_notes`.
  - Plain strings in the Report and the JSON. **Never `warnings.warn`** (`filterwarnings = ["error"]`).
  - **Sub-2-px warning.** Emitted whenever `unresolved_period_px` is not `None`; the text names the filter that is unresolved. `{lim:g}` is the limit.
    - Stripe filters set the limit (2x1): "Periods below {lim:g} px cannot be resolved at 2x1 binning: the stripes fall under 2 frame pixels; they were not searched".
    - References set the limit (1x2): "Periods below {lim:g} px were not searched at 1x2 binning: the 90-deg reference filters fall under 2 frame pixels (the stripes do not)".
    - Both set it: one sentence naming both.
  - **Calibration-coverage note:** 2.6.

`to_dict` order:
```
striped, score, threshold, transposed, bin_factors, units, regions,
spike_pixels, clipped_pixels, unresolved_period_px, warnings[, reader_notes]
```
- `unresolved_period_px` is a two-element list or `null`.
- `warnings` is a list.

`Report.UNITS: ClassVar[dict[str, str]]`:
- A `ClassVar`, so it is not a dataclass field; it holds no numbers, so it has no lockfile line.
- It covers every field that has a unit:
```
period_px            "sensor px"
angle_deg            "degrees from vertical, sensor geometry"
modulation_depth     "relative to the local envelope, as measured on the (binned) frame"
bbox                 "frame px (binned array; file layout when transposed)"
area_px              "frame px (binned array)"
mask                 "frame px (binned array; file layout when transposed)"
spike_pixels         "frame px (binned array)"
clipped_pixels       "frame px (binned array)"
unresolved_period_px "sensor px"
```
- `to_dict()["units"]` is a copy of it, emitted always (ruling Q4: AC 4 asks each field's unit to be stated).
- `Region` keeps its field names. `Report`'s and `Region`'s docstrings name the units.

### 2.6 Calibration coverage note (the ticket's Comment): decided

**Decision: yes, add a note to the Report.** Rulings Q5 and O2; there is no file-format or digest change, so it is not a hard-to-revert item.

- **Record.** `calibrate`, `calibrate_folder` and `stripe_free_score` take `bin_factors`. `calibrate` and `calibrate_folder` record `settings["bin_factors"] = {"horizontal": h, "vertical": v}` **only when the factors are not 1x1**.
  - `settings` already feed equality and the digest. The stored file, `PACKAGE_CALIBRATION_DIGEST` and `test_calibration.py:167`'s pinned 1x1 settings are unchanged.
  - `recalibrate --bin HxV` passes the factors through.
- **Read.** A read-only `Calibration.bin_factors` property: `BinFactors.from_dict(settings["bin_factors"])`, or `BinFactors()` when the key is absent. Malformed settings raise `ValueError`.
  - No new dataclass field, no `to_json` or `digest` change, no lockfile line.
- **Note.** `analyse` adds at most one coverage note when a Calibration set the Threshold. There is no note when `threshold=` was given.
  - **Bin mismatch** (`calibration.bin_factors != bin_factors`): "the calibration was made at {c} binning; its false-alarm rate does not cover {b} frames (binning makes the Mottle directional in the frame: Stripe-free scores up to 1.9x at the shortest searched Period)".
  - **Otherwise, larger frame** (`rows * cols > calibration.shape[0] * calibration.shape[1]`): "frame {r}x{c} has more pixels than the calibration's {R}x{C}; its false-alarm rate is not covered".
  - The pixel count is the right test: `analyse`'s docstring speaks of a "larger light area". A 512x512 frame (41% of the calibration's area) gets no note.
  - Smaller frames get no note: their rate is expected to be lower, as documented.
  - The note never changes the verdict or the Threshold.
- `analyse`'s docstring coverage paragraph gets the same wording (M3 numbers).

### 2.7 Docs

- **GLOSSARY.** Add **Bin Factors** ("horizontal x vertical; sensor pixels summed into one frame pixel per axis") and **Frame pixel** (vs. sensor pixel). **Period** is unchanged.
- **ADR 0001, Consequences.** Add one line: "Binning (ticket 08) makes isotropic Mottle directional in the frame. Measured at 1x2: Stripe-free max ratio 1.88x at 4.19 px, 1.06-1.27x at 4.69-12.8 px. The bin-transfer compensation was measured and rejected (it over-corrects 1x2 to 0.8-0.9x and inflates 2x1 up to 1.9x); binned frames are outside the calibration's claim, and the Report notes it. References count toward the searchable range (`searched_periods`)."
- **ADR 0002, Consequences.** Add one line: "A Calibration records non-1x1 bin factors in `settings`; `analyse` notes a bin mismatch or a frame with more pixels than the calibration's."
- **`_local_stripes` module docstring:** the resolvability rule. **`analyse` docstring:** the `bin_factors` paragraph, depth (M4) and coverage (M3).

## 3. Prototype (done)

P1 is done. See the sources and its findings, cited in 2.3. Its seeds `108_000-108_399` are reserved in `USED_SEEDS` (step 0). Nothing from its branch is merged.

## 4. Implementation steps (each ends on `make test-fast` green)

0. **Seeds, helpers and BASE outputs.**
   - `tests/protected.py`:
     - Add `BINNING_TEST_SEEDS = range(a, b)` **inside `TEST_SEED_BLOCK` (10-99)**, as every `*_TEST_SEEDS` must be (`test_feasibility_gate.py:76-87`). Test seeds may share; it needs no `USED_SEEDS` entry.
     - Add `BINNING_PROTOTYPE_SEEDS = range(108_000, 108_400)` and append it to `USED_SEEDS`. This changes the existing lockfile line `protected :: USED_SEEDS`; the approval is granted (section 7).
   - New `tests/binning.py`:
     - `bin_sensor_frame(frame, h, v)`: a block sum. It asserts `rows % v == cols % h == 0`.
     - `bin_truth_mask(mask, h, v)`: a block mean.
   - Run the BASE-output script (2.4), before any detector edit.
1. `BinFactors` (with `from_dict`) in `report.py`, exported. Validation tests.
2. `_local_stripes.py`:
   - `_Spectrum(frame, bins)`;
   - `searched_periods`, `unresolved_period_range` and `MIN_ARRAY_PERIOD_PX`;
   - `estimate_local_stripes(frame, light, bins)` and `gabor_at(..., bins)`;
   - the `tests/calibrate_regions.py` edit.
3. `analysis.py`: `bin_factors=`, the 2.3(c) conversions, `_Filters` reading `spec.bins`, and the no-searchable-Period `ValueError`.
   - Add the AC 5 identity tests **first** in this step; they stay green from here on.
   - Then run the BASE diff (2.4).
4. Report:
   - the new fields, `UNITS`, `to_dict` and the warnings;
   - `in_file_layout` keeps the new fields;
   - extend the `test_report_converts_to_json` key list.
5. Calibration: record and read `bin_factors` (2.6), and the coverage note in `analyse`.
6. CLI `--bin` and recalibrate `--bin`; docstrings, GLOSSARY, ADR 0001 and ADR 0002 lines.
7. Record the approvals in the ticket Comments, each with its reason (section 7).
8. Closing sequence after the review fixes:
   - `make check-slow`, then `make check`.
   - No `make measure`, no `make check-held-out`, no calibration re-store.
   - The handoff quotes the 2.4 evidence.

## 5. Acceptance criteria -> tests (real path)

Every frame is generated at sensor size with `generate(...)`, binned with `bin_sensor_frame`, then run through `analyse(binned, bin_factors=...)` or the CLI. The truth is the generator's sensor-px Period and Angle, checked with `truth_match.assert_matches_truth` (protected `PERIOD_REL_TOL` and `ANGLE_TOL_DEG`). The seeds are `BINNING_TEST_SEEDS`.

| AC | File :: test | Asserts |
|---|---|---|
| 1. 1x2, physical 10 deg -> about 10 deg | `test_analyse.py::test_one_by_two_binning_reports_the_physical_angle[10, -10]` | Sensor 512x256 -> frame 256x256, Period 8, Angle +-10. One region; `assert_matches_truth`. Sanity on the frame itself: its 2D FFT peak (computed inline; `tests/spectrum.py`'s band is +-12 deg) is at about +-19.4 deg. |
| 2. 2x1, 12 px -> about 12 | `test_analyse.py::test_two_by_one_binning_reports_the_physical_period[0, 10]` | Sensor 256x512 -> 256x256, Period 12. `period_px` within 5% of 12 and explicitly not within 5% of 6; Angle via `assert_matches_truth`. |
| 3. 2x1 warns below 4 px | `test_analyse.py::test_two_by_one_binning_warns_below_four_px` | `unresolved_period_px == (3.0, 4.0)`. A warning containing "below 4 px" and "stripes" is **present**. With `threshold=` given, `warnings` holds **exactly** that one warning (with the default calibration, the coverage note is also there; ruling M2). |
| 3 (contrast) | `test_analyse.py::test_one_by_two_binning_names_the_reference_in_its_warning`, `test_one_by_one_has_no_period_warning` | 1x2: `(3.0, 4.0)` and a warning naming "reference". 1x1: `None` and `()`. |
| 3 (CLI) | `test_cli.py::test_cli_bin_flag_reports_bin_factors_and_warning` | `--bin 2x1`: the JSON has `bin_factors == {"horizontal": 2, "vertical": 1}`, `unresolved_period_px == [3.0, 4.0]` and the warning. stderr is empty. |
| 4. bbox/mask in frame px, measurements in sensor px | `test_analyse.py::test_binned_region_bbox_and_mask_are_in_frame_pixels` | 2x1, one partial `StripedRegion`. `labels.shape == binned.shape`. The bbox lies inside the frame and matches the block-meaned truth mask (>= 0.5) **per axis**: row sides within `BBOX_TOL_PERIODS * p / v` frame px, column sides within `BBOX_TOL_PERIODS * p / h` (the protected tolerance converted per axis, not changed; ruling B1). `area_px == (labels == k).sum()`. `period_px` matches the sensor truth. |
| 4 (units) | `test_analyse.py::test_report_states_units` and the extended `test_report_converts_to_json` | `to_dict()["units"] == Report.UNITS`, which equals the 2.5 mapping literally. The new key order is pinned. |
| 4 (CLI, transpose) | `test_cli.py::test_cli_bin_with_transpose_keeps_bin_factors_in_sensor_axes` | A transposed file with `--transpose --bin 2x1`: the JSON `bin_factors` is 2x1, the bboxes are in file layout, `period_px` is about 12. |
| 5. 1x1 == no option | `test_analyse.py::test_one_by_one_binning_equals_no_option[kind]` | Kinds: clear stripes, two regions, spikes + clipped, Stripe-free mottled. Reports are `==`, `np.array_equal(labels)`, and `to_json()` is equal. `test_cli.py::test_cli_bin_one_by_one_equals_no_flag`: stdout byte-equal. Against BASE: the 2.4 diff, plus `make check-slow`'s calibration reproduction. |

Supporting tests, in the same files:
- `test_size_minimum_is_in_sensor_periods_under_binning[2x1|1x2, below|above]`: the size test's recipe and shapes at sensor size, then binned. Below (0.8x) is not reported; above (1.4x) is. This matches P1 M5's 84/84.
- `test_invalid_bin_factors_raise[0, -1, 1.5, True, "2"]`.
- `test_cli.py::test_cli_rejects_malformed_bin[2*1, 2x, x1, 0x1]`: exit 2.
- `test_bin_factors_leaving_no_searchable_period_raise`: `BinFactors(11, 1)` raises `ValueError`, and the CLI exits 1.
- Coverage note:
  - `test_binned_frame_notes_the_calibration_does_not_cover_it`: stored calibration, 2x1.
  - `test_frame_with_more_pixels_than_the_calibration_is_noted`: injected 64x64 calibration, 128x128 frame.
  - `test_frame_with_fewer_pixels_is_not_noted`.
  - `test_explicit_threshold_has_no_calibration_note`.
  - `test_calibration_with_matching_bin_factors_has_no_note`.
- `test_calibration.py`:
  - `test_one_by_one_calibration_settings_and_digest_are_unchanged`: no `bin_factors` key; the stored digest is still `PACKAGE_CALIBRATION_DIGEST`.
  - `test_binned_calibration_records_and_reads_bin_factors`: it also round-trips through `to_json` and `from_json`.
  - `test_malformed_bin_factors_setting_raises`.
- `test_report_in_file_layout_keeps_bin_factors_and_warnings`.

All new tests are small (256x256, 1-4 frames each). None gets a `wide` mark.

## 6. make measure?

**No.**
- CLAUDE.md runs `make measure` "at milestones where detector output is meant to move (stripe-detector 05, 07, 13)". The detector's code changes here, but its 1x1 output does not (2.4), and no measured set is binned.
- If `make check-slow` or the 2.4 diff shows any change at 1x1, stop. That is a bug in 2.4, not a trigger for a measure or a re-store.

## 7. Approvals and protected numbers

**Granted by the orchestrator.** Record each in the ticket's Comments with its reason when implementing.

- **Lockfile edits:**
  - Additions:
    - `denoisifier.report :: BinFactors.horizontal :: 1`
    - `denoisifier.report :: BinFactors.vertical :: 1`
    - `denoisifier.report :: Report.bin_factors`
    - `denoisifier._local_stripes :: MIN_ARRAY_PERIOD_PX :: 2.0`
    - `protected :: BINNING_TEST_SEEDS`
    - `protected :: BINNING_PROTOTYPE_SEEDS`
  - Changed line: `protected :: USED_SEEDS`, which gains `range(108_000, 108_400)`.
  - Reason: new numbers for a new option, plus reserving the seeds the prototype consumed. No existing value is loosened.
- **Expected-value extension:** the key list in `test_report_converts_to_json` gains `bin_factors`, `units`, `unresolved_period_px` and `warnings`. Exact-JSON CLI assertions, if any, are extended the same way. Reason: AC 4 requires the units in every report, and no check is removed.
- **Not touched:**
  - Tolerances: AC 4 converts `BBOX_TOL_PERIODS` per axis and does not change it.
  - `skip` / `xfail`, warning or lint suppression, `wide` marks, timeouts, gate config, the seed guard.
  - `slow_stamp.py`. No new `src/denoisifier/*.py` file is added; that is why `BinFactors` lives in `report.py` and the geometry in `_local_stripes.py`.
  - The stored calibration file and its digest.

## 8. Residual risks (accepted)

- Test frames are block-summed after the EMCCD chain, not binned on chip before the EM register. This is enough for geometry; no rate is claimed for binned frames, and the coverage note says so.
- The 2x1 Stripe-free tail is higher than at 1x1 (P1: 67-80 vs 31-49). It is not a Nyquist effect: it comes from 7.3-14.3 px winners and is partly the larger sensor area. It stays under the stored Threshold. It is noted, not fixed.
- P1 used 8 seeds per striped configuration, so a 1-in-20 miss rate would not show. The AC tests check geometry, not rates.

## File pointers

- Source:
  - `src/denoisifier/_local_stripes.py`: `_Spectrum`, the bank loop, `searched_periods`, `unresolved_period_range`, `gabor_at`.
  - `src/denoisifier/analysis.py`: `analyse`, `_Filters`, `_phase_steps`, `_passes_size_rule`, `_near`, `_interior_depth`, `_is_leakage`, `_refined`.
  - `src/denoisifier/report.py`, `src/denoisifier/calibration.py`, `src/denoisifier/cli.py`, `src/denoisifier/recalibrate.py`, `src/denoisifier/__init__.py`.
- Tests: `tests/test_analyse.py`, `tests/test_cli.py`, `tests/test_calibration.py`, new `tests/binning.py`, `tests/calibrate_regions.py`, `tests/protected.py`, `tests/protected_numbers.lock`.
- Docs: `GLOSSARY.md`, `docs/adr/0001-*.md`, `docs/adr/0002-*.md`.
