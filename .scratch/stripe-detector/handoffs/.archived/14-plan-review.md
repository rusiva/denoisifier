Plan: .scratch/stripe-detector/handoffs/14-plan.md @ uncommitted (BASE 0f1aede)

## Verified

- Crop pins, read from the local source with `python3 -I`: lines 1359..1422 carry axis 1359..1422; source rows have 2162 raw fields ending `,`; values `[0,0]=984`, `[0,63]=735`, `[63,0]=856`, `[63,63]=754`, `[31,31]=2022` (unique in the crop), sum 4886612, range 713..2022. All match plan lines 130 and 199.
- Footer: source lines 2561..2590 = 2 blank lines, 27 metadata lines (2563 `Date and Time:` .. 2589 `Grating Groove Density (l/mm):0`), 1 blank line. No footer line starts with a number in either sample, so `_grid_span` (frame_io.py:107) finds the plan's grid spans.
- kinetic.asc: line 215 `Number in Kinetics Series:    10`, line 217 is the 7-field ROI line, CRLF. AC5's `match=r"line 215 says ..."` holds.
- Detector on the crop through `uv run --locked` `analyse`: not striped, score 5.49 (as read) and 5.18 (transposed), 0.06 s each. This matches plan line 131. The CLI tests compare reports, so they don't depend on these scores anyway.
- Stamp: `frame_io.py` and `cli.py` are in `NOT_STAMPED_SRC` (tests/slow_stamp.py:71-74). Test files and `tests/data/` are not in `STAMPED_FILES` (slow_stamp.py:43-69). So plan line 231 holds.
- `tests/data/solis/*` is not git-ignored (`git check-ignore` rc=1). Ruff only includes `*.py`/`*.pyi`/`pyproject.toml`, so the `.asc` and `.md` files are not linted. No `.gitattributes` exists today, and `core.autocrlf` is unset.
- The existing 04 boundary tests (tests/test_read_frame.py:147-160: `abc,8,9` next to `1,2,3`) stay raising under T3, since there is no trailing comma on either side and the value count is equal. `test_metadata_line_between_grid_rows_is_an_error` (:163) keeps the message `line 2 has 2 values`.
- `read_frame` is exported from `denoisifier` (src/denoisifier/__init__.py:4,7), so the tests import it through the public path.

## Findings

No breaks, prototypes or owner items.

- N1 note: The plan's glossary list is incomplete (plan lines 99, 225, 233). `tests/test_glossary_terms.py:24` scans for `CURATED = ("orientation", "amplitude", "wavelength", "false positive")`, plus plural forms (`_pattern`). The plan names only two of the four. Add "amplitude" and "false positive" to the prose to avoid in new docstrings and comments.
- N2 note: Q1 is a weakening move (an expected value changes: tests/test_read_frame.py:86-88 is replaced). CLAUDE.md requires the approval **before** the change, recorded with its reason in the ticket Comments. Order of work item 9 records only the S6 supersession at the end. Get the orchestrator's approval before slice 2 and record it there. The ticket itself mandates the new behaviour, so this approval is a formality.
- N3 note: Step 3 (plan line 48) says the series check runs "before any grid parsing, so a series always gets the series error". `_grid_span`'s boundary check (frame_io.py:112-114) runs first and can raise `_parse_row` errors. Under T3, Solis metadata never has the shape of a trailing-comma grid, so this cannot happen with real exports. Reword the claim to "before the grid rows are parsed".
- N4 note: Plan line 88 justifies `np.ascontiguousarray` with "the same memory layout as without the option". Without the option, the axis drop returns `grid[:, 1:]` (frame_io.py:139), which is not C-contiguous. The copy is harmless; drop the justification or make the drop path contiguous too. 4c asserting `c_contiguous` is fine.
- N5 note: T3 trade-off. With a trailing-comma grid, a corrupted boundary row that lost its trailing comma (e.g. `abc,8,9` next to `1,2,3,`) is now skipped as metadata instead of raising. This is acceptable for real exports. Say it in the `read_frame` docstring next to the boundary rule.
- N6 note: Slice 1 ends red by design (plan line 219), so it does not land green on its own. Treat slices 1+2 as one landing unit if slices are committed separately.
- N7 note: Q2 (an unreadable series length raises) goes past the ticket's literal rule ("greater than 1 fails"). It follows the ticket's "never read silently as one tall frame" and is easy to reverse. It is within the implementer's and orchestrator's call, not the owner's.

## Closing check (plan re-read, uncommitted, BASE 0f1aede)

- [x] N1 closed by plan line 131 ("write **none of the four**", CURATED quoted) and line 275.
- [x] N2 closed by plan line 258: slice 1 step 1 records the Q1 approval in the ticket Comments before any test changes.
- [x] N3 closed by plan line 52: "before the grid rows are parsed", and the plan says `_grid_span` could raise first.
- [x] N4 closed by plan line 114: no layout-equivalence claim.
- [x] N5 closed by plan lines 78-95: the rule now runs both a raw and a normalized width check, and trailing-comma state is no longer a prerequisite. I checked this against the existing tests: no metadata line in tests/test_read_frame.py or tests/test_cli.py ends with an empty field, so the normalized check fires only where the raw check already did and every 04 test is unchanged. The ROI line has 7 fields and 3 of them are numbers ({left / right / bottom / top}: 1 / 20 / 1071 / 1090), so it is skipped in both 3d ROI cases. The five 3d damaged-row cases are red after slice 1 as the plan says.
- [x] N6 closed by plan lines 255-262: the fixtures and the parser change land in one commit.
- [x] N7 closed by plan line 107 and line 286 (Q2 ruling).

The changes did not open any new break. I spot-checked the new tests and the claims behind them:
- the old kept-axis warning text is pinned by no test;
- the Q2 regex matches the message format;
- the 3-limit test's case is red today at `column 3: ''`;
- the 4-kept-axis frame and notes are right.

Still open: none.
