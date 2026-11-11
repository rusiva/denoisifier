"""Command line: read a CSV frame, write the JSON report."""

from __future__ import annotations

import argparse
import dataclasses
import sys

from denoisifier.analysis import analyse
from denoisifier.frame_io import read_frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="denoisifier",
        description="Decide whether a frame is striped and report its stripe period and angle.",
    )
    parser.add_argument(
        "frame",
        help="frame as a comma-separated grid of numbers, such as an Andor Solis export; "
        "metadata lines before and after the grid are skipped",
    )
    parser.add_argument("-o", "--output", help="write the JSON report here (default: stdout)")
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
        frame_file = read_frame(
            args.frame, drop_axis_column=args.drop_axis_column, transpose=args.transpose
        )
        report = dataclasses.replace(analyse(frame_file.frame), reader_notes=frame_file.notes)
        text = report.to_json() + "\n"
        if args.output is None:
            sys.stdout.write(text)
        else:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text)
    except (OSError, ValueError) as e:
        print(f"denoisifier: error: {e}", file=sys.stderr)
        return 1
    return 0
