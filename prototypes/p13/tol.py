"""PROTOTYPE (ticket 13): the equality harness's ``tol`` mode (plan section 2).

One pass/fail row per pre-stated criterion of a Group II slice, with the max differences.
Profiles: ``slice4b`` (deterministic Angle tie-break), ``slice5`` (FFT engine and support
box), ``slice6`` (single-precision bank; O3 ruling), ``slice7``
(the finder: exact outside the breaks).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TIE_REL = 1e-9  # _local_stripes._BANK_TIE_REL (slice 4b), fixed here so any tree's pickles compare


class _Table:
    def __init__(self) -> None:
        self.rows: dict[str, tuple[float, float, list[str]]] = {}

    def check(self, criterion: str, value: float, bound: float, frame: str) -> None:
        worst, b, frames = self.rows.get(criterion, (0.0, bound, []))
        if not value <= bound:  # NaN fails
            frames.append(frame)
        self.rows[criterion] = (max(worst, value) if not math.isnan(value) else math.inf, b, frames)

    def flag(self, criterion: str, ok: bool, frame: str) -> None:
        self.check(criterion, 0.0 if ok else 1.0, 0.0, frame)

    def print(self) -> bool:
        print("| criterion | bound | max | result | failing frames |")
        print("|---|---|---|---|---|")
        for k, (worst, bound, frames) in self.rows.items():
            print(
                f"| {k} | {bound:g} | {worst:.3g} | {'PASS' if not frames else 'FAIL'} "
                f"| {', '.join(frames[:6])}{' ...' if len(frames) > 6 else ''} |"
            )
        return all(not f for _, _, f in self.rows.values())


def _rel(a: float, b: float) -> float:
    return abs(b - a) / max(abs(a), 1e-300)


def _bins(rep: dict[str, Any]) -> tuple[int, int]:
    b = rep["bin_factors"]
    return int(b["horizontal"]), int(b["vertical"])


def compare(ref: dict[str, Any], new: dict[str, Any], profile: str) -> bool:
    sys.path.insert(0, str(ROOT / "tests"))
    from protected import PACKAGE_STORED_THRESHOLD

    # Reported breaks and Forks are those above the stored break/Fork thresholds, so "found
    # identically" covers their side of those thresholds; the null screen checks S_b and S_f.

    t = _Table()
    n_changed = n_tied = n_exempt = 0
    for name, a in ref.items():
        b = new[name]
        ra, rb = a["report"], b["report"]
        la, lb = a["local"], b["local"]
        binned = _bins(ra) != (1, 1)
        light = la["ratio"] > 0
        ratio_rel = np.abs(lb["ratio"] - la["ratio"])[light] / la["ratio"][light]
        maps_equal = np.array_equal(la["period"], lb["period"]) and np.array_equal(
            la["angle_deg"], lb["angle_deg"]
        )
        same_found = (
            len(ra["regions"]) == len(rb["regions"])
            and len(ra["phase_breaks"]) == len(rb["phase_breaks"])
            and len(ra["forks"]) == len(rb["forks"])
            and np.array_equal(ra["labels"], rb["labels"])
            and ra["warnings"] == rb["warnings"]
        )
        t.flag("found identically (counts, labels, warnings)", same_found, name)
        if profile == "slice4b":
            # Slice 4b changes only which tied Angle wins: ratio and Period stay bit-identical,
            # and the Angle may change only where the reference's top-two gap is within eps.
            t.flag("ratio map array_equal", np.array_equal(la["ratio"], lb["ratio"]), name)
            t.flag("Period map array_equal", np.array_equal(la["period"], lb["period"]), name)
            changed = la["angle_deg"] != lb["angle_deg"]
            tied = _gap_mask(a, changed.shape, 0.0, TIE_REL)
            t.flag("Angle changes only at ref eps-tied px", not np.any(changed & ~tied), name)
            n_changed += int(changed.sum())
            n_tied += int(tied.sum())
            t.check("score rel diff", _rel(ra["score"], rb["score"]), 1e-9, name)
            if same_found:
                t.check("report fields rel diff", _fields_rel(ra, rb), 1e-9, name)
            continue
        if profile == "slice5":
            t.check("ratio rel diff on light px", float(ratio_rel.max(initial=0)), 1e-11, name)
            if "tie_gap" in a:
                # Ruling 2026-11-16: exempt only px whose ref (4b) top-two gap lies within
                # eps(1 +- 1e-3); there the ratio row above still applies.
                exempt = _gap_mask(a, light.shape, TIE_REL * (1 - 1e-3), TIE_REL * (1 + 1e-3))
                n_exempt += int(exempt.sum())
                keep = ~exempt
                maps_equal = np.array_equal(la["period"][keep], lb["period"][keep]) and (
                    np.array_equal(la["angle_deg"][keep], lb["angle_deg"][keep])
                )
                t.flag("Period and Angle maps array_equal (outside the eps band)", maps_equal, name)
            else:
                t.flag("Period and Angle maps array_equal", maps_equal, name)
            t.check("score rel diff", _rel(ra["score"], rb["score"]), 1e-9, name)
            if same_found:
                t.check("report fields rel diff", _fields_rel(ra, rb), 1e-9, name)
            continue
        th = PACKAGE_STORED_THRESHOLD
        t.flag("no stripe Threshold flip", (ra["score"] > th) == (rb["score"] > th), name)
        t.check("score rel diff", _rel(ra["score"], rb["score"]), 1e-5, name)
        if not same_found:
            continue
        for ga, gb in zip(ra["regions"], rb["regions"], strict=True):
            p = ga["period_px"]
            t.check("Period |dP/P| (5e-4)", _rel(p, gb["period_px"]), 5e-4, name)
            bound = 1e-4 if binned else 0.01
            key = "Angle |dA| deg (binned 1e-4)" if binned else "Angle |dA| deg (0.01)"
            t.check(key, abs(gb["angle_deg"] - ga["angle_deg"]), bound, name)
            dm = abs(gb["modulation_depth"] - ga["modulation_depth"])
            t.check("depth |dm| (1e-3)", dm, 1e-3, name)
            mask = ra["labels"] == ga["label"]
            peak = np.unravel_index(np.argmax(np.where(mask, la["ratio"], -np.inf)), mask.shape)
            t.check(
                "ratio rel diff at region peak",
                _rel(la["ratio"][peak], lb["ratio"][peak]),
                1e-5,
                name,
            )
        periods = {g["label"]: g["period_px"] for g in ra["regions"]}
        scale = max(_bins(ra))
        for ba, bb in zip(ra["phase_breaks"], rb["phase_breaks"], strict=True):
            p = periods[ba["region"]] / scale  # frame px per Period (approximately, binned)
            d = max(math.dist(u, v) for u, v in zip(ba["line"], bb["line"], strict=True)) / p
            t.check("break points (P) (0.005)", d, 0.005, name)
            dj = abs(math.remainder(bb["jump_rad"] - ba["jump_rad"], 2 * math.pi))
            t.check("break jump rad (5e-4)", dj, 5e-4, name)
        for fa, fb in zip(ra["forks"], rb["forks"], strict=True):
            p = periods[fa["region"]] / scale
            t.check(
                "Fork position (P) (0.0025)", math.dist(fa["point"], fb["point"]) / p, 0.0025, name
            )
            t.flag("Fork direction equal", fa["direction"] == fb["direction"], name)
    print(f"tol {profile}: {len(ref)} frames")
    if profile == "slice4b":
        print(f"Angle px changed: {n_changed}; ref eps-tied px: {n_tied}")
    if profile == "slice5":
        print(f"exempt px (ref gap in eps(1 +- 1e-3)): {n_exempt}")
    return t.print()


def _gap_mask(rec: dict[str, Any], shape: tuple[int, ...], lo: float, hi: float) -> Any:
    """Pixels whose recorded top-two stripe energy gap lies in [lo, hi]."""
    (rows, cols), gap = rec["tie_gap"]
    mask = np.zeros(shape, bool)
    sel = (gap >= lo) & (gap <= hi)
    mask[rows[sel], cols[sel]] = True
    return mask


def _fields_rel(ra: dict[str, Any], rb: dict[str, Any]) -> float:
    """Max relative difference over every float field of regions, breaks and Forks
    (relative to max(|x|, 1), so fields near 0, such as an Angle of 0, are compared absolutely);
    any non-float difference is inf."""
    worst = 0.0

    def walk(x: Any, y: Any) -> None:
        nonlocal worst
        if isinstance(x, dict):
            for k in x:
                walk(x[k], y[k])
        elif isinstance(x, list | tuple):
            for u, v in zip(x, y, strict=True):
                walk(u, v)
        elif isinstance(x, float):
            worst = max(worst, abs(y - x) / max(abs(x), 1.0))
        elif x != y:
            worst = math.inf

    for key in ("regions", "phase_breaks", "forks"):
        walk(ra[key], rb[key])
    return worst
