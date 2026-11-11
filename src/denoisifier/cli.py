"""Command line: read a CSV frame, write the JSON report and, on request, the Mask.

The JSON report holds ``striped``, ``score``, ``threshold``, ``transposed`` and
``regions``: one entry per Striped Region with its ``label``, ``period_px``,
``angle_deg``, ``modulation_depth``, ``bbox`` and ``area_px`` (ticket 05 moved
the Period, Angle and depth from the top level into the regions). With
``--mask PATH`` the Mask is written as a CSV laid out like the input grid:
0 outside every region, k inside the region whose ``label`` is k. Under
``--transpose`` the Mask and the bboxes follow the file's layout
(``"transposed": true``); Period and Angle are always measured on the
analysed (transposed) frame.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import sys
from pathlib import Path

from denoisifier.analysis import analyse
from denoisifier.frame_io import read_frame, write_mask_csv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="denoisifier",
        description="Decide whether a frame is striped and report each Striped Region's "
        "period, angle, modulation depth and bounding box as JSON (per-region values under "
        '"regions"; "transposed" records --transpose).',
    )
    parser.add_argument(
        "frame",
        help="frame as a comma-separated grid of numbers, such as an Andor Solis export; "
        "metadata lines before and after the grid are skipped",
    )
    parser.add_argument("-o", "--output", help="write the JSON report here (default: stdout)")
    parser.add_argument(
        "--mask",
        help="write the Striped Region mask here as a CSV laid out like the input: 0 outside "
        "regions, k inside the region labelled k in the report; with --transpose the mask "
        "and the bboxes follow the file's layout",
    )
    parser.add_argument(
        "--drop-axis-column",
        action="store_true",
        help="drop the first column as a Solis axis column (pixel or spectral axis); "
        "never done without this flag",
    )
    parser.add_argument(
        "--transpose",
        action="store_true",
        help="transpose the frame after reading (and after --drop-axis-column), for exports "
        "that write one sensor column per file row; never done without this flag",
    )
    args = parser.parse_args(argv)

    try:
        if args.mask is not None:
            _refuse_alias(args.mask, args.frame, "the input frame")
            if args.output is not None:
                _refuse_alias(args.mask, args.output, "the -o report")
        frame_file = read_frame(
            args.frame, drop_axis_column=args.drop_axis_column, transpose=args.transpose
        )
        report = dataclasses.replace(analyse(frame_file.frame), reader_notes=frame_file.notes)
        if args.transpose:
            report = report.in_file_layout()
        text = report.to_json() + "\n"
        if args.output is None:
            sys.stdout.write(text)
        else:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text)
        if args.mask is not None:
            write_mask_csv(report.labels, args.mask)
    except (OSError, ValueError) as e:
        print(f"denoisifier: error: {e}", file=sys.stderr)
        return 1
    return 0


def _refuse_alias(mask: str, other: str, what: str) -> None:
    """Refuse a --mask path that is ``other``, by path or as an existing link."""
    same = Path(mask).resolve() == Path(other).resolve()
    if not same and os.path.exists(mask) and os.path.exists(other):
        same = os.path.samefile(mask, other)
    if same:
        raise ValueError(f"--mask {mask} is the same file as {what} ({other})")
