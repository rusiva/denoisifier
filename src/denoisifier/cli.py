"""Command line: read a CSV frame, write the JSON report."""

from __future__ import annotations

import argparse
import sys

from denoisifier.analysis import analyse
from denoisifier.frame_io import read_frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="denoisifier",
        description="Decide whether a frame is striped and report its stripe period and angle.",
    )
    parser.add_argument("frame", help="frame as a plain comma-separated grid of floats, no header")
    parser.add_argument("-o", "--output", help="write the JSON report here (default: stdout)")
    args = parser.parse_args(argv)

    try:
        frame_file = read_frame(args.frame)
        text = analyse(frame_file.frame).to_json() + "\n"
        if args.output is None:
            sys.stdout.write(text)
        else:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text)
    except (OSError, ValueError) as e:
        print(f"denoisifier: error: {e}", file=sys.stderr)
        return 1
    return 0
