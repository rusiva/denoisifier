"""Frames on disk: comma-separated grids, including Solis exports."""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np

_SERIES_KEY = "Number in Kinetics Series"


@dataclass(frozen=True)
class FrameFile:
    """A frame as read from a file, plus notes from the reader.

    ``frame`` is a 2D float64 array, shape ``(rows, cols)``. ``notes`` holds
    anything the reader wants the experimenter to know about how the file was
    read, in this order: metadata lines skipped before the grid, metadata lines
    skipped after it, the trailing comma, then the axis column (the dropped
    note, then its warning if any; or the kept-axis warning), then the
    transposed note. Notes that start with ``"warning: "`` are warnings.
    ``notes`` is empty for a plain grid whose first column does not count up.
    """

    frame: np.ndarray
    notes: tuple[str, ...] = ()


def read_frame(
    path: str | os.PathLike[str],
    *,
    drop_axis_column: bool = False,
    transpose: bool = False,
) -> FrameFile:
    """Read a comma-separated grid of numbers, such as an Andor Solis export.

    The file is read as UTF-8 (a byte order mark is ignored; bytes that are not
    UTF-8 become a replacement character, which is not a number). Each line is
    split on commas and whitespace around each field is stripped. Blank lines
    are ignored everywhere and not counted.

    A line whose first field is a number is a grid line. The grid is every line
    from the first grid line to the last, and its width is the value count of
    its first line. Rows of the grid are rows of the frame (unless
    ``transpose`` is true).

    Trailing comma: Solis ends every grid row with a comma, so a row may end
    with one empty last field. The grid has a trailing comma when its first
    line does; then every grid line must have one, and without one no grid
    line may (an uneven trailing comma raises naming its line). The empty last
    field is not a value, and the notes say it was ignored. An empty interior
    field still raises. Known gap: a last value missing on only some rows is
    caught (uneven trailing comma or width), but a last value missing on every
    row, or in a one-row file, cannot be told apart from a trailing comma and
    reads as a grid one column narrower.

    Lines before and after the grid are metadata: they are skipped and counted
    in the notes. Except: a line there that looks like a corrupted grid row
    raises. It looks like one when it has the grid's width and more than half
    of its fields are numbers, counted either over all fields or over the
    fields without one trailing empty field (on both the line and the grid's
    first line), so a damaged first or last row is caught whether or not it
    kept its trailing comma.

    Kinetic series: when a metadata line says ``Number in Kinetics Series:``
    with a number above 1, or with a value that is not a whole number, the
    reader raises; series are not supported. A length of 1 reads normally.
    Known gap: detection uses that key only, so a file without it (for
    example a series whose metadata was stripped) is not proven to be a
    single frame.

    Inside the grid every line must have the grid's width (checked after the
    trailing comma) and every value must be a number, so a metadata line
    between grid rows or inline ``#`` text raises. Unlike ``np.loadtxt``,
    ``#`` lines are not stripped as comments: outside the grid they are
    metadata, inside it they are errors.

    A number is whatever Python's ``float()`` accepts, which includes ``nan``,
    ``inf`` and ``1_0`` (= 10). The reader keeps non-finite values; ``analyse``
    rejects them. A numeric header row (such as column indices) is not
    detected: it is kept as data.

    Every column is kept unless ``drop_axis_column`` is true, which drops the
    first column as a Solis axis column (pixel or spectral axis) and says so in
    the notes. The reader never drops it on its own. With at least 2 rows and 2
    columns it also checks whether the first column counts up (strictly
    increases) row by row, as an axis column does: a kept column that counts up
    gets a warning note, and a dropped column that does not gets one too. With
    one row that is not assessed, and the dropped note says so.

    ``transpose`` transposes the frame last, after any axis-column drop (the
    axis belongs to file rows), and the notes say so with the final shape.
    Solis may write one sensor column per file row; the detector looks for
    near-vertical stripes in frame rows, so such a file needs
    ``transpose=True``. The reader never transposes on its own.

    Raises ``ValueError`` naming the file when no line is a grid line, when a
    grid line has the wrong number of values or an uneven trailing comma
    (naming its line and the grid's first line), when a grid field is not a
    number (naming its line and column; positions are 1-based lines and
    columns of the file), when the metadata says the file is a kinetic series,
    or when ``drop_axis_column`` is true and the grid has only one column.
    """
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        raw_lines = [(n, line) for n, line in enumerate(f, start=1) if line.strip()]
    lines = [(n, _fields(line)) for n, line in raw_lines]
    stripped = [_strip_trailing_empty(fields) for _, fields in lines]
    start, stop = _grid_span(path, lines, stripped)
    _check_not_a_series(path, raw_lines[:start] + raw_lines[stop:])
    first_line = lines[start][0]
    first_values, grid_has_trailing = stripped[start]
    width = len(first_values)  # values, so a trailing empty field never counts
    notes = []
    for count, where in ((start, "before"), (len(lines) - stop, "after")):
        if count:
            noun = "line" if count == 1 else "lines"
            notes.append(f"skipped {count} metadata {noun} {where} the grid")
    if grid_has_trailing:
        notes.append("every grid row ends with a trailing comma; the empty last field was ignored")
    rows = []
    for (n, _), (values, row_has_trailing) in zip(
        lines[start:stop], stripped[start:stop], strict=True
    ):
        if grid_has_trailing and not row_has_trailing:
            raise ValueError(
                f"{path}: line {n} does not end with a trailing comma, "
                f"but the grid's first row (line {first_line}) does"
            )
        if row_has_trailing and not grid_has_trailing:
            raise ValueError(
                f"{path}: line {n} ends with a trailing comma (an empty last field), "
                f"but the grid's first row (line {first_line}) does not"
            )
        if len(values) != width:
            raise ValueError(
                f"{path}: line {n} has {len(values)} values, "
                f"but the grid's first row (line {first_line}) has {width}"
            )
        rows.append(_parse_row(path, n, values))
    grid = np.asarray(rows, dtype=np.float64)
    if drop_axis_column:
        grid, axis_notes = _drop_axis_column(path, grid)
        notes.extend(axis_notes)
    elif _counts_up(grid):
        after_transposing = " (after transposing it is the frame's first row)" if transpose else ""
        notes.append(
            f"warning: the file's first column counts up row by row "
            f"({_first_column_range(grid)}), like a Solis axis column; "
            f"it was kept as intensities{after_transposing}. If it is an axis, read with "
            "drop_axis_column=True (CLI: --drop-axis-column)"
        )
    if transpose:
        grid = np.ascontiguousarray(grid.T)
        n_rows, n_cols = grid.shape
        notes.append(
            f"transposed the frame, as requested: file rows are frame columns "
            f"({n_rows} x {n_cols} frame)"
        )
    return FrameFile(frame=grid, notes=tuple(notes))


def _grid_span(
    path: str | os.PathLike[str],
    lines: list[tuple[int, list[str]]],
    stripped: list[tuple[list[str], bool]],
) -> tuple[int, int]:
    """Indices ``start, stop`` of the grid in ``lines``; the rest is metadata.

    ``stripped`` holds ``_strip_trailing_empty`` of each line's fields, in order.
    The grid runs from the first line whose first field is a number to the last.
    Raises when there is no such line, or when a line outside the grid looks
    like a corrupted grid row: the grid's width and more than half numbers,
    counting either all fields or the fields without one trailing empty field,
    so a trailing comma, kept or lost, cannot hide a damaged row.
    """
    grid_lines = [i for i, (_, fields) in enumerate(lines) if _is_number(fields[0])]
    if not grid_lines:
        raise ValueError(f"{path}: no rows of numbers found")
    start, stop = grid_lines[0], grid_lines[-1] + 1
    first = lines[start][1]
    first_values = stripped[start][0]
    for i in [*range(start), *range(stop, len(lines))]:
        line_number, fields = lines[i]
        values = stripped[i][0]
        if _looks_like_a_row(fields, first) or _looks_like_a_row(values, first_values):
            _parse_row(path, line_number, fields)
    return start, stop


def _check_not_a_series(path: str | os.PathLike[str], metadata: list[tuple[int, str]]) -> None:
    """Raise when a metadata line says the file is a kinetic series of more than one frame.

    ``metadata`` holds the raw metadata lines with their line numbers. An
    unreadable series length raises too: the reader fails closed.
    """
    for line_number, line in metadata:
        key, sep, value = line.partition(":")
        if not sep or key.strip() != _SERIES_KEY:
            continue
        try:
            frames = int(value.strip())
        except ValueError:
            raise ValueError(
                f"{path}: line {line_number}: cannot read the kinetic series length "
                f"{value.strip()!r}; kinetic series are not supported"
            ) from None
        if frames > 1:
            raise ValueError(
                f"{path}: line {line_number} says the file is a kinetic series of {frames} "
                f"frames ({_SERIES_KEY}: {frames}); kinetic series are not supported, "
                "export a single frame"
            )


def _looks_like_a_row(fields: list[str], row: list[str]) -> bool:
    """Whether ``fields`` has ``row``'s width and more than half of them are numbers."""
    return len(fields) == len(row) and 2 * sum(map(_is_number, fields)) > len(row)


def _drop_axis_column(
    path: str | os.PathLike[str], grid: np.ndarray
) -> tuple[np.ndarray, list[str]]:
    """Drop column 0 as requested; returns the grid and the dropped note plus any warning."""
    if grid.shape[1] < 2:
        raise ValueError(f"{path}: cannot drop the axis column: the grid has only one column")
    if grid.shape[0] < 2:
        notes = [
            "dropped the first column as an axis column, as requested; "
            "with one row, whether it is an axis column was not assessed"
        ]
    else:
        notes = [
            f"dropped the first column as an axis column "
            f"({_first_column_range(grid)}), as requested"
        ]
        if not _counts_up(grid):
            notes.append(
                "warning: the first column was dropped as requested, but it does not "
                "count up row by row, so it may not be an axis column"
            )
    return grid[:, 1:], notes


def _first_column_range(grid: np.ndarray) -> str:
    """The first column's first and last values, as ``"<first> to <last>"``."""
    return f"{grid[0, 0]:g} to {grid[-1, 0]:g}"


def _counts_up(grid: np.ndarray) -> bool:
    """Whether the first column strictly increases row by row (needs 2 rows and 2 columns)."""
    return grid.shape[0] >= 2 and grid.shape[1] >= 2 and bool(np.all(np.diff(grid[:, 0]) > 0))


def _strip_trailing_empty(fields: list[str]) -> tuple[list[str], bool]:
    """The fields without one trailing empty field, and whether there was one."""
    if len(fields) >= 2 and fields[-1] == "":
        return fields[:-1], True
    return fields, False


def _fields(line: str) -> list[str]:
    return [field.strip() for field in line.split(",")]


def _is_number(field: str) -> bool:
    try:
        float(field)
    except ValueError:
        return False
    return True


def _parse_row(path: str | os.PathLike[str], line_number: int, fields: list[str]) -> list[float]:
    """The fields as floats; raises naming the line and column of the first non-number."""
    for column, field in enumerate(fields, start=1):
        if not _is_number(field):
            raise ValueError(
                f"{path}: line {line_number}, column {column}: {field!r} is not a number"
            )
    return [float(field) for field in fields]


def write_frame_csv(frame: np.ndarray, path: str | os.PathLike[str]) -> None:
    """Write a frame as a plain comma-separated grid, no header: the format ``read_frame`` reads."""
    np.savetxt(path, np.asarray(frame, dtype=float), delimiter=",", fmt="%.9g")
