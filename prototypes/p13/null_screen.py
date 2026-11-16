"""PROTOTYPE (ticket 13, plan section 3.3; Risk 1 ruling): the null screen. Kept for the ticket.

160 unregistered frames (seeds 602_000-602_159, reserved in USED_SEEDS), run once per
Group II commit and compared with G1's outputs (computed once and cached):

- 602_000-602_099: stripe-free, the stripe calibration recipe (``threshold_calibration``);
- 602_100-602_129: break-free striped full frames, the break/Fork calibration recipe;
- 602_130-602_159: break-free frames on ticket 09's tags, 10 each of ``free`` (region),
  ``full_free`` (full frame) and ``two_free`` (two compatible regions), harness2's layouts.

    uv run --locked python prototypes/p13/null_screen.py frames <dir>
    uv run --locked python prototypes/p13/null_screen.py run <src> <dir> <out.pkl> [workers]
    uv run --locked python prototypes/p13/null_screen.py compare <g1.pkl> <new.pkl> <slice>

``slice`` sets the stripe-free score bound: slice5 1e-9, slice6 1e-5, slice7 0 (relative).
"""

from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path
from typing import Any

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

ROOT = Path(__file__).resolve().parents[2]
FREE = range(602_000, 602_100)
STRIPED = range(602_100, 602_130)
TAGGED = range(602_130, 602_160)
SCORE_BOUND = {"slice5": 1e-9, "slice6": 1e-5, "slice7": 0.0}


def _frames() -> list[tuple[str, str, Any]]:
    """(name, kind, frame): kind 'free' (stripe-free) or 'striped' (break-free striped)."""
    sys.path.insert(0, str(ROOT / "tests"))
    import threshold_calibration as tc
    from cases import CASES
    from denoisifier.synthetic import generate
    from protected import BREAK_FORK_CALIBRATION_DEPTH, CALIBRATION_SHAPE
    from regions import TYPICAL, single_region, two_regions

    out: list[tuple[str, str, Any]] = []
    for s in FREE:
        out.append((f"free_{s}", "free", tc.synthetic(s, CALIBRATION_SHAPE, 0.0).frame))
    for s in STRIPED:
        f = tc.synthetic(s, CALIBRATION_SHAPE, BREAK_FORK_CALIBRATION_DEPTH).frame
        out.append((f"striped_{s}", "striped", f))
    for k, s in enumerate(TAGGED):
        case = CASES[s % 10]
        tag = ("free", "full_free", "two_free")[k // 10]
        if tag == "free":
            reg = single_region(case.period, case.angle_deg, depth=0.5)
            f = generate(seed=s, shape=(512, 512), mottle="scorched", regions=[reg], **TYPICAL)
        elif tag == "full_free":
            f = generate(
                seed=s,
                shape=(400, 1600),
                mottle="scorched",
                period=float(case.period),
                angle_deg=float(case.angle_deg),
                modulation_depth=0.5,
                **TYPICAL,
            )
        else:
            j = k - 20
            p = (5, 8, 12, 6)[j % 4]
            regs = two_regions(
                p,
                p,
                angle_deg=(case.angle_deg, case.angle_deg),
                gap_windows=(2 / 3, 1.0)[j // 4 % 2],
            )
            f = generate(seed=s, shape=(640, 1024), mottle="scorched", regions=regs, **TYPICAL)
        out.append((f"{tag}_{s}", "striped", f.frame))
    return out


def write_frames(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    frames = _frames()
    with (directory / "null_frames.pkl").open("wb") as f:
        pickle.dump(frames, f, protocol=5)
    print(f"wrote {len(frames)} frames to {directory / 'null_frames.pkl'}")


def _one(item: tuple[str, str, Any]) -> tuple[str, dict[str, Any]]:
    import numpy as np

    from denoisifier import analysis

    name, kind, frame = item
    report = analysis.analyse(frame)
    rec: dict[str, Any] = {
        "kind": kind,
        "score": report.score,
        "striped": report.striped,
        "n_regions": len(report.regions),
        "labels": np.asarray(report.labels),
        "warnings": list(report.warnings),
        "breaks": len(report.phase_breaks),
        "forks": len(report.forks),
    }
    if kind == "striped":
        ev = analysis._break_fork_evidence(frame)
        rec["s_b"], rec["s_f"] = float(ev.breaks), float(ev.forks)
    return name, rec


def _init(src: str) -> None:
    sys.path.insert(0, src)
    import denoisifier

    assert str(Path(denoisifier.__file__).resolve()).startswith(src), denoisifier.__file__


def run(src: Path, directory: Path, out: Path, workers: int) -> None:
    import multiprocessing

    with (directory / "null_frames.pkl").open("rb") as f:
        frames = pickle.load(f)
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(workers, initializer=_init, initargs=(str(src.resolve()),)) as pool:
        results = dict(pool.imap(_one, frames, chunksize=1))
    with out.open("wb") as f:
        pickle.dump(results, f, protocol=5)
    print(f"wrote {len(results)} records to {out} (src {src})")


def compare(g1: dict[str, Any], new: dict[str, Any], which: str) -> bool:
    import numpy as np

    sys.path.insert(0, str(ROOT / "tests"))
    from protected import (
        PACKAGE_BREAK_FORK_BREAK_THRESHOLD,
        PACKAGE_BREAK_FORK_FORK_THRESHOLD,
        PACKAGE_STORED_THRESHOLD,
    )

    bound = SCORE_BOUND[which]
    t, tb, tf = (
        PACKAGE_STORED_THRESHOLD,
        PACKAGE_BREAK_FORK_BREAK_THRESHOLD,
        PACKAGE_BREAK_FORK_FORK_THRESHOLD,
    )
    fails: dict[str, list[str]] = {
        "stripe-free: no side flip of the stored Threshold": [],
        f"stripe-free: max relative score shift <= {bound:g}": [],
        "break-free: no new break or Fork": [],
        "break-free: no S_b / S_f side flip": [],
        "break-free: region count and labels equal": [],
        "every frame: no new warning": [],
    }
    keys = list(fails)
    max_shift = 0.0
    for name, a in g1.items():
        b = new[name]
        if a["kind"] == "free":
            if (a["score"] > t) != (b["score"] > t):
                fails[keys[0]].append(name)
            shift = abs(b["score"] - a["score"]) / max(abs(a["score"]), 1e-300)
            max_shift = max(max_shift, shift)
            if shift > bound:
                fails[keys[1]].append(f"{name} {shift:.2e}")
        else:
            if b["breaks"] > a["breaks"] or b["forks"] > a["forks"]:
                fails[keys[2]].append(name)
            if (a["s_b"] > tb) != (b["s_b"] > tb) or (a["s_f"] > tf) != (b["s_f"] > tf):
                fails[keys[3]].append(name)
            if a["n_regions"] != b["n_regions"] or not np.array_equal(a["labels"], b["labels"]):
                fails[keys[4]].append(name)
        if set(b["warnings"]) - set(a["warnings"]):
            fails[keys[5]].append(name)
    print(f"null screen vs G1 ({which}), {len(g1)} frames; max stripe-free shift {max_shift:.3e}")
    print("| criterion | result | frames |")
    print("|---|---|---|")
    for k, v in fails.items():
        print(f"| {k} | {'PASS' if not v else 'FAIL'} | {', '.join(v[:8])} |")
    return not any(fails.values())


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "frames":
        write_frames(Path(argv[1]))
    elif cmd == "run":
        run(Path(argv[1]), Path(argv[2]), Path(argv[3]), int(argv[4]) if len(argv) > 4 else 6)
    elif cmd == "compare":
        with Path(argv[1]).open("rb") as f:
            g1 = pickle.load(f)
        with Path(argv[2]).open("rb") as f:
            new = pickle.load(f)
        return 0 if compare(g1, new, argv[3]) else 1
    else:
        raise SystemExit(f"unknown command {cmd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
