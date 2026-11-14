"""Recalibrate from a folder of Stripe-free frames (synthetic or real):

    python -m denoisifier.recalibrate FOLDER -o FILE [--drop-axis-column] [--transpose]
        [--clip-level LEVEL] [--bin HxV] [--workers N]

Writes the Calibration file (``Calibration.to_json``) that ``analyse(...,
calibration=Calibration.from_json(...))`` and the CLI's ``--calibration``
read. Nothing in the package imports this module, so ``python -m`` runs it
fresh.
"""

from __future__ import annotations

import argparse
import sys

from denoisifier.calibration import calibrate_folder
from denoisifier.cli import bin_factors_arg
from denoisifier.report import BinFactors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m denoisifier.recalibrate",
        description="Score every .csv and .asc frame in FOLDER (all Stripe-free, one shape) "
        "and write the Calibration file. Evaluate on other frames than these.",
    )
    parser.add_argument("folder", help="folder of Stripe-free frames (not searched recursively)")
    parser.add_argument("-o", "--output", required=True, help="write the Calibration JSON here")
    parser.add_argument(
        "--drop-axis-column",
        action="store_true",
        help="drop the first column of every file as a Solis axis column",
    )
    parser.add_argument(
        "--transpose", action="store_true", help="transpose every frame after reading"
    )
    parser.add_argument(
        "--clip-level",
        type=float,
        metavar="LEVEL",
        help="clip level for every frame (default: detected per frame); 'inf' turns it off",
    )
    parser.add_argument(
        "--bin",
        type=bin_factors_arg,
        default=BinFactors(),
        metavar="HxV",
        dest="bin_factors",
        help="bin factors of every frame as HORIZONTALxVERTICAL (default 1x1); recorded in "
        "the Calibration's settings when not 1x1",
    )
    parser.add_argument(
        "--workers", type=int, default=1, help="worker processes (default 1: serial)"
    )
    args = parser.parse_args(argv)
    try:
        cal = calibrate_folder(
            args.folder,
            drop_axis_column=args.drop_axis_column,
            transpose=args.transpose,
            clip_level=args.clip_level,
            workers=args.workers,
            bin_factors=args.bin_factors,
        )
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(cal.to_json())
    except (OSError, ValueError) as e:
        print(f"denoisifier.recalibrate: error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
