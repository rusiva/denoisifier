"""Command line: read a CSV frame, write the JSON report and, on request, the Mask.

The JSON report holds ``striped``, ``score``, ``threshold``, ``transposed``,
``regions``, ``phase_breaks``, ``forks``, ``spike_pixels`` and
``clipped_pixels``. ``regions`` has one entry
per Striped Region with its ``label``, ``period_px``, ``angle_deg``,
``modulation_depth``, ``bbox`` and ``area_px`` (ticket 05 moved the Period,
Angle and depth from the top level into the regions). ``spike_pixels`` counts
the pixels rejected as Spikes, ``clipped_pixels`` the Clipped Pixels that were
not (``--clip-level`` overrides the clip detection). ``phase_breaks`` lists
each Phase Break found (its region, its line and its Phase Jump), ``forks``
each Fork found (its region, its point and its direction). ``threshold`` is the
one used: by default the stored calibration's at a 1% false-alarm rate;
``--false-alarm-rate`` picks another rate and ``--calibration FILE`` another
calibration (``python -m denoisifier.recalibrate``).
``--break-fork-false-alarm-rate`` sets the share of striped frames without
phase breaks or forks that may show a fake one (default 0.05; calibrated on
the stored break and fork calibration only). With
``--mask PATH`` the Mask is written as a CSV laid out like the input grid:
0 outside every region, k inside the region whose ``label`` is k. Under
``--transpose`` the Mask and the bboxes follow the file's layout
(``"transposed": true``); Period and Angle are always measured on the
analysed (transposed) frame. ``--bin HxV`` gives the frame's bin factors
(horizontal first): Period, Angle and the 3x2-Period minimum are in sensor
pixels, bboxes, areas and the Mask in frame pixels, as the report's ``units``
say; ``bin_factors``, ``unresolved_period_px`` and ``warnings`` record them.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import sys
from pathlib import Path

from denoisifier.analysis import analyse
from denoisifier.calibration import Calibration
from denoisifier.frame_io import read_frame, write_mask_csv
from denoisifier.report import add_bin_option


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="denoisifier",
        description="Decide whether a frame is striped and report each Striped Region's "
        "period, angle, modulation depth and bounding box as JSON (per-region values under "
        '"regions"; "transposed" records --transpose; "spike_pixels" and "clipped_pixels" '
        "count the pixels rejected as spikes and the clipped pixels; "
        '"phase_breaks" and "forks" list the phase breaks and forks found; '
        "--bin gives the frame's bin "
        'factors, and "units" names the unit of each field).',
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
        "that write one sensor column per file row; never done without this flag; --bin "
        "factors refer to the transposed (sensor) axes",
    )
    parser.add_argument(
        "--clip-level",
        type=float,
        metavar="LEVEL",
        help="pixels at or above LEVEL that are not rejected as spikes are clipped (saturated) "
        "and left out of the modulation depth; default: detected as a plateau of equal values "
        "at the frame's maximum; 'inf' turns clipping off; use it after per-pixel dark "
        "subtraction, which breaks the plateau",
    )
    parser.add_argument(
        "--false-alarm-rate",
        type=float,
        metavar="RATE",
        help="stripe false-alarm rate the threshold is set at, between 0 and 1 (default: "
        "0.01), on the stored calibration or on --calibration",
    )
    parser.add_argument(
        "--calibration",
        metavar="FILE",
        help="a calibration JSON (written by python -m denoisifier.recalibrate) to set the "
        "threshold on instead of the stored one",
    )
    parser.add_argument(
        "--break-fork-false-alarm-rate",
        type=float,
        metavar="RATE",
        help="at most this share of striped frames without phase breaks or forks show a fake "
        "phase break or fork, between 0 and 1 (default: 0.05); calibrated at the stored "
        "stripe threshold, unbinned, 400x1600 full-frame stripes",
    )
    add_bin_option(
        parser,
        "bin factors of the frame as HORIZONTALxVERTICAL (default 1x1). Period, Angle and the "
        "3x2-Period minimum are in sensor pixels; bboxes, areas and the mask are in frame pixels.",
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
        calibration = None
        if args.calibration is not None:
            calibration = Calibration.from_json(Path(args.calibration).read_text(encoding="utf-8"))
        analysed = analyse(
            frame_file.frame,
            false_alarm_rate=args.false_alarm_rate,
            calibration=calibration,
            clip_level=args.clip_level,
            bin_factors=args.bin_factors,
            break_fork_false_alarm_rate=args.break_fork_false_alarm_rate,
        )
        report = dataclasses.replace(analysed, reader_notes=frame_file.notes)
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
