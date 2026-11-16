# 14 plan: frame reader loads real Solis exports

Ticket: `.scratch/stripe-detector/issues/14-real-solis-export-fixture.md`. BASE `0f1aede`.
Builds on ticket 04 (settled plan: `.scratch/stripe-detector/handoffs/.archived/04-plan.md`, rulings S1-S9). This ticket **supersedes 04's S6** (trailing comma rejected) for the one shape the ticket allows, and **extends 04's S2** (corrupted boundary rows) with a second, normalized-width check; every other 04 rule stands.

Status: **settled.** Rulings are in `.scratch/stripe-detector/handoffs/14-orchestrator.md`, section "Decisions" (Codex adversarial review plus the orchestrator's reading); each is linked under "Settled" at the end.

## Where things stand

- `src/denoisifier/frame_io.py`: `read_frame(path, *, drop_axis_column=False) -> FrameFile`. Lines are `(n, fields)` pairs (blank lines dropped); `_grid_span` finds the grid (first..last line whose first field is a number) and raises on a corrupted boundary row (grid's raw width and more than half numbers); grid rows are checked for width, then parsed by `_parse_row`; axis drop/warning last. Notes order today: before, after, axis.
- `src/denoisifier/cli.py`: `denoisifier FRAME [-o OUT] [--drop-axis-column]`; `reader_notes` go into the JSON via `dataclasses.replace`.
- `src/denoisifier/report.py`: no change needed.
- Tests: `tests/test_read_frame.py` (handwritten text via `_write`), `tests/test_cli.py` (subprocess via `_run`, `_assert_clean_failure`).

## What the real samples show (verified, read as text with `python -I`)

Source: WrightTools, `WrightTools/datasets/Solis/` (repo master at planning time `e1728bc`; last commit touching that folder `1104177`, 2021-10-25). Solis 4.28.30050.0, model DC-152Q-C00-FI.

| | `xpos ypos fluorescence.asc.gz` (local `solis-samples/1/xpos_ypos.asc`) | `kinetic.asc.gz` (local `solis-samples/2/kinetic.asc`) |
|---|---|---|
| sha256 (uncompressed) | `bbe84637d35c001db2c2cfac98ea6dd77902d10bf4a4c3868a58d4c315182877` | `da9e203527142e4124ee34167af03dc5dd250f6ef729954b8a654b4f983f9037` |
| bytes, endings | 20 574 498, LF only, no BOM | 16 197, CRLF (236), no BOM |
| grid | lines 1-2560, 2162 fields each (axis + 2160 values + empty), axis 1..2560 | lines 1-200, 22 fields each (axis + 20 values + empty), axis 1..20 restarting 9 times |
| after grid | 2 blank lines, 27 metadata lines (2563-2589), 1 final blank line | 2 blank, 33 metadata lines (203-235), 1 final blank |
| values | integers 92..2022; light in file rows ~800-1800 | integers 97..102 (dark) |
| metadata with commas | none | line 217 `{left,right,bottom,top}:      1,20,1071,1090`: **7 fields, 3 numeric** (`20`, `1071`, `1090`; the field `top}:      1` is not a number), no trailing empty field |
| series key | absent (`Acquisition Mode: Real Time`) | line 215 `Number in Kinetics Series:    10` |

Both footers contain `Wavelength (nm):              0`; trailing spaces occur on `Serial Number:                `. Metadata values are separated from keys by spaces, not commas, so each metadata line is one field except the ROI line.

The ROI line can never trip today's boundary check: 3 numeric fields out of 7 is not more than half of any width it could match (7 raw, or 6 or 7 values). So the boundary rule is not changed for the ROI line's sake; it is extended so a trailing comma cannot hide a damaged boundary row (rule T3).

## Seams

### 1. `frame_io.read_frame`

```python
def read_frame(
    path: str | os.PathLike[str],
    *,
    drop_axis_column: bool = False,
    transpose: bool = False,
) -> FrameFile:
```

`FrameFile` is unchanged. No new module- or class-level numbers (protected-number lockfile); the literals `1` in the series check and the existing inline expressions stay inline. One new module-level **string** constant is fine: `_SERIES_KEY = "Number in Kinetics Series"`.

Order of steps inside `read_frame` (new or changed steps in bold):

1. Read lines as today (`utf-8-sig`, `errors="replace"`, universal newlines, so CRLF needs nothing new; blank lines dropped).
2. **`_grid_span`** (changed, rule T3): finds the grid and raises on a corrupted boundary row.
3. **Series check** on the metadata lines (rule K), before the grid rows are parsed. (`_grid_span`'s boundary check runs first and could in principle raise its own error on a series file; real Solis metadata never looks like a grid row, so in practice a Solis series gets the series error.)
4. **Trailing-comma shape** (rules T1, T2), then the existing width check (counting values), then `_parse_row`.
5. Axis drop / warning (warning text changed, see "Kept-axis warning").
6. **Transpose** (rule X).

#### Rule T: trailing comma

A row "has a trailing comma" when it has at least 2 fields and its last field is `""` (after stripping). Helper:

```python
def _values(fields: list[str]) -> tuple[list[str], bool]:
    """The fields without a trailing empty one, and whether there was one."""
```

- **T1 grid shape.** The grid has a trailing comma iff its first grid line has one. The grid's width is the first line's value count (fields minus the trailing empty one).
- **T2 every grid row must match the first**, checked before the width check:
  - first row has one, row `n` does not: `ValueError(f"{path}: line {n} does not end with a trailing comma, but the grid's first row (line {n0}) does")`
  - first row has none, row `n` has one: `ValueError(f"{path}: line {n} ends with a trailing comma (an empty last field), but the grid's first row (line {n0}) does not")`
  - then the existing width check and message, counting values (so the trailing empty field never counts as a value);
  - then `_parse_row` on the values, so an empty **interior** field still raises `line {n}, column {c}: '' is not a number` (column is the 1-based file column; unchanged numbering because only the last field is removed).
  A row `1,2,,` (interior empty then trailing) is shape-consistent with a trailing grid and fails at `column 3: ''`.
- **Note** when the grid has trailing commas: `"every grid row ends with a trailing comma; the empty last field was ignored"`. No warning prefix (it is the documented Solis layout).
- **Known limit (Q1 ruling), documented in the `read_frame` docstring and pinned by tests:** a missing last value on only *some* rows is still caught (it shows up as an uneven trailing comma or an uneven width). A missing last value on *every* row, or in a one-row file, cannot be told apart from a trailing delimiter, and reads as a grid one column narrower.

#### Rule T3: corrupted boundary rows (extends 04 S2)

`_grid_span` keeps today's raw-width check and adds a normalized-width check. With `first = lines[start][1]` and `grid_values, _ = _values(first)`, a line outside the grid (`fields`, with `values, _ = _values(fields)`) is a corrupted grid row when **either**:

- **raw:** `len(fields) == len(first)` and `2 * sum(map(_is_number, fields)) > len(first)` (today's rule, unchanged); or
- **normalized:** `len(values) == len(grid_values)` and `2 * sum(map(_is_number, values)) > len(grid_values)` (at most one terminal empty field stripped from each side).

On a match, `_parse_row(path, line_number, fields)` raises the positioned error. A line outside the grid has a non-number first field by definition, so the error is always `line {n}, column 1: ... is not a number`. Trailing-comma state is **not** a prerequisite: a damaged first or last row is caught whether or not it kept its trailing comma. No line is ever dropped silently because of a trailing comma.

Worked cases (all checked against the rule above):

| grid | boundary line | raw | normalized | result |
|---|---|---|---|---|
| `1,2,3` | `abc,8,9` | 3=3, 2 of 3 | 3=3, 2 of 3 | raises (04 test, unchanged) |
| `1,2,3,` | `abc,8,9,` | 4=4, 2 of 4 (no) | 3=3, 2 of 3 | raises |
| `1,2,3,` | `abc,8,9` | 3≠4 | 3=3, 2 of 3 | raises |
| `1,2,3` | `abc,8,9,` | 4≠3 | 3=3, 2 of 3 | raises |
| `9,5,6,7,8,9,` (7 raw, 6 values) | ROI line (7 raw, 7 values, 3 numeric) | 7=7, 3 of 7 (no) | 7≠6 | skipped, counted |
| `9,5,6,7,8,9,10,` (8 raw, 7 values) | ROI line | 7≠8 | 7=7, 3 of 7 (no) | skipped, counted |
| `6,5` | `Gain:,300` (04 metadata) | 2=2, 1 of 2 (no) | 2=2, 1 of 2 (no) | skipped, counted |

#### Rule K: kinetic series

```python
def _check_not_a_series(path: str | os.PathLike[str], metadata: list[tuple[int, list[str]]]) -> None:
```

`metadata` = `lines[:start] + lines[stop:]` (both sides; Solis writes it after the grid, but other versions may not). For each line, `key, sep, value = ",".join(fields).partition(":")` (re-joining keeps a comma-containing value intact; field stripping only removes whitespace around commas). If `sep` and `key.strip() == _SERIES_KEY`:

- `value.strip()` parses with `int()` and is `> 1`: `ValueError(f"{path}: line {n} says the file is a kinetic series of {k} frames ({_SERIES_KEY}: {k}); kinetic series are not supported, export a single frame")`
- parses and is `<= 1`: read normally, no note.
- does not parse (Q2 ruling: fail closed): `ValueError(f"{path}: line {n}: cannot read the kinetic series length {value.strip()!r}; kinetic series are not supported")`.

Detection is from the metadata key only (Q3 ruling). Known gap, stated in the docstring and the ticket Comments: a file without the `Number in Kinetics Series` key is not proven to be a single frame (for example a series whose footer was stripped). The existing "does not count up" warning fires on such a file only when the axis column is dropped.

#### Rule X: transpose

Applied last, after the axis-column drop or warning (the axis belongs to file rows, so it is dropped before transposing). `transpose=True`: `grid = np.ascontiguousarray(grid.T)` and append the note
`f"transposed the frame, as requested: file rows are frame columns ({rows} x {cols} frame)"` with the shape **after** transposing (the final rows x columns). Never guessed; default `False` adds nothing. (The copy is a plain choice so the returned array is C-contiguous; no layout-equivalence claim, since the drop path returns a non-contiguous view today and stays as it is.)

#### Kept-axis warning

The warning for a kept axis column names **the file's first column**, since after transposing it is the frame's first row:

- without `transpose`: `"warning: the file's first column counts up row by row ({range}), like a Solis axis column; it was kept as intensities. If it is an axis, read with drop_axis_column=True (CLI: --drop-axis-column)"`
- with `transpose=True`: the same text with `" (after transposing it is the frame's first row)"` inserted after `"it was kept as intensities"`.

No existing test pins the old text (checked: tests assert only `startswith("warning: ")` and `"--drop-axis-column"`). The dropped note and its "does not count up" warning are unchanged.

Notes order (update `FrameFile` docstring): before, after, trailing comma, axis (dropped note then its warning, or the kept-axis warning), transposed.

#### Docstrings

- `read_frame`: replace "a trailing comma (an empty last field) raises" with rule T and its known limit; describe rule T3 (both boundary checks); add rule K with its known gap; add rule X and why transposing exists ("Solis may write one sensor column per file row; the detector looks for near-vertical stripes in frame rows, so such a file needs `transpose=True`").
- `FrameFile.notes`: new order.
- Glossary check (`tests/test_glossary_terms.py`, `CURATED = ("orientation", "amplitude", "wavelength", "false positive")`, plurals included; `*.py` docstrings and comments in `src/denoisifier` and `tests`): write **none of the four** in new docstrings or comments, test files included (say "transposed", not "orientation"). Prefer "frame" over "image" in prose.

### 2. `cli.main`

```python
parser.add_argument(
    "--transpose",
    action="store_true",
    help="transpose the frame after reading (and after --drop-axis-column), for exports "
    "that write one sensor column per file row; never done without this flag",
)
...
frame_file = read_frame(args.frame, drop_axis_column=args.drop_axis_column, transpose=args.transpose)
```

Errors (series, trailing-comma shape, boundary rows) are `ValueError`, so they already print one `denoisifier: error:` line and exit 1. Update the `frame` help: "frame as a comma-separated grid of numbers, such as an Andor Solis export; metadata lines before and after the grid are skipped".

### 3. `report.py`, `analysis.py`, `__init__.py`

No change. (Touching `__init__.py` or `analysis.py` would need a `make check-slow`; nothing here needs it.)

## Fixtures

Directory `tests/data/solis/` (Q6 ruling; `pytest` collects only `test_*.py`, so data files there are inert). Files:

### `tests/data/solis/xpos_ypos_crop.asc` (LF, ~17 KB)

Q5 ruling. Cut from `xpos ypos fluorescence.asc` (sha256 above) with a throwaway script in the scratchpad, never committed; read the source as text with `python -I`:

- **Grid:** file lines **1359..1422** (64 lines; axis values 1359..1422). From each line, split on `","` and keep field 0 (axis) and fields **1077..1140** (64 values = source value columns 1077..1140), then a trailing `,`: `",".join([f[0]] + f[1077:1141]) + ","`. Line ending `\n`.
- **Footer:** source lines 2561..2590 verbatim (2 blank lines, the 27 metadata lines, 1 final blank line), so the file ends `...Grating Groove Density (l/mm):0\n\n`. Trailing spaces inside metadata kept.
- Content pins (computed from the source, verified in review; use them in the test as independent anchors): frame (after drop) `[0,0] = 984`, `[0,63] = 735`, `[63,0] = 856`, `[63,63] = 754`, `[31,31] = 2022` (the source's maximum, unique in the crop), sum `4886612`. Values 713..2022, all lit.
- Why this crop: centred on the source maximum, fully lit (positive light, passes `MIN_SIDE` 40). Tests compare values and report fields and never assert a Verdict, so a later detector change cannot turn them red. (Today it scores 5.5 / 5.2 against threshold 154, recorded for context only.)

### `tests/data/solis/kinetic.asc` (CRLF, 16 197 bytes)

The whole uncompressed `kinetic.asc`, byte for byte (sha256 `da9e2035...f9037`). Whole file rather than a cut: original provenance, real CRLF, real ROI line, and small enough.

### `tests/data/solis/NOTICE.md`

Content (exact):

```
# Andor Solis sample exports

From WrightTools (https://github.com/wright-group/WrightTools), folder
`WrightTools/datasets/Solis/`, under the MIT licence below. Exported by
Andor Solis 4.28 (Andor Zyla, model DC-152Q-C00-FI).

- `xpos_ypos_crop.asc`: a crop of `xpos ypos fluorescence.asc.gz`
  (uncompressed sha256 bbe84637d35c001db2c2cfac98ea6dd77902d10bf4a4c3868a58d4c315182877):
  file lines 1359-1422 (axis values 1359-1422), the axis column plus value
  columns 1077-1140, each line ending with its original trailing comma, then
  the original footer (lines 2561-2590) unchanged. The footer describes the
  full 2560 x 2160 export, not the crop.
- `kinetic.asc`: `kinetic.asc.gz` uncompressed, unchanged
  (sha256 da9e203527142e4124ee34167af03dc5dd250f6ef729954b8a654b4f983f9037).

## Licence

The MIT License (MIT)

Copyright (c) 2016-2018 WrightTools Developers.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

(Licence text fetched from `gh api repos/wright-group/WrightTools/license`, file `LICENSE.txt`, SPDX `MIT`.)

### `.gitattributes` (new, repo root)

```
tests/data/solis/*.asc -text
```

Keeps the CRLF fixture byte-exact under any `core.autocrlf` (unset here, but a Windows-host checkout could convert it). The kinetic test asserts the CRLF is really there, so a silent conversion turns red instead of passing on LF.

## Tests: one per acceptance criterion, on the real path

Fixture paths in tests: `SOLIS = Path(__file__).parent / "data" / "solis"` (in both test modules). No new seeds, no numbers in `tests/protected.py`. Reader tests through public `read_frame` (`from denoisifier import read_frame`); CLI tests through `_run` (subprocess). Handwritten grids whose notes are asserted exactly use a **falling** first column, so the kept-axis warning does not add a note.

| AC | Test (file) | Input | Assertions |
|---|---|---|---|
| 1 default load | `test_real_solis_export_loads_by_default_with_notes` (test_read_frame.py) | `SOLIS / "xpos_ypos_crop.asc"` | shape `(64, 65)`; `frame[:, 0] == arange(1359, 1423)`; `frame[31, 32] == 2022`; notes exactly 3, in order: `"skipped 27 metadata lines after the grid"`, `"every grid row ends with a trailing comma; the empty last field was ignored"`, a note starting `"warning: "` containing `"file's first column"`, `"1359 to 1422"` and `"--drop-axis-column"` |
| 2 drop axis | `test_real_solis_export_with_axis_dropped_is_the_source_crop` (test_read_frame.py) | same, `drop_axis_column=True` | shape `(64, 64)`; equals an independent parse in the test (`[[float(x) for x in line.split(",")[1:-1]] for line in text.splitlines()[:64]]`); pins `[0,0]=984`, `[0,63]=735`, `[63,0]=856`, `[63,63]=754`, `[31,31]=2022`, `sum == 4886612`; notes: after, trailing comma, dropped (3, no `"warning: "`) |
| 1/2 unit | `test_trailing_comma_on_every_row_is_accepted_and_noted` (replaces `test_trailing_comma_is_rejected`, Q1 approval) | `"4,2,\n3,1,\n"` (falling first column) | frame `[[4,2],[3,1]]`; notes `== ("every grid row ends with a trailing comma; the empty last field was ignored",)` |
| 1/2 limit | `test_one_row_trailing_comma_reads_as_a_trailing_delimiter` | `"5,6,\n"` | frame `[[5,6]]`; notes `== (trailing-comma note,)` (pins the documented limit: a one-row file cannot show a missing last value) |
| 3a | `test_trailing_comma_missing_on_one_row_raises_naming_it` | `"1,2,\n3,4\n5,6,\n"` | `match=r"line 2 does not end with a trailing comma"`, message contains `"line 1"` and the path |
| 3b | `test_trailing_comma_on_only_some_rows_raises_naming_it` | `"1,2\n3,4,\n5,6\n"` | `match=r"line 2 ends with a trailing comma"` |
| 3 limit | `test_missing_last_value_on_one_row_is_caught` (parametrize) | `"1,2,3\n4,5,\n"` (row 2 lost its last value, comma kept); `"1,2,\n4,5,6\n"` (row 1 short) | first: `match=r"line 2 ends with a trailing comma"`; second: `match=r"line 2 does not end with a trailing comma"` |
| 3c | `test_empty_interior_field_with_trailing_commas_raises_naming_it` | `"1,,3,\n4,5,6,\n"` | `match=r"line 1, column 2: '' is not a number"` (existing `test_empty_field_in_grid_raises_naming_its_position` stays) |
| 3d (T3 damaged rows) | `test_corrupted_boundary_row_raises_with_or_without_its_trailing_comma` (parametrize, ids as named) | `trailing-both-first`: `"abc,8,9,\n1,2,3,\n4,5,6,\n"` (line 1); `trailing-both-last`: `"1,2,3,\n4,5,6,\nabc,8,9,\n"` (line 3); `lost-comma-first`: `"abc,8,9\n1,2,3,\n4,5,6,\n"` (line 1); `lost-comma-last`: `"1,2,3,\n4,5,6,\nabc,8,9\n"` (line 3); `extra-comma-last`: `"1,2,3\n4,5,6\nabc,8,9,\n"` (line 3) | `match=rf"line {line}, column 1: 'abc' is not a number"`. Existing `test_corrupted_first_or_last_row_is_an_error_not_metadata` stays unchanged |
| 3d (T3 ROI) | `test_real_roi_line_next_to_a_trailing_comma_grid_is_skipped` (parametrize, ids `raw-width-match`, `value-count-match`) | 3 grid rows `"9,5,6,7,8,9,\n8,5,6,7,8,9,\n7,5,6,7,8,9,\n"` (7 raw, 6 values) or `"9,5,6,7,8,9,10,\n8,5,6,7,8,9,10,\n7,5,6,7,8,9,10,\n"` (8 raw, 7 values), then `"{left,right,bottom,top}:      1,20,1071,1090\n"` (copied from kinetic.asc line 217) | loads (3 x 6 or 3 x 7); notes `== ("skipped 1 metadata line after the grid", trailing-comma note)` |
| 4a library | `test_transpose_returns_the_transposed_frame_and_notes_it` | `"0,5,6\n1,7,8\n2,9,10\n"`, `drop_axis_column=True, transpose=True` | frame `[[5,7,9],[6,8,10]]` (proves transpose after the drop); last note contains `"transposed"` and `"2 x 3"` |
| 4b library default | `test_default_read_does_not_transpose` | same text, `drop_axis_column=True` | frame `[[5,6],[7,8],[9,10]]`; no note contains `"transposed"` |
| 4 kept axis | `test_kept_axis_warning_names_the_file_column_when_transposed` | `"0,5,6\n1,7,8\n2,9,10\n"`, `transpose=True` | frame `[[0,1,2],[5,7,9],[6,8,10]]`; notes exactly 2: a `"warning: "` note containing `"file's first column"` and `"frame's first row"`, then the transposed note containing `"3 x 3"` |
| 4c real file | `test_real_solis_export_transposes_on_request` | crop, `drop_axis_column=True, transpose=True` | `frame == read_frame(crop, drop_axis_column=True).frame.T`; `frame.flags.c_contiguous`; last note contains `"transposed"` and `"64 x 64"` |
| 5 kinetic | `test_kinetic_series_is_rejected` (test_read_frame.py; parametrize `drop_axis_column` False/True) | `SOLIS / "kinetic.asc"` | `b"\r\n" in path.read_bytes()` (guards the fixture); `pytest.raises(ValueError, match=r"line 215 says the file is a kinetic series of 10 frames")` and message contains `"kinetic series are not supported"` |
| 5 unit | `test_series_length_of_one_reads_normally` | `"6,5\n4,7\nNumber in Kinetics Series:    1\n"` | frame `[[6,5],[4,7]]`; notes `("skipped 1 metadata line after the grid",)` |
| 5 unit (Q2) | `test_unreadable_series_length_is_an_error` | `"6,5\n4,7\nNumber in Kinetics Series:    ten\n"` | `match=r"line 3: cannot read the kinetic series length 'ten'"` |
| 6a CLI | `test_cli_reads_real_solis_export_and_reports_reader_notes` (test_cli.py) | crop with `--drop-axis-column -o out`; and the same frame (`read_frame(crop, drop_axis_column=True).frame`) written plain with `write_frame_csv` | both exit 0; Solis `reader_notes` = 3 notes (after, trailing comma, dropped); reports equal after popping `reader_notes` |
| 6b CLI transpose | `test_cli_transposes_real_solis_export_on_request` | crop with `--drop-axis-column --transpose`; and `frame.T` written plain | both exit 0; last `reader_notes` entry contains `"transposed"`; reports equal after popping `reader_notes` (proves the transposed frame reaches `analyse`) |
| 6c CLI series | `test_cli_fails_cleanly_on_kinetic_series` | `kinetic.asc` | `_assert_clean_failure(result, "kinetic series are not supported")` |

The CLI tests never assert `striped`; they compare reports, so a later detector change cannot turn them red. `test_report_converts_to_json` stays unchanged.

## Order of work (red-green slices; each starts with a failing test, each commit green)

`make test-fast` after every change. One commit per slice; slices 1 and 2 of the earlier draft are merged into slice 1 so no commit lands red.

1. **Fixtures and trailing comma (T1, T2)**, one commit.
   1. **Record the Q1 approval in ticket 14's Comments** before any test is touched: weakening move "changing an expected value", replacing `test_trailing_comma_is_rejected` with `test_trailing_comma_on_every_row_is_accepted_and_noted`; approved by the orchestrator (Codex agrees), reason: two real Solis exports (WrightTools, MIT) end every grid row with a comma, so the old expectation encoded a wrong layout assumption; limit: a missing last value on every row, or in a one-row file, cannot be told apart from a trailing delimiter (documented and tested). Link `.scratch/stripe-detector/handoffs/14-orchestrator.md` "Decisions".
   2. Cut the crop, copy `kinetic.asc`, write `NOTICE.md` and `.gitattributes`.
   3. Red: AC2 `test_real_solis_export_with_axis_dropped_is_the_source_crop` (today: `line 1359, column 66: '' is not a number`), `test_trailing_comma_on_every_row_is_accepted_and_noted` (replacing `test_trailing_comma_is_rejected`), `test_one_row_trailing_comma_reads_as_a_trailing_delimiter`, 3a, 3b, the 3 limit test (its `"1,2,3\n4,5,\n"` case raises today, but at `column 3: ''`, so the `match` is red).
   4. Green: `_values`, shape check, value-count width, note. `_grid_span` unchanged in this slice.
   5. Add AC1 and 3c (should be green; AC1's `"file's first column"` assertion is added in slice 4 with the text change). Commit.
2. **Boundary rows (T3).** Red: the five 3d damaged-row cases (after slice 1 they are skipped as metadata and the file loads). Green: the normalized-width check in `_grid_span`. Add the 3d ROI test (green: a regression guard for the real line). Existing 04 boundary tests stay green. Commit.
3. **Kinetic series (K).** Red: AC5 tests, the Q2 test (today the CRLF file reads as a 200 x 21 frame), and 6c (CLI exits 0 today). Green: `_check_not_a_series`. Add `test_series_length_of_one_reads_normally` alongside. Commit.
4. **Transpose (X) and the kept-axis warning.** Red: 4a, 4c, the 4-kept-axis test (no keyword: `TypeError`); add `"file's first column"` to AC1 (red: old text). Green: `transpose` parameter, note, warning text. 4b alongside. Commit.
5. **CLI.** Red: 6b (no `--transpose` flag: argparse exits 2). Green: the flag. 6a alongside (should already pass after slice 1; it is the real-path proof). Commit.
6. **Docstrings and help** per "Docstrings": none of `orientation`, `amplitude`, `wavelength`, `false positive` (or plurals) in `*.py` prose. Commit.
7. `make check` at the end (it must report the stamp fresh; see below).
8. Ticket: tick boxes; append to `## Comments` the gate quote (command, exit status, pytest's final summary line, `git rev-parse --short HEAD` plus `-dirty`), the S6 supersession and S2 extension note, and the known gaps (Q1 limit, Q3 metadata-only detection).

## Gate implications

- **Slow-tier stamp:** `frame_io.py` and `cli.py` are in `NOT_STAMPED_SRC`; `tests/test_read_frame.py`, `tests/test_cli.py`, `tests/data/solis/*`, `.gitattributes` are not in `STAMPED_FILES` (it lists files, not globs). So no `make check-slow` is needed, provided the implementer does **not** touch `src/denoisifier/__init__.py`, `analysis.py`, `tests/protected.py`, `tests/conftest.py`, `pyproject.toml` or the `Makefile`. In a fresh worktree a `make check-slow` is still needed once (per-tree stamp).
- **Protected-number lockfile:** pins module- and class-level numbers in `src/denoisifier` and all of `tests/protected.py`. The plan adds only a string constant and inline literals; no lockfile edit.
- **Glossary check:** scans `*.py` docstrings and comments in `src/denoisifier` and `tests` for `orientation`, `amplitude`, `wavelength`, `false positive` (and plurals). Fixture files (`.asc`, `.md`) are not scanned, so the source footer's `Wavelength (nm)` line can stay verbatim. No new glossary entries (kinetic series, trailing comma, axis column are file-format words, not domain terms; same call as 04 S8 O7).
- **Lint/types:** ruff and mypy see only `*.py`; the fixtures are inert. `transpose: bool` is typed; `_values` and `_check_not_a_series` fully annotated (mypy strict on the package).
- **Timeouts:** reading a 64 x 66 file is instant; nothing near the 60 s per-test timeout.
- **Weakening moves:** exactly one, approved (Q1): replacing `test_trailing_comma_is_rejected`. Recorded in the ticket Comments as the first step of slice 1. Nothing else: no tolerance, skip, suppression, selection, timeout or gate-config change. Changing the kept-axis warning text changes no asserted value. `.gitattributes` is not listed gate config.
- **pytest collection:** `testpaths = ["tests"]` collects `test_*.py` only; `tests/data/` holds no Python, so nothing new is collected or imported.

## Settled

All rulings: `.scratch/stripe-detector/handoffs/14-orchestrator.md`, section "Decisions". Codex's adversarial review agreed with each, except Q4 (Codex disagreed with the draft; the ruling follows Codex) and N5 (superseded).

- **Q1 Replacing `test_trailing_comma_is_rejected`:** approved weakening move ([Decisions, Q1](14-orchestrator.md#decisions)). Recorded in ticket 14's Comments before the test is replaced (slice 1, step 1). The limit (uniform missing last value, one-row file) is documented and tested.
- **Q2 Unreadable series length:** raise, fail closed ([Decisions, Q2](14-orchestrator.md#decisions)). Rule K, test `test_unreadable_series_length_is_an_error`.
- **Q3 Series without the key:** metadata-key detection only; known gap recorded in the docstring and ticket Comments ([Decisions, Q3](14-orchestrator.md#decisions)).
- **Q4 Boundary rows:** the draft's shape rule (matching trailing-comma state) is dropped. Raw-width check kept, normalized-width check added; ROI evidence corrected to 7 fields, 3 numeric ([Decisions, Q4](14-orchestrator.md#decisions)). Rule T3, tests 3d.
- **Q5 Crop:** lines 1359-1422 x value columns 1077-1140; tests compare values and report fields, never a Verdict ([Decisions, Q5](14-orchestrator.md#decisions)).
- **Q6 Fixture directory:** `tests/data/solis/` ([Decisions, Q6](14-orchestrator.md#decisions)).
- **N1** all four glossary terms listed (Docstrings, Gate implications). **N2** approval recorded before the test changes (slice 1, step 1). **N3** "series error always first" claim dropped (step 3 of `read_frame`). **N4** contiguous-copy rationale dropped (rule X). **N5** superseded by Q4 (no boundary row is lost to a trailing comma). **N6** fixtures and parser change land in one commit (slice 1). **N7** as Q2 ([Decisions, N1-N7](14-orchestrator.md#decisions)).
- **Transpose:** axis dropped before transposing; note reports the final rows x columns; kept-axis warning names the file's first column, the frame's first row after transposing ([Decisions, Transpose](14-orchestrator.md#decisions)). Rule X, "Kept-axis warning", test 4-kept-axis.
- **Trailing-comma unit test:** uses a falling first column (`"4,2,\n3,1,\n"`) so its single note is exact ([Decisions, plan bug](14-orchestrator.md#decisions)).
