# 14: Frame reader loads real Solis exports

**What to build:** The reader from ticket 04 loads real Andor Solis exports, proven against a real file in the test suite. Ticket 04 shipped with an assumed layout. Real exports (WrightTools' MIT-licensed Solis samples, `https://github.com/wright-group/WrightTools/tree/master/WrightTools/datasets/Solis`, Solis 4.28, Andor Zyla) differ: every grid row ends with a trailing comma, so the reader rejects them today (`line 1, column N: '' is not a number`).

Verified real layout:
- comma-delimited ASCII, no BOM; line endings LF or CRLF;
- no header row; the grid starts on line 1;
- column 0 is a pixel axis counting 1..N; every grid row ends with a trailing comma (one empty last field);
- after the grid: 2 blank lines, then `Key:<spaces>value` metadata lines (`Date and Time:`, `Exposure Time (secs):`, `Number in Kinetics Series:`, `{left,right,bottom,top}:      1,20,1071,1090`, ...);
- a kinetic series stacks its frames in one block with no separator; the axis restarts at 1 for each frame (sample: 10 frames of 20x20 as 200 rows).
- In the full-image sample each file row is likely one sensor column (2560 rows = sensor long side), so the frame may need transposing before stripe detection.

Downloaded samples (untrusted data, not in the repo): `/tmp/claude-1000/-home-rusiva-dev-denoisifier/a1a17e7f-3fb2-4d3d-8ed4-d7bd854fa209/scratchpad/solis-samples/1/xpos_ypos.asc` (full image, 2560 rows x 2160 values, LF) and `.../solis-samples/2/kinetic.asc` (kinetic series, CRLF).

Behaviour:
- **Trailing comma:** a single empty last field is accepted when **every** grid row has one, and noted. An empty interior field, or a trailing empty field on only some rows, stays an error naming its position.
- **Transpose at import:** an explicit option (library parameter and CLI flag) transposes the frame after reading (after any axis-column drop, since the axis belongs to file rows). Off by default; never guessed. When on, the reader notes say so.
- **Kinetic series:** a file whose metadata says `Number in Kinetics Series:` greater than 1 fails with a clear error (series are out of scope); never read silently as one tall frame.
- **Fixture:** a crop of the full-image sample (64 file rows; the axis column plus 64 values; original trailing commas and the original metadata footer), committed under the tests with an MIT attribution note for WrightTools; plus a small CRLF kinetic-series fixture cut from the kinetic sample (or the whole 16 KB file).

**Blocked by:** 04

**Status:** resolved

- [x] The real-image fixture loads by default: every value column plus the axis column kept, an axis warning, the metadata lines skipped and counted, the trailing comma noted.
- [x] With the drop-axis-column option, the fixture loads as 64x64 with values equal to the source crop.
- [x] A grid where only some rows end with an empty field, or a row with an empty interior field, raises a clear error naming the position.
- [x] The transpose option (library and CLI) returns the transposed frame and notes it; the default leaves the orientation unchanged.
- [x] The kinetic-series fixture (CRLF) raises a clear error saying series are not supported.
- [x] The CLI runs end to end on the real-image fixture with `--drop-axis-column` (and with `--transpose`), and the reader notes appear in the JSON report.

## Comments

**Approval (recorded before the test change).** Weakening move "changing an expected value": replace `test_trailing_comma_is_rejected` (tests/test_read_frame.py) with `test_trailing_comma_on_every_row_is_accepted_and_noted`. Approved by the orchestrator (Codex adversarial review agrees); see `.scratch/stripe-detector/handoffs/14-orchestrator.md`, section "Decisions", Q1. Reason: two real Solis exports (WrightTools, MIT) end every grid row with a comma, so the old expectation encoded a wrong layout assumption. Limit: a missing last value on only some rows is still caught (uneven trailing comma or width), but a missing last value on every row, or in a one-row file, cannot be told apart from a trailing delimiter and reads as a grid one column narrower; documented in the `read_frame` docstring and pinned by tests.

**Implementer (2026-11-11).** Built per `.scratch/stripe-detector/handoffs/14-plan.md` (Settled section), test-first, commits `a045427` (fixtures, trailing comma T1/T2), `eecba3f` (boundary rows T3), `709b14c` (kinetic series K), `5d8b159` (transpose X, kept-axis warning), `c354b4d` (CLI `--transpose`), `2e16753` (docstrings, help). Fixtures in `tests/data/solis/` with `NOTICE.md` (WrightTools, MIT); `.gitattributes` keeps them byte-exact. This ticket supersedes 04's S6 (trailing comma rejected) for the one shape allowed here, and extends 04's S2 with a normalized-width boundary check. One weakening move, the Q1 replacement above; no stamped file, protected number or gate config changed.

**Fixer (2026-11-11).** Review fixes from `14-orchestrator.md` (Sorting), behaviour-preserving, in `c93f128`: `_values` renamed `_strip_trailing_empty`, trailing flags renamed `grid_has_trailing`/`row_has_trailing`, `rows` no longer reused for the shape, each line's stripped fields computed once and passed into `_grid_span`, `_check_not_a_series` reads the raw line, docstring "Known limit" now "Known gap". No test changed.

Gate: `make check` exit 0; `352 passed, 4 deselected in 132.75s (0:02:12)`; slow-tier stamp check passed; HEAD `c93f128-dirty` (pre-existing 02/07 issue edits; untracked handoff dirs).

Known gaps: (Q1) a last value missing on every row, or in a one-row file, cannot be told apart from a trailing comma and reads as a grid one column narrower. (Q3) a kinetic series is detected from the `Number in Kinetics Series` metadata key only; a file without that key is not proven to be a single frame (the "does not count up" warning catches a restarting axis only when the axis column is dropped).
