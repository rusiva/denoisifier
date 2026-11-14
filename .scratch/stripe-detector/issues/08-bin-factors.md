# 08: Bin factors

**What to build:** An experimenter who bins the sensor (possibly unequally) still gets correct detection and measurements. Bin factors (horizontal and vertical, default 1×1) are a library option and a CLI flag. All periods, angles, region-size minimums and positions in the report are in **sensor pixels**. The bin factors change the *detection* as well as the reporting: the search range (period 3–20 px, angle ±10° from vertical) and the 3×2-period region minimum are converted into binned-array coordinates before searching. Any part of the period range that falls below 2 array pixels after binning is reported as a warning.

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] With 1×2 binning, stripes at a physical 10° tilt (about 19.4° in the array) are detected and reported as about 10°.
- [ ] With 2×1 binning, a physical period of 12 px is reported as about 12 px (not 6).
- [ ] With 2×1 binning, the report warns that physical periods below 4 px can't be resolved.
- [ ] Region bounding boxes and the mask stay in frame (array) coordinates, while measurements are in sensor pixels; the report says which units each field uses.
- [ ] 1×1 binning gives the same results as no option.

## Comments

- 2026-11-14, from ticket 07 (plan Q9): the shipped calibration is at 400x1600 unbinned, and its rate claim does not cover binned frames or frames of a larger light area. Decide here whether a shape or binning mismatch with the calibration is noted in the Report.
- 2026-11-14, implementer (plan `.scratch/stripe-detector/handoffs/08-plan.md`, section 7). Approvals granted by the orchestrator in the settled plan, recorded with their reasons:
  - **Lockfile additions** (`tests/protected_numbers.lock`): `denoisifier.report :: BinFactors.horizontal :: 1`, `BinFactors.vertical :: 1`, `Report.bin_factors :: BinFactors(horizontal=1, vertical=1)`, `denoisifier._local_stripes :: MIN_ARRAY_PERIOD_PX :: 2.0`, `protected :: BINNING_TEST_SEEDS :: range(10, 14)`, `protected :: BINNING_PROTOTYPE_SEEDS :: range(108000, 108400)`. Reason: new numbers for a new option, and reserving the seeds prototype P1 consumed. No existing value is loosened.
  - **Lockfile change**: `protected :: USED_SEEDS` gains `range(108000, 108400)` (`BINNING_PROTOTYPE_SEEDS`). Reason: P1 looked at those seeds; reserving them keeps them out of later evaluations.
  - **Expected-value extension**: `test_analyse.py::test_report_converts_to_json`'s key list gains `bin_factors`, `units`, `unresolved_period_px` and `warnings` (and asserts their 1x1 values). Reason: AC 4 requires each field's unit in every report; no check is removed. No other exact-JSON assertion needed extending.
  - **Why `BinFactors` lives in `report.py`** (`NOT_STAMPED_SRC`): it is data plus validation only; every computation from it (frequency grid, searched Periods, size rule, merge gap, interior depth, phase steps) is in the stamped `_local_stripes.py` and `analysis.py`. The lockfile pins its defaults, and the slow tier runs only at 1x1. No new `src/denoisifier/*.py` file, so `slow_stamp.py` is untouched.
  - **Not touched**: tolerances (AC 4 converts `BBOX_TOL_PERIODS` per axis and does not change it), skip/xfail, warning or lint suppression, `wide` marks, timeouts, gate config, the seed guard, the stored calibration file and its digest.
- 2026-11-14, implementer: review note N7 applied. `calibrate(..., settings=...)` refuses `settings` that already hold `"bin_factors"` (ValueError; the recorded factors come only from `bin_factors=`), tested by `test_calibration.py::test_settings_with_bin_factors_are_refused`. `calibrate_folder` takes no `settings`, so it builds its own and cannot receive the key.
- 2026-11-14, implementer: the ticket-07 Comment (plan Q9) is decided as plan 2.6: yes, noted. When a Calibration set the Threshold, `Report.warnings` gets at most one coverage note: a bin-factor mismatch, else a frame with more pixels than the calibration's (so the 640x1024 two-region test frame now carries that note at the default). No note with `threshold=`, none for smaller frames; the note never changes the verdict or the Threshold.
- 2026-11-14, fixer (code review disposition F1-F9, `.scratch/stripe-detector/handoffs/08-orchestrator.md`). Approvals granted by the orchestrator, recorded with their reasons:
  - **Lockfile rename** (F1): `denoisifier._local_stripes :: MIN_ARRAY_PERIOD_PX :: 2.0` becomes `MIN_FRAME_PERIOD_PX :: 2.0`, value unchanged. Reason: GLOSSARY.md lists "array pixel" as the term to avoid ("Frame pixel"). With it, `Report.UNITS` reads "frame px" instead of "frame px (binned array)", and `test_report_states_units`'s expected strings follow the rename (no check removed or loosened).
  - **Additive protected numbers** (F2): `protected :: BINNED_FRAME_ANGLE_DEG :: 19.43` and `BINNED_FRAME_ANGLE_TOL_DEG :: 0.01`, moved unchanged from an inline `pytest.approx` in `test_one_by_two_binning_reports_the_physical_angle`. Reason: CLAUDE.md keeps test-side tolerances and expected values in `tests/protected.py`.
  - F6 note: the sensor/frame conversions are helpers in the stamped `_local_stripes.py` (`frame_px`, `sensor_frequency`, `pixel_size`), not `BinFactors` methods, so `BinFactors` in the unstamped `report.py` stays data and validation (the reason S3 was passed) and `tests/slow_stamp.py` is untouched. 1x1 output re-diffed against BASE 0032d7f (4 frame kinds, default and `threshold=inf`, with and without `BinFactors(1, 1)`): identical.
