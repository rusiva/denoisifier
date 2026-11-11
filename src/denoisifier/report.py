"""The Report that ``analyse`` returns."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field

import numpy as np


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
    convention in GLOSSARY.md; ``modulation_depth`` the Modulation Depth
    relative to the local Envelope. ``bbox`` is the tight box of the region's
    pixels and ``area_px`` their count.
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
class Report:
    """What ``analyse`` found in one frame.

    ``striped == bool(regions) == (score > threshold)``: the frame is Striped
    when at least one Striped Region is reported. ``regions`` are ordered by
    descending area, then by higher peak ratio, then by their first pixel in
    row-major order. ``labels`` (int32, frame shape) is the Mask: 0 outside
    every region, k inside the region with ``label == k``; each region's
    pixels lie inside its tight ``bbox`` and number ``area_px``. ``mask()`` is
    the boolean union of the regions.

    ``transposed`` is True when ``labels`` and the bboxes are in the file's
    layout of a transposed read (``in_file_layout``); Period and Angle are
    always in the analysed frame's convention. ``reader_notes`` are the
    frame reader's notes when the frame came from a file (the CLI sets them),
    and ``None`` otherwise.
    """

    striped: bool
    score: float
    threshold: float
    regions: tuple[Region, ...]
    labels: np.ndarray = field(compare=False, repr=False)
    transposed: bool = False
    reader_notes: tuple[str, ...] | None = None

    def mask(self) -> np.ndarray:
        """Boolean, frame shape: True inside any reported region."""
        return np.asarray(self.labels > 0)

    def in_file_layout(self) -> Report:
        """This report with ``labels`` and every bbox transposed back to the file's layout.

        Period, Angle, Modulation Depth, score and label values are unchanged."""
        return dataclasses.replace(
            self,
            labels=np.ascontiguousarray(self.labels.T),
            regions=tuple(dataclasses.replace(r, bbox=r.bbox.transposed()) for r in self.regions),
            transposed=True,
        )

    def to_dict(self) -> dict[str, object]:
        """Plain Python types only, so ``json.dumps`` works. ``labels`` is not
        included (the mask CSV carries it); ``reader_notes`` is included, as a
        list, only when it is not ``None``."""
        d: dict[str, object] = {
            "striped": bool(self.striped),
            "score": float(self.score),
            "threshold": float(self.threshold),
            "transposed": bool(self.transposed),
            "regions": [r.to_dict() for r in self.regions],
        }
        if self.reader_notes is not None:
            d["reader_notes"] = list(self.reader_notes)
        return d

    def to_json(self) -> str:
        # allow_nan=False: a NaN can never become invalid JSON.
        return json.dumps(self.to_dict(), indent=2, allow_nan=False)
