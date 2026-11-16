Plan: .scratch/stripe-detector/handoffs/08-plan.md @ uncommitted (BASE 0032d7f)

## Findings

- [ ] B1 break: AC 4 bbox tolerance (plan section 5, row "4. bbox/mask") is "`BBOX_TOL_PERIODS * period / 2` frame px" on every side. Under 2x1 only the columns are binned. Rows are 1 frame px per sensor px, so `/2` on the row sides halves the protected tolerance (tests/protected.py:167, "per side, in Periods") and can fail for no reason. It is also a tolerance change, which needs an approval. → per axis: row sides `BBOX_TOL_PERIODS * p / v`, column sides `BBOX_TOL_PERIODS * p / h`.
- [ ] B2 break: `tests/calibrate_regions.py:264` builds `analysis._Filters(_Spectrum(frame), light)`, and :33 imports `estimate_local_stripes`. Plan 2.3(c) adds `self.bins` to `_Filters` and a `bins` argument to `estimate_local_stripes(frame, light, bins)` (step 2). If either is required, that helper breaks (mypy/import) and step 2 is redone. → `_Filters` reads `spec.bins` (no new constructor argument), and `estimate_local_stripes`/`_phase_steps`/`_interior_depth` take `bins` with a `BinFactors()` default, or the plan lists the helper's edit.
- [ ] B3 break: the Report gains `bin_factors: BinFactors = BinFactors()`. That class-level default holds numbers, so `protected_lock.live_numbers` pins it as `denoisifier.report :: Report.bin_factors`. Section 7 lists only the `BinFactors` fields and `Calibration.bin_factors`. `Report.UNITS` must be un-annotated or a `ClassVar`; an annotated dict on a frozen dataclass becomes a field with a mutable default (ValueError at import). → add both to section 7 and 2.5, so the lockfile approval covers every entry in one request.
- [ ] P1 prototype: do bank filters between 2 and 3 frame px work? At 1x1 the shortest filter is 3 px: centre 0.333 cycles/px, window sigma 0.053, so 3 sigma reaches 0.49, inside Nyquist. Under 2x1 the first searched Period is 4.19 sensor px (checked: `_PERIODS[3]`). That is 2.10 frame px: centre 0.477, sigma 0.076 in frame frequency, so about half the Gaussian lies past the 0.5 edge of `fftfreq` (`_local_stripes.py:75-76, 93-98`). Under 1x2 the same holds for the 4.19 reference. A cut-off reference catches about half the noise energy, which inflates the ratio on stripe-free frames. Block summing also damps the binned axis (|cos(pi f)| per 2-bin), which lowers the reference's share of the Mottle. Separately, `_phase_steps` measures phase steps near pi there, and noise can wrap them, flipping fx. The plan's P1 does not reach this region: P1a only compares the rule with no rule, P1b uses Periods of 5 or more under 1x2 and only 12 under 2x1. → Extend P1:
  - (i) P1a gets a 1x1 baseline on the same seeds, with each frame's winning bank Period, binned vs 1x1.
  - (ii) P1b adds 2x1 at sensor Periods {4.2, 4.7, 5.3, 6} and 1x2 at {4.2, 4.7}, Angles {0, 10}.
  
  Result that changes the plan: binned stripe-free scores well above 1x1, or Period/Angle misses, at Periods with frame Period < 3. Then the rule must keep each window inside Nyquist (for example a minimum of 3 frame px), which departs from the ticket's "2 array pixels". That makes it an owner item.
- [ ] O1 owner: Q2. Should the reference filters count toward the searchable range? Under 1x2 the plan stops searching, and warns about, 3-4 px. Stripes at those Periods are about 2.9-3.8 frame px, so the ticket's literal rule ("falls below 2 array pixels", issue line 3) would search them. That changes an agreed requirement. Also, the planned warning text says "(under 2 frame pixels)", which is false for the stripes there: it is the reference that falls below. Options:
  - A: plan (a). It is conservative, gives no inflated ratios, and warns at 1x2 too. The warning text should say the 90-deg reference is what goes unresolved.
  - B: the literal rule (stripes only). It searches 3-4 px under 1x2 with a reference off the grid, and so risks False Alarms.
  
  Recommend A, subject to P1.
- [ ] O2 owner: Q5 / section 2.6. This adds a field to the Calibration file format and digest, a `recalibrate --bin` flag, and a new Report warning. Those are data-format and public-interface changes. There is also a defect in the shape clause: "larger than `calibration.shape` on either side" fires on default 1x1 runs for any frame over 400 rows. A 512x512 frame has 41% of the calibration's area, yet it would be flagged, and that contradicts `analyse`'s docstring ("larger light area", analysis.py:201-204). Options:
  - A: plan 2.6, with the shape clause changed to the frame's pixel count above `rows*cols` of the calibration.
  - B: a note on bin mismatch only (no shape clause), keeping `Calibration.bin_factors` and `recalibrate --bin`.
  - C: docstring only, no note.
  
  Recommend A.
- N1 note: raise the "nothing searchable" `ValueError` on `not searched_periods(bins)`, not `limit > 20`. Both agree today (10x1 gives exactly 20.0 and keeps `_PERIODS[-1] == 20.0`), but a single source cannot drift.
- N2 note: the 1x1-equals-BASE claim (2.4) is proven exactly on the slow tier only for stripe-free scores. The regression check counts passes and does not compare Period, Angle, bbox or depth. → before step 2, save BASE `to_json()` and `labels` for the four AC 5 kinds to scratch, and diff them after step 3.
- N3 note: name P1's seed block. It must be fresh, outside `CALIBRATION_SEEDS`/`USED_SEEDS`, and disjoint from `BINNING_TEST_SEEDS`.
- N4 note: the `test_report_converts_to_json` key-list extension (test_analyse.py:315-323) and the lockfile additions are approval moves for the orchestrator. Q4's always-emit schema is settled by AC 4 ("the report says which units each field uses"), so it is not an owner item.
- N5 note: the CLI writes `warnings` only into the JSON (cli.py:100-115). Consider echoing them to stderr, so that a `-o` user sees the sub-2-px and coverage warnings.
- N6 note: `calibration.py`, which is stamped, will call `BinFactors.to_dict`/validation in unstamped `report.py` for the digest of binned calibrations. The stored 1x1 digest is unaffected. The plan's reading (section 7: `report.py` stays unstamped) holds, and the precedent is `calibration.py` already importing the unstamped `frame_io.py`.

Claims verified: `_Spectrum`/`fftfreq` (`_local_stripes.py:68-90`); the bank (:23-24, `_PERIODS[-1] == 20.0`); the ratio box (:127); the size rule, `_near`, `_interior_depth` and `_phase_steps` sites (analysis.py:582-590, 566-579, 706-729, 489-509); `report.py` in `NOT_STAMPED_SRC` (slow_stamp.py:80-83); the pinned key order (test_analyse.py:315); the spectrum oracle band of 12 deg (protected.py:22); `generate`'s Angle convention, under which the 1x2 frame Angle is atan(2 tan t) = 19.4 deg; the 2x1/1x2 limit of exactly (3.0, 4.0).

## Closing check (plan as settled 2026-11-14)

- [x] B1: plan:243, the bbox check is per axis, rows `BBOX_TOL_PERIODS * p / v` and columns `... * p / h` ("ruling B1").
- [x] B2: plan:33, 74, 216, the `tests/calibrate_regions.py` lines 261/264 get `BinFactors()`, and that edit is listed in step 0/1.
- [x] B3: plan:138, 281 add the lockfile line `Report.bin_factors`; plan:156-157 make `Report.UNITS` a `ClassVar` with no lockfile line.
- [x] P1: plan:9, 82-87, 119, 199, the prototype ran. Without the reference rule, 1x2 Period 3 scores a median of 1216, against 22.8 with the rule. 2x1 at 4.2 px resolves 8/8, phase wrap is 0.7%, and the 2-frame-px minimum stands. The 1x2 Mottle rise of 1.88x is recorded in ADR 0001 (plan:193).
- [x] O1: plan:10, Q2 = A, ruled by the orchestrator. plan:144, the 1x2 warning now names the 90-deg reference ("the stripes do not").
- [x] O2: plan:175-187 settles it. Non-1x1 factors go in `settings`, so the file format, the digest and the stored calibration are unchanged and the item is no longer hard to revert. The coverage test is the pixel count (`rows * cols`), and plan:185 says a 512x512 frame gets no note.
- [x] N1: plan:89 raises on `not searched_periods(bins)`.
- [x] N2: plan:130-133 saves the BASE golden before step 2, then diffs after step 3 and at the end.
- [x] N3: plan:199, 206, the P1 seeds are 108_000-108_399, reserved in `USED_SEEDS`. plan:205 puts the test seeds in `TEST_SEED_BLOCK`.
- [x] N4: plan:226, 286, the approvals are recorded in Comments.
- [x] N5: plan:32, 58, nothing goes to stderr, because of the CLI rule that stderr carries one line, on errors only (`test_cli.py:43-45`). Settled.
- [x] N6: plan:43, the reasoning for leaving `report.py` unstamped is recorded.
- N7 note (new, not blocking): `calibrate(settings=...)` takes the caller's `settings`. Plan:177 writes `settings["bin_factors"]` into them. The plan does not say what happens when the caller's settings already carry a `bin_factors` key, at 1x1 or with factors that conflict. → refuse a caller-supplied `bin_factors` key with `ValueError`, or let the keyword win and document that.

Open: none blocking. N7 is a note.
