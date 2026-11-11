"""Frames on disk: the plain comma-separated grid format."""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FrameFile:
    """A frame as read from a file, plus notes from the reader.

    ``frame`` is a 2D float64 array, shape ``(rows, cols)``. ``notes`` holds
    anything the reader wants the experimenter to know about how the file was
    read; it is always empty for plain grids.
    """

    frame: np.ndarray
    notes: tuple[str, ...] = ()


def read_frame(path: str | os.PathLike[str]) -> FrameFile:
    """Read a plain comma-separated grid of floats with no header.

    Rows of the file are rows of the frame. Every column is kept.
    """
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        lines = [(n, _fields(line)) for n, line in enumerate(f, start=1) if line.strip()]
    grid_at = [i for i, (_, fields) in enumerate(lines) if _is_number(fields[0])]
    if not grid_at:
        raise ValueError(f"{path}: no rows of numbers found")
    start, stop = grid_at[0], grid_at[-1] + 1
    n0, first = lines[start]
    width = len(first)
    for n, fields in lines[:start] + lines[stop:]:
        if len(fields) == width and 2 * sum(map(_is_number, fields)) > width:
            _numbers(path, n, fields)  # a corrupted grid row, not metadata: raises
    notes = []
    for count, where in ((start, "before"), (len(lines) - stop, "after")):
        if count:
            noun = "line" if count == 1 else "lines"
            notes.append(f"skipped {count} metadata {noun} {where} the grid")
    rows = []
    for n, fields in lines[start:stop]:
        if len(fields) != width:
            raise ValueError(
                f"{path}: line {n} has {len(fields)} values, "
                f"but the grid's first row (line {n0}) has {width}"
            )
        rows.append(_numbers(path, n, fields))
    return FrameFile(frame=np.asarray(rows, dtype=np.float64), notes=tuple(notes))


def _fields(line: str) -> list[str]:
    return [field.strip() for field in line.split(",")]


def _is_number(field: str) -> bool:
    try:
        float(field)
    except ValueError:
        return False
    return True


def _numbers(path: str | os.PathLike[str], n: int, fields: list[str]) -> list[float]:
    for c, field in enumerate(fields, start=1):
        if not _is_number(field):
            raise ValueError(f"{path}: line {n}, column {c}: {field!r} is not a number")
    return [float(field) for field in fields]


def write_frame_csv(frame: np.ndarray, path: str | os.PathLike[str]) -> None:
    """Write a frame as a plain comma-separated grid, no header: the format ``read_frame`` reads."""
    np.savetxt(path, np.asarray(frame, dtype=float), delimiter=",", fmt="%.9g")
