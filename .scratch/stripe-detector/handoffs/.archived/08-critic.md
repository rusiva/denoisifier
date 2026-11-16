# 08 critic: adversarial verdict on the plan's Q1-Q7 and the review's items

Read at BASE `0032d7f`, plan and review uncommitted. Read-only pass: nothing was run, so every number below is arithmetic from the cited lines, not a measurement.

**Human decisions needed: none now.** One becomes an owner item only if prototype P1 shows a result that contradicts AC 3's "4 px" (see Q2 / P1).

## Summary

| Item | Verdict | Human? |
|---|---|---|
| Q1 option shape | Agree: `BinFactors` dataclass | no |
| Q2 references count | Agree (a); (b) is broken by arithmetic, no prototype needed for that | no (yes, criterion c, only if P1 forces a limit other than 4 px) |
| Q3 plain-px constants | Agree: keep in frame px | no |
| Q4 always emit | Agree; `units` is incomplete and `unresolved_period_px` is missing from `to_dict` | no |
| Q5 calibration note | Agree a note is needed; change the mechanism: record in `settings`, not a new file field | no |
| Q6 `--bin HxV` | Agree; the plan's stated reason is wrong, the ticket's own notation is the right one | no |
| Q7 `ValueError` | Agree | no |
| B1 | Correct | no |
| B2 | Finding correct, proposed fix wrong: make `bins` required, edit the helper | no |
| B3 | Correct, and incomplete (see M1) | no |
| P1 | Correct, and still too narrow (see M3, M5) | no |
| O1 | Not an owner item | no |
| O2 | Not an owner item; shape clause by pixel count is right | no |
| N1-N4, N6 | Agree | no |
| N5 | Disagree: keep warnings JSON-only | no |

## Open questions

### Q1. Library option shape: agree with (a)
- `Calibration.shape` is `(rows, cols)` (`calibration.py:63`). A bare `(h, v)` tuple would be the opposite axis order beside it, and a swap is silent: it gives a wrong Period and Angle, not an error.
- spec.md:105 names the option "horizontal and vertical bin factors", which is the dataclass's field names.
- Public API, but not a human item: the alternatives are not equivalent, the tuple is worse.
- Placement in unstamped `report.py`: acceptable. `test_stamped_files_cover_the_slow_tier` (`test_slow_stamp.py:249-262`) checks only classification and the slow tier's `tests/` imports, and the lockfile pins the two defaults. The letter of `slow_stamp.py:79` ("do not affect detector output") is stretched, since `analyse(bin_factors=None)` takes its defaults from there. Record that reasoning in Comments. The slow tier is all 1x1, so stamping it would not catch a binned-path change anyway.

### Q2. References count: agree with (a); (b) is not viable
- Under the plan's grid (`fy = fftfreq(rows) / v`), the grid spans +-0.5/v cycles per sensor px. Under 1x2 a reference at Period 3 sits at 0.333, outside +-0.25. Its Gaussian (`_local_stripes.py:93-98`) is then near zero everywhere on the grid.
- So `e_reference` collapses and `denom` falls to the floor (`_local_stripes.py:128-129`). The ratio becomes about `(depth / _A0)^2`: noise at an apparent depth of 0.05 gives about 280, against a stored 1% Threshold of 100.8 (`protected.py:238`). That is a False Alarm on most binned frames. No prototype is needed to reject (b).
- (c) contradicts ADR 0001: the reference is "the same bank rotated 90 deg" because Mottle is isotropic in sensor coordinates.
- Not an owner item (against O1). spec.md:114 says what must be warned at the least. Warning about more, with accurate text, still meets "not silently skipped", and AC 1-3 are unaffected (AC 3 is 2x1, limit 4 px either way).
- The warning text must not say "under 2 frame pixels" for 1x2: there the stripes are 3-4 frame px and it is the reference that is unresolved (O1 is right on this).
- Becomes an owner item (criterion c, changes an agreed AC number) only if P1 shows the limit must be other than 4 px under 2x1.

### Q3. Plain-px constants: agree with (a)
- `_PAD` and `MIN_SIDE` guard FFT padding of the array (`analysis.py:81-86`). `_PEAK_FOOTPRINT_PX` is a `maximum_filter` size on the array (`analysis.py:413`). `_data_quality` works on readout pixels.
- `_light` only keeps the dark surround out (`analysis.py:293-300`).
- One conflict to record, not to escalate: spec.md:114 says "positions in the report are in sensor pixels", while AC 4 keeps bboxes in frame px. AC 4 is right: `BoundingBox` is defined as slices into `labels` (`report.py:14`).

### Q4. Always emit: agree, with two defects
- AC 4 settles it (N4 is right).
- `unresolved_period_px` is a new `Report` field but is absent from the plan's `to_dict` order (plan 2.5). A JSON reader then gets the limit only as warning text. Emit it, and add it to `units`.
- `units` omits fields that have units: `spike_pixels` and `clipped_pixels` are counts of frame px, and `modulation_depth` is of the binned frame (see M4). AC 4 says "each field".
- Do not implement the warnings with `warnings.warn`: `filterwarnings = ["error"]` (`pyproject.toml:58`) would turn each into a test error, and suppressing it is a weakening move.

### Q5. Calibration mismatch: agree on the note, change the mechanism
- (b) and (c) are wrong for the reasons the plan gives. Without `stripe_free_score(bin_factors=...)` a user with binned frames cannot make a covered calibration at all, which ADR 0002's "Recalibration" consequence promises.
- The plan's mechanism is not the existing idiom. It adds a top-level field to a format that ADR 0002 calls "hard to reverse once users hold calibration files of this format", and makes `digest()` and `to_json` conditional on the value.
- The existing idiom is `settings`: "settings record how the set was made and are compared" (`calibration.py:55-58`), and `calibrate_folder` already records the read options that change the scores there (`transpose`, `clip_level`, `calibration.py:276-285`). `settings` is already in the digest and in equality.
- Answer: record `settings["bin_factors"] = {"horizontal": h, "vertical": v}` only when not 1x1, and expose a read-only `Calibration.bin_factors` property that parses it (absent means 1x1, malformed raises `ValueError`). No format change, no digest code change, no new dataclass field, no `Calibration.bin_factors` lockfile line. The stored file and `PACKAGE_CALIBRATION_DIGEST` are untouched.
- "Only when not 1x1" is also forced by `test_calibration.py:167`, which pins `calibrate_folder`'s settings exactly.
- With that, no persisted schema changes, so criterion (c) does not apply. Add one consequence line to ADR 0002 either way; the plan's "ADR: none needed" is wrong for this.
- Shape clause: O2's fix is right. "Larger on either side" contradicts `analysis.py:201-204` ("larger light area"). Use `rows * cols` above the calibration's.

### Q6. CLI syntax: agree with (a), for a different reason
- The plan's reason, "one token avoids order mistakes", is false: `1x2` is exactly the token whose order can be read two ways.
- The right reason: the ticket and the spec already write "1x2" as horizontal x vertical (issue line 9: 1x2 turns 10 deg into 19.4 deg, so the 2 is vertical). The flag matches the project's own notation, and the help text states the order.
- `frame_io.py` parses no binning from the Solis header, so there is nothing to cross-check against.
- CLI syntax is easy to extend later (named flags can be added beside it), so not criterion (c).

### Q7. Nothing searchable: agree with (a)
- Same as the existing refusals: `ValueError` for a frame under `MIN_SIDE` (`analysis.py:229-233`), which the CLI turns into exit 1 (`cli.py:117-119`).
- N1 is right: raise on `not searched_periods(bins)`.

## Review items

### B1: correct
- `test_analyse.py:466` uses `BBOX_TOL_PERIODS * period` on all four sides at 1x1. In frame px that is `/ v` on row sides and `/ h` on column sides. The plan's `/ 2` everywhere halves the row tolerance under 2x1.

### B2: finding correct, fix wrong
- The break is real (`tests/calibrate_regions.py:261, 264`). It is a runtime `TypeError`, not a mypy failure: mypy covers the package only (`pyproject.toml:68`).
- Defaults on internal functions are the wrong fix. There are six internal call sites (`analysis.py:247, 351, 439, 536, 656, 670`). A forgotten `bins` at `_is_leakage`'s `_Spectrum(without)` (`analysis.py:656`) would silently analyse the rest at 1x1 under binning, and no planned test covers leakage under binning.
- Answer: `bins` is a required argument of `_Spectrum`, `estimate_local_stripes`, `_phase_steps` and `_interior_depth`; `_Filters` reads `spec.bins`; the plan lists the two-line edit of `tests/calibrate_regions.py` (not a protected file, not stamped). Only the public `analyse`, `stripe_free_score` and `calibrate*` get a default.

### B3: correct, incomplete
- `Report.bin_factors` is pinned by `live_numbers` (`protected_lock.py:139-146`): confirmed. `UNITS` must be a `ClassVar`: confirmed.
- See M1 for the entry both missed.

### P1: correct
- The arithmetic holds: at 4.19 sensor px under 2x1 the filter centre is 0.477 cycles per frame px with sigma 0.076, so about 38% of the window is past Nyquist.
- The two sides differ, which the review does not say. Under 2x1 the cut window is the *stripe* filter's: lower sensitivity and wrapped phase steps, not False Alarms. Under 1x2 it is the *reference's*: inflated ratios. A single minimum may be wrong for both. See M3 for the larger effect.

### O1, O2: neither is an owner item
- O1: see Q2. O2: see Q5.

### Notes
- N2: agree, and it matters. `make check-slow` proves exact equality only for Stripe-free scores; the regression check counts passes. The scratch diff of `to_json()` and `labels` against BASE is the only proof for striped frames. Quote it in the handoff.
- N3: agree. A scratch script has no seed guard installed (the installs are `conftest.py`, `feasibility.main()`, `bench.main()`).
- N5: disagree. `reader_notes` are JSON-only (`cli.py:106`), and the CLI tests require stderr to carry exactly one line, on errors only (`test_cli.py:43-45`). Keep warnings in the JSON.
- N6: agree (see Q1).

## Missed by both the plan and the review

### M1. `BINNING_TEST_SEEDS` as planned fails a test, and the lockfile change is not additive
- Every name ending `_TEST_SEEDS` must lie inside `TEST_SEED_BLOCK = range(10, 100)` (`test_feasibility_gate.py:76-87`, `protected.py:103`). A "fresh block added to `USED_SEEDS`" (plan step 0) outside 10-99 fails `test_seed_sets_are_disjoint_and_unused`.
- Fix: pick the binning test seeds inside 10-99 (test seeds may share). They need no `USED_SEEDS` entry: the block is already there.
- The P1 prototype range does go into `USED_SEEDS` (ticket 07's precedent, `protected.py:318-319`). That **changes the existing lockfile line** `protected :: USED_SEEDS` (`protected_numbers.lock:210`). Plan section 7's "additive only, no existing value changes" is false. The approval request must name this line.

### M2. AC 3's test contradicts section 2.6
- The AC 3 test asserts "exactly one warning". With the default calibration at 2x1, section 2.6 adds a second one ("the calibration was made at 1x1 binning").
- Fix: assert on `unresolved_period_px` and on the presence of the sub-2-px warning; assert "exactly one" only with `threshold=` given.

### M3. Binning makes the Mottle directional in the array, which is ADR 0001's stated revisit condition
- Summing h pixels multiplies a component at f cycles per sensor px along that axis by `|sin(pi h f) / (h sin(pi f))|`. Under 1x2 that damps the reference (wavevector along the binned axis) and not the stripe filter.
- For a 2-bin the energy factor is `cos^2(pi / P)`: 0.53 at 4.19 px, 0.75 at 6, 0.85 at 8, 0.93 at 12, 0.975 at 20. So the Mottle part of the ratio is inflated at every Period under 1x2, by up to about 1.9x at the short end, on top of the Nyquist cut. Under 2x1 it is deflated by the same factors.
- White noise stays balanced: both filters keep the same area on the frequency grid.
- ADR 0001 says "If the real mottle turns out to be directional, this decision needs revisiting". Plan 2.7's "ADR: none needed" does not hold.
- No AC breaks, because no rate is claimed for binned frames and the coverage note says so. But P1a must report binned vs 1x1 Stripe-free scores **per winning Period** (the review's P1 (i) asks for this; make it a pass condition, not just a table).
- If the inflation is large, the principled fix is to scale the reference energy by the known ratio of the two bin factors at each filter centre, which restores ADR 0001's premise in sensor coordinates. That is a binned-only change (the factor is exactly 1 at 1x1). Decide from P1's numbers; record the outcome in ADR 0001's consequences or a new ADR.

### M4. Modulation Depth under binning is unaddressed
- The same factor lowers the measured depth of real stripes when the binned axis is across them: under 2x1, x0.97 at 12 px, x0.87 at 6 px, x0.73 at 4.2 px.
- No AC breaks: `assert_matches_truth` checks Period and Angle only (`truth_match.py:7-9`) and `DEPTH_TOL` is 0.1. But the ticket promises "correct detection and measurements", and a `depth` assertion added to an AC 2 test at a short Period would fail.
- Answer: report the depth of the frame as given (as at 1x1), and say so in `units` and in `analyse`'s docstring with the factor. Do not correct it in this ticket: a correction amplifies noise at short Periods and would need its own validation.

### M5. The size rule's margins are untested under binning before the tests are written
- `MIN_HALF_DEPTH_WIDTH_PERIODS = 3.24` and `..._HEIGHT_... = 1.93` were fitted at 1x1 with sub-pixel half-peak spans (`analysis.py:103-115`). Under 2x1 a frame px is 2 sensor px, so the interpolation is twice as coarse, and M4's damping lowers the depth map the span is measured on.
- The planned test uses the existing 0.8 / 1.4 factors (`protected.py:171-172`). If it misses, the only compliant moves are a code fix or a stop; add this case to P1b so it is found before step 3, not after.

### M6. `make measure`: the plan's "no" is right, but say why against CLAUDE.md's wording
- CLAUDE.md's closing sequence says `make measure` "only when the detector changed since the last measure". The detector's code changes here; its 1x1 output does not. The governing sentence is the write-target rule: `make measure` runs "at milestones where detector output is meant to move (stripe-detector 05, 07, 13)".
- The handoff must carry the evidence that output did not move: the green calibration reproduction (300 exact scores) and N2's diff for striped frames. Without N2's diff the claim is unproven for striped frames.
