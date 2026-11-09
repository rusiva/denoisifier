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


def read_frame(path: str | os.PathLike) -> FrameFile:
    """Read a plain comma-separated grid of floats with no header.

    Rows of the file are rows of the frame. Every column is kept.
    """
    frame = np.loadtxt(path, delimiter=",", dtype=float, ndmin=2)
    return FrameFile(frame=frame)


def write_frame_csv(frame: np.ndarray, path: str | os.PathLike) -> None:
    """Write a frame as a plain comma-separated grid, no header: the format ``read_frame`` reads."""
    np.savetxt(path, np.asarray(frame, dtype=float), delimiter=",", fmt="%.9g")
