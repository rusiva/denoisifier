Plan: .scratch/stripe-detector/handoffs/04-plan.md @ uncommitted (BASE 0e56381, tree clean apart from .scratch)

## Findings

- [ ] B1 break: rule 6 (plan:34-37) puts the whole axis rule under "only with >= 2 rows and >= 2 columns". Read that way, the one-column drop error (plan:37, test 2e) can never fire, and `drop_axis_column=True` on a one-row grid would silently not drop. Read the other way (guard covers only `looks_like_axis`), a one-row drop goes ahead with no warning, because `np.all(np.diff([x]) > 0)` on an empty diff is True. Nothing tests the one-row drop, so either reading ships untested. → Restate rule 6: (i) `drop_axis_column=True` always drops column 0 when cols >= 2, else raises the one-column error; (ii) the >= 2 rows guard applies only to `looks_like_axis` (for both the kept-axis warning and the "does not count up" warning). Add a test, e.g. `"3,5,6\n"` with drop gives shape (1,2) and pins the chosen note set.
- [ ] O1 owner: real Solis layout (plan:136, O8). The ticket's headline is "load real Andor Solis CSV exports". If real exports end each row with a trailing comma, use a numeric column-index header row of the grid's width, or use a non-comma delimiter, then every real export fails. The trailing comma and the delimiter fail with a clear error. A numeric header row of the grid's width is worse: rule 3 (plan:27) would silently read it as a data row, which is the silent-corruption case the ticket forbids. None of this can be checked in the repo, because no real export is on file (`grep -ri solis tests/` finds only spec text). Options: A ship as planned, with clear errors, and add a real-file fixture in a follow-up (risk: AC "loads real exports" unproven, and a header-row case can corrupt silently) / B owner supplies one real export (or confirms the layout) before slice 2, and the plan adds the trailing-empty-field and header-row rules only if the file shows them. Recommend B if a file is at hand within the ticket, else A with the gap stated in the handoff.
- N1 note: rule 4 (plan:31) says a non-grid line between grid lines is reported as "not a number, column 1", but plan:32 checks field count first, so `"Gain:,300"` inside a 3-wide grid is reported as uneven. Both errors are clear. Pick one wording and add a test (no test covers a metadata line inside the grid; 6d covers only a bad value in the last row).
- N2 note: slice 5 (plan:113) says it is "driven by 7a", but 7a is only written in slice 6, so slice 5 has no red test. Merge slices 5 and 6, or write 7a first.
- N3 note: the grid-line test is `float()`, which also accepts `"nan"`, `"inf"` and `"1_0"` (= 10.0, checked). `analyse` rejects non-finite values downstream (analysis.py:58), so NaN/inf give a clear error from the CLI. The `"1_0"` case is the one silently accepted spelling; harmless, but worth a line in the docstring or a regex if the implementer wants strictness.
- N4 note: `np.loadtxt` used to strip `#` comments. Under the new rule a `#` line outside the grid is metadata and inside the grid it is an error. That is fine, but it is a behaviour change worth one docstring line.
- N5 note: an empty or blank-only file now raises "no rows of numbers found" (before, `loadtxt` gave an empty array plus a warning). That is good, but 6e covers only a text-only file, so add `""` or `"\n\n"` to it.
- N6 note: speed is fine. A Python parser on a 1600x401 `%.9g` grid took 0.11 s against 0.05 s for `loadtxt` (measured in the uv env), well inside spec story 39's ~5 s. `tests/bench.py` does not read frames.

## Verified claims

- frame_io.py, cli.py and report.py match plan:8-11. `FrameFile.notes` already exists, and the CLI drops the notes today.
- cli.py, report.py and frame_io.py are in `NOT_STAMPED_SRC` (tests/slow_stamp.py:71-74). `__init__.py` is stamped and already exports `read_frame` and `FrameFile`.
- `test_report_converts_to_json` asserts the exact key list (tests/test_analyse.py:156), so O5 keeps it green.
- The glossary check scans docstrings and comments in src/ and tests/ for "wavelength" (tests/test_glossary_terms.py:24); string data is not scanned.
- In CLI frame `F`, column 0 rises and then falls, so a plain run has `reader_notes == []`. The plain and Solis-shaped files both go through `%.9g`, so the reports compare equal. 64 >= `MIN_SIDE` (analysis.py:29).
- O2-O7 are within implementer latitude or already settled by ticket and spec (spec:104, :106). No weakening move and no lockfile edit is planned.

## Closing check (plan re-read, uncommitted, BASE 0e56381)

- [x] B1: plan:39-44 rule 7 splits explicit drop (any grid size; < 2 columns is an error) from the heuristic (>= 2 rows and >= 2 columns only); one-row drop note at plan:55; tests 2e, 2f (plan:107-108); S4 at plan:159.
- [x] O1: owner ruled "ship, note gap" (04-orchestrator.md:33); plan:166-168 "Known gap" says the handoff must state that real-file compatibility is unproven; numeric header row pinned as data by rule 9 / test 1b; trailing comma rejected by rule 5 / test 6h.
- [x] N1: plan:36 (field count checked first), test 6g (plan:121).
- [x] N2: slice 5 starts red with 7a/7b (plan:138).
- [x] N3: plan:64, tests 5b and 7d (plan:114, :126).
- [x] N4: plan:65.
- [x] N5: rule 6 (plan:38), 6e parametrized with `""` and whitespace-only input (plan:119).
- [x] N6: plan:150.
- N7 note (new, from the S2 fold): rule 4's "more than half numeric" test means a corrupted boundary row in a grid only 1 or 2 columns wide (`abc,5` below a 2-wide grid, `abc` below a 1-wide grid) is still skipped as metadata. It is counted in the notes, so it is not silent, and it is the accepted price of keeping `Gain:,300` as metadata (04-orchestrator.md:23). Real frames are >= 40 columns wide (MIN_SIDE), so this does not block.

I re-checked the new fixtures against the rules: 4 (`Exposure Time (secs):,0.1` has 1 of 2 fields numeric, so it is metadata), 6f (the replaced `\xff` byte leaves 2 of 3 numeric, so it is an error at column 1), 6h, 6g, 2f (note contains "dropped" and "not assessed"), 7d (`%.9g` writes `nan`, and analysis.py:58 says "non-finite"). All are consistent.

Open: none (N7 is a note).
