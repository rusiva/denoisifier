"""The Report that ``analyse`` returns."""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
from dataclasses import dataclass, field
from typing import ClassVar

import numpy as np


@dataclass(frozen=True)
class BinFactors:
    """How many sensor pixels were summed into one frame pixel along each axis.

    ``horizontal`` bins along a row (the frame's columns), ``vertical`` along a
    column (its rows); written ``HxV`` (the CLI's ``--bin``). Each is a plain
    ``int >= 1``: anything else raises ``TypeError`` (not an int, or a bool)
    or ``ValueError`` (below 1). Named fields, not a tuple, because
    ``Calibration.shape`` is (rows, cols), the other order.

    The sensor/frame conversions that use them are in the detector
    (``denoisifier._local_stripes``), so this class stays data and validation.
    """

    horizontal: int = 1
    vertical: int = 1

    def __post_init__(self) -> None:
        for axis in ("horizontal", "vertical"):
            value = getattr(self, axis)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"bin factor {axis} must be an int, got {value!r}")
            if value < 1:
                raise ValueError(f"bin factor {axis} must be at least 1, got {value!r}")

    def __str__(self) -> str:
        return f"{self.horizontal}x{self.vertical}"

    def to_dict(self) -> dict[str, int]:
        return {"horizontal": self.horizontal, "vertical": self.vertical}

    @classmethod
    def of(cls, value: object) -> BinFactors:
        """A ``bin_factors=`` option (``analyse``, ``calibrate``,
        ``calibrate_folder``): ``value`` itself, 1x1 for ``None``, and
        ``TypeError`` for anything that is not a ``BinFactors``."""
        if value is None:
            return cls()
        if not isinstance(value, cls):
            raise TypeError(f"bin_factors must be a BinFactors, got {value!r}")
        return value

    @classmethod
    def parse(cls, text: str) -> BinFactors:
        """Read ``HxV`` (horizontal first, ``x`` or ``X``), as ``--bin`` takes
        it; ValueError on anything else."""
        m = re.fullmatch(r"(\d+)[xX](\d+)", text)
        if m is None:
            raise ValueError(f"expected HORIZONTALxVERTICAL such as 1x2, got {text!r}")
        return cls(horizontal=int(m[1]), vertical=int(m[2]))

    @classmethod
    def from_dict(cls, d: object) -> BinFactors:
        """Read ``{"horizontal": h, "vertical": v}``; ValueError on anything else."""
        if not isinstance(d, dict) or set(d) != {"horizontal", "vertical"}:
            raise ValueError(f"bin factors must be {{'horizontal': h, 'vertical': v}}, got {d!r}")
        try:
            return cls(horizontal=d["horizontal"], vertical=d["vertical"])
        except TypeError as e:
            raise ValueError(str(e)) from None


def add_bin_option(parser: argparse.ArgumentParser, help_text: str) -> None:
    """Add ``--bin HxV`` (``BinFactors.parse``, default 1x1, as
    ``args.bin_factors``) to ``parser``: the one ``--bin`` of the CLI and of
    ``python -m denoisifier.recalibrate``."""

    def bin_factors(text: str) -> BinFactors:
        try:
            return BinFactors.parse(text)
        except ValueError as e:
            raise argparse.ArgumentTypeError(str(e)) from None

    parser.add_argument(
        "--bin",
        type=bin_factors,
        default=BinFactors(),
        metavar="HxV",
        dest="bin_factors",
        help=help_text,
    )


@dataclass(frozen=True)
class BoundingBox:
    """Half-open pixel box, like slices: ``labels[row_start:row_stop, col_start:col_stop]``."""

    row_start: int
    row_stop: int
    col_start: int
    col_stop: int

    def transposed(self) -> BoundingBox:
        return BoundingBox(self.col_start, self.col_stop, self.row_start, self.row_stop)

    def to_dict(self) -> dict[str, int]:
        return {
            "row_start": int(self.row_start),
            "row_stop": int(self.row_stop),
            "col_start": int(self.col_start),
            "col_stop": int(self.col_stop),
        }


@dataclass(frozen=True)
class Region:
    """One reported Striped Region.

    ``label`` (1-based) is the value of this region's pixels in
    ``Report.labels`` and in the mask CSV. ``period_px`` is the Period in
    sensor pixels; ``angle_deg`` the Angle in degrees, with the sign
    convention in GLOSSARY.md, in the sensor's geometry; ``modulation_depth``
    the Modulation Depth relative to the local Envelope, as measured on the
    frame as given (binning damps it; see ``analyse``). ``bbox`` is the tight
    box of the region's pixels and ``area_px`` their count, both in frame
    pixels. ``Report.UNITS`` lists each field's unit.
    """

    label: int
    period_px: float
    angle_deg: float
    modulation_depth: float
    bbox: BoundingBox
    area_px: int

    def to_dict(self) -> dict[str, object]:
        return {
            "label": int(self.label),
            "period_px": float(self.period_px),
            "angle_deg": float(self.angle_deg),
            "modulation_depth": float(self.modulation_depth),
            "bbox": self.bbox.to_dict(),
            "area_px": int(self.area_px),
        }


@dataclass(frozen=True)
class PhaseBreak:
    """One reported Phase Break.

    ``line`` is a polyline of (row, col) points in frame px (two points in
    this version: the break's run across its region). ``jump_rad``, in
    (-pi, pi], is the local stripe phase on the positive side minus the
    other side; the positive side is where ``cross(end - start, p - start)
    > 0``, with ``cross(a, b) = a_col * b_row - a_row * b_col``. The stripe
    phase grows with the column, so a positive jump moves the stripes on the
    positive side toward column 0 by jump / 2 pi Periods (toward row 0 in
    file layout when transposed). In the analysed frame the points are in
    col-increasing order, so the positive side is below a horizontal line;
    in file layout they are row-decreasing. Near vertical, point order and
    the sign flip together. ``region`` is the label of its Striped Region.
    """

    region: int
    line: tuple[tuple[float, float], ...]
    jump_rad: float

    def transposed(self) -> PhaseBreak:
        """The break in the transposed layout: points swapped, order reversed,
        so every pixel keeps its side; the jump is unchanged."""
        return dataclasses.replace(self, line=tuple((c, r) for r, c in reversed(self.line)))

    def to_dict(self) -> dict[str, object]:
        return {
            "region": int(self.region),
            "line": [[float(r), float(c)] for r, c in self.line],
            "jump_rad": float(self.jump_rad),
        }


@dataclass(frozen=True)
class Fork:
    """One reported Fork.

    ``point`` (row, col) in frame px. ``direction`` +1: going toward row 0
    of the analysed frame past the fork, one stripe becomes two (a row on the
    row-0 side crosses one more stripe); -1 the same going away from row 0.
    In file layout when transposed, read "column 0" for "row 0"; the value is
    the same in both layouts. ``region`` is the label of its Striped Region.
    """

    region: int
    point: tuple[float, float]
    direction: int

    def transposed(self) -> Fork:
        """The fork in the transposed layout: the point swapped, the
        direction unchanged."""
        return dataclasses.replace(self, point=(self.point[1], self.point[0]))

    def to_dict(self) -> dict[str, object]:
        return {
            "region": int(self.region),
            "point": [float(self.point[0]), float(self.point[1])],
            "direction": int(self.direction),
        }


@dataclass(frozen=True)
class Report:
    """What ``analyse`` found in one frame.

    ``striped == bool(regions) == (score > threshold)``: the frame is Striped
    when at least one Striped Region is reported. ``regions`` are ordered by
    descending area, then by higher peak ratio, then by their first pixel in
    row-major order. ``labels`` (int32, frame shape) is the Mask: 0 outside
    every region, k inside the region with ``label == k``; each region's
    pixels lie inside its tight ``bbox`` and number ``area_px``. ``mask()`` is
    the boolean union of the regions.

    ``score`` is the Stripe Score: the highest peak ratio over the qualifying
    groups (0.0 when there are none). It can change in steps under small
    pixel changes, because a group appears or vanishes at the size and
    leakage rules. ``threshold`` is the Threshold used (by default the stored
    calibration's at a 1% false-alarm rate; see ``analyse``).

    ``transposed`` is True when ``labels`` and the bboxes are in the file's
    layout of a transposed read (``in_file_layout``); Period and Angle are
    always in the analysed frame's convention. ``reader_notes`` are the
    frame reader's notes when the frame came from a file (the CLI sets them),
    and ``None`` otherwise.

    ``spike_pixels`` counts the pixels rejected as Spikes; ``clipped_pixels``
    counts the Clipped Pixels that were not rejected as Spikes, so the two
    never count a pixel twice (a Spike saturated inside the clip plateau is
    counted as clipped).

    ``bin_factors`` are the frame's ``BinFactors``. Period and Angle are in
    sensor pixels; ``labels``, the bboxes, areas and pixel counts in frame
    pixels; ``UNITS`` names the unit of each field, and
    ``to_dict`` carries it as ``"units"``. ``unresolved_period_px`` is the
    part of the 3-20 px Period range (sensor px) that was not searched
    because a filter there falls under ``MIN_FRAME_PERIOD_PX`` frame pixels
    (``denoisifier._local_stripes``), or ``None``.
    ``warnings`` are frame-level analysis warnings (that range, a frame
    the calibration does not cover, and regions whose Phase Breaks were not
    searched), separate from ``reader_notes``.

    ``phase_breaks`` (``PhaseBreak``) are the Phase Breaks found in the
    reported regions, ordered by region label, then by descending
    ``|jump_rad|``, then by first point in row-major order; each ``line`` is
    in frame px (file layout when transposed).

    ``forks`` (``Fork``) are the Forks found in the reported regions,
    ordered by region label, then by point in row-major order; each
    ``point`` is in frame px (file layout when transposed) and its
    ``direction`` is the same value in both layouts.
    """

    UNITS: ClassVar[dict[str, str]] = {
        "period_px": "sensor px",
        "angle_deg": "degrees from vertical, sensor geometry",
        "modulation_depth": "relative to the local envelope, as measured on the (binned) frame",
        "bbox": "frame px (file layout when transposed)",
        "area_px": "frame px",
        "mask": "frame px (file layout when transposed)",
        "spike_pixels": "frame px",
        "clipped_pixels": "frame px",
        "unresolved_period_px": "sensor px",
        "line": (
            "frame px, (row, col) points; file layout when transposed "
            "(points swapped and order reversed)"
        ),
        "jump_rad": (
            "radians, phase on the positive side (cross-product rule) minus the other; "
            "same value in both layouts"
        ),
        "point": "frame px, (row, col); file layout when transposed (swapped)",
        "direction": (
            "+1: one stripe becomes two going toward row 0 of the analysed frame (toward "
            "column 0 in file layout when transposed); -1 the reverse; same value in both layouts"
        ),
    }

    striped: bool
    score: float
    threshold: float
    regions: tuple[Region, ...]
    spike_pixels: int
    clipped_pixels: int
    labels: np.ndarray = field(compare=False, repr=False)
    transposed: bool = False
    reader_notes: tuple[str, ...] | None = None
    bin_factors: BinFactors = BinFactors()
    unresolved_period_px: tuple[float, float] | None = None
    warnings: tuple[str, ...] = ()
    phase_breaks: tuple[PhaseBreak, ...] = ()
    forks: tuple[Fork, ...] = ()

    def mask(self) -> np.ndarray:
        """Boolean, frame shape: True inside any reported region."""
        return np.asarray(self.labels > 0)

    def in_file_layout(self) -> Report:
        """This report with ``labels``, every bbox, every Phase Break line and
        every Fork point transposed back to the file's layout
        (``PhaseBreak.transposed``, ``Fork.transposed``).

        Period, Angle, Modulation Depth, score, label values, jumps, Fork
        directions,
        ``bin_factors``, ``unresolved_period_px`` and ``warnings`` are
        unchanged."""
        return dataclasses.replace(
            self,
            labels=np.ascontiguousarray(self.labels.T),
            regions=tuple(dataclasses.replace(r, bbox=r.bbox.transposed()) for r in self.regions),
            phase_breaks=tuple(b.transposed() for b in self.phase_breaks),
            forks=tuple(f.transposed() for f in self.forks),
            transposed=True,
        )

    def to_dict(self) -> dict[str, object]:
        """Plain Python types only, so ``json.dumps`` works. ``labels`` is not
        included (the mask CSV carries it); ``reader_notes`` is included, as a
        list, only when it is not ``None``. ``units`` is a copy of ``UNITS``."""
        d: dict[str, object] = {
            "striped": bool(self.striped),
            "score": float(self.score),
            "threshold": float(self.threshold),
            "transposed": bool(self.transposed),
            "bin_factors": self.bin_factors.to_dict(),
            "units": dict(self.UNITS),
            "regions": [r.to_dict() for r in self.regions],
            "phase_breaks": [b.to_dict() for b in self.phase_breaks],
            "forks": [f.to_dict() for f in self.forks],
            "spike_pixels": int(self.spike_pixels),
            "clipped_pixels": int(self.clipped_pixels),
            "unresolved_period_px": (
                None
                if self.unresolved_period_px is None
                else [float(x) for x in self.unresolved_period_px]
            ),
            "warnings": list(self.warnings),
        }
        if self.reader_notes is not None:
            d["reader_notes"] = list(self.reader_notes)
        return d

    def to_json(self) -> str:
        # allow_nan=False: a NaN can never become invalid JSON.
        return json.dumps(self.to_dict(), indent=2, allow_nan=False)
