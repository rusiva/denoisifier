# 04 plan: frame reader handles Solis exports

Ticket: `.scratch/stripe-detector/issues/04-frame-reader-solis-exports.md`. BASE `0e56381`.
Spec: `.scratch/stripe-detector/spec.md` stories 30-32, "Frame reading" and "Report" modules, test seam 2.
Rulings: `.scratch/stripe-detector/handoffs/04-orchestrator.md`, section "Decisions" (folded below; see "Settled").

## Where things stand

- `src/denoisifier/frame_io.py`: `read_frame(path) -> FrameFile` is `np.loadtxt(..., delimiter=",", ndmin=2)`; `FrameFile(frame, notes: tuple[str, ...] = ())` already exists (ticket 01 made it for this ticket). `write_frame_csv` writes the plain grid.
- `src/denoisifier/cli.py`: `denoisifier FRAME [-o OUT]`; catches `OSError`/`ValueError` and prints one `denoisifier: error: ...` line, exit 1. It drops `frame_file.notes` today.
- `src/denoisifier/report.py`: frozen `Report`, `to_dict()` with six keys in fixed order, `to_json()` with `allow_nan=False`.
- Tests: `tests/test_read_frame.py` (4 tests, handwritten CSVs via `_write(tmp_path, text)`), `tests/test_cli.py` (subprocess runs via `_run`, `_assert_clean_failure`).

## Seams

### 1. `frame_io.read_frame`

```python
def read_frame(
    path: str | os.PathLike[str], *, drop_axis_column: bool = False
) -> FrameFile:
```

Replace `np.loadtxt` with a small line parser (stdlib + numpy only). Rules:

1. **Open** with `encoding="utf-8-sig", errors="replace"`. `-sig` strips a BOM (otherwise `float("﻿1.5")` fails and the first grid row would be read as metadata). `errors="replace"` keeps non-UTF-8 bytes in Solis metadata from crashing the read; a replaced character in a grid row, or in a row that rule 4 treats as a corrupted grid row, fails `float()` and becomes a positioned error.
2. **Split** each line on `","`; strip whitespace around each field. Blank (whitespace-only) lines are ignored everywhere and not counted (S3). A delimiter-only line (`","`) is not blank: its fields are empty strings and fail as numbers.
3. **Grid line** = a line whose first field parses with `float()` (S1). The grid is the contiguous block from the first grid line to the last grid line. The grid width `w` is the field count of the first grid line.
4. **Lines outside the grid** (before the first grid line, after the last one), checked one by one (S2, the boundary-row ruling):
   - if the line has exactly `w` fields and more than half of them parse with `float()` (`2 * numeric > w`, an inline expression, not a module constant), it is a corrupted grid row: raise the not-a-number error for its first non-numeric field (message below);
   - otherwise it is metadata: skipped, counted as "before" or "after".
   So `abc,8,9` above or below a 3-wide grid is an error, while `Gain:,300` next to a 2-wide grid (1 of 2 numeric) is metadata.
5. **Inside the grid** (first to last grid line inclusive) every line must have `w` fields, checked first, then every field must parse with `float()` (S9):
   - uneven: `ValueError(f"{path}: line {n} has {k} values, but the grid's first row (line {n0}) has {k0}")`
   - not a number: `ValueError(f"{path}: line {n}, column {c}: {field!r} is not a number")`
   A metadata-like line between grid lines (`Gain:,300` inside a 3-wide grid) is reported as uneven; a same-width text line is reported as not-a-number at column 1. A trailing comma on a row gives an empty last field: uneven if only some rows have it, otherwise not-a-number at the last column (S6: rejected by default, a terminal empty field may be a missing pixel).
   Line and column numbers are 1-based file positions (what an experimenter sees in an editor).
6. **No grid line at all** (including an empty or whitespace-only file): `ValueError(f"{path}: no rows of numbers found")`.
7. **Axis column** (S4). Two independent parts:
   - **Explicit drop** (`drop_axis_column=True`), on any grid size: if the grid has fewer than 2 columns, `ValueError(f"{path}: cannot drop the axis column: the grid has only one column")`; otherwise drop column 0 and add a dropped note.
   - **Heuristic** `looks_like_axis = np.all(np.diff(grid[:, 0]) > 0)` (strictly increasing), evaluated only when the grid has >= 2 rows and >= 2 columns (an empty diff would otherwise read as "counts up"):
     - not dropping and `looks_like_axis`: keep every column, add the kept-axis warning;
     - dropping and not `looks_like_axis`: add the "does not count up" warning after the dropped note (S5);
     - dropping with one row: the heuristic is not evaluated; the dropped note says the column's axis identity was not assessed, and no warning is added.
8. Return `FrameFile(frame=np.asarray(grid, dtype=np.float64), notes=tuple(notes))`. Notes order: before, after, axis (dropped note, then its warning if any).
9. **Numeric header row** (S7): not detected; a numeric first row (e.g. column indices) is kept as data, because the ticket says never guess.

No module-level numeric constants in `frame_io.py` (the protected-number lockfile pins every module- and class-level number in `src/denoisifier`; a new one needs a lockfile edit, a weakening move). String constants are fine.

### Note format (exact strings; tests match on the stable parts)

- `"skipped {n} metadata line(s) before the grid"` (singular/plural via `"line" if n == 1 else "lines"`)
- `"skipped {n} metadata line(s) after the grid"`
- `"dropped the first column as an axis column ({first:g} to {last:g}), as requested"` (>= 2 rows)
- `"dropped the first column as an axis column, as requested; with one row, whether it is an axis column was not assessed"` (1 row)
- `"warning: the first column counts up row by row ({first:g} to {last:g}), like a Solis axis column; it was kept as intensities. If it is an axis, read with drop_axis_column=True (CLI: --drop-axis-column)"`
- `"warning: the first column was dropped as requested, but it does not count up row by row, so it may not be an axis column"`

Warnings start with `"warning: "`; plain notes do not. Tests assert on the counts, `"before"`/`"after"`, `"dropped"`, `"not assessed"`, the `"warning: "` prefix and `"--drop-axis-column"`, not on the full sentence.

### Docstring content (`read_frame`, module, `FrameFile.notes`)

- The rules above, the note kinds and the errors.
- Number syntax is Python's `float()`: it also accepts `nan`, `inf` and `1_0` (= 10). The reader keeps non-finite values; `analyse` rejects them (S8, N3).
- `#` lines are no longer stripped as comments (behaviour change from `np.loadtxt`): outside the grid a `#` line is metadata (unless rule 4 makes it a corrupted row), inside the grid it is an error; inline `#` text in a numeric row is an error, not stripped (N4).
- Numeric header rows are kept as data (rule 9); trailing commas are rejected (rule 5).
- Module docstring: "plain comma-separated grid format" becomes "comma-separated grids, including Solis exports". `FrameFile.notes`: "always empty for plain grids" becomes "empty for a plain grid whose first column does not count up".

Docstrings and comments must not say "wavelength": `tests/test_glossary_terms.py` flags it (curated avoided term, GLOSSARY **Period**). Say "axis column" (pixel or spectral axis). Keep it out of string data too, for consistency.

### 2. `report.Report`

Add a last field `reader_notes: tuple[str, ...] | None = None` (spec: "`reader_notes` (when the frame came from a file)"). `analyse` leaves it `None` (no change to `analysis.py`). `to_dict()` appends `"reader_notes": list(self.reader_notes)` only when it is not `None` (S8), so `test_report_converts_to_json`'s exact key list stays true for a library `analyse` call. Widen the `to_dict` return annotation to `dict[str, bool | float | list[str] | None]`.

### 3. `cli.main`

```
parser.add_argument(
    "--drop-axis-column",
    action="store_true",
    help="drop the first column as a Solis axis column (pixel or spectral axis); never done without this flag",
)
```

Update the `frame` help to "frame as a comma-separated grid of numbers; metadata lines before and after the grid are skipped". Then:

```python
frame_file = read_frame(args.frame, drop_axis_column=args.drop_axis_column)
report = dataclasses.replace(analyse(frame_file.frame), reader_notes=frame_file.notes)
text = report.to_json() + "\n"
```

So the JSON from the CLI always has `reader_notes` (an empty list for a plain grid). Notes go only into the JSON, not to stderr (S8). No analysis logic in the CLI.

## Tests: one per acceptance criterion, on the real path

All reader tests: `tests/test_read_frame.py`, handwritten text (or bytes via `write_bytes`) through the existing `_write(tmp_path, text)` helper and the public `read_frame` (imported from `denoisifier`). CLI tests: `tests/test_cli.py`, subprocess via `_run`, so `reader_notes` is tested on its real path (file -> CLI -> JSON). No new seeds: CLI tests use the deterministic frame `F` (below).

| AC | Test | Input | Assertion |
|---|---|---|---|
| 1 plain grid keeps every column | keep `test_plain_grid_gives_2d_array_of_right_shape`; add `test_plain_grid_with_falling_first_column_has_no_notes` | `"1.5,2,3\n-4,5e2,6\n"`; `"9,1,1\n7,1,1\n8,1,1\n"` | shape `(2,3)` / `(3,3)`, exact values, `notes == ()` |
| 1b numeric header row kept | `test_numeric_header_row_is_kept_as_data` | `"1,2,3\n9,5,6\n8,7,8\n"` (column 0 not rising) | frame equals all 3 rows exactly; `notes == ()` |
| 2a axis kept by default, warned | `test_axis_column_is_kept_by_default_with_a_warning` | `"0,5,6\n1,7,8\n2,9,10\n"` | frame equals all 3 columns exactly; `len(notes) == 1`; `notes[0].startswith("warning: ")`, contains `"--drop-axis-column"` |
| 2b axis dropped on request | `test_axis_column_is_dropped_when_requested` | same text, `drop_axis_column=True` | frame `== [[5,6],[7,8],[9,10]]`; exactly one note, contains `"dropped"`, no note starts with `"warning: "` |
| 2c non-integer axis | `test_spectral_axis_column_is_dropped_when_requested` | `"532.1,5,6\n532.4,7,8\n532.8,9,10\n"`, `drop_axis_column=True` | frame `== [[5,6],[7,8],[9,10]]` |
| 2d drop on a non-axis column | `test_dropping_a_column_that_does_not_count_up_warns` | `"3,5,6\n1,7,8\n"`, `drop_axis_column=True` | frame `== [[5,6],[7,8]]`; notes are one `"dropped"` note then one `"warning: "` note |
| 2e drop on a one-column grid | `test_dropping_the_only_column_is_an_error` | `"1\n2\n"`, `drop_axis_column=True` | `pytest.raises(ValueError, match="only one column")` |
| 2f drop on a one-row grid | `test_dropping_on_a_one_row_grid_drops_without_assessing` | `"3,5,6\n"`, `drop_axis_column=True` | frame `== [[5,6]]`; exactly one note, contains `"dropped"` and `"not assessed"`, does not start with `"warning: "` |
| 3 regression: real rising column | rewrite `test_every_column_is_kept_even_when_first_counts_up` | rising side of a profile crop: `"10,12,15\n11,14,18\n13,17,22\n"` | frame equals the input exactly (all 3 columns); exactly one note and it starts with `"warning: "` |
| 4 metadata before and after | `test_metadata_lines_before_and_after_the_grid_are_skipped_and_counted` | header `"Andor Solis export\n"`, `"Exposure Time (secs):,0.1\n"`; grid `"6,5\n4,7\n"` (first column falls); footer `"Date and Time:,Mon Nov 10\n"`, `"Gain:,300\n"`, `"Software Version:,4.32\n"`; trailing blank line | frame `== [[6,5],[4,7]]`; notes `== ("skipped 2 metadata lines before the grid", "skipped 3 metadata lines after the grid")`. Covers the ruling's "`Gain:,300` after a 2-wide grid is skipped and counted" (1 of 2 fields numeric). |
| 4b Solis-shaped file | `test_solis_export_with_axis_and_metadata_loads_when_dropping` | header `"Andor Solis export\n"`, axis grid `"0,5,6\n1,7,8\n2,9,10\n"`, footer `"Gain:,300\n"`, `drop_axis_column=True` | frame `== [[5,6],[7,8],[9,10]]`; notes are before, after, dropped, in that order |
| 4c BOM | `test_byte_order_mark_does_not_hide_the_first_row` | bytes `b"\xef\xbb\xbf3,2\n1,4\n"` via `write_bytes` (first column falls) | frame `== [[3,2],[1,4]]`; `notes == ()` |
| 5 negatives | `test_negative_values_load_unchanged` | `"-1.5,-2e-3,0\n-4,-0,7\n"` (first column falls) | `np.array_equal` with the literal values; `notes == ()` |
| 5b non-finite kept by the reader | `test_float_syntax_includes_non_finite_values` | `"nan,1\n-inf,2\n"` | `np.isnan(frame[0,0])`, `frame[1,0] == -np.inf`, other values exact (pins the documented `float()` syntax; rejection is 7d) |
| 6a uneven rows | `test_uneven_rows_raise_naming_the_row` | `"1,2,3\n4,5\n6,7,8\n"` | `pytest.raises(ValueError, match=r"line 2 has 2 values")`, message also contains `"line 1"` and the path |
| 6b not a number | `test_non_number_in_grid_raises_naming_its_position` | `"1,2,3\n4,x,6\n7,8,9\n"` | `match=r"line 2, column 2: 'x' is not a number"` |
| 6c empty field | `test_empty_field_in_grid_raises_naming_its_position` | `"1,2,3\n4,,6\n"` | `match=r"line 2, column 2: '' is not a number"` |
| 6d bad last row is not metadata | `test_bad_value_in_last_row_is_an_error_not_metadata` | `"1,2,3\n4,5,6\n7,8,abc\n"` | `match=r"line 3, column 3"` |
| 6e no grid | `test_file_with_no_numbers_is_an_error`, parametrized | `"Andor Solis export\nGain:,300\n"`, `""`, `"\n  \n\t\n"` | `match="no rows of numbers"` |
| 6f corrupted boundary rows | `test_corrupted_first_or_last_row_is_an_error_not_metadata`, parametrized | `"abc,8,9\n1,2,3\n4,5,6\n"` (line 1); `"1,2,3\n4,5,6\nabc,8,9\n"` (line 3); bytes `b"\xff,8,9\n1,2,3\n4,5,6\n"` via `write_bytes` (line 1, replaced character) | `pytest.raises(ValueError, match=r"line {n}, column 1: .* is not a number")` |
| 6g metadata line inside the grid | `test_metadata_line_between_grid_rows_is_an_error` | `"1,2,3\nGain:,300\n4,5,6\n"` | `match=r"line 2 has 2 values"` (field count is checked first) |
| 6h trailing comma | `test_trailing_comma_is_rejected` | `"1,2,\n3,4,\n"` | `match=r"line 1, column 3: '' is not a number"` |
| 7a CLI flag + notes | `test_cli_drops_axis_column_on_request_and_reports_reader_notes` (test_cli.py) | frame `F` written two ways: plain via `write_frame_csv`, and Solis-shaped (header line `"Andor Solis export"`, `np.column_stack([np.arange(64), F])` via `write_frame_csv` to a temp file read back as text, footer line `"Gain:,300"`) | run CLI on both with `-o`; Solis run with `--drop-axis-column`; both exit 0; plain `report["reader_notes"] == []`; Solis `reader_notes` has 3 entries (before, after, dropped); the two reports are equal after removing `reader_notes` |
| 7b CLI warns without the flag | `test_cli_keeps_axis_column_by_default_and_warns_in_the_report` | the Solis-shaped file, no flag | exit 0; one `reader_notes` entry starts with `"warning: "` and contains `"--drop-axis-column"` |
| 7c CLI error path | `test_cli_fails_cleanly_on_uneven_rows` | `"1,2,3\n4,5\n"` | `_assert_clean_failure(result, "line 2")` |
| 7d CLI rejects non-finite | `test_cli_fails_cleanly_on_non_finite_values` | `F` with `F[10, 10] = np.nan`, via `write_frame_csv` | `_assert_clean_failure(result, "non-finite")` |

The library `analyse` dict is unchanged (S8); the existing `test_report_converts_to_json` key-order test guards that and must stay green unchanged.

Deterministic CLI frame `F`: `y, x = np.mgrid[0:64, 0:64]; F = 1 + 100 * np.exp(-((x - 32) ** 2 + (y - 32) ** 2) / (2 * 15 ** 2))`. It is >= `MIN_SIDE` (40), has positive light, and needs no seed. Its column 0 rises then falls, so the plain run has no notes. Whether it is Striped does not matter; the test compares the two reports to each other. Numbers in `tests/test_cli.py` are not protected numbers.

## Order of work (tdd red-green slices; each starts with a failing test)

1. **Parser rewrite, errors first.** Red: 6a, 6b, 6c, 6h (`np.loadtxt` messages do not match). Green: line parser with rules 1, 2, 5, 6 (every non-blank line is a grid line for now). Add 4c, 5, 5b alongside; existing tests stay green.
2. **Metadata and boundary rows.** Red: 4, 6d, 6e, 6f, 6g. Green: rule 3 (first-field grid line), rule 4 (corrupted-row check, before/after counting), rule 6 for empty input.
3. **Axis warning.** Red: rewritten 3 and 2a (no warning yet). Green: the heuristic part of rule 7. Add 1 (falling column, no notes) and 1b alongside.
4. **Drop on request.** Red: 2b, 2c, 2d, 2e, 2f, 4b (no keyword yet). Green: the explicit-drop part of rule 7 and the one-row note.
5. **Report field and CLI.** Red: 7a, 7b (no flag, no `reader_notes`). Green: `Report.reader_notes` and `to_dict` (S8), then the flag and `dataclasses.replace` in `cli.py`. Add 7c, 7d alongside (characterization of the error path).
6. **Docstrings** per "Docstring content". No "wavelength".
7. `make test-fast` after each slice; `make check` at the end.
8. Ticket: tick the boxes, append to `## Comments` (gate quote per CLAUDE.md, plus the known gap below), set `Status:` per orchestrator.

## Gate implications

- **Stamp:** `frame_io.py`, `cli.py`, `report.py` are in `NOT_STAMPED_SRC`; `tests/test_read_frame.py`, `tests/test_cli.py` are not stamped. The plan touches no stamped file, so `make check` stays green without `make check-slow`, provided the implementer does **not** touch `src/denoisifier/__init__.py` (stamped; `read_frame` and `FrameFile` are already exported), `analysis.py`, `tests/protected.py` or `tests/conftest.py`. Any of those edits means a background `make check-slow` (about 6 min).
- **Protected-number lockfile:** no new module- or class-level numbers in `src/denoisifier` (the `Report` field default is `None`; the "more than half" test is an inline expression). No new seeds in `tests/protected.py`. So no lockfile edit, no approval needed.
- **Glossary:** no new domain terms (S8). The glossary test forbids "wavelength" in docstrings/comments.
- **Weakening moves:** none planned. Rewriting `test_every_column_is_kept_even_when_first_counts_up` strengthens it (warning assertion, realistic input); it changes no protected number.
- **Lint/types:** mypy strictness applies; the `to_dict` annotation widens.
- **Speed:** a Python parser on a 1600x401 grid takes about 0.11 s (review N6), well inside spec story 39.

## Settled

All rulings are in `.scratch/stripe-detector/handoffs/04-orchestrator.md`, "## Decisions".

- **S1 grid line** = first field parses as a number (planner O1, superseded in part by S2). Rule 3.
- **S2 corrupted boundary rows** (Codex high finding): a line outside the grid with the grid's width and more than half its fields numeric is an error, not metadata. Rule 4; tests 4, 6f.
- **S3 blank lines** ignored, not counted; delimiter-only rows still fail (planner O3). Rule 2; test 6e.
- **S4 explicit drop independent of the heuristic** (review B1, planner O4, Codex medium): fewer than 2 columns is an error, else drop; the >= 2 rows/cols guard applies only to `looks_like_axis`; a one-row drop says axis identity was not assessed. Rule 7; tests 2e, 2f.
- **S5 drop on a column that does not count up** = drop and warn (planner O2). Rule 7; test 2d.
- **S6 trailing comma** rejected by default with a clear error. Rule 5; test 6h.
- **S7 numeric header row** not detected; kept as data. Rule 9; test 1b.
- **S8 agreed as proposed:** `reader_notes` omitted from `to_dict` when `None` (O5); notes in the JSON only, not stderr (O6); no glossary entries (O7).
- **S9 review notes:** N1 field count checked first, test 6g; N2 slice 5 starts with 7a/7b before the Report change; N3 `float()` syntax documented, tests 5b and 7d; N4 `#` handling change documented; N5 empty and whitespace-only inputs in 6e; N6 speed fine. Codex medium (BOM fixture contradicted the axis warning): 4c now uses a falling first column and asserts exact values.

### Known gap: real Solis export layout

Review O1 / planner O8, escalated to the owner (external knowledge). No real Andor Solis export is in the repo, so the layout this plan assumes (comma-delimited rows, text-keyed metadata lines, axis in column 0, no trailing comma, no numeric header row) is unverified. The conservative parser ships either way: an unexpected delimiter or trailing comma fails with a positioned error, and a numeric header row is kept as data (S7), which is the one case that still reads without an error. The handoff must not claim real-Solis compatibility is proven; it states this gap. A real-file fixture (and any trailing-comma or header-row rule it shows is needed, under an explicit format) may follow in a later ticket.
